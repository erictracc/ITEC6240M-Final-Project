import os
from dotenv import load_dotenv

load_dotenv()

def load_settings():
    return {
        "host": os.getenv("HOST", "127.0.0.1"),
        "port": int(os.getenv("PORT", 5000)),
        "database_uri": os.getenv("MONGO_URI"),
        "database_name": os.getenv("DB_NAME")
    }