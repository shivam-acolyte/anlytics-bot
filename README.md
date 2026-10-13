# TrackingBot - Analytics & AI BI Platform

A standalone business intelligence and conversational analytics web platform built with Python (FastAPI), PostgreSQL, Chart.js, and an AI Analytics Chatbot.

## Key Features

1. **📊 Reports & Visuals Dashboard (`/reports`)**:
   - **Daily Refresh Engine**: Auto-refreshes daily metrics and caches hourly/daily rollups.
   - **Global Filters**: Website / Domain selector, Date range (7d, 30d, 60d, 90d).
   - **24×7 Heatmap**: Day of week vs Hour of day matrix highlighting lowest dead zone and peak periods.
   - **Daily Trend Timeline**: Dual-axis line chart for active users and event volume.
   - **Top Visited Pages & Referrers**: Detailed tables and source breakdowns.
   - **Embedded On-Page Chart Bot**: Assistant banner allowing you to generate new dynamic visual charts on the fly.

2. **💬 Dedicated AI Analytics Chatbot (`/chat`)**:
   - Full conversational analyst capable of processing 640k+ tracking events.
   - Answers questions like *"When is user traffic lowest?"*, *"What are peak hours?"*, *"Show multi-website distribution"*.
   - Dual-engine: Attempts OpenAI GPT-4o, with intelligent built-in SQL analytical fallback if quota is unavailable.
   - SQL query transparency toggle and embedded chart visuals.

3. **⚙️ Database Tables & Schema Inspector (`/settings`)**:
   - View connected PostgreSQL database.
   - Browse tables, approximate row counts, and column data types.

## How to Run

```bash
cd trackingbot
python run.py
```

The application will start at **http://localhost:8080**.
