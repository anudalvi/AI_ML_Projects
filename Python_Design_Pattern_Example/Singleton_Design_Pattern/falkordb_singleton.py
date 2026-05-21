from falkordb import FalkorDB  # type: ignore
from config.config_settings import ConfigSettings

class FalkorDBSingleton:
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FalkorDBSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._db is None:
            settings = ConfigSettings()
            self._db = FalkorDB(host=settings.falkordb_config.falkor_host, port=settings.falkordb_config.falkor_port)
    
    '''def get_db(self):
        return self._db'''
    @classmethod
    def get_db(cls):
        """Class method to fetch or initialize the single database connection."""
        if cls._db is None:
            try:
                settings = ConfigSettings()
                cls._db = FalkorDB(
                    host=settings.falkordb_config.falkor_host, 
                    port=settings.falkordb_config.falkor_port
                )
                # Double check that the library didn't return None on failure
                if cls._db is None:
                    raise RuntimeError("FalkorDB initialization returned None.")
            except Exception as e:
                # Log this error using your application logger if available
                print(f"CRITICAL: Failed to connect to FalkorDB: {e}")
                raise e
                
        return cls._db