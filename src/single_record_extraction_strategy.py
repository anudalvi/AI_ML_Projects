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

class SingleRecordExtractionStrategy(ExtractionStrategy):

    async def extract(self,inputs:dict,node_config:dict):
        output_data = []   
        try:
            primary_source_key = node_config.get("primary_source_key")
            input_data = inputs.get(primary_source_key)
            
            if input_data is None:
                self.logger.error(f"Input data not found for source key {primary_source_key}")
                return None
            
            primary_filter = node_config.get("primary_filter")
            secondary_sources = node_config.get("secondary_sources")
            
            for record in input_data:
                if record is None:
                    continue
                if not HelperFunctions.apply_operation(record, primary_filter):
                    continue
                output_data_dict = {} 
                for field_cfg in node_config.get("fields",[]):
                    target_column = field_cfg.get("target_column")
                    source_column = field_cfg.get("source_column")
                    field_transforms = field_cfg.get("transform",[])
                    field_value = record.get(source_column)
                    field_value = TransformRegistry.apply_transform(field_value,field_transforms,inputs)
                    output_data_dict[target_column] = field_value
                    #self.logger.info(f"Field value for {target_column}: {field_value}")     
                if secondary_sources:
                    self.__process_secondary_sources(secondary_sources,inputs,output_data_dict)
                output_data.append(output_data_dict)
            return output_data
        except Exception as e:
            self.logger.error(f"Error extracting data: {e}",exc_info=True)
            raise e    
    
    def __process_secondary_sources(self,secondary_sources,inputs,output_data_dict):
        key_arr = []
        try:
            for secondary_source in secondary_sources:
                secondary_source_key = secondary_source.get("secondary_source_key")
                secondary_source_data = inputs.get(secondary_source_key)
                exclude_list = secondary_source.get("exclude_keys") if secondary_source.get("exclude_keys") is not None else []
                for record in secondary_source_data:
                    if record is None:
                        continue
                    if HelperFunctions.apply_operation(record, secondary_source.get("secondary_source_filter")):
                        key_field = secondary_source.get("key_field")
                        value_field = secondary_source.get("value_field")
                        if record[key_field] is not None:
                            if record[key_field] not in exclude_list:
                                if record[key_field] not in key_arr:
                                    key_arr.append(record[key_field])
                                    output_data_dict[record[key_field]] = record[value_field] if record[value_field] is not None else ''
                                else:
                                    output_data_dict[record[key_field]] += ' ' + record[value_field] if record[value_field] is not None else ''
        except Exception as e:
            self.logger.error(f"Error processing secondary sources: {e}",exc_info=True)
            raise e    

