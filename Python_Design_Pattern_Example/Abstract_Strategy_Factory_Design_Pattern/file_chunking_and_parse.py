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
from src.extract_Strategy_interface import ExtractionStrategy
from src.data_transformation_registry import TransformRegistry
from src.helpers_function_class import HelperFunctions
from src.file_walk_strategy import FileWalkStrategy

class FileChunkingAndParse(FileWalkStrategy):
    async def extract(self,inputs:dict,node_config:dict):
        output_data = []
        chunk_arr = []
        primary_filter = node_config.get("primary_filter")
        source_files_cfg = node_config.get("source_files")
        if source_files_cfg is None:
            self.logger.error("node_config is missing required key 'source_files'")
            return None
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

                if source_files_cfg.get("sub_folder_from_field",'') != '':
                    folder_path = self._resolve_folder_path(source_files_cfg,record)
                    if not folder_path or not os.path.exists(folder_path):
                        self.logger.error(f"Sub folder path not found for record {record}")
                        continue
                    if source_files_cfg.get("source_files_transform"):
                        source_files_transforms = source_files_cfg.get("source_files_transform")
                        files_arr = TransformRegistry.apply_transform(folder_path,source_files_transforms,record)
                    
                    if files_arr:
                        for file in files_arr:
                            context_data = {
                                "_context.file_name":file.name,
                                "_context.file_path":file.absolute(),
                                "_context.file_start_page":self._extract_page_range(file,source_files_cfg["source_file_extension"])["file_start_page"],
                                "_context.file_end_page":self._extract_page_range(file,source_files_cfg["source_file_extension"])["file_end_page"],
                                "_context.record":record
                            }
                            chunk_file_config = node_config.get("chunk_file_config")    
                            chunk_arr = self._chunk_file(file,chunk_file_config)
                            sub_group_config = node_config.get("sub_group_chunk_config")
                            chunk_arr = self._lookahead_chunk_merge(chunk_arr,sub_group_config)
                            node_type_output = self._build_groups(chunk_arr,sub_group_config,context_data)
                            output_data.append(node_type_output)
            return output_data
        except Exception as e:
            self.logger.error(f"Error extracting data: {e}",exc_info=True)
            raise e    
    
    def _chunk_file(self,file,chunk_file_config):
        chunk_arr = []
        try:
            with open(file,'r',encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            self.logger.error(f"Error reading file: {e}",exc_info=True)
            return None
        try:
            page_sections = file_content.split(chunk_file_config['page_sections_pattern'])
            for page_num, page_section in enumerate(page_sections):
                for part in re.split(chunk_file_config['header_split_pattern'],page_section):
                    if not part.split():
                        continue
                    
                    sub_parts = re.split(chunk_file_config['sub_parts_pattern'],part)
                    for sub_part in sub_parts:
                        clean_chunk = sub_part.strip()
                        if clean_chunk:
                            chunk_data = {}
                            chunk_data["page"] = page_num + 1
                            chunk_data["content"] = clean_chunk
                            chunk_data["type"] = self._get_chunk_type(clean_chunk, chunk_file_config["chunk_type_conditions"]) 
                            chunk_arr.append(chunk_data)
            return chunk_arr                
        except Exception as e:
            self.logger.error(f"Error chunking file: {e}",exc_info=True)
            return None    
    
    def _get_chunk_type(self,clean_chunk,chunk_type_conditions):
        transform = []
        for chunktype_condition in chunk_type_conditions:
            if chunktype_condition["condition"] == "startswith":
                transform = [{
                    "name":chunktype_condition["condition"],
                    "args": {"prefix":chunktype_condition["cond_value"]}
                }]      
                if TransformRegistry.apply_transform(clean_chunk,transform,{}):
                    return chunktype_condition["type"]
            elif chunktype_condition["condition"] == "regex_match":
                transform = [{
                    "name":chunktype_condition["condition"],
                    "args": {"pattern":chunktype_condition["cond_value"]}
                }]
                if TransformRegistry.apply_transform(clean_chunk,transform,{}):
                    return chunktype_condition["type"]
            elif chunktype_condition["condition"] == "default":
                return chunktype_condition["type"]
        return "text"
    
    def _extract_page_range(self,chunk_file,file_extension):
        try:
            file_start_page = chunk_file.name.replace(file_extension,'').split("__")[1].split('_')[-2]
            file_end_page = chunk_file.name.replace(file_extension,'').split("__")[1].split('_')[-1]
            return {
                "file_start_page":file_start_page,
                "file_end_page":file_end_page
            }
        except Exception as e:
            self.logger.error(f"Error extracting page range: {e}",exc_info=True)
            return {
                "file_start_page":"1",
                "file_end_page":"1"
            }
    

    def _build_groups(self,chunk_arr,sub_group_cfg,context_data):
        try: 
            output_data = { group_name:[] for group_name in sub_group_cfg.keys() }
            for i in range(len(chunk_arr)):
                context_data={**context_data,"_context.chunk":chunk_arr[i]}
                chunk_type = chunk_arr[i]["type"]
                for sub_group_type,sub_group_type_cfg in sub_group_cfg.items():
                    if chunk_type != sub_group_type_cfg['chunk_type']:
                        continue

                    data_node = {}
                    for field_cfg in sub_group_type_cfg['fields']:
                        target_column = field_cfg.get("target_column")
                        source_data = context_data.get(field_cfg.get("source")) if field_cfg.get("source") is not None else None
                        source_column = field_cfg.get("source_column") if field_cfg.get("source_column") is not None else None
                        field_transforms = field_cfg.get("transform",[])
                        field_value = source_data.get(source_column) if source_column is not None and source_data is not None else None
                        field_value = TransformRegistry.apply_transform(field_value,field_transforms,context_data)
                        if field_value is None:
                            self.logger.warning(f"Field value not found for source {field_cfg.get('source','')} and source_column {source_column}")
                            continue
                        data_node[target_column] = field_value
                    output_data[sub_group_type].append(data_node)
            return output_data
        except Exception as e:
            self.logger.error(f"Error building groups: {e}",exc_info=True)
            return None


    def _lookahead_chunk_merge(self,chunk_arr,sub_group_cfg):
        try:
            for i in range(len(chunk_arr)):
                chunk_type = chunk_arr[i]["type"]
                
                for sub_group_type,sub_group_type_cfg in sub_group_cfg.items():
                    if chunk_type != sub_group_type_cfg['chunk_type']:
                        continue

                    if "lookahead_type_content_cfg" in sub_group_type_cfg.keys():
                        lookahead_type_content_cfg = sub_group_type_cfg["lookahead_type_content_cfg"]
                        type_condition_map = {index:type_condition for index,type_condition in enumerate(lookahead_type_content_cfg["type_conditions"])}
                        if chunk_arr[i][lookahead_type_content_cfg["condition_column"]]==type_condition_map[0] and chunk_arr[i+1][lookahead_type_content_cfg["condition_column"]]==type_condition_map[1] and chunk_arr[i+2][lookahead_type_content_cfg["condition_column"]]==type_condition_map[2] and i<len(chunk_arr)-3:
                            chunk_arr[i][lookahead_type_content_cfg["chunk_column"]]=chunk_arr[i][lookahead_type_content_cfg["chunk_column"]] + ' ' + chunk_arr[i+2][lookahead_type_content_cfg["chunk_column"]]
            return chunk_arr
        except Exception as e:
            self.logger.error(f"Error building groups: {e}",exc_info=True)
            return None 
    