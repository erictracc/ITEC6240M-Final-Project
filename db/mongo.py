from pymongo import MongoClient
from config_manager import load_settings
from utils.logger import setup_logger

logger = setup_logger()
settings = load_settings()

try:
    client = MongoClient(settings["database_uri"])
    db = client[settings["database_name"]]
    logger.info(f"[MongoDB] Connected → {settings['database_name']}")
except Exception as e:
    logger.error(f"[MongoDB] Connection Error → {str(e)}")
    db = None

def get_db():
    return db