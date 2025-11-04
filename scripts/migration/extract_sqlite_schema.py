#!/usr/bin/env python3
"""
Extract complete schema from SQLite database
"""
import sqlite3
import json
import sys
from pathlib import Path

def extract_schema(db_path: str, output_file: str):
    """Extract complete schema from SQLite database"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    schema_info = {
        "database": db_path,
        "tables": {},
        "indexes": {},
        "views": {},
        "triggers": {}
    }

    # Get all tables
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    tables = cursor.fetchall()
    print(f"📊 Found {len(tables)} tables")

    for table_name, create_sql in tables:
        # Get table info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = cursor.fetchall()

        schema_info["tables"][table_name] = {
            "create_sql": create_sql,
            "columns": [
                {
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": col[3],
                    "default": col[4],
                    "pk": col[5]
                }
                for col in columns
            ],
            "row_count": row_count,
            "foreign_keys": [
                {
                    "id": fk[0],
                    "seq": fk[1],
                    "table": fk[2],
                    "from": fk[3],
                    "to": fk[4],
                    "on_update": fk[5],
                    "on_delete": fk[6]
                }
                for fk in foreign_keys
            ]
        }

        print(f"  ✅ {table_name}: {row_count} rows, {len(columns)} columns")

    # Get all indexes
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    indexes = cursor.fetchall()
    print(f"\n📑 Found {len(indexes)} indexes")

    for index_name, create_sql in indexes:
        if create_sql:  # Some indexes are auto-created
            schema_info["indexes"][index_name] = create_sql
            print(f"  ✅ {index_name}")

    # Get all views
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='view'
        ORDER BY name
    """)

    views = cursor.fetchall()
    print(f"\n👁️  Found {len(views)} views")

    for view_name, create_sql in views:
        schema_info["views"][view_name] = create_sql
        print(f"  ✅ {view_name}")

    # Get all triggers
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='trigger'
        ORDER BY name
    """)

    triggers = cursor.fetchall()
    print(f"\n⚡ Found {len(triggers)} triggers")

    for trigger_name, create_sql in triggers:
        schema_info["triggers"][trigger_name] = create_sql
        print(f"  ✅ {trigger_name}")

    conn.close()

    # Save to JSON
    with open(output_file, 'w') as f:
        json.dump(schema_info, f, indent=2)

    print(f"\n✅ Schema saved to: {output_file}")

    # Print summary
    total_rows = sum(t["row_count"] for t in schema_info["tables"].values())
    print(f"\n📊 Summary:")
    print(f"  Tables: {len(schema_info['tables'])}")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Indexes: {len(schema_info['indexes'])}")
    print(f"  Views: {len(schema_info['views'])}")
    print(f"  Triggers: {len(schema_info['triggers'])}")

    return schema_info

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "unified_mcp_system.db"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "sqlite_schema.json"

    print(f"🔍 Extracting schema from: {db_path}\n")
    extract_schema(db_path, output_file)
