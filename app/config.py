import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from trackingbot directory or parent
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

def _intelligent_get(key: str, default: str = "") -> str:
    """Retrieve setting with precedence:
    1. Streamlit secrets (flat or nested table e.g. [postgres], [mysql], [openai])
    2. os.environ / .env
    3. default value
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None:
            # 1. Direct match (flat key)
            if key in st.secrets:
                return str(st.secrets[key])
            if key.lower() in st.secrets:
                return str(st.secrets[key.lower()])

            # 2. Check nested sections
            aliases = {
                "DB_HOST": [("postgres", "host"), ("postgresql", "host"), ("postgres", "DB_HOST"), ("database", "host")],
                "DB_PORT": [("postgres", "port"), ("postgresql", "port"), ("postgres", "DB_PORT"), ("database", "port")],
                "DB_USER": [("postgres", "user"), ("postgresql", "user"), ("postgres", "DB_USER"), ("postgres", "username"), ("database", "user")],
                "DB_PASSWORD": [("postgres", "password"), ("postgresql", "password"), ("postgres", "DB_PASSWORD"), ("database", "password")],
                "DB_NAME": [("postgres", "database"), ("postgresql", "database"), ("postgres", "dbname"), ("postgres", "DB_NAME"), ("database", "database")],
                "MYSQL_HOST": [("mysql", "host"), ("mysql", "MYSQL_HOST")],
                "MYSQL_PORT": [("mysql", "port"), ("mysql", "MYSQL_PORT")],
                "MYSQL_USER": [("mysql", "user"), ("mysql", "MYSQL_USER"), ("mysql", "username")],
                "MYSQL_PASSWORD": [("mysql", "password"), ("mysql", "MYSQL_PASSWORD")],
                "MYSQL_DATABASE": [("mysql", "database"), ("mysql", "MYSQL_DATABASE"), ("mysql", "dbname")],
                "OPENAI_API_KEY": [("openai", "api_key"), ("openai", "OPENAI_API_KEY")],
                "OPENAI_MODEL": [("openai", "model"), ("openai", "OPENAI_MODEL")],
            }

            if key in aliases:
                for section, field in aliases[key]:
                    if section in st.secrets and isinstance(st.secrets[section], dict):
                        sec_dict = st.secrets[section]
                        if field in sec_dict:
                            return str(sec_dict[field])
                        if field.lower() in sec_dict:
                            return str(sec_dict[field.lower()])
                        if field.upper() in sec_dict:
                            return str(sec_dict[field.upper()])
    except Exception:
        pass

    env_val = os.getenv(key)
    if env_val is not None:
        return env_val
    return default

def _intelligent_get_int(key: str, default: int) -> int:
    val = _intelligent_get(key, str(default))
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

# Backwards compatibility aliases
_get_setting = _intelligent_get
_get_int_setting = _intelligent_get_int

class Config:
    APP_NAME = "TrackingBot Analytics & AI Platform"
    APP_HOST = _get_setting("APP_HOST", "0.0.0.0")
    APP_PORT = _get_int_setting("APP_PORT", 8080)
    DEBUG = _get_setting("DEBUG", "True").lower() in ("true", "1", "yes")

    # PostgreSQL Database
    DB_HOST = _get_setting("DB_HOST", "localhost")
    DB_PORT = _get_setting("DB_PORT", "5432")
    DB_USER = _get_setting("DB_USER", "postgres")
    DB_PASSWORD = _get_setting("DB_PASSWORD", "")
    DB_NAME = _get_setting("DB_NAME", "acolye-living-v2")

    # StartupFlora MySQL Database
    MYSQL_HOST = _get_setting("MYSQL_HOST", "165.99.228.81")
    MYSQL_PORT = _get_int_setting("MYSQL_PORT", 3306)
    MYSQL_USER = _get_setting("MYSQL_USER", "ART")
    MYSQL_PASSWORD = _get_setting("MYSQL_PASSWORD", "Art@12345")
    MYSQL_DATABASE = _get_setting("MYSQL_DATABASE", "insights_db")

    # AI Configuration
    OPENAI_API_KEY = _get_setting("OPENAI_API_KEY", "")
    OPENAI_MODEL = _get_setting("OPENAI_MODEL", "gpt-4o-mini")

    # Configurable Analytics Tables
    ANALYTICS_TABLES = [
        t.strip() for t in _get_setting(
            "ANALYTICS_TABLES",
            "tracking_events,tracking_sessions,tracking_users,tracking_ip_locations"
        ).split(",") if t.strip()
    ]

    # Daily Refresh schedule (hour in 24h format, default 4 AM IST / 22:30 UTC)
    DAILY_REFRESH_HOUR = _get_int_setting("DAILY_REFRESH_HOUR", 4)

config = Config()
