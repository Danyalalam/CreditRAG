import json
import sqlite3

def sanitize_column_name(name):
    return name.replace(' ', '_').replace('-', '_').lower()

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = sanitize_column_name(f"{parent_key}{sep}{k}" if parent_key else k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v) if v is not None else None))
    return dict(items)

def json_to_sqlite(json_path: str, db_path: str, table_name: str) -> None:
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        data = [data]
    
    flattened_data = [flatten_dict(item) for item in data]
    
    # Get all possible columns from all records
    all_columns = set()
    for item in flattened_data:
        all_columns.update(item.keys())
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table with all possible columns
    columns_sql = ", ".join([f'"{col}" TEXT' for col in all_columns])
    cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
    cursor.execute(f'CREATE TABLE {table_name} ({columns_sql})')
    
    # Insert data
    placeholders = ",".join(["?" for _ in all_columns])
    columns_str = ",".join([f'"{col}"' for col in all_columns])
    insert_sql = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})'
    
    # Ensure all rows have values for all columns
    rows = []
    for item in flattened_data:
        row = [item.get(col) for col in all_columns]
        rows.append(row)
    
    cursor.executemany(insert_sql, rows)
    conn.commit()
    conn.close()

# Test
json_to_sqlite('src/sample_json/identityiq_1.json', 'database.db', 'credit_reports')