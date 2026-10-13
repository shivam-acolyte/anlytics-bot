from app.database import db
from app.mysql_database import mysql_db
import json

print("=== PostgreSQL tracking_events ===")
with db.get_cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tracking_events'
        ORDER BY ordinal_position;
    """)
    for r in cur.fetchall():
        print(f"  {r['column_name']} ({r['data_type']})")

print("\n=== MySQL tracking_events ===")
with mysql_db.get_cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tracking_events'
        ORDER BY ordinal_position;
    """)
    for r in cur.fetchall():
        print(f"  {r['column_name']} ({r['data_type']})")

print("\n=== Sample event data (PG) ===")
with db.get_cursor() as cur:
    cur.execute("""
        SELECT event_name, event_data, page_url, referrer
        FROM tracking_events 
        WHERE event_data IS NOT NULL 
        LIMIT 5;
    """)
    for r in cur.fetchall():
        print(r)

print("\n=== Sample event data (MySQL) ===")
with db_mysql.get_cursor() as cur:
    cur.execute("""
        SELECT event_name, event_data, page_url, referrer
        FROM tracking_events 
        WHERE event_data IS NOT NULL 
        LIMIT 5;
    """)
    for r in cur.fetchall():
        print(r)
