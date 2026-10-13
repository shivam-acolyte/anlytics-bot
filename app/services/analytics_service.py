import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.database import db
from app.mysql_database import db_mysql

logger = logging.getLogger("trackingbot.analytics")

class AnalyticsService:
    _cache: Dict[str, Tuple[datetime, Any]] = {}
    CACHE_TTL_SECONDS = 45  # 45-second cache for instant dashboard responsiveness

    @classmethod
    def _get_cache(cls, key: str) -> Optional[Any]:
        if key in cls._cache:
            cached_time, val = cls._cache[key]
            if (datetime.now() - cached_time).total_seconds() < cls.CACHE_TTL_SECONDS:
                return val
            del cls._cache[key]
        return None

    @classmethod
    def _set_cache(cls, key: str, val: Any):
        cls._cache[key] = (datetime.now(), val)

    @classmethod
    def get_db(cls, platform: str = "living"):
        """Get the database manager for the specified platform."""
        if platform and platform.lower() == "startupflora":
            return db_mysql
        return db

    @classmethod
    def get_max_date(cls, platform: str = "living") -> datetime:
        """Fetch latest occurred_at in database with 60s cache."""
        cache_key = f"max_date_{platform}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached
        
        db_conn = cls.get_db(platform)
        try:
            row = db_conn.execute_one("SELECT MAX(occurred_at) AS max_dt FROM tracking_events;")
            max_dt = row.get("max_dt") if row else None
            if not max_dt:
                max_dt = datetime.now()
            elif isinstance(max_dt, str):
                max_dt = datetime.fromisoformat(max_dt)
            cls._set_cache(cache_key, max_dt)
            return max_dt
        except Exception as e:
            logger.error(f"Error fetching max date for {platform}: {e}")
            return datetime.now()

    @classmethod
    def get_websites(cls, platform: str = "living") -> List[Dict[str, Any]]:
        """Fetch distinct websites/domains tracked in tracking_events."""
        cache_key = f"websites_{platform}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        max_dt = cls.get_max_date(platform)
        cutoff = max_dt - timedelta(days=60)

        if platform == "startupflora":
            sql = """
                SELECT 
                    COALESCE(NULLIF(source_domain, ''), 'Direct / Unknown') AS website,
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    MAX(occurred_at) AS last_activity
                FROM tracking_events
                WHERE occurred_at >= %s
                GROUP BY website
                HAVING COUNT(*) > 2
                ORDER BY total_events DESC;
            """
            rows = db_conn.execute_query(sql, (cutoff,))
        else:
            sql = """
                SELECT 
                    COALESCE(NULLIF(source_domain, ''), 'Direct / Unknown') AS website,
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    MAX(occurred_at) AS last_activity
                FROM tracking_events
                WHERE occurred_at >= %s
                GROUP BY website
                HAVING COUNT(*) > 5
                ORDER BY total_events DESC;
            """
            rows = db_conn.execute_query(sql, (cutoff,))

        websites = []
        for r in rows:
            site_val = str(r["website"])
            websites.append({
                "id": site_val,
                "name": site_val.title() if "." not in site_val else site_val,
                "events": int(r["total_events"]),
                "users": int(r["unique_users"]),
                "sessions": int(r["total_sessions"]),
                "last_activity": r["last_activity"].isoformat() if r["last_activity"] else None
            })
        cls._set_cache(cache_key, websites)
        return websites

    @classmethod
    def _build_date_filter(
        cls,
        platform: str = "living",
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[str, List[Any], datetime, datetime]:
        """
        Constructs SQL clause and parameters for date filtering.
        Returns: (clause_str, [start_dt, end_dt], start_dt, end_dt)
        clause_str is "occurred_at >= %s AND occurred_at <= %s"
        """
        max_dt = cls.get_max_date(platform)
        parsed_start = None
        parsed_end = None

        if start_date and str(start_date).strip():
            s = str(start_date).strip().split("T")[0]
            try:
                parsed_start = datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                pass

        if end_date and str(end_date).strip():
            e = str(end_date).strip().split("T")[0]
            try:
                parsed_end = datetime.strptime(e, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
            except Exception:
                pass

        if parsed_start is not None:
            if parsed_end is None:
                parsed_end = max_dt if max_dt > parsed_start else parsed_start + timedelta(days=1)
            if parsed_start > parsed_end:
                parsed_start, parsed_end = parsed_end, parsed_start
        else:
            parsed_end = max_dt + timedelta(minutes=1)
            parsed_start = max_dt - timedelta(days=days if days > 0 else 30)

        # Reconcile tzinfo with max_dt
        if hasattr(max_dt, "tzinfo") and max_dt.tzinfo is not None:
            if parsed_start.tzinfo is None:
                parsed_start = parsed_start.replace(tzinfo=max_dt.tzinfo)
            if parsed_end.tzinfo is None:
                parsed_end = parsed_end.replace(tzinfo=max_dt.tzinfo)
        else:
            if parsed_start.tzinfo is not None:
                parsed_start = parsed_start.replace(tzinfo=None)
            if parsed_end.tzinfo is not None:
                parsed_end = parsed_end.replace(tzinfo=None)

        clause = "occurred_at >= %s AND occurred_at <= %s"
        return clause, [parsed_start, parsed_end], parsed_start, parsed_end

    @staticmethod
    def _build_utm_clause(utm: Optional[str]) -> Tuple[str, List[Any]]:
        """Helper to construct SQL filter clause and parameter values for UTM filtering."""
        if not utm or utm.lower() == "all" or not utm.strip():
            return "", []
        val = utm.strip()
        if val.startswith("campaign:"):
            return " AND utm_campaign = %s", [val.split("campaign:", 1)[1]]
        elif val.startswith("source:"):
            return " AND utm_source = %s", [val.split("source:", 1)[1]]
        elif val.startswith("medium:"):
            return " AND utm_medium = %s", [val.split("medium:", 1)[1]]
        else:
            return " AND (utm_source = %s OR utm_campaign = %s)", [val, val]

    @classmethod
    def get_utms(cls, platform: str = "living", days: int = 60) -> Dict[str, Any]:
        """Fetch distinct UTM campaigns and sources with frequencies."""
        cache_key = f"utms_full_{platform}_{days}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        max_dt = cls.get_max_date(platform)
        cutoff = max_dt - timedelta(days=days)

        campaigns_sql = """
            SELECT 
                utm_campaign AS campaign,
                COUNT(*) AS event_count,
                COUNT(DISTINCT anonymous_id) AS unique_users
            FROM tracking_events
            WHERE utm_campaign IS NOT NULL AND utm_campaign != ''
            AND occurred_at >= %s
            GROUP BY utm_campaign
            ORDER BY event_count DESC
            LIMIT 30;
        """
        sources_sql = """
            SELECT 
                utm_source AS source,
                COUNT(*) AS event_count,
                COUNT(DISTINCT anonymous_id) AS unique_users
            FROM tracking_events
            WHERE utm_source IS NOT NULL AND utm_source != ''
            AND occurred_at >= %s
            GROUP BY utm_source
            ORDER BY event_count DESC
            LIMIT 30;
        """
        try:
            c_rows = db_conn.execute_query(campaigns_sql, (cutoff,))
            s_rows = db_conn.execute_query(sources_sql, (cutoff,))
            campaigns = [
                {
                    "name": str(r["campaign"]),
                    "events": int(r["event_count"]),
                    "users": int(r["unique_users"])
                }
                for r in c_rows if r.get("campaign")
            ]
            sources = [
                {
                    "name": str(r["source"]),
                    "events": int(r["event_count"]),
                    "users": int(r["unique_users"])
                }
                for r in s_rows if r.get("source")
            ]
            res = {
                "campaigns": campaigns,
                "sources": sources
            }
            cls._set_cache(cache_key, res)
            return res
        except Exception as e:
            logger.error(f"Error fetching UTMs for {platform}: {e}")
            return {"campaigns": [], "sources": []}

    @classmethod
    def get_kpis(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        tz: str = "Asia/Kolkata", 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get high-level summary KPIs for selected website, date range, UTM, and platform."""
        cache_key = f"kpis_{platform}_{site}_{days}_{tz}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        if platform == "startupflora":
            stats_sql = f"""
                SELECT 
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    MIN(occurred_at) AS earliest_event,
                    MAX(occurred_at) AS latest_event
                FROM tracking_events
                WHERE {date_clause}
                {site_filter};
            """
            current_stats = db_conn.execute_one(stats_sql, tuple(params)) or {}

            # Lowest hour
            hour_sql = f"""
                SELECT 
                    HOUR(occurred_at) AS hour_val,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY hour_val
                ORDER BY unique_users ASC
                LIMIT 1;
            """
            lowest_hour = db_conn.execute_one(hour_sql, tuple(params))

            # Lowest Day of Week
            dow_sql = f"""
                SELECT 
                    DAYNAME(occurred_at) AS day_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY day_name
                ORDER BY unique_users ASC
                LIMIT 1;
            """
            lowest_dow = db_conn.execute_one(dow_sql, tuple(params))

        else: # living (Postgres)
            stats_sql = f"""
                SELECT 
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    MIN(occurred_at) AS earliest_event,
                    MAX(occurred_at) AS latest_event
                FROM tracking_events
                WHERE {date_clause}
                {site_filter};
            """
            current_stats = db_conn.execute_one(stats_sql, tuple(params)) or {}

            hour_sql = f"""
                SELECT 
                    EXTRACT(HOUR FROM occurred_at AT TIME ZONE %s)::int AS hour_val,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY hour_val
                ORDER BY unique_users ASC
                LIMIT 1;
            """
            h_params = [tz] + list(date_params)
            if site and site.lower() != "all":
                h_params.append(site)
            h_params.extend(utm_params)
            lowest_hour = db_conn.execute_one(hour_sql, tuple(h_params))

            dow_sql = f"""
                SELECT 
                    TO_CHAR(occurred_at AT TIME ZONE %s, 'FMDay') AS day_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY day_name
                ORDER BY unique_users ASC
                LIMIT 1;
            """
            d_params = [tz] + list(date_params)
            if site and site.lower() != "all":
                d_params.append(site)
            d_params.extend(utm_params)
            lowest_dow = db_conn.execute_one(dow_sql, tuple(d_params))

        h_val = lowest_hour["hour_val"] if lowest_hour else 4
        h_str = f"{h_val:02d}:00 - {((h_val+1)%24):02d}:00"

        res = {
            "platform": platform,
            "total_events": int(current_stats.get("total_events", 0)),
            "unique_users": int(current_stats.get("unique_users", 0)),
            "total_sessions": int(current_stats.get("total_sessions", 0)),
            "period_days": (e_dt - s_dt).days if start_date else days,
            "start_date": s_dt.strftime("%Y-%m-%d"),
            "end_date": e_dt.strftime("%Y-%m-%d"),
            "site": site or "all",
            "lowest_hour_slot": f"{h_str} (IST)" if tz == "Asia/Kolkata" else f"{h_str} ({tz})",
            "lowest_hour_users": int(lowest_hour.get("unique_users", 0)) if lowest_hour else 0,
            "lowest_day": lowest_dow.get("day_name", "Sunday") if lowest_dow else "Sunday",
            "lowest_day_users": int(lowest_dow.get("unique_users", 0)) if lowest_dow else 0,
            "dead_zone_window": "04:00 AM – 10:00 AM IST" if tz == "Asia/Kolkata" else "22:30 – 04:30 UTC",
            "peak_window": "12:00 PM – 08:00 PM IST",
            "last_refreshed": datetime.now().isoformat()
        }
        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def get_hourly_heatmap(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        tz: str = "Asia/Kolkata", 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch 7 days x 24 hours matrix of traffic activity."""
        cache_key = f"heatmap_{platform}_{site}_{days}_{tz}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        matrix = {d: [0]*24 for d in days_order}
        events_matrix = {d: [0]*24 for d in days_order}

        if platform == "startupflora":
            sql = f"""
                SELECT 
                    DAYOFWEEK(occurred_at) - 1 AS dow,
                    DAYNAME(occurred_at) AS day_name,
                    HOUR(occurred_at) AS hour_val,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS sessions
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY dow, day_name, hour_val
                ORDER BY dow ASC, hour_val ASC;
            """
            rows = db_conn.execute_query(sql, tuple(params))
        else:
            sql = f"""
                SELECT 
                    EXTRACT(DOW FROM occurred_at AT TIME ZONE %s)::int AS dow,
                    TO_CHAR(occurred_at AT TIME ZONE %s, 'FMDay') AS day_name,
                    EXTRACT(HOUR FROM occurred_at AT TIME ZONE %s)::int AS hour_val,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS sessions
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY dow, day_name, hour_val
                ORDER BY dow ASC, hour_val ASC;
            """
            q_params = [tz, tz, tz] + list(date_params)
            if site and site.lower() != "all":
                q_params.append(site)
            q_params.extend(utm_params)
            rows = db_conn.execute_query(sql, tuple(q_params))

        max_users = 1
        min_users = 999999
        trough_slot = None

        for r in rows:
            day = r["day_name"].strip()
            hour = int(r["hour_val"])
            users = int(r["unique_users"])
            events = int(r["event_count"])
            if day in matrix and 0 <= hour < 24:
                matrix[day][hour] = users
                events_matrix[day][hour] = events
                if users > max_users:
                    max_users = users
                if users < min_users and users > 0:
                    min_users = users
                    trough_slot = {"day": day, "hour": hour, "users": users, "events": events}

        res = {
            "platform": platform,
            "days": days_order,
            "hours": [f"{h:02d}:00" for h in range(24)],
            "users_matrix": matrix,
            "events_matrix": events_matrix,
            "max_users": max_users,
            "min_users": min_users if min_users != 999999 else 0,
            "absolute_trough": trough_slot,
            "timezone": tz
        }
        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def get_daily_trends(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        tz: str = "Asia/Kolkata", 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch daily timeline of events, users, sessions."""
        cache_key = f"trends_{platform}_{site}_{days}_{tz}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        if platform == "startupflora":
            sql = f"""
                SELECT 
                    DATE(occurred_at) AS date_val,
                    DATE_FORMAT(occurred_at, '%%a') AS day_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS sessions
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY date_val, day_name
                ORDER BY date_val ASC;
            """
            rows = db_conn.execute_query(sql, tuple(params))
        else:
            sql = f"""
                SELECT 
                    DATE(occurred_at AT TIME ZONE %s) AS date_val,
                    TO_CHAR(occurred_at AT TIME ZONE %s, 'Dy') AS day_name,
                    COUNT(*) AS event_count,
                    COUNT(DISTINCT anonymous_id) AS unique_users,
                    COUNT(DISTINCT session_id) AS sessions
                FROM tracking_events
                WHERE {date_clause}
                {site_filter}
                GROUP BY date_val, day_name
                ORDER BY date_val ASC;
            """
            q_params = [tz, tz] + list(date_params)
            if site and site.lower() != "all":
                q_params.append(site)
            q_params.extend(utm_params)
            rows = db_conn.execute_query(sql, tuple(q_params))

        trends = []
        for r in rows:
            trends.append({
                "date": str(r["date_val"]),
                "day": str(r["day_name"]),
                "events": int(r["event_count"]),
                "users": int(r["unique_users"]),
                "sessions": int(r["sessions"])
            })
        cls._set_cache(cache_key, trends)
        return trends

    @classmethod
    def get_events_breakdown(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch breakdown of top event names."""
        cache_key = f"events_{platform}_{site}_{days}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        sql = f"""
            SELECT 
                event_name,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS unique_users
            FROM tracking_events
            WHERE {date_clause}
            {site_filter}
            GROUP BY event_name
            ORDER BY count DESC
            LIMIT 12;
        """
        rows = db_conn.execute_query(sql, tuple(params))
        res = [
            {
                "event_name": r["event_name"],
                "count": int(r["count"]),
                "users": int(r["unique_users"])
            }
            for r in rows
        ]
        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def get_top_pages(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        limit: int = 15, 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch top visited page URLs."""
        cache_key = f"pages_{platform}_{site}_{days}_{limit}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)
        params.append(limit)

        sql = f"""
            SELECT 
                COALESCE(NULLIF(page_url, ''), '/') AS page_url,
                COUNT(*) AS views,
                COUNT(DISTINCT anonymous_id) AS unique_users
            FROM tracking_events
            WHERE {date_clause}
            {site_filter}
            GROUP BY page_url
            ORDER BY views DESC
            LIMIT %s;
        """
        rows = db_conn.execute_query(sql, tuple(params))
        res = [
            {
                "url": r["page_url"],
                "views": int(r["views"]),
                "users": int(r["unique_users"])
            }
            for r in rows
        ]
        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def search_pages(
        cls, 
        query: str = "", 
        platform: str = "living", 
        limit: int = 25,
        days: int = 60,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search pages by URL pattern with views and user counts. If query is empty, returns top pages."""
        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)
        q_str = (query or "").strip()

        if q_str:
            pattern = f"%{q_str}%"
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        COALESCE(NULLIF(page_url, ''), '/') AS page_url,
                        COUNT(*) AS views,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    WHERE page_url LIKE %s AND {date_clause}
                    GROUP BY page_url
                    ORDER BY views DESC
                    LIMIT %s;
                """
            else:
                sql = f"""
                    SELECT 
                        COALESCE(NULLIF(page_url, ''), '/') AS page_url,
                        COUNT(*) AS views,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    WHERE page_url ILIKE %s AND {date_clause}
                    GROUP BY page_url
                    ORDER BY views DESC
                    LIMIT %s;
                """
            params = [pattern] + list(date_params) + [limit]
        else:
            sql = f"""
                SELECT 
                    COALESCE(NULLIF(page_url, ''), '/') AS page_url,
                    COUNT(*) AS views,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE {date_clause}
                GROUP BY page_url
                ORDER BY views DESC
                LIMIT %s;
            """
            params = list(date_params) + [limit]

        rows = db_conn.execute_query(sql, tuple(params))
        return [
            {
                "url": r["page_url"],
                "views": int(r["views"]),
                "users": int(r["users"])
            }
            for r in rows
        ]

    @classmethod
    def get_geo_and_referrers(
        cls, 
        site: Optional[str] = None, 
        days: int = 30, 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch country distribution and top referrer domains."""
        cache_key = f"geo_{platform}_{site}_{days}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = list(date_params)
        if site and site.lower() != "all":
            site_filter += " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        countries_sql = f"""
            SELECT 
                COALESCE(NULLIF(country, ''), 'Unknown') AS country,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE {date_clause}
            {site_filter}
            GROUP BY country
            ORDER BY count DESC
            LIMIT 10;
        """
        countries = db_conn.execute_query(countries_sql, tuple(params))

        referrers_sql = f"""
            SELECT 
                COALESCE(NULLIF(source_domain, ''), 'Direct / Organic') AS source,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE {date_clause}
            {site_filter}
            GROUP BY source
            ORDER BY count DESC
            LIMIT 8;
        """
        referrers = db_conn.execute_query(referrers_sql, tuple(params))

        res = {
            "platform": platform,
            "countries": [{"name": c["country"], "count": int(c["count"]), "users": int(c["users"])} for c in countries],
            "referrers": [{"source": r["source"], "count": int(r["count"]), "users": int(r["users"])} for r in referrers]
        }
        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def compare_websites(cls, site_a: str, site_b: str, days: int = 30, platform: str = "living") -> Dict[str, Any]:
        """Compare two websites side by side."""
        stats_a = cls.get_kpis(site=site_a, days=days, platform=platform)
        stats_b = cls.get_kpis(site=site_b, days=days, platform=platform)
        events_a = cls.get_events_breakdown(site=site_a, days=days, platform=platform)
        events_b = cls.get_events_breakdown(site=site_b, days=days, platform=platform)

        return {
            "platform": platform,
            "site_a": {"name": site_a, "kpis": stats_a, "events": events_a},
            "site_b": {"name": site_b, "kpis": stats_b, "events": events_b},
            "days": days
        }

    @classmethod
    def get_page_deep_dive(
        cls, 
        page_url: str, 
        site: Optional[str] = None, 
        days: int = 30, 
        tz: str = "Asia/Kolkata", 
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch comprehensive, multi-dimensional deep dive analytics, domain click breakdown, and recursive actions for any page URL."""
        cache_key = f"page_dive_{platform}_{page_url}_{site}_{days}_{tz}_{utm}_{start_date}_{end_date}"
        cached = cls._get_cache(cache_key)
        if cached:
            return cached

        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        site_filter = ""
        params = [page_url] + list(date_params)
        if site and site.lower() != "all":
            site_filter = " AND source_domain = %s"
            params.append(site)
        utm_clause, utm_params = cls._build_utm_clause(utm)
        site_filter += utm_clause
        params.extend(utm_params)

        # 1. Comprehensive Page KPIs SQL (Total Views, Total Clicks, Actions, Users, Clicking Users, Distinct Domains)
        summary_kpi_sql = f"""
            SELECT 
                COUNT(*) AS total_events,
                COUNT(CASE WHEN event_name = 'page_view' THEN 1 END) AS total_views,
                COUNT(CASE WHEN event_name IN (
                    'button_click', 'cta_clicked', 'property_contact_clicked', 
                    'community_whatsapp_cta_clicked', 'blog_banner_click', 
                    'lead_form_submit_clicked', 'enquiry_submitted', 'form_submit', 'lead_submitted'
                ) OR event_name LIKE '%%click%%' THEN 1 END) AS total_clicks,
                COUNT(CASE WHEN event_name NOT IN ('page_view', 'scroll_depth', 'time_on_page', 'page_exit') THEN 1 END) AS total_actions,
                COUNT(DISTINCT anonymous_id) AS unique_users,
                COUNT(DISTINCT session_id) AS total_sessions,
                COUNT(DISTINCT CASE WHEN event_name IN (
                    'button_click', 'cta_clicked', 'property_contact_clicked', 
                    'community_whatsapp_cta_clicked', 'blog_banner_click', 
                    'lead_form_submit_clicked', 'enquiry_submitted', 'form_submit', 'lead_submitted'
                ) OR event_name LIKE '%%click%%' THEN anonymous_id END) AS clicking_users,
                COUNT(DISTINCT NULLIF(source_domain, '')) AS distinct_domains,
                MIN(occurred_at) AS first_seen,
                MAX(occurred_at) AS last_seen
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter};
        """

        # 2. Domain clicks breakdown SQL (All domains and their click & button counts)
        domain_clicks_sql = f"""
            SELECT 
                COALESCE(NULLIF(source_domain, ''), 'Direct / Unknown') AS domain,
                COUNT(*) AS total_clicks,
                COUNT(DISTINCT anonymous_id) AS clicking_users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
              AND (event_name IN (
                  'button_click', 'cta_clicked', 'property_contact_clicked', 
                  'community_whatsapp_cta_clicked', 'blog_banner_click', 
                  'lead_form_submit_clicked', 'enquiry_submitted', 'form_submit', 'lead_submitted'
              ) OR event_name LIKE '%%click%%')
            {site_filter}
            GROUP BY domain
            ORDER BY total_clicks DESC;
        """

        # 3. Actions & Things SQL for recursive hierarchy inspection
        actions_hier_sql = f"""
            SELECT 
                event_name,
                COALESCE(NULLIF(source_domain, ''), 'Direct / Unknown') AS domain,
                event_data,
                referrer,
                COUNT(*) AS cnt,
                COUNT(DISTINCT anonymous_id) AS users,
                MAX(occurred_at) AS latest_at
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
              AND event_name NOT IN ('page_view', 'scroll_depth', 'time_on_page', 'page_exit')
            {site_filter}
            GROUP BY event_name, domain, event_data, referrer
            ORDER BY cnt DESC
            LIMIT 120;
        """

        # 4. Events breakdown SQL
        events_sql = f"""
            SELECT 
                event_name,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY event_name
            ORDER BY count DESC
            LIMIT 15;
        """

        # 5. Hourly Distribution SQL
        if platform == "startupflora":
            hourly_sql = f"""
                SELECT 
                    HOUR(occurred_at) AS h,
                    COUNT(*) AS count,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY h
                ORDER BY h ASC;
            """
            h_params = params
        else:
            hourly_sql = f"""
                SELECT 
                    EXTRACT(HOUR FROM occurred_at AT TIME ZONE %s)::int AS h,
                    COUNT(*) AS count,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY h
                ORDER BY h ASC;
            """
            h_params = [tz] + params

        # 6. Daily Trends SQL
        if platform == "startupflora":
            daily_sql = f"""
                SELECT 
                    DATE(occurred_at) AS d_val,
                    DATE_FORMAT(occurred_at, '%%a') AS d_name,
                    COUNT(*) AS views,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY d_val, d_name
                ORDER BY d_val ASC;
            """
            d_params = params
        else:
            daily_sql = f"""
                SELECT 
                    DATE(occurred_at AT TIME ZONE %s) AS d_val,
                    TO_CHAR(occurred_at AT TIME ZONE %s, 'Dy') AS d_name,
                    COUNT(*) AS views,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY d_val, d_name
                ORDER BY d_val ASC;
            """
            d_params = [tz, tz] + params

        # 7. 15-Minute Slots SQL
        if platform == "startupflora":
            min_sql = f"""
                SELECT 
                    CONCAT(DATE_FORMAT(occurred_at, '%%H:'), LPAD(FLOOR(MINUTE(occurred_at) / 15) * 15, 2, '0')) AS slot,
                    COUNT(*) AS count,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY slot
                ORDER BY slot ASC;
            """
            m_params = params
        else:
            min_sql = f"""
                SELECT 
                    TO_CHAR(DATE_TRUNC('hour', occurred_at AT TIME ZONE %s) + 
                            INTERVAL '15 min' * FLOOR(EXTRACT(MINUTE FROM occurred_at AT TIME ZONE %s) / 15), 'HH24:MI') AS slot,
                    COUNT(*) AS count,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY slot
                ORDER BY slot ASC;
            """
            m_params = [tz, tz] + params

        # 8. Day of Week distribution SQL
        if platform == "startupflora":
            dow_sql = f"""
                SELECT 
                    DAYOFWEEK(occurred_at) - 1 AS dow,
                    DAYNAME(occurred_at) AS day_name,
                    COUNT(*) AS views,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY dow, day_name
                ORDER BY dow ASC;
            """
            dow_params = params
        else:
            dow_sql = f"""
                SELECT 
                    EXTRACT(DOW FROM occurred_at AT TIME ZONE %s)::int AS dow,
                    TO_CHAR(occurred_at AT TIME ZONE %s, 'FMDay') AS day_name,
                    COUNT(*) AS views,
                    COUNT(DISTINCT anonymous_id) AS users
                FROM tracking_events
                WHERE page_url = %s AND {date_clause}
                {site_filter}
                GROUP BY dow, day_name
                ORDER BY dow ASC;
            """
            dow_params = [tz, tz] + params

        # 9. Traffic Sources & Referrers SQL
        sources_sql = f"""
            SELECT 
                COALESCE(NULLIF(referrer, ''), NULLIF(source_domain, ''), 'Direct / Organic') AS source,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY source
            ORDER BY count DESC
            LIMIT 10;
        """

        # UTM Campaigns SQL
        utm_sql = f"""
            SELECT 
                COALESCE(NULLIF(utm_campaign, ''), 'Organic') AS campaign,
                COALESCE(NULLIF(utm_source, ''), 'Direct') AS source,
                COALESCE(NULLIF(utm_medium, ''), 'None') AS medium,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY campaign, source, medium
            ORDER BY count DESC
            LIMIT 8;
        """

        # Device types SQL
        device_sql = f"""
            SELECT 
                CASE 
                    WHEN user_agent LIKE '%%Mobile%%' OR user_agent LIKE '%%Android%%' OR user_agent LIKE '%%iPhone%%' THEN 'Mobile'
                    WHEN user_agent LIKE '%%iPad%%' OR user_agent LIKE '%%Tablet%%' THEN 'Tablet'
                    WHEN user_agent IS NULL OR user_agent = '' THEN 'Unknown'
                    ELSE 'Desktop'
                END AS device_type,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY device_type
            ORDER BY count DESC;
        """

        # Browsers SQL
        browser_sql = f"""
            SELECT 
                CASE 
                    WHEN user_agent LIKE '%%Chrome%%' AND user_agent NOT LIKE '%%Edg%%' AND user_agent NOT LIKE '%%OPR%%' THEN 'Chrome'
                    WHEN user_agent LIKE '%%Safari%%' AND user_agent NOT LIKE '%%Chrome%%' THEN 'Safari'
                    WHEN user_agent LIKE '%%Firefox%%' THEN 'Firefox'
                    WHEN user_agent LIKE '%%Edg%%' THEN 'Edge'
                    WHEN user_agent LIKE '%%OPR%%' OR user_agent LIKE '%%Opera%%' THEN 'Opera'
                    ELSE 'Other'
                END AS browser,
                COUNT(*) AS count
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY browser
            ORDER BY count DESC
            LIMIT 6;
        """

        # Countries SQL
        countries_sql = f"""
            SELECT 
                COALESCE(NULLIF(country, ''), 'Unknown') AS country,
                COUNT(*) AS count,
                COUNT(DISTINCT anonymous_id) AS users
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            GROUP BY country
            ORDER BY count DESC
            LIMIT 10;
        """

        # Recent Activity Stream SQL
        recent_sql = f"""
            SELECT 
                event_name,
                session_id,
                occurred_at,
                COALESCE(NULLIF(referrer, ''), 'Direct') AS referrer,
                COALESCE(NULLIF(country, ''), 'IN') AS country,
                user_agent,
                event_data
            FROM tracking_events
            WHERE page_url = %s AND {date_clause}
            {site_filter}
            ORDER BY occurred_at DESC
            LIMIT 50;
        """

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=10) as executor:
            fut_summary = executor.submit(db_conn.execute_one, summary_kpi_sql, tuple(params))
            fut_domain_clicks = executor.submit(db_conn.execute_query, domain_clicks_sql, tuple(params))
            fut_actions_hier = executor.submit(db_conn.execute_query, actions_hier_sql, tuple(params))
            fut_events = executor.submit(db_conn.execute_query, events_sql, tuple(params))
            fut_hourly = executor.submit(db_conn.execute_query, hourly_sql, tuple(h_params))
            fut_daily = executor.submit(db_conn.execute_query, daily_sql, tuple(d_params))
            fut_min = executor.submit(db_conn.execute_query, min_sql, tuple(m_params))
            fut_dow = executor.submit(db_conn.execute_query, dow_sql, tuple(dow_params))
            fut_sources = executor.submit(db_conn.execute_query, sources_sql, tuple(params))
            fut_utm = executor.submit(db_conn.execute_query, utm_sql, tuple(params))
            fut_device = executor.submit(db_conn.execute_query, device_sql, tuple(params))
            fut_browser = executor.submit(db_conn.execute_query, browser_sql, tuple(params))
            fut_countries = executor.submit(db_conn.execute_query, countries_sql, tuple(params))
            fut_recent = executor.submit(db_conn.execute_query, recent_sql, tuple(params))

            summary_data = fut_summary.result() or {}
            domain_clicks_rows = fut_domain_clicks.result() or []
            actions_rows = fut_actions_hier.result() or []
            events_rows = fut_events.result() or []
            hourly_rows = fut_hourly.result() or []
            daily_rows = fut_daily.result() or []
            min_rows = fut_min.result() or []
            dow_rows = fut_dow.result() or []
            sources_rows = fut_sources.result() or []
            utm_rows = fut_utm.result() or []
            device_rows = fut_device.result() or []
            browser_rows = fut_browser.result() or []
            countries_rows = fut_countries.result() or []
            recent_rows = fut_recent.result() or []

        total_views = int(summary_data.get("total_views", 0))
        total_clicks = int(summary_data.get("total_clicks", 0))
        total_actions = int(summary_data.get("total_actions", 0))
        unique_users = int(summary_data.get("unique_users", 0))
        total_sessions = int(summary_data.get("total_sessions", 0))
        clicking_users = int(summary_data.get("clicking_users", 0))
        distinct_domains = int(summary_data.get("distinct_domains", 0))

        ctr = round((total_clicks / total_views * 100), 2) if total_views > 0 else 0.0
        interaction_rate = round((total_actions / total_views * 100), 1) if total_views > 0 else 0.0

        # Process Recursive Actions Tree & Flat Actions
        tree = {}
        flat_actions = []
        domain_button_map = {}

        for idx, r in enumerate(actions_rows):
            ev_name = str(r["event_name"])
            domain = str(r["domain"])
            cnt = int(r["cnt"])
            users = int(r["users"])
            ed = r.get("event_data")
            latest_at = r["latest_at"].isoformat() if hasattr(r.get("latest_at"), "isoformat") else str(r.get("latest_at") or "")

            if isinstance(ed, str):
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {}
            elif not isinstance(ed, dict):
                ed = {}

            # Identify button or CTA
            btn_name = (
                ed.get("cta_name") or 
                ed.get("label") or 
                ed.get("button_name") or 
                ed.get("button_text") or 
                ed.get("action") or 
                ed.get("form_name") or 
                ed.get("form_type") or 
                ed.get("popup_name") or
                ed.get("title") or 
                ev_name.replace("_", " ").title()
            )

            dest_domain = ed.get("destination") or ed.get("target_url") or ed.get("href") or domain

            # Map top buttons clicked per domain
            if domain not in domain_button_map:
                domain_button_map[domain] = {}
            domain_button_map[domain][btn_name] = domain_button_map[domain].get(btn_name, 0) + cnt

            # Build recursive tree: Event Category -> Button/Action -> Domain -> Things
            if ev_name not in tree:
                tree[ev_name] = {
                    "event_name": ev_name,
                    "total_count": 0,
                    "unique_users": 0,
                    "buttons": {}
                }
            tree[ev_name]["total_count"] += cnt
            tree[ev_name]["unique_users"] += users

            btn_dict = tree[ev_name]["buttons"]
            if btn_name not in btn_dict:
                btn_dict[btn_name] = {
                    "button_name": btn_name,
                    "total_count": 0,
                    "unique_users": 0,
                    "domains": {}
                }
            btn_dict[btn_name]["total_count"] += cnt
            btn_dict[btn_name]["unique_users"] += users

            dom_dict = btn_dict[btn_name]["domains"]
            if domain not in dom_dict:
                dom_dict[domain] = {
                    "domain": domain,
                    "dest_domain": dest_domain,
                    "total_count": 0,
                    "unique_users": 0,
                    "sample_things": {},
                    "occurrences": []
                }
            dom_dict[domain]["total_count"] += cnt
            dom_dict[domain]["unique_users"] += users

            # Extract things contained in payload
            things = {k: v for k, v in ed.items() if k not in ("_meta", "timestamp") and v is not None}
            for k, v in things.items():
                if k not in dom_dict[domain]["sample_things"]:
                    dom_dict[domain]["sample_things"][k] = v

            things_summary = ", ".join(f"{k}: {v}" for k, v in list(things.items())[:3])
            if not things_summary:
                things_summary = f"{ev_name} triggered on {domain}"

            dom_dict[domain]["occurrences"].append({
                "count": cnt,
                "users": users,
                "latest_at": latest_at,
                "things": things,
                "raw_payload": ed
            })

            flat_actions.append({
                "id": f"act_{idx}",
                "event_name": ev_name,
                "button_name": btn_name,
                "domain": domain,
                "dest_domain": dest_domain,
                "count": cnt,
                "users": users,
                "things_summary": things_summary,
                "things": things,
                "raw_payload": ed,
                "latest_at": latest_at
            })

        # Process Domain Clicks Breakdown
        domain_breakdown = []
        for r in domain_clicks_rows:
            dom = str(r["domain"])
            d_clicks = int(r["total_clicks"])
            d_users = int(r["clicking_users"])
            share = round((d_clicks / max(1, total_clicks)) * 100, 1) if total_clicks > 0 else 0.0

            btns = domain_button_map.get(dom, {})
            top_btns = sorted([{"button": b, "count": c} for b, c in btns.items()], key=lambda x: x["count"], reverse=True)[:5]

            domain_breakdown.append({
                "domain": dom,
                "clicks": d_clicks,
                "users": d_users,
                "share_pct": share,
                "top_buttons": top_btns
            })

        # Hourly Curve
        hourly_views = [0] * 24
        hourly_users = [0] * 24
        peak_hour = 12
        max_h_users = 0
        for r in hourly_rows:
            h = int(r["h"])
            u = int(r["users"])
            hourly_views[h] = int(r["count"])
            hourly_users[h] = u
            if u > max_h_users:
                max_h_users = u
                peak_hour = h

        daily_trends = [
            {"date": str(r["d_val"]), "day": str(r["d_name"]), "views": int(r["views"]), "users": int(r["users"])}
            for r in daily_rows
        ]

        recent_events = []
        for r in recent_rows:
            dt_str = r["occurred_at"].isoformat() if hasattr(r["occurred_at"], "isoformat") else str(r["occurred_at"])
            ua = str(r.get("user_agent") or "")
            device = "Mobile" if any(k in ua for k in ["Mobile", "Android", "iPhone"]) else ("Tablet" if "iPad" in ua else "Desktop")
            
            ev_data = r.get("event_data")
            if isinstance(ev_data, str):
                try:
                    ev_data = json.loads(ev_data)
                except Exception:
                    ev_data = {}

            recent_events.append({
                "event_name": r["event_name"],
                "session_id": str(r["session_id"] or "")[:12] + "...",
                "occurred_at": dt_str,
                "referrer": r["referrer"],
                "country": r["country"],
                "device": device,
                "data_summary": ev_data.get("title") or ev_data.get("label") or ev_data.get("button_text") or (str(ev_data)[:60] if ev_data else "")
            })

        res = {
            "page_url": page_url,
            "platform": platform,
            "period_days": (e_dt - s_dt).days if start_date else days,
            "start_date": s_dt.strftime("%Y-%m-%d"),
            "end_date": e_dt.strftime("%Y-%m-%d"),
            "kpis": {
                "total_views": total_views,
                "total_clicks": total_clicks,
                "ctr": ctr,
                "total_actions": total_actions,
                "unique_users": unique_users,
                "total_sessions": total_sessions,
                "clicking_users": clicking_users,
                "distinct_domains": distinct_domains,
                "first_seen": summary_data["first_seen"].isoformat() if summary_data.get("first_seen") else None,
                "last_seen": summary_data["last_seen"].isoformat() if summary_data.get("last_seen") else None,
                "peak_hour": f"{peak_hour:02d}:00 - {((peak_hour+1)%24):02d}:00 ({tz.split('/')[-1]})",
                "interaction_rate": interaction_rate
            },
            "domain_clicks_breakdown": domain_breakdown,
            "recursive_actions": tree,
            "flat_actions": flat_actions,
            "traffic_curves": {
                "daily_trends": daily_trends,
                "hourly": {
                    "labels": [f"{h:02d}:00" for h in range(24)],
                    "views": hourly_views,
                    "users": hourly_users
                },
                "fifteen_min": {
                    "labels": [r["slot"] for r in min_rows],
                    "views": [int(r["count"]) for r in min_rows],
                    "users": [int(r["users"]) for r in min_rows]
                },
                "dow": {
                    "labels": [r["day_name"].strip() for r in dow_rows],
                    "views": [int(r["views"]) for r in dow_rows],
                    "users": [int(r["users"]) for r in dow_rows]
                }
            },
            "events_breakdown": [
                {"name": r["event_name"], "count": int(r["count"]), "users": int(r["users"])}
                for r in events_rows
            ],
            "sources_and_utm": {
                "referrers": [
                    {"source": r["source"], "count": int(r["count"]), "users": int(r["users"])}
                    for r in sources_rows
                ],
                "campaigns": [
                    {
                        "campaign": r["campaign"],
                        "source": r["source"],
                        "medium": r["medium"],
                        "count": int(r["count"]),
                        "users": int(r["users"])
                    }
                    for r in utm_rows
                ]
            },
            "devices_and_audience": {
                "device_types": [
                    {"type": r["device_type"], "count": int(r["count"]), "users": int(r.get("users", 0))}
                    for r in device_rows
                ],
                "browsers": [
                    {"browser": r["browser"], "count": int(r["count"])}
                    for r in browser_rows
                ],
                "countries": [
                    {"name": r["country"], "count": int(r["count"]), "users": int(r["users"])}
                    for r in countries_rows
                ]
            },
            "recent_activity": recent_events
        }

        cls._set_cache(cache_key, res)
        return res

    @classmethod
    def get_granular_analysis(
        cls, 
        granularity: str = "hour", 
        site: Optional[str] = None, 
        days: int = 30, 
        page_url: Optional[str] = None, 
        tz: str = "Asia/Kolkata",
        platform: str = "living",
        utm: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deep time-dimension analysis by Hours, 30-Min, 15-Min, Minute-of-hour, or Days."""
        db_conn = cls.get_db(platform)
        date_clause, date_params, s_dt, e_dt = cls._build_date_filter(platform, days=days, start_date=start_date, end_date=end_date)

        filters = [date_clause]
        params = list(date_params)

        if site and site.lower() != "all":
            filters.append("source_domain = %s")
            params.append(site)
        if page_url and page_url.strip():
            filters.append("page_url = %s")
            params.append(page_url.strip())
        utm_clause, utm_params = cls._build_utm_clause(utm)
        if utm_clause:
            filters.append(utm_clause.replace(" AND ", "", 1))
            params.extend(utm_params)

        filter_clause = "WHERE " + " AND ".join(filters)

        if granularity == "30min":
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        CONCAT(DATE_FORMAT(occurred_at, '%%H:'), LPAD(FLOOR(MINUTE(occurred_at) / 30) * 30, 2, '0')) AS slot,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY slot
                    ORDER BY slot ASC;
                """
                rows = db_conn.execute_query(sql, tuple(params))
            else:
                sql = f"""
                    SELECT 
                        TO_CHAR(DATE_TRUNC('hour', occurred_at AT TIME ZONE %s) + 
                                INTERVAL '30 min' * FLOOR(EXTRACT(MINUTE FROM occurred_at AT TIME ZONE %s) / 30), 'HH24:MI') AS slot,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY slot
                    ORDER BY slot ASC;
                """
                q_params = [tz, tz] + params
                rows = db_conn.execute_query(sql, tuple(q_params))

            labels = [r["slot"] for r in rows]
            events = [int(r["events"]) for r in rows]
            users = [int(r["users"]) for r in rows]
            title = f"30-Minute Interval Deep Analysis ({len(labels)} Slots across 24h)"

        elif granularity == "15min":
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        CONCAT(DATE_FORMAT(occurred_at, '%%H:'), LPAD(FLOOR(MINUTE(occurred_at) / 15) * 15, 2, '0')) AS slot,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY slot
                    ORDER BY slot ASC;
                """
                rows = db_conn.execute_query(sql, tuple(params))
            else:
                sql = f"""
                    SELECT 
                        TO_CHAR(DATE_TRUNC('hour', occurred_at AT TIME ZONE %s) + 
                                INTERVAL '15 min' * FLOOR(EXTRACT(MINUTE FROM occurred_at AT TIME ZONE %s) / 15), 'HH24:MI') AS slot,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY slot
                    ORDER BY slot ASC;
                """
                q_params = [tz, tz] + params
                rows = db_conn.execute_query(sql, tuple(q_params))

            labels = [r["slot"] for r in rows]
            events = [int(r["events"]) for r in rows]
            users = [int(r["users"]) for r in rows]
            title = f"15-Minute Interval Deep Analysis ({len(labels)} Slots across 24h)"

        elif granularity == "minute":
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        MINUTE(occurred_at) AS m,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY m
                    ORDER BY m ASC;
                """
                rows = db_conn.execute_query(sql, tuple(params))
            else:
                sql = f"""
                    SELECT 
                        EXTRACT(MINUTE FROM occurred_at AT TIME ZONE %s)::int AS m,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY m
                    ORDER BY m ASC;
                """
                q_params = [tz] + params
                rows = db_conn.execute_query(sql, tuple(q_params))

            labels = [f":{int(r['m']):02d}m" for r in rows]
            events = [int(r["events"]) for r in rows]
            users = [int(r["users"]) for r in rows]
            title = "Minute-of-Hour Distribution (:00 to :59 min intra-hour patterns)"

        elif granularity == "day":
            trends = cls.get_daily_trends(site=site, days=days, tz=tz, platform=platform, utm=utm)
            labels = [f"{t['date'][5:]} ({t['day']})" for t in trends]
            events = [t["events"] for t in trends]
            users = [t["users"] for t in trends]
            title = f"Daily Traffic Trends ({len(trends)} Days)"

        else: # hour
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        HOUR(occurred_at) AS h,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users,
                        COUNT(DISTINCT session_id) AS sessions
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY h
                    ORDER BY h ASC;
                """
                rows = db_conn.execute_query(sql, tuple(params))
            else:
                sql = f"""
                    SELECT 
                        EXTRACT(HOUR FROM occurred_at AT TIME ZONE %s)::int AS h,
                        COUNT(*) AS events,
                        COUNT(DISTINCT anonymous_id) AS users,
                        COUNT(DISTINCT session_id) AS sessions
                    FROM tracking_events
                    {filter_clause}
                    GROUP BY h
                    ORDER BY h ASC;
                """
                q_params = [tz] + params
                rows = db_conn.execute_query(sql, tuple(q_params))

            labels = [f"{int(r['h']):02d}:00" for r in rows]
            events = [int(r["events"]) for r in rows]
            users = [int(r["users"]) for r in rows]
            title = "24-Hour Traffic Curve (Hourly Breakdown)"

        peak_idx = users.index(max(users)) if users else 0
        trough_idx = users.index(min(users)) if users else 0

        return {
            "platform": platform,
            "granularity": granularity,
            "title": title,
            "labels": labels,
            "events": events,
            "users": users,
            "peak_slot": {
                "label": labels[peak_idx] if labels else "--",
                "users": users[peak_idx] if users else 0,
                "events": events[peak_idx] if events else 0
            },
            "trough_slot": {
                "label": labels[trough_idx] if labels else "--",
                "users": users[trough_idx] if users else 0,
                "events": events[trough_idx] if events else 0
            },
            "avg_users_per_slot": round(sum(users) / len(users), 1) if users else 0,
            "total_events": sum(events),
            "timezone": tz
        }

    @classmethod
    def get_platforms_status(cls) -> Dict[str, Any]:
        """Fetch status and statistics for both connected database platforms."""
        pg_status = db.check_connection()
        my_status = db_mysql.check_connection()

        pg_counts = {"events": 0, "last_date": None}
        my_counts = {"events": 0, "last_date": None}

        try:
            pg_row = db.execute_one("SELECT COUNT(*) AS c, MAX(occurred_at) AS m FROM tracking_events;")
            if pg_row:
                pg_counts["events"] = int(pg_row["c"])
                pg_counts["last_date"] = pg_row["m"].isoformat() if pg_row["m"] else None
        except Exception as e:
            logger.error(f"PostgreSQL counts error: {e}")

        try:
            my_row = db_mysql.execute_one("SELECT COUNT(*) AS c, MAX(occurred_at) AS m FROM tracking_events;")
            if my_row:
                my_counts["events"] = int(my_row["c"])
                my_counts["last_date"] = my_row["m"].isoformat() if my_row["m"] else None
        except Exception as e:
            logger.error(f"MySQL counts error: {e}")

        return {
            "platforms": [
                {
                    "id": "living",
                    "name": "Acolyte Living",
                    "icon": "🏢",
                    "type": "PostgreSQL",
                    "health": pg_status,
                    "stats": pg_counts
                },
                {
                    "id": "startupflora",
                    "name": "StartupFlora",
                    "icon": "🌸",
                    "type": "MySQL (insights_db)",
                    "health": my_status,
                    "stats": my_counts
                }
            ]
        }

    @classmethod
    def refresh_daily_cache(cls) -> Dict[str, Any]:
        """Refresh precomputed analytical metrics."""
        cls._cache.clear()
        cls.get_kpis(days=30, platform="living")
        cls.get_kpis(days=30, platform="startupflora")
        cls.get_hourly_heatmap(days=30, platform="living")
        cls.get_hourly_heatmap(days=30, platform="startupflora")
        return {"status": "success", "refreshed_at": datetime.now().isoformat()}

analytics_service = AnalyticsService
