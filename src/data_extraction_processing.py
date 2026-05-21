from src.data_transformation_registry import TransformRegistry
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
from src.single_record_extraction_strategy import SingleRecordExtractionStrategy
from src.Strategy_Registry import StrategyRegistry
from src.file_walk_strategy import FileWalkStrategy
from src.file_chunking_and_parse import FileChunkingAndParse

class DataExtractionProcessing:
    '''def __init__(self,logger=None,settings=None):
        self.logger = logger if logger is not None else LoggerConfig().get_logger()
        self.settings = settings if settings is not None else ConfigSettings()
        self.column_mapping = self._load_column_mapping()'''
    def __init__(self):
        self.settings = ConfigSettings()
        self.logger = LoggerConfig().get_logger()
        self.column_mapping = self._load_column_mapping()

    def _load_column_mapping(self):
        try:
            with open(self.settings.datasource_config.nodes_mapping_filepath, 'r') as f:
                nodes_mapping = json.load(f)
            return nodes_mapping.get("extraction_pipeline",{})
        except Exception as e:
            self.logger.error(f"Error loading column mapping: {e}",exc_info=True)
            return {}    

    async def run_extraction_pipeline(self,inputs:dict):
        results = {}
        try:  
            for node_config in self.column_mapping:
                node_name = node_config.get("node_key")
                strategy_type = node_config.get("strategy_type")
                strategy_cls = StrategyRegistry.get_registry(strategy_type)
                if strategy_cls is None:
                    self.logger.error(f"Strategy type {strategy_type} not found for node {node_name}")
                    results[node_name] = None
                    continue
                strategy = strategy_cls(logger=self.logger,settings=self.settings)
                results[node_name] = await strategy.extract(inputs,node_config)
                #print(f"Results for node {node_name}: {results[node_name]} \n")
                self.logger.info(f"\nResults for node {node_name}: {results[node_name]} \n")
            return results
        except Exception as e:
            self.logger.error(f"Error running extraction pipeline: {e}",exc_info=True)
            return None    



