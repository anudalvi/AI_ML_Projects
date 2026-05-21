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

class FileWalkStrategy( ExtractionStrategy):
    async def extract(self,inputs:dict,node_config:dict):
        files_arr = []
        output_data = []
        primary_filter = node_config.get("primary_filter",{})
        source_files_cfg = node_config.get("source_files",{})
        primary_source_key = node_config.get("primary_source_key")
        try:
            input_data = inputs.get(primary_source_key)
            if input_data is None:
                self.logger.error(f"Input data not found for source key {primary_source_key}")
                return None
            
            for record in input_data: 
                if record is None:
                    continue
                if not HelperFunctions.apply_operation(record, primary_filter):
                    continue

                if source_files_cfg and "sub_folder_from_field" in source_files_cfg:
                    folder_path = self._resolve_folder_path(source_files_cfg,record)
                    if not folder_path or not os.path.exists(folder_path):
                        self.logger.error(f"Markdown folder path not found for record {record}")
                        continue
                    if source_files_cfg.get("source_files_transform"):
                        source_files_transforms = source_files_cfg.get("source_files_transform")
                        files_arr = TransformRegistry.apply_transform(folder_path,source_files_transforms,record)
                    if files_arr:
                        for file in files_arr:
                            output_data_dict = {}   
                            for field_cfg in node_config['fields']: 
                                target_column = field_cfg.get("target_column")
                                source_column = field_cfg.get("source_column") if field_cfg.get("source_column") is not None else None
                                field_value = file if "_file." in field_cfg.get("source") else record.get(source_column)
                                field_transforms = field_cfg.get("transform")
                                field_value = TransformRegistry.apply_transform(field_value,field_transforms,record)
                                output_data_dict[target_column] = field_value
                            output_data.append(output_data_dict)
            return output_data
        except Exception as e:
            self.logger.error(f"Error extracting data: {e}",exc_info=True)
            raise e    
    
    def _resolve_settings(self,source_files_cfg):
        base_path_settings = source_files_cfg["base_path_settings"]
        obj = self.settings
        for i in base_path_settings.split('.'):
            obj = getattr(obj,i,None)
        return obj
    
    def _resolve_folder_path(self,source_files_cfg,record):
        try:
            base_path = self._resolve_settings(source_files_cfg)
            if not base_path:
                self.logger.error(f"Base path not found for source files config {source_files_cfg}")
                return None
            pdf_file_path = record[source_files_cfg.get("sub_folder_from_field")]
            if not pdf_file_path:
                self.logger.error(f"PDF file path not found for record {record}")
                return None
            sub_folder_transforms = source_files_cfg.get("sub_folder_transform",[])
            pdf_file_path_basename = TransformRegistry.apply_transform(pdf_file_path,sub_folder_transforms,record)
            if not pdf_file_path_basename:
                self.logger.error(f"PDF file path basename not found for record {record}")
                return None
            return os.path.join(str(base_path),str(pdf_file_path_basename)) 
        except Exception as e:
            self.logger.error(f"Error resolving folder path: {e}",exc_info=True)
            return None