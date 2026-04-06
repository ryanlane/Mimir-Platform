#!/usr/bin/env python
"""Quick script to check database tables"""
from app.db.base import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Database has {len(tables)} tables:')
for table in tables:
    print(f'  - {table}')

# Check some indexes too
for table_name in ['channels', 'scenes', 'display_clients']:
    if table_name in tables:
        indexes = inspector.get_indexes(table_name)
        print(f'\n{table_name} has {len(indexes)} indexes:')
        for index in indexes:
            print(f'  - {index["name"]}: {index["column_names"]}')
