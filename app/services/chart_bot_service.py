import logging
from typing import Dict, Any, List, Optional
from app.database import db
from app.services.analytics_service import analytics_service

logger = logging.getLogger("trackingbot.chart_bot")

class ChartBotService:

    @classmethod
    def generate_chart(cls, prompt: str, site: Optional[str] = None, days: int = 30, platform: str = "living") -> Dict[str, Any]:
        """
        Parses natural language chart prompt and generates Chart.js configuration.
        """
        p = prompt.lower().strip()
        db_conn = analytics_service.get_db(platform)
        max_dt = analytics_service.get_max_date(platform)
        from datetime import timedelta
        cutoff = max_dt - timedelta(days=days)

        site_filter = ""
        params = [cutoff]
        if site and site.lower() != "all":
            site_filter = "AND source_domain = %s"
            params.append(site)

        # 1. Day comparison by hour (e.g. Sunday vs Wednesday or Monday vs Friday)
        if "sunday" in p or "compare day" in p or ("vs" in p and ("sun" in p or "mon" in p or "fri" in p or "wed" in p)):
            day1 = "Sunday"
            day2 = "Wednesday" if "wed" in p else ("Monday" if "mon" in p else "Friday")

            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        DAYNAME(occurred_at) AS day_name,
                        HOUR(occurred_at) AS h,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    WHERE occurred_at >= %s
                    AND DAYNAME(occurred_at) IN ('{day1}', '{day2}')
                    {site_filter}
                    GROUP BY day_name, h
                    ORDER BY h ASC;
                """
            else:
                sql = f"""
                    SELECT 
                        TO_CHAR(occurred_at AT TIME ZONE 'Asia/Kolkata', 'FMDay') AS day_name,
                        EXTRACT(HOUR FROM occurred_at AT TIME ZONE 'Asia/Kolkata')::int AS h,
                        COUNT(DISTINCT anonymous_id) AS users
                    FROM tracking_events
                    WHERE occurred_at >= %s
                    AND TO_CHAR(occurred_at AT TIME ZONE 'Asia/Kolkata', 'FMDay') IN ('{day1}', '{day2}')
                    {site_filter}
                    GROUP BY day_name, h
                    ORDER BY h ASC;
                """
            rows = db_conn.execute_query(sql, tuple(params))
            hours = [f"{h:02d}:00" for h in range(24)]
            d1_data = [0]*24
            d2_data = [0]*24

            for r in rows:
                day = r["day_name"].strip()
                h = int(r["h"])
                u = int(r["users"])
                if day == day1:
                    d1_data[h] = u
                elif day == day2:
                    d2_data[h] = u

            return {
                "title": f"Hourly Comparison: {day1} (Dead Day) vs {day2} (Peak Day)",
                "description": f"Displays hourly unique user counts comparing {day1} against {day2}.",
                "chart_type": "line",
                "labels": hours,
                "datasets": [
                    {
                        "label": f"{day1} Users",
                        "data": d1_data,
                        "borderColor": "#ef4444",
                        "backgroundColor": "rgba(239, 68, 68, 0.2)",
                        "fill": True,
                        "tension": 0.4
                    },
                    {
                        "label": f"{day2} Users",
                        "data": d2_data,
                        "borderColor": "#10b981",
                        "backgroundColor": "rgba(16, 185, 129, 0.2)",
                        "fill": True,
                        "tension": 0.4
                    }
                ]
            }

        # 2. Hourly breakdown of users / events
        if "hour" in p or "time" in p or "dead zone" in p or "low" in p:
            if platform == "startupflora":
                sql = f"""
                    SELECT 
                        HOUR(occurred_at) AS h,
                        COUNT(DISTINCT anonymous_id) AS users,
                        COUNT(*) AS events
                    FROM tracking_events
                    WHERE occurred_at >= %s
                    {site_filter}
                    GROUP BY h
                    ORDER BY h ASC;
                """
            else:
                sql = f"""
                    SELECT 
                        EXTRACT(HOUR FROM occurred_at AT TIME ZONE 'Asia/Kolkata')::int AS h,
                        COUNT(DISTINCT anonymous_id) AS users,
                        COUNT(*) AS events
                    FROM tracking_events
                    WHERE occurred_at >= %s
                    {site_filter}
                    GROUP BY h
                    ORDER BY h ASC;
                """
            rows = db_conn.execute_query(sql, tuple(params))
            hours = [f"{r['h']:02d}:00" for r in rows]
            users = [int(r["users"]) for r in rows]

            return {
                "title": "24-Hour Traffic Curve (IST)",
                "description": "Visualizing the 24-hour cycle showing the morning dead zone (04:00 - 10:00 IST) and evening peak.",
                "chart_type": "bar",
                "labels": hours,
                "datasets": [{
                    "label": "Unique Users",
                    "data": users,
                    "backgroundColor": [
                        "#ef4444" if 4 <= int(r['h']) <= 9 else ("#10b981" if 15 <= int(r['h']) <= 19 else "#6366f1")
                        for r in rows
                    ]
                }]
            }

        # 3. Country / Geographic Distribution
        if "country" in p or "geo" in p or "location" in p:
            geo = analytics_service.get_geo_and_referrers(site=site, days=days, platform=platform)
            countries = geo["countries"][:7]

            return {
                "title": "Geographic Traffic Distribution",
                "description": "Distribution of visitor traffic across top countries.",
                "chart_type": "doughnut",
                "labels": [c["name"] for c in countries],
                "datasets": [{
                    "label": "Visitors",
                    "data": [c["users"] for c in countries],
                    "backgroundColor": ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#64748b"]
                }]
            }

        # 4. Top Events / Conversion Funnel
        if "event" in p or "funnel" in p or "action" in p:
            events = analytics_service.get_events_breakdown(site=site, days=days, platform=platform)[:8]
            return {
                "title": "Top Tracking Events Volume",
                "description": "Volume of tracked interactions across the platform.",
                "chart_type": "bar",
                "labels": [e["event_name"] for e in events],
                "datasets": [{
                    "label": "Total Events",
                    "data": [e["count"] for e in events],
                    "backgroundColor": "#8b5cf6"
                }]
            }

        # 5. Default: Daily Trend Timeline
        trends = analytics_service.get_daily_trends(site=site, days=days, platform=platform)
        return {
            "title": f"Custom Daily Activity Trend ({days} Days)",
            "description": "Timeline displaying active users and total events day by day.",
            "chart_type": "line",
            "labels": [t["date"][5:] for t in trends],
            "datasets": [
                {
                    "label": "Daily Unique Users",
                    "data": [t["users"] for t in trends],
                    "borderColor": "#6366f1",
                    "backgroundColor": "rgba(99, 102, 241, 0.15)",
                    "fill": True,
                    "tension": 0.3
                },
                {
                    "label": "Total Sessions",
                    "data": [t["sessions"] for t in trends],
                    "borderColor": "#06b6d4",
                    "backgroundColor": "rgba(6, 182, 212, 0.15)",
                    "fill": True,
                    "tension": 0.3
                }
            ]
        }

chart_bot_service = ChartBotService
