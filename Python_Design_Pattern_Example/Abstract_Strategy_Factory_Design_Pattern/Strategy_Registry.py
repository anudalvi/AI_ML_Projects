from src.extract_Strategy_interface import ExtractionStrategy
from src.single_record_extraction_strategy import SingleRecordExtractionStrategy
from src.file_walk_strategy import FileWalkStrategy
from src.file_chunking_and_parse import FileChunkingAndParse
from src.image_json_file_parsing_strategy import ImageJsonFileParsingStrategy
from typing import Type,Dict,Any


class StrategyRegistry:
    _registry: Dict[str,Type[ExtractionStrategy]] = {}
    @classmethod
    def register(cls,strategy_name:str,strategy_class:Type[ExtractionStrategy]):
        cls._registry[strategy_name] = strategy_class
    
    @classmethod
    def get_registry(cls,strategy_name:str):
        if strategy_name not in cls._registry:
            print(strategy_name)
            raise ValueError(f"Strategy name {strategy_name} not found")
        return cls._registry[strategy_name]

StrategyRegistry.register("single_record",SingleRecordExtractionStrategy)
StrategyRegistry.register("file_walk",FileWalkStrategy)
StrategyRegistry.register("file_chunking_and_parse",FileChunkingAndParse)
StrategyRegistry.register("image_json_file_parsing",ImageJsonFileParsingStrategy)