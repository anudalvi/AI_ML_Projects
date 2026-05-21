import logging
import os
from typing import Optional
from config.config_settings import ConfigSettings

class LoggerConfig:
    _instance: Optional["LoggerConfig"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is None:
            self.config_settings = ConfigSettings()
            self._logger = self.__set_logger()
    
    def __set_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.config_settings.log_name)
        # Avoid adding handlers if they already exist (e.g., if __init__ is called multiple times)
        if not logger.handlers:
            logger.setLevel(self.config_settings.log_level)
            
            # Ensure log directory exists
            os.makedirs(self.config_settings.log_file_path, exist_ok=True)
            log_file = os.path.join(self.config_settings.log_file_path, self.config_settings.log_file_name)
            
            fh = logging.FileHandler(log_file)
            sh = logging.StreamHandler()
            
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            sh.setFormatter(formatter)
            
            logger.addHandler(fh)
            logger.addHandler(sh)
        return logger
    
    def get_logger(self) -> logging.Logger:
        assert self._logger is not None, "Logger was not initialized. Call LoggerConfig() first."
        return self._logger