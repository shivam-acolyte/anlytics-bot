import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Any, Optional
from app.config import config

logger = logging.getLogger("trackingbot.database")

class Database:
    _pool: Optional[pool.ThreadedConnectionPool] = None

    @classmethod
    def get_pool(cls) -> pool.ThreadedConnectionPool:
        if cls._pool is None:
            try:
                cls._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    host=config.DB_HOST,
                    port=config.DB_PORT,
                    user=config.DB_USER,
                    password=config.DB_PASSWORD,
                    dbname=config.DB_NAME,
                    connect_timeout=10
                )
                logger.info("Connected to PostgreSQL connection pool successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL pool: {e}")
                raise e
        return cls._pool

    @classmethod
    def execute_query(cls, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return list of dictionaries."""
        pool_inst = cls.get_pool()
        conn = pool_inst.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                rows = cur.fetchall()
                # Convert RealDictRow to standard python dict
                return [dict(row) for row in rows]
        except Exception as e:
            conn.rollback()
            logger.error(f"Error executing query: {sql} | Error: {e}")
            raise e
        finally:
            pool_inst.putconn(conn)

    @classmethod
    def execute_one(cls, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Execute query returning a single row or None."""
        results = cls.execute_query(sql, params)
        return results[0] if results else None

    @classmethod
    def check_connection(cls) -> Dict[str, Any]:
        """Verify DB health and return version & database name."""
        try:
            row = cls.execute_one("SELECT version(), current_database(), current_schema();")
            return {
                "status": "connected",
                "database": row["current_database"] if row else config.DB_NAME,
                "version": row["version"].split(",")[0] if row else "PostgreSQL",
                "host": config.DB_HOST,
                "port": config.DB_PORT
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "host": config.DB_HOST,
                "port": config.DB_PORT
            }

    @classmethod
    def get_table_schema(cls, table_name: str) -> List[Dict[str, Any]]:
        """Get column names and data types for a table."""
        sql = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """
        return cls.execute_query(sql, (table_name,))

    @classmethod
    def list_available_tables(cls) -> List[Dict[str, Any]]:
        """List all public user tables and approximate row counts."""
        sql = """
            SELECT 
                t.table_name,
                COALESCE(s.n_live_tup, 0) AS approximate_rows
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
            WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name ASC;
        """
        return cls.execute_query(sql)

db = Database
