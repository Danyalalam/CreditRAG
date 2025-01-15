from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

class DatabaseManager:
    def __init__(self, db_path="credit_reports.db"):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.Session()