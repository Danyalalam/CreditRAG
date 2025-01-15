from sqlalchemy import create_engine
import pandas as pd
import json
from tabulate import tabulate

class DatabaseViewer:
    def __init__(self):
        self.engine = create_engine('sqlite:///credit_reports.db')
    
    def show_table_counts(self):
        tables = ['reports', 'credit_scores', 'summaries', 
                 'personal_information', 'account_histories',
                 'inquiries', 'credit_contacts', 'data_furnishers']
        
        counts = {}
        for table in tables:
            df = pd.read_sql(f'SELECT COUNT(*) as count FROM {table}', self.engine)
            counts[table] = df['count'][0]
        
        print("\nDatabase Summary:")
        print(tabulate([(k, v) for k, v in counts.items()], 
                      headers=['Table', 'Count'], 
                      tablefmt='grid'))


def main():
    viewer = DatabaseViewer()
    viewer.show_table_counts()


if __name__ == "__main__":
    main()