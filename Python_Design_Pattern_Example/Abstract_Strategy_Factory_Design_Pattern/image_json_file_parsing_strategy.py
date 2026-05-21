from src.file_chunking_and_parse import FileChunkingAndParse
from pathlib import Path
import pymupdf
import requests
from config.config_settings import ConfigSettings
from config.log_config import LoggerConfig
import re
import pandas as pd
import asyncio
import threading
import os
import json
import re
from src.data_transformation_registry import TransformRegistry
from src.helpers_function_class import HelperFunctions
from src.file_walk_strategy import FileWalkStrategy

class ImageJsonFileParsingStrategy(FileChunkingAndParse):
    async def extract(self,inputs:dict,node_config:dict):
        output_data = []
        primary_filter = node_config.get("primary_filter")
        source_files_cfg = node_config.get("source_files",{})
        primary_source_key = node_config.get("primary_source_key")
        try:
            input_data = inputs.get(primary_source_key)
            if input_data is None:
                self.logger.error(f"Input data not found for source key {primary_source_key}")
                return None
            
            for record in input_data: 
                files_arr = None
                if record is None:
                    continue
                if not HelperFunctions.apply_operation(record, primary_filter):
                    continue

                if source_files_cfg.get("sub_folder_from_field") is not None:
                    folder_path = self._resolve_folder_path(source_files_cfg,record)
                    if not folder_path or not os.path.exists(folder_path):
                        self.logger.error(f"Sub folder path not found for record {record}")
                        continue
                    if source_files_cfg.get("source_files_transform"):
                        source_files_transforms = source_files_cfg.get("source_files_transform")
                        files_arr = TransformRegistry.apply_transform(folder_path,source_files_transforms,record)
                    if files_arr:
                        for file in files_arr:
                            file_data = self._read_file(file,node_config["parse_file_config"])
                            if file_data is None:
                                continue
                            context_data = {
                                "_context.file_data":file_data,
                                "_context.file_path":file.absolute(),
                                "_context.file_name":file.name,
                                "_context.record":record
                            }
                            missing_fields = self._file_schema_validation(file_data,file.name,node_config["file_schema_validation"])
                            self.logger.info(f"\nFile {file.name} : {missing_fields}")
                            if len(missing_fields[file.name]) == 0:
                                output_data.append(self._extract_json_file_data_node(node_config,context_data))
            #self.logger.info(f"\nOutput Data Node for {node_config['node_key']} : {output_data}")
            return output_data
        except Exception as e:
            self.logger.error(f"Error extracting data: {e}",exc_info=True)
            raise e     
    
    def _read_file(self,file_path:Path,parse_file_config:dict):
        json_data = None
        try:
            try:
                with open(file_path,parse_file_config["file_mode"],encoding=parse_file_config["file_encoding"]) as f:
                    json_data = json.load(f)
            except json.JSONDecodeError:
                self.logger.warning(f"Malformed JSON in {file_path}. Attempting robust extraction.")
                # Fallback to your manual extraction only if standard load fails
                with open(file_path, parse_file_config["file_mode"], encoding=parse_file_config["file_encoding"]) as f:
                    raw = f.read()
                    start, end = raw.find(parse_file_config["fallback_extraction"]["json_start_char"]), raw.rfind(parse_file_config["fallback_extraction"]["json_end_char"])
                if start != -1 and end != -1:
                    try:
                        json_data = json.loads(raw[start:end+1])
                    except Exception as e:
                        self.logger.error(f"Error reading file {file_path}: {e}",exc_info=True)
            if not json_data:
                self.logger.error(f"JSON data not found for file {file_path}")
                return None
            # Support legacy double-encoded JSON if any exists, and ensure base case is a dict
            if isinstance(json_data, str):
                self.logger.info(f"JSON Data is string, use loads to convert to dict.")
                json_data = json.loads(json_data)   
            return json_data
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}",exc_info=True)
            return None     

    def _file_schema_validation(self,file_data:dict,file_name:str,schema_validation_config:dict):
        json_validation={}
        try:
            if isinstance(file_data,dict):
                classification = file_data.get(schema_validation_config["main_field"], '')
                if classification is not None and classification.lower() in schema_validation_config["field_validation"]:
                    required_fields = schema_validation_config["field_validation"][classification.lower()]
                    missing_fields = [field for field in required_fields if field not in file_data]
                    # Check for safety or safety_alert
                    if schema_validation_config.get("special_check",False):
                        special_check = schema_validation_config["special_check"]
                        if classification.lower() in special_check:
                            if special_check[classification.lower()][0] not in file_data.keys() and special_check[classification.lower()][1] not in file_data.keys():
                                missing_fields.append(special_check[classification.lower()][0]+' / '+special_check[classification.lower()][1])
                else:
                    self.logger.error(f"Error validating json schema: 'classification' missing or invalid in {file_name}")
                    missing_fields=[f"Unknown classification: {classification}"]
            else:
                self.logger.error(f"Error validating json schema: data is not a dict in {file_name}")
                missing_fields=["Invalid json data"]
            json_validation[file_name]=missing_fields
            return json_validation        
        except Exception as e:
            self.logger.error(f"Error validating file schema for {file_name}: {e}",exc_info=True)
            return {}     


    def _extract_json_file_data_node(self,node_config:dict,context_data:dict):
        common_fields_cfg = []
        try:
            data_node = {}
            if "common_fields" in node_config:
                common_fields_cfg = node_config.get("common_fields",[])
            for common_field in common_fields_cfg:
                target_column = common_field.get("target_column")
                source = common_field.get("source") if common_field.get("source") else None
                source_data = context_data.get(source) if source is not None else None
                source_column = common_field.get("source_column") if common_field.get("source_column") else None        
                field_transforms = common_field.get("transform",[])
                field_value = source_data.get(source_column) if source_column is not None and source_data is not None else source_data
                field_value = TransformRegistry.apply_transform(field_value,field_transforms,context_data)
                data_node[target_column] = field_value
            if 'conditional_mapping' in node_config:
                conditional_mapping_cfg=node_config.get("conditional_mapping")
                branch_mapping_cfg = self._match_conditional_mapping_type(conditional_mapping_cfg,context_data)
                if branch_mapping_cfg is None:
                    self.logger.error(f"Error extracting json file data node: No branch mapping found for {context_data.get('_context.file_data','').get(conditional_mapping_cfg.get('descriminator_field'))}")
                    return None
                for field_config in branch_mapping_cfg["fields"]:
                    target_column = field_config.get("target_column")
                    source = field_config.get("source") if field_config.get("source") else None
                    source_data = context_data.get(source) if source is not None else None 
                    source_column = self._get_source_column(field_config.get("source_column"),source_data) if source_data is not None else None
                    field_transforms = field_config.get("transform",[])
                    field_value = source_data.get(source_column) if source_column is not None and source_data is not None else source_data
                    field_value = TransformRegistry.apply_transform(field_value,field_transforms,context_data)
                    data_node[target_column] = field_value
            return data_node
            
        except Exception as e:
            self.logger.error(f"Error extracting json file data node: {e}",exc_info=True)
            return None         
 
    def _match_conditional_mapping_type(self,conditional_mapping_cfg:dict,context_data:dict):
        try:
            classification = context_data.get("_context.file_data",{}).get(conditional_mapping_cfg["descriminator_field"])
            if classification.lower() in conditional_mapping_cfg["field_branches"]:
                return conditional_mapping_cfg["field_branches"][classification.lower()]
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error matching conditional mapping type: {e}",exc_info=True)
            return None     

    def _get_source_column(self,source_column:str,source_data:dict):
        try:
            for column in source_column.split("or"):
                if column.strip() in source_data.keys():
                    return column.strip()
            return None
        except Exception as e:
            self.logger.error(f"Error getting source column: {e}",exc_info=True)
            return None     