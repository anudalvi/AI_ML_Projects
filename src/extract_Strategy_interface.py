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
from abc import ABC, abstractmethod 

class ExtractionStrategy(ABC):
    def __init__(self,logger=None,settings=None):
        self.logger = logger if logger is not None else LoggerConfig().get_logger()
        self.settings = settings if settings is not None else ConfigSettings()

    @abstractmethod
    async def extract(self, inputs: dict, node_config: dict) -> list | None:
        pass

