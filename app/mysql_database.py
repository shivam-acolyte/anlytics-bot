import pymysql
import pymysql.cursors
import queue
import threading
import logging
from typing import List, Dict, Any, Optional
from app.config import config

logger = logging.getLogger("trackingbot.mysql_database")

class MySQLDatabase:
    _pool: Optional[queue.Queue] = None
    _lock = threading.Lock()
    _max_connections = 15
    _created_connections = 0

    @classmethod
    def _create_connection(cls) -> pymysql.Connection:
        """Create a new raw PyMySQL connection with DictCursor."""
        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            autocommit=True
        )

    @classmethod
    def get_connection(cls) -> pymysql.Connection:
        """Acquire a connection from pool or create a new one."""
        with cls._lock:
            if cls._pool is None:
                cls._pool = queue.Queue(maxsize=cls._max_connections)
        
        try:
            conn = cls._pool.get_nowait()
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn = cls._create_connection()
            return conn
        except queue.Empty:
            with cls._lock:
                if cls._created_connections < cls._max_connections:
                    cls._created_connections += 1
                    return cls._create_connection()
            # Wait for connection to be returned
            conn = cls._pool.get(timeout=10)
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn = cls._create_connection()
            return conn

    @classmethod
    def release_connection(cls, conn: pymysql.Connection):
        """Return connection back to the pool."""
        if cls._pool is not None:
            try:
                cls._pool.put_nowait(conn)
            except queue.Full:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            try:
                conn.close()
            except Exception:
                pass

    @classmethod
    def execute_query(cls, sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return list of dictionaries."""
        conn = cls.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                rows = cur.fetchall()
                return list(rows) if rows else []
        except Exception as e:
            logger.error(f"Error executing MySQL query: {sql} | Error: {e}")
            raise e
        finally:
            cls.release_connection(conn)

    @classmethod
    def execute_one(cls, sql: str, params: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Execute query returning a single row or None."""
        results = cls.execute_query(sql, params)
        return results[0] if results else None

    @classmethod
    def check_connection(cls) -> Dict[str, Any]:
        """Verify MySQL health and return version & database name."""
        try:
            row = cls.execute_one("SELECT VERSION() AS ver, DATABASE() AS cur_db;")
            return {
                "status": "connected",
                "database": row["cur_db"] if row else config.MYSQL_DATABASE,
                "version": f"MySQL {row['ver']}" if row else "MySQL",
                "host": config.MYSQL_HOST,
                "port": config.MYSQL_PORT
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "host": config.MYSQL_HOST,
                "port": config.MYSQL_PORT
            }

    @classmethod
    def get_table_schema(cls, table_name: str) -> List[Dict[str, Any]]:
        """Get column names and data types for a MySQL table."""
        sql = """
            SELECT 
                COLUMN_NAME AS column_name, 
                DATA_TYPE AS data_type, 
                IS_NULLABLE AS is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
        """
        return cls.execute_query(sql, (config.MYSQL_DATABASE, table_name))

    @classmethod
    def list_available_tables(cls) -> List[Dict[str, Any]]:
        """List all tables and approximate row counts."""
        sql = """
            SELECT 
                TABLE_NAME AS table_name,
                COALESCE(TABLE_ROWS, 0) AS approximate_rows
            FROM information_schema.tables
            WHERE table_schema = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME ASC;
        """
        return cls.execute_query(sql, (config.MYSQL_DATABASE,))

db_mysql = MySQLDatabase
