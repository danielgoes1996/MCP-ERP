#!/usr/bin/env python3
"""
Convert SQLite schema to PostgreSQL schema
"""
import json
import re
import sys
from typing import Dict, List

class SQLiteToPostgresConverter:
    """Convert SQLite DDL to PostgreSQL DDL"""

    # Type mapping SQLite -> PostgreSQL
    TYPE_MAP = {
        'INTEGER': 'INTEGER',
        'TEXT': 'TEXT',
        'REAL': 'DOUBLE PRECISION',
        'BLOB': 'BYTEA',
        'NUMERIC': 'NUMERIC',
        'DATETIME': 'TIMESTAMP',
        'DATE': 'DATE',
        'BOOLEAN': 'BOOLEAN',
        'VARCHAR': 'VARCHAR',
    }

    def __init__(self, schema_json: Dict):
        self.schema = schema_json
        self.sequences = []

    def convert_type(self, sqlite_type: str) -> str:
        """Convert SQLite type to PostgreSQL type"""
        if not sqlite_type:
            return 'TEXT'

        sqlite_type_upper = sqlite_type.upper()

        # Handle parameterized types like VARCHAR(255)
        match = re.match(r'(\w+)(\([^)]+\))?', sqlite_type_upper)
        if match:
            base_type = match.group(1)
            params = match.group(2) or ''

            if base_type in self.TYPE_MAP:
                return self.TYPE_MAP[base_type] + params
            elif 'INT' in base_type:
                return 'INTEGER' + params
            elif 'CHAR' in base_type or 'TEXT' in base_type:
                return 'TEXT'
            elif 'REAL' in base_type or 'FLOAT' in base_type or 'DOUBLE' in base_type:
                return 'DOUBLE PRECISION'
            elif 'BLOB' in base_type:
                return 'BYTEA'

        return 'TEXT'

    def convert_table_sql(self, table_name: str, create_sql: str) -> str:
        """Convert SQLite CREATE TABLE to PostgreSQL"""

        # Remove SQLite-specific syntax
        sql = create_sql.replace('AUTOINCREMENT', '')

        # Convert INTEGER PRIMARY KEY to SERIAL
        sql = re.sub(
            r'(\w+)\s+INTEGER\s+PRIMARY\s+KEY',
            r'\1 SERIAL PRIMARY KEY',
            sql,
            flags=re.IGNORECASE
        )

        # Convert types
        for sqlite_type, pg_type in self.TYPE_MAP.items():
            sql = re.sub(
                rf'\b{sqlite_type}\b',
                pg_type,
                sql,
                flags=re.IGNORECASE
            )

        # Convert DEFAULT CURRENT_TIMESTAMP
        sql = re.sub(
            r'DEFAULT\s+CURRENT_TIMESTAMP',
            'DEFAULT CURRENT_TIMESTAMP',
            sql,
            flags=re.IGNORECASE
        )

        # Convert ON DELETE/UPDATE CASCADE
        sql = re.sub(
            r'ON\s+DELETE\s+(\w+)',
            lambda m: f'ON DELETE {m.group(1).upper()}',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'ON\s+UPDATE\s+(\w+)',
            lambda m: f'ON UPDATE {m.group(1).upper()}',
            sql,
            flags=re.IGNORECASE
        )

        return sql

    def convert_index_sql(self, index_sql: str) -> str:
        """Convert SQLite CREATE INDEX to PostgreSQL"""
        if not index_sql:
            return None

        # PostgreSQL syntax is very similar, just clean up
        sql = index_sql

        # Remove IF NOT EXISTS (PostgreSQL doesn't support it in all versions)
        sql = re.sub(r'IF\s+NOT\s+EXISTS\s+', '', sql, flags=re.IGNORECASE)

        return sql

    def convert_view_sql(self, view_sql: str) -> str:
        """Convert SQLite CREATE VIEW to PostgreSQL"""
        # Views are usually compatible, but clean up
        sql = view_sql

        # Update any datetime functions
        sql = re.sub(
            r"datetime\('now'\)",
            "CURRENT_TIMESTAMP",
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r"date\('now'\)",
            "CURRENT_DATE",
            sql,
            flags=re.IGNORECASE
        )

        return sql

    def convert_trigger_sql(self, trigger_name: str, trigger_sql: str) -> str:
        """Convert SQLite trigger to PostgreSQL trigger"""
        # PostgreSQL triggers use a different syntax
        # This is a complex conversion, skip for now and handle manually if needed
        return f"-- TODO: Manual conversion needed for trigger: {trigger_name}\n-- {trigger_sql}\n"

    def generate_schema(self) -> str:
        """Generate complete PostgreSQL schema"""

        output = []
        output.append("-- ============================================")
        output.append("-- PostgreSQL Schema - Converted from SQLite")
        output.append("-- ============================================\n")

        output.append("-- Generated: Auto-converted")
        output.append("-- Tables: " + str(len(self.schema['tables'])))
        output.append("-- Total rows: " + str(sum(t['row_count'] for t in self.schema['tables'].values())))
        output.append("\n")

        # Add extensions
        output.append("-- Extensions")
        output.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        output.append("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\";")
        output.append("CREATE EXTENSION IF NOT EXISTS \"btree_gin\";\n")

        # Convert tables
        output.append("-- ============================================")
        output.append("-- TABLES")
        output.append("-- ============================================\n")

        for table_name, table_info in sorted(self.schema['tables'].items()):
            output.append(f"-- Table: {table_name} ({table_info['row_count']} rows)")

            # Get the CREATE TABLE SQL
            create_sql = table_info['create_sql']
            if create_sql:
                converted_sql = self.convert_table_sql(table_name, create_sql)
                output.append(converted_sql + ";\n")

        # Convert indexes
        output.append("\n-- ============================================")
        output.append("-- INDEXES")
        output.append("-- ============================================\n")

        for index_name, index_sql in sorted(self.schema['indexes'].items()):
            converted_sql = self.convert_index_sql(index_sql)
            if converted_sql:
                output.append(f"-- Index: {index_name}")
                output.append(converted_sql + ";\n")

        # Convert views
        if self.schema['views']:
            output.append("\n-- ============================================")
            output.append("-- VIEWS")
            output.append("-- ============================================\n")

            for view_name, view_sql in sorted(self.schema['views'].items()):
                output.append(f"-- View: {view_name}")
                converted_sql = self.convert_view_sql(view_sql)
                output.append(converted_sql + ";\n")

        # Add note about triggers
        if self.schema['triggers']:
            output.append("\n-- ============================================")
            output.append("-- TRIGGERS")
            output.append("-- ============================================")
            output.append("-- Note: Triggers require manual conversion")
            output.append(f"-- Found {len(self.schema['triggers'])} triggers to convert manually\n")

            for trigger_name in sorted(self.schema['triggers'].keys()):
                output.append(f"-- TODO: Convert trigger: {trigger_name}")

        return '\n'.join(output)

def main():
    schema_file = sys.argv[1] if len(sys.argv) > 1 else "scripts/migration/sqlite_schema.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "scripts/migration/postgres_schema.sql"

    print(f"🔄 Converting SQLite schema to PostgreSQL...\n")
    print(f"📖 Reading: {schema_file}")

    with open(schema_file, 'r') as f:
        schema_json = json.load(f)

    converter = SQLiteToPostgresConverter(schema_json)
    postgres_sql = converter.generate_schema()

    with open(output_file, 'w') as f:
        f.write(postgres_sql)

    print(f"✅ Wrote: {output_file}")
    print(f"\n📊 Converted:")
    print(f"  Tables: {len(schema_json['tables'])}")
    print(f"  Indexes: {len(schema_json['indexes'])}")
    print(f"  Views: {len(schema_json['views'])}")
    print(f"  Triggers: {len(schema_json['triggers'])} (require manual conversion)")

if __name__ == "__main__":
    main()
