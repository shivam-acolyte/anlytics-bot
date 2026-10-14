import logging
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.database import db
from app.mysql_database import db_mysql

logger = logging.getLogger("trackingbot.lead_service")

class LeadService:
    @classmethod
    def get_db(cls, platform: str = "startupflora"):
        if platform and platform.lower() == "startupflora":
            return db_mysql
        return db

    @classmethod
    def _parse_user_agent(cls, ua: Optional[str]) -> Dict[str, str]:
        """Simple heuristic user-agent parser for browser, OS, and device."""
        if not ua:
            return {"browser": "Unknown", "os": "Unknown", "device": "Desktop"}
        
        ua_lower = ua.lower()
        device = "Desktop"
        if any(w in ua_lower for w in ["mobile", "android", "iphone", "ipod", "windows phone"]):
            device = "Mobile"
        elif "ipad" in ua_lower or "tablet" in ua_lower:
            device = "Tablet"
            
        os_name = "Unknown OS"
        if "windows" in ua_lower:
            os_name = "Windows"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            os_name = "iOS"
        elif "android" in ua_lower:
            os_name = "Android"
        elif "mac os" in ua_lower:
            os_name = "macOS"
        elif "linux" in ua_lower:
            os_name = "Linux"

        browser = "Unknown Browser"
        if "edg" in ua_lower:
            browser = "Edge"
        elif "chrome" in ua_lower and "chromium" not in ua_lower:
            browser = "Chrome"
        elif "firefox" in ua_lower:
            browser = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "Safari"
        elif "opera" in ua_lower or "opr" in ua_lower:
            browser = "Opera"
        elif "instagram" in ua_lower:
            browser = "Instagram Webview"

        return {"browser": browser, "os": os_name, "device": device}

    @classmethod
    def _format_duration(cls, seconds: int) -> str:
        """Format seconds into readable string (e.g. 2m 14s)."""
        if seconds <= 0:
            return "< 1s"
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    @classmethod
    def get_leads_summary(
        cls,
        platform: str = "startupflora",
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregate metrics, top endpoints, sources, and daily trends for leads."""
        db_conn = cls.get_db(platform)
        
        # Build date condition
        if platform == "startupflora":
            date_filter = "WHERE 1=1"
            params: List[Any] = []
            if start_date and end_date:
                date_filter += " AND created_at >= %s AND created_at <= %s"
                params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            elif days:
                date_filter += " AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)"
                params.append(days)

            # Total leads
            total_sql = f"SELECT COUNT(*) AS total FROM enquiries {date_filter};"
            total_row = db_conn.execute_one(total_sql, tuple(params))
            total_leads = int(total_row["total"]) if total_row else 0

            # Top endpoints
            ep_sql = f"""
                SELECT 
                    COALESCE(NULLIF(endpoint, ''), 'Unspecified') AS endpoint_url,
                    COUNT(*) AS count
                FROM enquiries
                {date_filter}
                GROUP BY endpoint_url
                ORDER BY count DESC
                LIMIT 10;
            """
            top_endpoints = db_conn.execute_query(ep_sql, tuple(params))

            # Top sources
            src_sql = f"""
                SELECT 
                    COALESCE(NULLIF(source, ''), 'Direct / Unknown') AS source_name,
                    COUNT(*) AS count
                FROM enquiries
                {date_filter}
                GROUP BY source_name
                ORDER BY count DESC
                LIMIT 8;
            """
            top_sources = db_conn.execute_query(src_sql, tuple(params))

            # Daily trend
            trend_sql = f"""
                SELECT 
                    DATE_FORMAT(created_at, '%%Y-%%m-%%d') AS lead_date,
                    COUNT(*) AS count
                FROM enquiries
                {date_filter}
                GROUP BY lead_date
                ORDER BY lead_date ASC;
            """
            daily_trend = db_conn.execute_query(trend_sql, tuple(params))

        else:
            # PostgreSQL (Acolyte Living)
            date_filter = "WHERE 1=1"
            params = []
            if start_date and end_date:
                date_filter += ' AND "createdAt" >= %s AND "createdAt" <= %s'
                params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            elif days:
                date_filter += " AND \"createdAt\" >= NOW() - INTERVAL '%s days'"
                # Note: psycopg2 interval format
                pass

            if not (start_date and end_date) and days:
                total_sql = f'SELECT COUNT(*) AS total FROM leads WHERE "createdAt" >= NOW() - INTERVAL \'{days} days\';'
                total_row = db_conn.execute_one(total_sql)
            else:
                total_sql = f'SELECT COUNT(*) AS total FROM leads {date_filter};'
                total_row = db_conn.execute_one(total_sql, tuple(params))
            total_leads = int(total_row["total"]) if total_row else 0

            if not (start_date and end_date) and days:
                date_sub = f"\"createdAt\" >= NOW() - INTERVAL '{days} days'"
            elif start_date and end_date:
                date_sub = f"\"createdAt\" >= '{start_date} 00:00:00' AND \"createdAt\" <= '{end_date} 23:59:59'"
            else:
                date_sub = "1=1"

            # Endpoints parsed safely from notes
            ep_sql = f"""
                SELECT 
                    CASE 
                        WHEN notes LIKE '{{%%' THEN COALESCE(
                            NULLIF(notes::jsonb->'attribution'->>'form_page_path', ''),
                            NULLIF(notes::jsonb->'attribution'->>'landing_page', ''),
                            '/contact-us'
                        )
                        ELSE '/contact-us'
                    END AS endpoint_url,
                    COUNT(*) AS count
                FROM leads
                WHERE {date_sub}
                GROUP BY endpoint_url
                ORDER BY count DESC
                LIMIT 10;
            """
            try:
                raw_ep = db_conn.execute_query(ep_sql)
                top_endpoints = [
                    {"endpoint_url": (r["endpoint_url"] or "/contact-us").replace("https://acolyteliving.com", ""), "count": r["count"]}
                    for r in raw_ep
                ]
            except Exception as e:
                logger.error(f"Error fetching PG endpoints: {e}")
                top_endpoints = []

            src_sql = f"""
                SELECT 
                    COALESCE(NULLIF(source, ''), 'Direct / Unknown') AS source_name,
                    COUNT(*) AS count
                FROM leads
                WHERE {date_sub}
                GROUP BY source_name
                ORDER BY count DESC
                LIMIT 8;
            """
            try:
                top_sources = db_conn.execute_query(src_sql)
            except Exception:
                top_sources = []

            trend_sql = f"""
                SELECT 
                    TO_CHAR("createdAt", 'YYYY-MM-DD') AS lead_date,
                    COUNT(*) AS count
                FROM leads
                WHERE {date_sub}
                GROUP BY lead_date
                ORDER BY lead_date ASC;
            """
            try:
                daily_trend = db_conn.execute_query(trend_sql)
            except Exception:
                daily_trend = []

        return {
            "total_leads": total_leads,
            "top_endpoints": top_endpoints,
            "top_sources": top_sources,
            "daily_trend": daily_trend,
            "platform": platform
        }

    @classmethod
    def get_leads_list(
        cls,
        platform: str = "startupflora",
        page: int = 1,
        limit: int = 25,
        search: Optional[str] = None,
        endpoint: Optional[str] = None,
        source: Optional[str] = None,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch paginated leads list with detailed endpoint attribution and matching status."""
        db_conn = cls.get_db(platform)
        offset = max(0, (page - 1) * limit)

        if platform == "startupflora":
            where_clauses = ["1=1"]
            params: List[Any] = []

            if start_date and end_date:
                where_clauses.append("created_at >= %s AND created_at <= %s")
                params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            elif days:
                where_clauses.append("created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)")
                params.append(days)

            if search and search.strip():
                s = f"%{search.strip()}%"
                where_clauses.append("(full_name LIKE %s OR email LIKE %s OR phone_number LIKE %s OR endpoint LIKE %s OR message LIKE %s)")
                params.extend([s, s, s, s, s])

            if endpoint and endpoint.strip():
                where_clauses.append("endpoint = %s")
                params.append(endpoint.strip())

            if source and source.strip():
                where_clauses.append("source = %s")
                params.append(source.strip())

            where_str = " AND ".join(where_clauses)

            # Count total
            count_sql = f"SELECT COUNT(*) AS total FROM enquiries WHERE {where_str};"
            count_row = db_conn.execute_one(count_sql, tuple(params))
            total_records = int(count_row["total"]) if count_row else 0

            # Fetch rows
            fetch_sql = f"""
                SELECT 
                    id,
                    COALESCE(full_name, 'Anonymous') AS full_name,
                    email,
                    phone_number,
                    COALESCE(endpoint, '/') AS endpoint,
                    COALESCE(source, 'Direct') AS source,
                    subject,
                    company_name,
                    message,
                    created_at
                FROM enquiries
                WHERE {where_str}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s;
            """
            fetch_params = list(params) + [limit, offset]
            rows = db_conn.execute_query(fetch_sql, tuple(fetch_params))

            # Format rows
            leads = []
            for r in rows:
                c_at = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r["created_at"], datetime) else str(r["created_at"])
                leads.append({
                    "id": r["id"],
                    "full_name": r["full_name"],
                    "email": r["email"] or "N/A",
                    "phone_number": r["phone_number"] or "N/A",
                    "endpoint": r["endpoint"],
                    "source": r["source"],
                    "subject": r.get("subject") or "",
                    "company_name": r.get("company_name") or "",
                    "message": (r.get("message") or "")[:120],
                    "created_at": c_at,
                    "platform": "startupflora"
                })

        else:
            # PostgreSQL (Acolyte Living)
            where_clauses = ["1=1"]
            params = []

            if start_date and end_date:
                where_clauses.append('"createdAt" >= %s AND "createdAt" <= %s')
                params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            elif days:
                where_clauses.append(f'"createdAt" >= NOW() - INTERVAL \'{days} days\'')

            if search and search.strip():
                s = f"%{search.strip()}%"
                where_clauses.append('(name ILIKE %s OR email ILIKE %s OR phone ILIKE %s OR source ILIKE %s OR notes ILIKE %s)')
                params.extend([s, s, s, s, s])

            if source and source.strip():
                where_clauses.append("source = %s")
                params.append(source.strip())

            where_str = " AND ".join(where_clauses)

            count_sql = f'SELECT COUNT(*) AS total FROM leads WHERE {where_str};'
            count_row = db_conn.execute_one(count_sql, tuple(params))
            total_records = int(count_row["total"]) if count_row else 0

            fetch_sql = f"""
                SELECT 
                    id,
                    COALESCE(name, 'Anonymous') AS full_name,
                    email,
                    phone AS phone_number,
                    source,
                    status,
                    notes,
                    "createdAt" AS created_at
                FROM leads
                WHERE {where_str}
                ORDER BY "createdAt" DESC
                LIMIT %s OFFSET %s;
            """
            fetch_params = list(params) + [limit, offset]
            rows = db_conn.execute_query(fetch_sql, tuple(fetch_params))

            leads = []
            for r in rows:
                c_at = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r["created_at"], datetime) else str(r["created_at"])
                
                # Parse endpoint from notes attribution
                endpoint_val = "/contact-us"
                notes_obj = {}
                if r.get("notes"):
                    try:
                        notes_obj = json.loads(r["notes"]) if isinstance(r["notes"], str) else r["notes"]
                        attr = notes_obj.get("attribution", {})
                        endpoint_val = attr.get("form_page_path") or attr.get("landing_page") or attr.get("form_page_url") or endpoint_val
                        endpoint_val = endpoint_val.replace("https://acolyteliving.com", "")
                    except Exception:
                        pass

                leads.append({
                    "id": r["id"],
                    "full_name": r["full_name"],
                    "email": r["email"] or "N/A",
                    "phone_number": r["phone_number"] or "N/A",
                    "endpoint": endpoint_val,
                    "source": r.get("source") or "Direct",
                    "subject": r.get("status") or "New",
                    "company_name": "",
                    "message": json.dumps(notes_obj.get("attribution", {})) if notes_obj else "",
                    "created_at": c_at,
                    "platform": "living"
                })

        total_pages = max(1, (total_records + limit - 1) // limit)
        return {
            "leads": leads,
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "platform": platform
        }

    @classmethod
    def get_lead_endpoints(
        cls,
        platform: str = "startupflora",
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """Get distinct endpoints with counts for filter dropdown."""
        db_conn = cls.get_db(platform)
        if platform == "startupflora":
            sql = """
                SELECT 
                    endpoint,
                    COUNT(*) AS lead_count
                FROM enquiries
                WHERE endpoint IS NOT NULL AND endpoint != ''
                  AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY endpoint
                ORDER BY lead_count DESC
                LIMIT 50;
            """
            rows = db_conn.execute_query(sql, (days,))
            return [{"endpoint": r["endpoint"], "count": r["lead_count"]} for r in rows]
        else:
            sql = f"""
                SELECT 
                    CASE 
                        WHEN notes LIKE '{{%%' THEN COALESCE(
                            NULLIF(notes::jsonb->'attribution'->>'form_page_path', ''),
                            NULLIF(notes::jsonb->'attribution'->>'landing_page', ''),
                            '/contact-us'
                        )
                        ELSE '/contact-us'
                    END AS endpoint,
                    COUNT(*) AS lead_count
                FROM leads
                WHERE "createdAt" >= NOW() - INTERVAL '{days} days'
                GROUP BY endpoint
                ORDER BY lead_count DESC
                LIMIT 50;
            """
            try:
                rows = db_conn.execute_query(sql)
                return [{"endpoint": (r["endpoint"] or "/contact-us").replace("https://acolyteliving.com", ""), "count": r["lead_count"]} for r in rows]
            except Exception as e:
                logger.error(f"Error fetching PG endpoints list: {e}")
                return [{"endpoint": "/contact-us", "count": 1}]

    @classmethod
    def get_lead_sources(
        cls,
        platform: str = "startupflora",
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """Get distinct sources with counts for filter dropdown."""
        db_conn = cls.get_db(platform)
        if platform == "startupflora":
            sql = """
                SELECT 
                    source,
                    COUNT(*) AS count
                FROM enquiries
                WHERE source IS NOT NULL AND source != ''
                  AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY source
                ORDER BY count DESC
                LIMIT 30;
            """
            rows = db_conn.execute_query(sql, (days,))
            return [{"source": r["source"], "count": r["count"]} for r in rows]
        else:
            sql = f"""
                SELECT 
                    source,
                    COUNT(*) AS count
                FROM leads
                WHERE source IS NOT NULL AND source != ''
                  AND "createdAt" >= NOW() - INTERVAL '{days} days'
                GROUP BY source
                ORDER BY count DESC
                LIMIT 30;
            """
            try:
                rows = db_conn.execute_query(sql)
                return [{"source": r["source"], "count": r["count"]} for r in rows]
            except Exception:
                return []

    @classmethod
    def get_lead_journey_and_details(
        cls,
        lead_id: int,
        platform: str = "startupflora"
    ) -> Dict[str, Any]:
        """Fetch all details for a lead, match their session, and reconstruct the full chronological user journey."""
        db_conn = cls.get_db(platform)
        
        # 1. Fetch Lead Record
        lead_data: Optional[Dict[str, Any]] = None
        if platform == "startupflora":
            row = db_conn.execute_one("SELECT * FROM enquiries WHERE id = %s;", (lead_id,))
            if not row:
                raise ValueError(f"Lead #{lead_id} not found on platform {platform}")
            lead_data = {
                "id": row["id"],
                "full_name": row.get("full_name") or "Anonymous",
                "email": row.get("email") or "",
                "phone_number": row.get("phone_number") or "",
                "endpoint": row.get("endpoint") or "/",
                "source": row.get("source") or "Direct",
                "subject": row.get("subject") or "",
                "company_name": row.get("company_name") or "",
                "message": row.get("message") or "",
                "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(row.get("created_at"), datetime) else str(row.get("created_at")),
                "raw_created_at": row.get("created_at"),
                "branch": row.get("branch") or "",
                "file": row.get("file") or ""
            }
        else:
            # PostgreSQL
            row = db_conn.execute_one('SELECT * FROM leads WHERE id = %s;', (lead_id,))
            if not row:
                raise ValueError(f"Lead #{lead_id} not found on platform {platform}")
            
            notes_str = row.get("notes") or "{}"
            notes_obj = {}
            endpoint_val = "/contact-us"
            try:
                notes_obj = json.loads(notes_str) if isinstance(notes_str, str) else notes_str
                attr = notes_obj.get("attribution", {})
                endpoint_val = attr.get("form_page_path") or attr.get("landing_page") or attr.get("form_page_url") or endpoint_val
                endpoint_val = endpoint_val.replace("https://acolyteliving.com", "")
            except Exception:
                pass

            lead_data = {
                "id": row["id"],
                "full_name": row.get("name") or "Anonymous",
                "email": row.get("email") or "",
                "phone_number": row.get("phone") or "",
                "endpoint": endpoint_val,
                "source": row.get("source") or "Direct",
                "subject": row.get("status") or "New",
                "company_name": "",
                "message": notes_str if isinstance(notes_str, str) else json.dumps(notes_obj),
                "created_at": row["createdAt"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(row.get("createdAt"), datetime) else str(row.get("createdAt")),
                "raw_created_at": row.get("createdAt"),
                "notes_parsed": notes_obj,
                "nationality": row.get("nationality"),
                "location": row.get("location"),
                "moveInDate": str(row.get("moveInDate")) if row.get("moveInDate") else None,
                "duration": row.get("duration")
            }

        # 2. Match Session & User Journey
        matched_session_id = None
        matched_ip = None
        matched_ua = None
        match_strategy = "none"

        created_dt = lead_data["raw_created_at"]
        endpoint = lead_data["endpoint"]

        if platform == "startupflora":
            # Strategy A: Match by email or phone in tracking_users
            if lead_data["email"] or lead_data["phone_number"]:
                tu = db_conn.execute_one("""
                    SELECT ip_address, user_agent, user_uuid 
                    FROM tracking_users 
                    WHERE (email IS NOT NULL AND email != '' AND email = %s)
                       OR (phone IS NOT NULL AND phone != '' AND phone = %s)
                    LIMIT 1;
                """, (lead_data["email"], lead_data["phone_number"]))
                if tu:
                    matched_ip = tu.get("ip_address")
                    matched_ua = tu.get("user_agent")
                    match_strategy = "tracking_user_profile"

            # Strategy B: Match event closest in time on this endpoint
            if not matched_session_id and created_dt:
                near_event = db_conn.execute_one("""
                    SELECT session_id, ip_address, user_agent
                    FROM tracking_events
                    WHERE (page_url = %s OR page_url LIKE CONCAT('%%', %s, '%%'))
                      AND occurred_at BETWEEN DATE_SUB(%s, INTERVAL 30 MINUTE) AND DATE_ADD(%s, INTERVAL 30 MINUTE)
                    ORDER BY ABS(TIMESTAMPDIFF(SECOND, occurred_at, %s)) ASC
                    LIMIT 1;
                """, (endpoint, endpoint, created_dt, created_dt, created_dt))
                if near_event:
                    matched_session_id = near_event.get("session_id")
                    matched_ip = matched_ip or near_event.get("ip_address")
                    matched_ua = matched_ua or near_event.get("user_agent")
                    match_strategy = "endpoint_time_proximity"

            # Strategy C: Match event by IP if available
            if not matched_session_id and matched_ip and created_dt:
                ip_event = db_conn.execute_one("""
                    SELECT session_id, ip_address, user_agent
                    FROM tracking_events
                    WHERE ip_address = %s
                      AND occurred_at BETWEEN DATE_SUB(%s, INTERVAL 1 HOUR) AND DATE_ADD(%s, INTERVAL 1 HOUR)
                    ORDER BY ABS(TIMESTAMPDIFF(SECOND, occurred_at, %s)) ASC
                    LIMIT 1;
                """, (matched_ip, created_dt, created_dt, created_dt))
                if ip_event:
                    matched_session_id = ip_event.get("session_id")
                    match_strategy = "ip_proximity"

        else:
            # PostgreSQL matching
            # Strategy A: Match by email or phone in tracking_users
            if lead_data["email"] or lead_data["phone_number"]:
                tu = db_conn.execute_one("""
                    SELECT user_uuid, ip_address, user_agent, first_source 
                    FROM tracking_users 
                    WHERE (email IS NOT NULL AND LOWER(email) = LOWER(%s))
                       OR (phone IS NOT NULL AND phone = %s)
                    LIMIT 1;
                """, (lead_data["email"], lead_data["phone_number"]))
                if tu:
                    matched_ip = tu.get("ip_address")
                    matched_ua = tu.get("user_agent")
                    # Check if tracking_events has events for this user_uuid
                    ev_u = db_conn.execute_one("""
                        SELECT session_id FROM tracking_events WHERE tracking_user_uuid = %s ORDER BY occurred_at DESC LIMIT 1;
                    """, (tu["user_uuid"],))
                    if ev_u:
                        matched_session_id = ev_u.get("session_id")
                        match_strategy = "tracking_user_uuid"

            # Strategy B: Match event closest in time on this endpoint (accounting for UTC vs Local tz)
            if not matched_session_id and created_dt:
                clean_ep = endpoint.replace("https://acolyteliving.com", "")
                near_event = db_conn.execute_one("""
                    SELECT session_id, ip_address, user_agent
                    FROM tracking_events
                    WHERE (page_url = %s OR page_url LIKE %s)
                      AND occurred_at BETWEEN (%s::timestamp AT TIME ZONE 'UTC') - INTERVAL '30 minutes'
                                          AND (%s::timestamp AT TIME ZONE 'UTC') + INTERVAL '30 minutes'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (occurred_at - (%s::timestamp AT TIME ZONE 'UTC')))) ASC
                    LIMIT 1;
                """, (clean_ep, f"%{clean_ep}%", created_dt, created_dt, created_dt))
                if near_event:
                    matched_session_id = near_event.get("session_id")
                    matched_ip = matched_ip or near_event.get("ip_address")
                    matched_ua = matched_ua or near_event.get("user_agent")
                    match_strategy = "endpoint_time_proximity"

        # 3. Retrieve All Events in the Matched Session
        session_events: List[Dict[str, Any]] = []
        if matched_session_id:
            if platform == "startupflora":
                ev_rows = db_conn.execute_query("""
                    SELECT 
                        id,
                        event_name,
                        page_url,
                        referrer,
                        source_domain,
                        utm_source,
                        utm_medium,
                        utm_campaign,
                        utm_content,
                        ip_address,
                        user_agent,
                        event_data,
                        occurred_at
                    FROM tracking_events
                    WHERE session_id = %s
                    ORDER BY occurred_at ASC;
                """, (matched_session_id,))
            else:
                ev_rows = db_conn.execute_query("""
                    SELECT 
                        id,
                        event_name,
                        page_url,
                        referrer,
                        source_domain,
                        utm_source,
                        utm_medium,
                        utm_campaign,
                        utm_content,
                        ip_address,
                        user_agent,
                        event_data,
                        occurred_at
                    FROM tracking_events
                    WHERE session_id = %s
                    ORDER BY occurred_at ASC;
                """, (matched_session_id,))

            session_events = ev_rows

        # 4. Compute User Journey & Session Metrics
        journey_timeline: List[Dict[str, Any]] = []
        session_metrics: Dict[str, Any] = {
            "has_session": bool(matched_session_id),
            "session_id": matched_session_id or "Not directly captured",
            "match_strategy": match_strategy,
            "total_events_count": len(session_events),
            "total_session_time_seconds": 0,
            "total_session_time_formatted": "0s",
            "time_to_convert_seconds": 0,
            "time_to_convert_formatted": "0s",
            "unique_pages_visited": [],
            "landing_page": endpoint,
            "exit_page": endpoint,
            "conversion_step_index": -1
        }

        if session_events:
            first_event_time = session_events[0]["occurred_at"]
            last_event_time = session_events[-1]["occurred_at"]

            if isinstance(first_event_time, datetime) and isinstance(last_event_time, datetime):
                total_duration = max(0, int((last_event_time - first_event_time).total_seconds()))
                session_metrics["total_session_time_seconds"] = total_duration
                session_metrics["total_session_time_formatted"] = cls._format_duration(total_duration)

            pages_seq = []
            conversion_idx = -1

            for idx, ev in enumerate(session_events):
                p_url = ev.get("page_url") or "/"
                if p_url not in pages_seq:
                    pages_seq.append(p_url)

                ev_time = ev.get("occurred_at")
                offset_sec = 0
                if isinstance(ev_time, datetime) and isinstance(first_event_time, datetime):
                    offset_sec = max(0, int((ev_time - first_event_time).total_seconds()))

                ev_name = ev.get("event_name") or "event"
                is_conv = ev_name in ["lead_submitted", "form_submit", "enquiry_modal_submitted"] or "submit" in ev_name
                if is_conv and conversion_idx == -1:
                    conversion_idx = idx
                    session_metrics["time_to_convert_seconds"] = offset_sec
                    session_metrics["time_to_convert_formatted"] = cls._format_duration(offset_sec)

                # Parse event_data if string
                ev_data_parsed = ev.get("event_data")
                if isinstance(ev_data_parsed, str):
                    try:
                        ev_data_parsed = json.loads(ev_data_parsed)
                    except Exception:
                        pass

                journey_timeline.append({
                    "step": idx + 1,
                    "event_name": ev_name,
                    "page_url": p_url,
                    "occurred_at": ev_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ev_time, datetime) else str(ev_time),
                    "offset_seconds": offset_sec,
                    "offset_formatted": f"+{cls._format_duration(offset_sec)}" if offset_sec > 0 else "0s",
                    "referrer": ev.get("referrer"),
                    "source_domain": ev.get("source_domain"),
                    "utm_source": ev.get("utm_source"),
                    "utm_medium": ev.get("utm_medium"),
                    "utm_campaign": ev.get("utm_campaign"),
                    "is_conversion": is_conv,
                    "event_data": ev_data_parsed
                })

            session_metrics["unique_pages_visited"] = pages_seq
            session_metrics["landing_page"] = session_events[0].get("page_url") or endpoint
            session_metrics["exit_page"] = session_events[-1].get("page_url") or endpoint
            session_metrics["conversion_step_index"] = conversion_idx

            # Fallback time to convert if no explicit submit event recorded in session
            if session_metrics["time_to_convert_seconds"] == 0 and session_metrics["total_session_time_seconds"] > 0:
                session_metrics["time_to_convert_seconds"] = session_metrics["total_session_time_seconds"]
                session_metrics["time_to_convert_formatted"] = session_metrics["total_session_time_formatted"]

            # Fallback IP & UA from first event
            matched_ip = matched_ip or session_events[0].get("ip_address")
            matched_ua = matched_ua or session_events[0].get("user_agent")

        # 5. Retrieve IP Geo Location & Network Diagnostics
        ip_location_data: Dict[str, Any] = {
            "ip_address": matched_ip or "Unknown",
            "country": "Unknown",
            "city": "Unknown",
            "region": "Unknown",
            "isp": "Unknown",
            "is_proxy": False,
            "is_mobile": False
        }
        if matched_ip:
            loc_row = db_conn.execute_one("""
                SELECT 
                    country, city, region_name, isp, is_proxy, is_mobile
                FROM tracking_ip_locations
                WHERE ip_address = %s
                LIMIT 1;
            """, (matched_ip,))
            if loc_row:
                ip_location_data["country"] = loc_row.get("country") or "Unknown"
                ip_location_data["city"] = loc_row.get("city") or "Unknown"
                ip_location_data["region"] = loc_row.get("region_name") or "Unknown"
                ip_location_data["isp"] = loc_row.get("isp") or "Unknown"
                ip_location_data["is_proxy"] = bool(loc_row.get("is_proxy"))
                ip_location_data["is_mobile"] = bool(loc_row.get("is_mobile"))

        # 6. Parse User Agent for Device & Browser Info
        client_device_data = cls._parse_user_agent(matched_ua)
        client_device_data["user_agent_raw"] = matched_ua or "Unknown"

        return {
            "lead": lead_data,
            "session_metrics": session_metrics,
            "journey_timeline": journey_timeline,
            "ip_location": ip_location_data,
            "client_device": client_device_data,
            "platform": platform
        }

lead_service = LeadService
