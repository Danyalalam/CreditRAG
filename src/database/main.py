import os
import time
import psutil
from db_manager import DatabaseManager
from json_loader import JsonLoader
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def is_file_locked(filepath):
    for proc in psutil.process_iter():
        try:
            files = proc.open_files()
            if files:
                for item in files:
                    if filepath in item.path:
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def safe_remove_db(db_path):
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        if is_file_locked(db_path):
            logging.warning(f"Database is locked, waiting... (attempt {attempt + 1})")
            time.sleep(2)
            attempt += 1
        else:
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logging.info("Successfully removed existing database")
                return True
            except Exception as e:
                logging.error(f"Error removing database: {str(e)}")
        
    logging.error("Could not remove database file after maximum attempts")
    return False

def process_json_files():
    db_path = "credit_reports.db"
    
    # Safely remove existing database
    if not safe_remove_db(db_path):
        return
        
    db_manager = DatabaseManager()
    loader = JsonLoader(db_manager)
    
    json_dir = "src/sample_json"
    json_files = sorted([f for f in os.listdir(json_dir) if f.endswith('.json')])

    for json_file in json_files:
        try:
            file_path = os.path.join(json_dir, json_file)
            logging.info(f"Processing {json_file}")
            loader.load_json(file_path)
            logging.info(f"Successfully processed {json_file}")
        except Exception as e:
            logging.error(f"Error processing {json_file}: {str(e)}")

if __name__ == "__main__":
    process_json_files()