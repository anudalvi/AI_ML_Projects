from sys import exc_info
import os
import json
from falkordb import FalkorDB  # type: ignore
from config.log_config import LoggerConfig
from config.config_settings import ConfigSettings
#from src.assembly_instruction_data_process import AssemblyInstructionDataExtractor
from pathlib import Path
from src.graph_query_generation import GraphQueryGeneration

#docker run -d -p 6379:6379 --name IKEA_Catalog -v /home/anu/falkor_data:/data falkordb/falkordb:latest
#docker run -d -p 3000:3000 --name IKEA_UI falkordb/falkordb-browser:latest
#ls -lh /home/anu/falkor_data
class KnowledgeBaseVectorstoreProcessing(GraphQueryGeneration):
    '''def __init__(self,logger:LoggerConfig=None ,settings: ConfigSettings = None):
        self.logger = LoggerConfig().get_logger() if logger is None else logger
        self.settings = ConfigSettings() if settings is None else settings
        #self.falkordb = FalkorDB(host=self.settings.falkordb_config.falkor_host, port=self.settings.falkordb_config.falkor_port)
        self.graph_query_generation = GraphQueryGeneration(logger,settings)'''
    def __init__(self):
        settings = ConfigSettings()
        logger_config = LoggerConfig()
        super().__init__(logger_config, settings)
        '''self.assembly_process = AssemblyInstructionDataExtractor(logger,settings)
        self.product_details_node = {}
        self.markdown_chunk_nodes = []
        self.image_json_node_arr = []
        self.instruction_manual_node = []
        self.markdown_file_chunk_nodes = []'''
    

    async def generate_graph_nodes_relationships(self,source_data,input):
        query_stmt = ''
        try:
            
            for json_file_path in Path(self.settings.falkordb_config.falkor_ddl_json_files).glob('*.json'):
                with open(json_file_path, 'r') as f:
                    node_ddl = json.load(f)
                graph = self.falkordb.select_graph(node_ddl.get("graph_dbname"))    
                self.logger.info(f"DDL json file under process: {json_file_path.name}")
                for node in node_ddl['nodes']:
                    node_array_name = node['node_array_name'].split('.')[0] if '.' in node['node_array_name'] else node['node_array_name']
                    sub_node_array_name = node['node_array_name'].split('.')[1] if '.' in node['node_array_name'] else None
                    
                    #print(f"{node_array_name}: {len(source_data[node_array_name])}")
                    if len(source_data[node_array_name]) == 1 :
                        node_data = await self.get_node_source_data(node,source_data[node_array_name])
                        query_stmt,params = await self.create_single_node_graph_query(node,node_data)
                        self.logger.info(f"Single node graph query statement: {query_stmt}")
                        self.logger.info(f"Single node graph query parameters: {params}")
                        self.logger.info(f"Node data: {node_data}")
                        result = graph.query(query_stmt, params)
                        self.logger.info(f"Single node graph query result: {result.nodes_created}")            
                    else:
                        if sub_node_array_name:
                            for node_data in source_data[node_array_name]:
                                self.logger.info(f"Query for sub node array name: {node_array_name}.{sub_node_array_name}\n")
                                sub_node_data = node_data[sub_node_array_name]
                                query_stmt = await self.create_multiple_node_graph_query(node,sub_node_data,node_array_name,sub_node_array_name)
                                self.logger.info(f"Multiple node graph query statement: {query_stmt}")
                                sub_node_data = await self.get_node_source_data(node,sub_node_data) 
                                self.logger.info(f"Sub node data: {sub_node_data}")   
                                if query_stmt:
                                    result = graph.query(query_stmt,{'sub_node_data':sub_node_data})
                                    self.logger.info(f"Multiple node graph query result: {result.result_set[0][0]}")
                        else:
                            node_data = source_data[node_array_name]
                            self.logger.info(f"Query for node array name: {node_array_name}\n")
                            query_stmt = await self.create_multiple_node_graph_query(node,node_data,node_array_name)
                            self.logger.info(f"Multiple node graph query statement: {query_stmt}")
                            node_data = await self.get_node_source_data(node,node_data)
                            self.logger.info(f"Node data: {node_data}")
                            if query_stmt:
                                result = graph.query(query_stmt,{'node_data':node_data})
                                self.logger.info(f"Multiple node graph query result: {result.result_set[0][0]}")
                    for index_column in node.get('index_columns',[]):
                        query_stmt = await self.create_node_index_query(node,index_column,node.get('entity_name'),node.get('entity_alias'),node_ddl.get("graph_dbname"))
                        self.logger.info(f"Node index query statement: {query_stmt}")  
                        if query_stmt:
                            result = graph.query(query_stmt)
                            if result.indices_created == 1:
                                self.logger.info(f"Success: Index created!")
                            else:
                                self.logger.info(f"Failed: Index not created! OR Index already exists!")
            for json_file_path in Path(self.settings.falkordb_config.falkor_ddl_json_files).glob('*.json'):
                self.logger.info(f"DDL json file under process for creating relationships: {json_file_path.name}")
                with open(json_file_path, 'r') as f:
                    node_ddl = json.load(f)
                graph = self.falkordb.select_graph(node_ddl.get("graph_dbname",''))
                if 'relationships' in node_ddl: 
                    for relationship in node_ddl.get('relationships',[]): 
                        query_stmt = await self.create_relationship_graph_query(relationship,node_ddl.get("graph_dbname"))
                        self.logger.info(f"Relationship graph query statement: {query_stmt}")
                        if query_stmt:
                            result = graph.query(query_stmt)
                            self.logger.info(f"Relationship graph query result: {result.relationships_created}")
                            if result.relationships_created != 0:
                                self.logger.info(f"Success: Relationship created!")
                            else:
                                self.logger.info(f"Failed: Relationship not created! OR Relationship already exists!")

            self.falkordb.execute_command("SAVE")
            self.logger.info(f"Graph nodes relationships created successfully!")
        except Exception as e:
            self.logger.error(f"Error generating graph nodes relationships: {e}", exc_info=True)
            return None 

        
