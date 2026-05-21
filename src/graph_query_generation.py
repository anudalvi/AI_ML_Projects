import os
import json
from falkordb import FalkorDB  # type: ignore
from config.log_config import LoggerConfig
from config.config_settings import ConfigSettings
#from src.assembly_instruction_data_process import AssemblyInstructionDataExtractor
from pathlib import Path    
from typing import Optional
from src.falkordb_singleton import FalkorDBSingleton
import pandas as pd

class GraphQueryGeneration:
    def __init__(self,logger:LoggerConfig ,settings: ConfigSettings):
        self.logger = logger.get_logger()
        self.settings = settings
        #self.falkordb = FalkorDB(host=self.settings.falkordb_config.falkor_host, port=self.settings.falkordb_config.falkor_port)
        #self.falkordb = FalkorDBSingleton().get_db()  
        self.falkordb = FalkorDBSingleton.get_db()      
    
    async def create_single_node_graph_query(self,node_ddl,node_data):
        pk_str = ''
        set_clauses = []
        params = {}
        query_stmt =''
        try:
            query_stmt = f"MERGE({node_ddl['entity_alias']}:{node_ddl['entity_name']}"
            for node_col,data_col in node_ddl['mapping_details']['key_column'].items():
                pk_str = pk_str + f"{node_col}:${node_col},"
                params[node_col] = node_data[0].get(data_col)
            for node_column,data_column in node_ddl['mapping_details']['Column_Mapping'].items():
                set_clauses.append(f"{node_ddl['entity_alias']}.{node_column} = ${node_column}")
                params[node_column] = node_data[0].get(data_column)
            query_stmt = f"MERGE ({node_ddl['entity_alias']}:{node_ddl['entity_name']}{{{pk_str[:-1]}}})" + "\nSET " + ", \n".join(set_clauses) 
            #self.logger.info(f"Single node graph query statement: {query_stmt}")
            return query_stmt,params
        except Exception as e:
            self.logger.error(f"Error occured while creating single node graph query statement: {e}", exc_info=True)
            return query_stmt,params
    
    
    async def create_multiple_node_graph_query(self,node_ddl,node_data,node_array_name,sub_node_array_name:Optional[str]=None):
        pk_str = ''
        set_clauses = []
        try:
            if sub_node_array_name:
                query_stmt = f"UNWIND $sub_node_data as node_data \n" 
            else:
                query_stmt = f"UNWIND $node_data as node_data \n" 
            for node_col,data_col in node_ddl['mapping_details']['key_column'].items():
                pk_str = pk_str + f"{node_col}:node_data.{data_col},"
            for node_column,data_column in node_ddl['mapping_details']['Column_Mapping'].items():
                set_clauses.append(f"{node_ddl['entity_alias']}.{node_column} = node_data.{data_column}")
            query_stmt = query_stmt + f"MERGE ({node_ddl['entity_alias']}:{node_ddl['entity_name']}{{{pk_str[:-1]}}})" + "\nSET " + ", \n".join(set_clauses) + f'\nRETURN count({node_ddl["entity_alias"]})'
            #self.logger.info(f"Multiple node graph query statement: {query_stmt}")
            return query_stmt
        except Exception as e:
            self.logger.error(f"Error occured while creating multiple node graph query statement: {e}", exc_info=True)
            return None
    
    
    async def create_relationship_graph_query(self,relationship,graph_dbname):
        query_stmt = ""
        try:
            if relationship.get("match_type") == "MATCH":
                query_stmt = f"MATCH ({relationship.get('from_node_alias')}:{relationship.get('from_node')}),({relationship.get('to_node_alias')}:{relationship.get('to_node')}) \nWHERE "
                if 'join_conditions' in relationship:
                    for join_from_node_key,join_to_node_key in relationship['join_conditions'].items():
                        query_stmt = query_stmt + f"{relationship.get('from_node_alias')}.{join_from_node_key} = {relationship.get('to_node_alias')}.{join_to_node_key}" + " AND "
                query_stmt = query_stmt[:-5] + f"\nMERGE ({relationship.get('from_node_alias')})-[:{relationship.get('relationship_name')}]->({relationship.get('to_node_alias')})"
            elif relationship.get("match_type") == "OPTIONAL MATCH":
                query_stmt = f"MATCH ({relationship.get('from_node_alias')}:{relationship.get('from_node')})\nOPTIONAL MATCH ({relationship.get('to_node_alias')}:{relationship.get('to_node')}) \nWHERE "
                if 'join_conditions' in relationship:
                    for join_from_node_key,join_to_node_key in relationship['join_conditions'].items():
                        query_stmt = query_stmt + f"{relationship.get('from_node_alias')}.{join_from_node_key} = {relationship.get('to_node_alias')}.{join_to_node_key}" + " AND "
                query_stmt = query_stmt[:-5] + f"\nWITH {relationship.get('from_node_alias')}, {relationship.get('to_node_alias')} \n WHERE {relationship.get('from_node_alias')} IS NOT NULL AND {relationship.get('to_node_alias')} IS NOT NULL \n"
                query_stmt = query_stmt + f"MERGE ({relationship.get('from_node_alias')})-[:{relationship.get('relationship_name')}]->({relationship.get('to_node_alias')})"
            return query_stmt
        except Exception as e:
            self.logger.error(f"Error creating relationship graph query: {e}", exc_info=True)
            return None
    
    
    async def create_node_index_query(self,node,index_column,entity_name,entity_alias,graph_dbname):
        try:
            if not self._get_graph_indexes(node,index_column,entity_name,entity_alias,graph_dbname):
                query_stmt = f"CREATE INDEX FOR ({entity_alias}:{entity_name}) ON ({entity_alias}.{index_column})"
                return query_stmt
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error creating graph query: {e}",exc_info=True)
            return None 
    

    def _get_graph_indexes(self,node,index_column,entity_name,entity_alias,graph_dbname):
        index_exists = False
        try:
            #falkordb = FalkorDBSingleton().get_db()
            graph = self.falkordb.select_graph(graph_dbname)
            result = graph.query("CALL db.indexes()")
            header_names = [h[1] for h in result.header]
            data = [list(record) for record in result.result_set]
            df_indexes = pd.DataFrame(data, columns=header_names)
            df_indexes.to_csv("indexes.csv", index=False)
            #self.logger.info(f"Graph indexes: {df_indexes[['label','properties']]}")
            for _, row in df_indexes.iterrows():
                if row['label'] == entity_name and index_column in row['properties']:
                    self.logger.info("Index already exists")
                    index_exists = True
                    break
            if index_exists:
                return True
            else:
                self.logger.info("Index does not exist")
                return False
        except Exception as e:
            self.logger.error(f"Error getting graph indexes: {e}",exc_info=True)
            return False 
    

    async def get_node_source_data(self,node,node_data):
        source_data = []
        context_source_data = []
        try:
            if 'node_data_filter' in node:
                for record in node_data:
                    if record[node['node_data_filter']['filter_key']].lower()==node['node_data_filter']["filter_value"]:
                        context_source_data.append(record)   
            else:
                context_source_data = node_data

            if "is_child_node_mapping" in node:
                if node["is_child_node_mapping"]:
                    column_mapping_cfg = node['Parent_Child_Node_Mapping']
                    #key_column_cfg = node['mapping_details']['key_column']
                    for record in context_source_data:
                        temp_record1 = self.__get_temp_record(record,column_mapping_cfg)  
                        #temp_record2 = self.__get_temp_record(record,key_column_cfg)  
                        #temp_record2.update(temp_record1)
                        if 'part_id' in temp_record1 and 'part_name' in temp_record1:
                            source_data.append(temp_record1)
            else:
                for record in context_source_data:
                    source_data.append(record)
            return source_data
        except Exception as e:
            self.logger.error(f"Error getting node source data: {e}",exc_info=True)
            return None
    

    def __get_temp_record(self,record,column_mapping_cfg):
        temp_record = {}
        for k,v in column_mapping_cfg.items():
            v_arr = v.split(".")
            if len(v_arr)==2:
                if type(record[v_arr[0]])==list:
                    for item in record[v_arr[0]]:
                        temp_record[k] = item[v_arr[1]]
                else:
                    temp_record[k] = record[v_arr[0]][v_arr[1]]
            else:
                temp_record[k] = record[v_arr[0]]   
        return temp_record