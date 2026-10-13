"""
TrackingBot Streamlit Analytics Platform
Standalone, multi-database, high-performance BI & Analytics application.
Supports Streamlit Community Cloud and direct connections to PostgreSQL (Acolyte Living) & MySQL (StartupFlora).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from typing import Dict, Any, List, Optional

# Set Page Config (Must be the first Streamlit call)
st.set_page_config(
    page_title="TrackingBot Analytics | Multi-Database Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import Services & Databases
from app.config import config
from app.database import db
from app.mysql_database import db_mysql
from app.services.analytics_service import analytics_service
from app.services.ai_chat_service import ai_chat_service

# ==============================================================================
# Custom CSS for Midnight Navy / Cyan Dark Theme
# ==============================================================================
st.markdown("""
<style>
    /* Global Styles & Color Palette */
    :root {
        --bg-main: #0b0f19;
        --bg-card: #111827;
        --border-color: rgba(56, 189, 248, 0.15);
        --text-main: #f1f5f9;
        --text-muted: #94a3b8;
        --cyan-accent: #38bdf8;
        --indigo-accent: #6366f1;
        --emerald-accent: #10b981;
        --pink-accent: #ec4899;
        --amber-accent: #f59e0b;
    }

    /* Streamlit Main Container Tweaks */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }

    /* KPI Card Style */
    .kpi-card {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.1rem 1.25rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        transition: all 0.2s ease-in-out;
        position: relative;
        overflow: hidden;
        margin-bottom: 0.75rem;
    }
    .kpi-card:hover {
        border-color: rgba(56, 189, 248, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(56, 189, 248, 0.12);
    }
    .kpi-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 0.35rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kpi-value {
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    .kpi-subtext {
        font-size: 0.76rem;
        color: #64748b;
        margin-top: 0.35rem;
    }

    /* Status Pill */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background-color: #34d399;
        box-shadow: 0 0 8px #34d399;
    }

    /* Property Identity Banner */
    .prop-banner {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
    }

    /* Custom Scrollbars */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0b0f19;
    }
    ::-webkit-scrollbar-thumb {
        background: #1e293b;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #334155;
    }
</style>
""", unsafe_allow_html=True)

# Plotly Common Dark Layout
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94a3b8", family="Inter, system-ui, sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
    hovermode="x unified"
)

# ==============================================================================
# Cached Data Fetchers
# ==============================================================================
@st.cache_data(ttl=60)
def fetch_platforms_status():
    return analytics_service.get_platforms_status()

@st.cache_data(ttl=60)
def fetch_websites(platform: str):
    return analytics_service.get_websites(platform=platform)

@st.cache_data(ttl=60)
def fetch_utms(platform: str, days: int):
    return analytics_service.get_utms(platform=platform, days=days)

@st.cache_data(ttl=60)
def fetch_overview_kpis(platform: str, site: Optional[str], days: int, start_date: Optional[str], end_date: Optional[str]):
    return analytics_service.get_kpis(site=site, days=days, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_daily_trends(platform: str, site: Optional[str], days: int, start_date: Optional[str], end_date: Optional[str]):
    return analytics_service.get_daily_trends(site=site, days=days, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_heatmap(platform: str, site: Optional[str], days: int, start_date: Optional[str], end_date: Optional[str]):
    return analytics_service.get_hourly_heatmap(site=site, days=days, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_top_pages(platform: str, site: Optional[str], days: int, limit: int = 15, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return analytics_service.get_top_pages(site=site, days=days, limit=limit, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_geo_and_referrers(platform: str, site: Optional[str], days: int, start_date: Optional[str], end_date: Optional[str]):
    return analytics_service.get_geo_and_referrers(site=site, days=days, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_page_deep_dive(page_url: str, platform: str, days: int, site: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return analytics_service.get_page_deep_dive(page_url=page_url, site=site, days=days, platform=platform, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=60)
def fetch_granular_timeline(granularity: str, platform: str, days: int, site: Optional[str] = None, page_url: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return analytics_service.get_granular_analysis(granularity=granularity, site=site, days=days, page_url=page_url, platform=platform, start_date=start_date, end_date=end_date)

# ==============================================================================
# Sidebar & Global Filter State
# ==============================================================================
with st.sidebar:
    st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:1.25rem;">
            <div style="background:linear-gradient(135deg, #38bdf8 0%, #6366f1 100%);padding:8px 12px;border-radius:10px;font-size:1.3rem;">⚡</div>
            <div>
                <h2 style="margin:0;font-size:1.25rem;font-weight:700;color:#f1f5f9;">TrackingBot</h2>
                <p style="margin:0;font-size:0.75rem;color:#38bdf8;font-weight:600;">MULTI-DATABASE BI</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 1. Platform Selector
    platform_option = st.selectbox(
        "🏢 Database Platform",
        options=["living", "startupflora"],
        format_func=lambda x: "🏢 Acolyte Living (PostgreSQL)" if x == "living" else "🌸 StartupFlora (MySQL)",
        index=0,
        help="Select the database instance to query analytics from."
    )

    # 2. Page Navigation
    page_selection = st.radio(
        "📌 Navigation View",
        options=[
            "📊 Overview Dashboard",
            "🔍 Page Deep Dive & Recursive Actions",
            "⚡ Event Explorer & Timeline",
            "💬 AI Analytics Assistant"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("### 📅 Date Range Filter")

    # Range presets
    preset_choice = st.selectbox(
        "Preset Range",
        options=["7 Days", "30 Days", "60 Days", "90 Days", "Custom Range"],
        index=1
    )

    days_map = {"7 Days": 7, "30 Days": 30, "60 Days": 60, "90 Days": 90, "Custom Range": 30}
    selected_days = days_map[preset_choice]

    start_date_str = None
    end_date_str = None

    if preset_choice == "Custom Range":
        c_from, c_to = st.columns(2)
        with c_from:
            d_from = st.date_input("From", value=datetime.now() - timedelta(days=30))
        with c_to:
            d_to = st.date_input("To", value=datetime.now())
        start_date_str = d_from.strftime("%Y-%m-%d")
        end_date_str = d_to.strftime("%Y-%m-%d")

    # Optional Domain Filter
    try:
        websites_list = fetch_websites(platform_option)
        site_options = ["All Domains"] + [w["website"] for w in websites_list if w.get("website")]
        selected_site_label = st.selectbox("🌐 Domain / Website", options=site_options, index=0)
        selected_site = None if selected_site_label == "All Domains" else selected_site_label
    except Exception:
        selected_site = None

    st.markdown("---")

    # Refresh Button
    if st.button("🔄 Refresh Data Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Connection Status Widget
    try:
        platforms_meta = fetch_platforms_status()
        current_p = next((p for p in platforms_meta["platforms"] if p["id"] == platform_option), None)
        if current_p and current_p["health"]["status"] == "connected":
            st.markdown(f"""
                <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:8px;padding:10px;margin-top:10px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                        <span style="font-size:0.75rem;font-weight:700;color:#34d399;">● CONNECTED</span>
                        <span style="font-size:0.7rem;color:#94a3b8;">{current_p['type']}</span>
                    </div>
                    <div style="font-size:0.78rem;color:#f1f5f9;margin-top:4px;font-weight:600;">
                        {current_p['health'].get('database', '')}
                    </div>
                    <div style="font-size:0.7rem;color:#64748b;">
                        Host: {current_p['health'].get('host', '')}:{current_p['health'].get('port', '')}
                    </div>
                    <div style="font-size:0.7rem;color:#38bdf8;margin-top:4px;">
                        Total Events: {current_p['stats'].get('events', 0):,}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.error("Database connection issue. Check credentials in secrets.")
    except Exception as e:
        st.caption(f"Status check note: {e}")

# ==============================================================================
# Helper to Render KPI Card
# ==============================================================================
def render_kpi_card(title: str, value: Any, subtext: str, icon: str, color: str = "#38bdf8"):
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">
                <span>{title}</span>
                <span style="font-size:1.1rem;">{icon}</span>
            </div>
            <div class="kpi-value" style="color: {color};">{value}</div>
            <div class="kpi-subtext">{subtext}</div>
        </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# PAGE 1: 📊 Overview Dashboard
# ==============================================================================
if page_selection == "📊 Overview Dashboard":
    st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:12px;">
            <div>
                <h1 style="margin:0;font-size:2rem;font-weight:800;color:#f1f5f9;">Overview Analytics</h1>
                <p style="margin:0;color:#94a3b8;font-size:0.92rem;">Cross-platform traffic, event volume, and interactive behavior trends.</p>
            </div>
            <div class="status-pill">
                <span class="status-dot"></span> Live Analytics Engine
            </div>
        </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading Overview KPIs & Metrics..."):
        kpi_data = fetch_overview_kpis(
            platform=platform_option,
            site=selected_site,
            days=selected_days,
            start_date=start_date_str,
            end_date=end_date_str
        )
        trends_data = fetch_daily_trends(
            platform=platform_option,
            site=selected_site,
            days=selected_days,
            start_date=start_date_str,
            end_date=end_date_str
        )

    # 6 High-Density KPI Cards
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        render_kpi_card("Total Events", f"{kpi_data.get('total_events', 0):,}", "Recorded tracking events", "⚡", "#38bdf8")
    with k2:
        render_kpi_card("Unique Visitors", f"{kpi_data.get('unique_users', 0):,}", "Distinct anonymous users", "👥", "#818cf8")
    with k3:
        render_kpi_card("Total Sessions", f"{kpi_data.get('total_sessions', 0):,}", "Active user sessions", "🔄", "#34d399")
    with k4:
        render_kpi_card("Lowest Hour", kpi_data.get('lowest_hour_slot', '--'), f"{kpi_data.get('lowest_hour_users', 0)} users (dead zone)", "🌙", "#f87171")
    with k5:
        render_kpi_card("Quiet Day", kpi_data.get('lowest_day', '--'), f"{kpi_data.get('lowest_day_users', 0)} users minimum", "📅", "#fbbf24")
    with k6:
        render_kpi_card("Peak Window", kpi_data.get('peak_window', '12:00 - 20:00'), "Highest user traffic", "🔥", "#f472b6")

    st.markdown("<br>", unsafe_allow_html=True)

    # Interactive Daily Trends Chart (Plotly Dual-Axis)
    if trends_data:
        df_trends = pd.DataFrame(trends_data)
        fig_trends = go.Figure()

        # Bar chart for Events
        fig_trends.add_trace(go.Bar(
            x=df_trends["date"],
            y=df_trends["events"],
            name="Total Events",
            marker=dict(color="rgba(56, 189, 248, 0.45)", line=dict(color="#38bdf8", width=1.5)),
            yaxis="y1"
        ))

        # Line chart for Unique Users
        fig_trends.add_trace(go.Scatter(
            x=df_trends["date"],
            y=df_trends["users"],
            name="Unique Users",
            mode="lines+markers",
            line=dict(color="#ec4899", width=3, shape="spline"),
            marker=dict(size=6, color="#ec4899"),
            yaxis="y2"
        ))

        fig_trends.update_layout(
            **PLOTLY_DARK_LAYOUT,
            title="📈 Daily Volume Trends (Events & Unique Visitors)",
            height=360,
            yaxis=dict(title="Event Volume", gridcolor="rgba(255,255,255,0.05)"),
            yaxis2=dict(title="Unique Users", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_trends, use_container_width=True)

    # Heatmap Section & Top Pages Table
    col_heat, col_pages = st.columns([1.1, 0.9])

    with col_heat:
        st.markdown("#### 🕒 24-Hour Activity Heatmap")
        heatmap_data = fetch_heatmap(
            platform=platform_option,
            site=selected_site,
            days=selected_days,
            start_date=start_date_str,
            end_date=end_date_str
        )
        if heatmap_data and "users_matrix" in heatmap_data:
            days_order = heatmap_data["days"]
            hours = heatmap_data["hours"]
            z_vals = [heatmap_data["users_matrix"][d] for d in days_order]

            fig_hm = go.Figure(data=go.Heatmap(
                z=z_vals,
                x=hours,
                y=days_order,
                colorscale="Viridis",
                colorbar=dict(title="Users", thickness=12)
            ))
            fig_hm.update_layout(
                **PLOTLY_DARK_LAYOUT,
                height=320,
                xaxis=dict(tickangle=-45)
            )
            st.plotly_chart(fig_hm, use_container_width=True)

    with col_pages:
        st.markdown("#### 📄 Top Visited Pages")
        top_pages = fetch_top_pages(
            platform=platform_option,
            site=selected_site,
            days=selected_days,
            limit=8,
            start_date=start_date_str,
            end_date=end_date_str
        )
        if top_pages:
            df_top = pd.DataFrame(top_pages)
            df_top.columns = ["Page URL", "Total Views", "Unique Users"]
            st.dataframe(
                df_top,
                use_container_width=True,
                height=310,
                hide_index=True
            )

    # Geo & Referrer Breakdown
    geo_data = fetch_geo_and_referrers(
        platform=platform_option,
        site=selected_site,
        days=selected_days,
        start_date=start_date_str,
        end_date=end_date_str
    )
    c_geo, c_ref = st.columns(2)
    with c_geo:
        st.markdown("#### 🌍 Geographic Distribution")
        if geo_data.get("countries"):
            df_geo = pd.DataFrame(geo_data["countries"][:6])
            fig_geo = px.bar(
                df_geo, x="name", y="count", color="count",
                labels={"name": "Country", "count": "Events"},
                color_continuous_scale="Tealgrn"
            )
            fig_geo.update_layout(**PLOTLY_DARK_LAYOUT, height=260, coloraxis_showscale=False)
            st.plotly_chart(fig_geo, use_container_width=True)
    with c_ref:
        st.markdown("#### 🔗 Top Referrer Sources")
        if geo_data.get("referrers"):
            df_ref = pd.DataFrame(geo_data["referrers"][:6])
            fig_ref = px.pie(
                df_ref, names="source", values="count",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_ref.update_layout(**PLOTLY_DARK_LAYOUT, height=260)
            st.plotly_chart(fig_ref, use_container_width=True)

# ==============================================================================
# PAGE 2: 🔍 Page Deep Dive & Recursive Actions (Core Request)
# ==============================================================================
elif page_selection == "🔍 Page Deep Dive & Recursive Actions":
    st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:12px;">
            <div>
                <h1 style="margin:0;font-size:2rem;font-weight:800;color:#f1f5f9;">Page Deep Dive & Recursive Actions</h1>
                <p style="margin:0;color:#94a3b8;font-size:0.92rem;">Granular URL inspection, domain click attribution, and multi-level actions hierarchy.</p>
            </div>
            <div class="status-pill" style="background:rgba(236,72,153,0.12);color:#f472b6;border-color:rgba(236,72,153,0.3);">
                <span>🎯</span> 360° Recursive Suite
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Searchable URL Selectbox & Custom URL Input
    with st.container():
        st.markdown("##### 🔍 Target Page URL Selector")
        c_url_select, c_url_custom = st.columns([1.2, 0.8])

        # Fetch top pages for the dropdown
        with st.spinner("Loading tracked pages..."):
            top_p_list = fetch_top_pages(
                platform=platform_option,
                site=selected_site,
                days=selected_days,
                limit=30,
                start_date=start_date_str,
                end_date=end_date_str
            )
            popular_urls = [p["url"] for p in top_p_list] if top_p_list else []
            # Include default property url if living
            if platform_option == "living" and "/properties/uk/london/apartments-13912" not in popular_urls:
                popular_urls.insert(0, "/properties/uk/london/apartments-13912")

        with c_url_select:
            selected_dropdown_url = st.selectbox(
                "Select from Most Visited Pages",
                options=popular_urls if popular_urls else ["/"],
                index=0
            )

        with c_url_custom:
            custom_url_input = st.text_input(
                "Or Type / Paste Custom Page URL",
                value="",
                placeholder="e.g. /properties/uk/london/apartments-13912"
            )

        active_target_url = custom_url_input.strip() if custom_url_input.strip() else selected_dropdown_url

    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch Deep Dive Data
    with st.spinner(f"Analyzing {active_target_url}..."):
        dive = fetch_page_deep_dive(
            page_url=active_target_url,
            platform=platform_option,
            days=selected_days,
            site=selected_site,
            start_date=start_date_str,
            end_date=end_date_str
        )

    kpis = dive.get("kpis", {})

    # Display Property Header if it is a property URL
    if "apartments-13912" in active_target_url or "properties" in active_target_url:
        st.markdown(f"""
            <div class="prop-banner">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:space-between;">
                    <div>
                        <span style="font-size:0.75rem;font-weight:700;color:#38bdf8;text-transform:uppercase;letter-spacing:0.05em;">ACCOMMODATION DEEP DIVE</span>
                        <h2 style="margin:2px 0 6px 0;font-size:1.45rem;color:#f1f5f9;font-weight:700;">iQ Bankside, London SE1 0NR</h2>
                        <div style="display:flex;gap:16px;color:#94a3b8;font-size:0.85rem;flex-wrap:wrap;">
                            <span>📍 <strong>City:</strong> London</span>
                            <span>🏢 <strong>Supplier:</strong> iQ Student Accommodation</span>
                            <span>💰 <strong>From:</strong> £499/week</span>
                            <span>🆔 <strong>Property ID:</strong> 13912</span>
                        </div>
                    </div>
                    <div>
                        <code style="background:rgba(0,0,0,0.4);color:#38bdf8;padding:6px 12px;border-radius:6px;font-size:0.85rem;">{active_target_url}</code>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # 8 KPI Metrics Cards Grid
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Total Pageviews", f"{kpis.get('total_views', 0):,}", "Page hits logged on this URL", "👁️", "#818cf8")
    with col2:
        render_kpi_card("Total Clicks", f"{kpis.get('total_clicks', 0):,}", "Buttons & CTAs clicked", "🖱️", "#f472b6")
    with col3:
        render_kpi_card("Click-Through Rate", f"{kpis.get('ctr', 0.0)}%", "Total clicks ÷ Total pageviews", "🎯", "#c084fc")
    with col4:
        render_kpi_card("Total Actions", f"{kpis.get('total_actions', 0):,}", "Non-passive user interactions", "⚡", "#38bdf8")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card("Unique Visitors", f"{kpis.get('unique_users', 0):,}", "Distinct anonymous users", "👥", "#60a5fa")
    with col6:
        render_kpi_card("Clicking Users", f"{kpis.get('clicking_users', 0):,}", "Users who performed clicks", "👆", "#34d399")
    with col7:
        render_kpi_card("Active Domains", f"{kpis.get('distinct_domains', 0):,}", "Domains sending traffic/clicks", "🌐", "#fbbf24")
    with col8:
        render_kpi_card("Peak Traffic Slot", kpis.get("peak_hour", "--"), "Highest activity period", "⏰", "#fde047")

    st.markdown("<br>", unsafe_allow_html=True)

    # Domain Click Breakdown Section
    st.markdown("### 🌐 Domain Breakdown on Clicks & Buttons")
    domain_breakdown = dive.get("domain_clicks_breakdown", [])

    if domain_breakdown:
        d_col1, d_col2 = st.columns([1, 1.2])
        with d_col1:
            df_dom = pd.DataFrame(domain_breakdown)
            fig_dom = px.pie(
                df_dom,
                names="domain",
                values="clicks",
                hole=0.55,
                title="Clicks Share by Domain",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_dom.update_layout(**PLOTLY_DARK_LAYOUT, height=290)
            st.plotly_chart(fig_dom, use_container_width=True)

        with d_col2:
            st.markdown("#### Domain Attribution Table")
            table_rows = []
            for d in domain_breakdown:
                top_b_str = ", ".join(f"{b['button']} ({b['count']})" for b in d.get("top_buttons", [])) or "None"
                table_rows.append({
                    "Domain": d["domain"],
                    "Clicks": d["clicks"],
                    "Clicking Users": d["users"],
                    "Share %": f"{d['share_pct']}%",
                    "Top CTAs Clicked": top_b_str
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, height=270, hide_index=True)
    else:
        st.info("ℹ️ No button/CTA clicks recorded on this page for the selected time window. Pageviews and passive interactions are captured below.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Recursive Actions, Buttons & Things Inspector
    st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
            <div>
                <h3 style="margin:0;font-size:1.35rem;color:#f1f5f9;">🌳 Recursive Actions, Buttons & Things Inspector</h3>
                <p style="margin:0;color:#94a3b8;font-size:0.85rem;">Multi-level tree: <strong>Event Type ➔ Button / CTA ➔ Domain ➔ Things Contained & Payloads</strong>.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    rec_tree = dive.get("recursive_actions", {})
    flat_actions = dive.get("flat_actions", [])

    tab_tree, tab_flat, tab_json = st.tabs(["🌳 Hierarchical Tree View", "📋 Flat Action Table", "📦 Raw JSON Payloads"])

    with tab_tree:
        if rec_tree:
            for ev_name, ev_info in rec_tree.items():
                with st.expander(f"🔹 Event Category: **{ev_name}** — ({ev_info['total_count']} total triggers, {ev_info['unique_users']} unique users)", expanded=True):
                    buttons = ev_info.get("buttons", {})
                    for btn_name, btn_info in buttons.items():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;🎯 **Button / Action:** `{btn_name}` — *{btn_info['total_count']} clicks ({btn_info['unique_users']} users)*")
                        domains = btn_info.get("domains", {})
                        for dom_name, dom_info in domains.items():
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;🌐 **Domain:** `{dom_name}` (*{dom_info['total_count']} events*)")
                            sample_things = dom_info.get("sample_things", {})
                            if sample_things:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;📦 **Things Contained:**")
                                st.json(sample_things)
        else:
            st.info("No interactive action events logged on this URL in this date window.")

    with tab_flat:
        if flat_actions:
            search_query = st.text_input("Filter actions table:", placeholder="Search by button, domain, event...")
            df_actions = pd.DataFrame(flat_actions)
            if search_query:
                mask = df_actions.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)
                df_actions = df_actions[mask]

            display_cols = ["event_name", "button_name", "domain", "count", "users", "things_summary", "latest_at"]
            st.dataframe(
                df_actions[display_cols],
                column_config={
                    "event_name": "Event Type",
                    "button_name": "CTA / Button",
                    "domain": "Domain",
                    "count": "Triggers",
                    "users": "Users",
                    "things_summary": "Payload Summary",
                    "latest_at": "Last Recorded"
                },
                use_container_width=True,
                height=350,
                hide_index=True
            )
        else:
            st.info("No flat action records found.")

    with tab_json:
        if flat_actions:
            selected_act = st.selectbox(
                "Select action payload to inspect:",
                options=range(len(flat_actions)),
                format_func=lambda i: f"#{i+1}: {flat_actions[i]['event_name']} | {flat_actions[i]['button_name']} ({flat_actions[i]['domain']})"
            )
            st.json(flat_actions[selected_act]["raw_payload"])
        else:
            st.info("No action payloads available.")

    # Page Traffic Curves
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📈 Page Specific Traffic Curves & Audience")
    curves = dive.get("traffic_curves", {})
    daily_p_trends = curves.get("daily_trends", [])
    hourly_p = curves.get("hourly", {})

    c_ptrend, c_phour = st.columns(2)
    with c_ptrend:
        if daily_p_trends:
            df_pt = pd.DataFrame(daily_p_trends)
            fig_pt = px.line(
                df_pt, x="date", y="views",
                markers=True,
                title="Daily Page Views Trend",
                color_discrete_sequence=["#38bdf8"]
            )
            fig_pt.update_layout(**PLOTLY_DARK_LAYOUT, height=280)
            st.plotly_chart(fig_pt, use_container_width=True)

    with c_phour:
        if hourly_p and "labels" in hourly_p:
            fig_ph = px.bar(
                x=hourly_p["labels"],
                y=hourly_p["views"],
                labels={"x": "Hour Slot", "y": "Views"},
                title="24-Hour Distribution (Hourly)",
                color_discrete_sequence=["#6366f1"]
            )
            fig_ph.update_layout(**PLOTLY_DARK_LAYOUT, height=280)
            st.plotly_chart(fig_ph, use_container_width=True)

# ==============================================================================
# PAGE 3: ⚡ Event Explorer & Granular Timeline
# ==============================================================================
elif page_selection == "⚡ Event Explorer & Timeline":
    st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:12px;">
            <div>
                <h1 style="margin:0;font-size:2rem;font-weight:800;color:#f1f5f9;">Event Explorer & Granular Timeline</h1>
                <p style="margin:0;color:#94a3b8;font-size:0.92rem;">Deep time-slot dissection (15-min, 30-min, hourly) & raw event stream.</p>
            </div>
            <div class="status-pill" style="background:rgba(56,189,248,0.12);color:#38bdf8;border-color:rgba(56,189,248,0.3);">
                <span>⚡</span> Time-Series Engine
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Granularity Switcher
    gran_col1, gran_col2 = st.columns([1, 3])
    with gran_col1:
        selected_gran = st.selectbox(
            "Time Granularity",
            options=["hour", "30min", "15min", "minute", "day"],
            format_func=lambda x: {"hour": "🕒 Hourly (24 Slots)", "30min": "⏱️ 30-Minute Windows", "15min": "⚡ 15-Minute Windows", "minute": "📊 Minute-by-Minute", "day": "📅 Daily Breakdown"}[x],
            index=0
        )

    with st.spinner("Analyzing granular time dimensions..."):
        gran_data = fetch_granular_timeline(
            granularity=selected_gran,
            platform=platform_option,
            days=selected_days,
            site=selected_site,
            start_date=start_date_str,
            end_date=end_date_str
        )

    if gran_data and "labels" in gran_data:
        df_gran = pd.DataFrame({
            "Time Slot": gran_data["labels"],
            "Events": gran_data["events"],
            "Users": gran_data["users"]
        })

        fig_gran = go.Figure()
        fig_gran.add_trace(go.Bar(
            x=df_gran["Time Slot"],
            y=df_gran["Events"],
            name="Events Volume",
            marker=dict(color="rgba(99, 102, 241, 0.6)", line=dict(color="#6366f1", width=1))
        ))
        fig_gran.add_trace(go.Scatter(
            x=df_gran["Time Slot"],
            y=df_gran["Users"],
            name="Unique Users",
            mode="lines+markers",
            line=dict(color="#38bdf8", width=2.5)
        ))
        fig_gran.update_layout(
            **PLOTLY_DARK_LAYOUT,
            title=gran_data.get("title", "Granular Timeline"),
            height=340
        )
        st.plotly_chart(fig_gran, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 Raw Event Stream & Payload Inspection")

    # Fetch recent raw events
    db_conn = analytics_service.get_db(platform_option)
    try:
        raw_events_sql = """
            SELECT 
                occurred_at,
                event_name,
                page_url,
                COALESCE(NULLIF(source_domain, ''), 'direct') AS source_domain,
                anonymous_id,
                session_id,
                country,
                event_data
            FROM tracking_events
            ORDER BY occurred_at DESC
            LIMIT 100;
        """
        raw_rows = db_conn.execute_query(raw_events_sql)
        if raw_rows:
            df_raw = pd.DataFrame(raw_rows)
            st.dataframe(
                df_raw[["occurred_at", "event_name", "page_url", "source_domain", "country", "anonymous_id"]],
                use_container_width=True,
                height=380,
                hide_index=True
            )
            with st.expander("🔍 Inspect Full Event Payload by Index"):
                inspect_idx = st.number_input("Event Row Index", min_value=0, max_value=len(raw_rows)-1, value=0)
                st.write("**Event Details:**", raw_rows[inspect_idx]["event_name"], "|", raw_rows[inspect_idx]["page_url"])
                st.json(raw_rows[inspect_idx]["event_data"] or {})
    except Exception as e:
        st.error(f"Error streaming events: {e}")

# ==============================================================================
# PAGE 4: 💬 AI Analytics Assistant
# ==============================================================================
elif page_selection == "💬 AI Analytics Assistant":
    st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:12px;">
            <div>
                <h1 style="margin:0;font-size:2rem;font-weight:800;color:#f1f5f9;">AI Analytics Assistant</h1>
                <p style="margin:0;color:#94a3b8;font-size:0.92rem;">Natural Language SQL & Data Intelligence powered by OpenAI GPT-4o-mini & Built-In Analytical Engine.</p>
            </div>
            <div class="status-pill" style="background:rgba(99,102,241,0.12);color:#818cf8;border-color:rgba(99,102,241,0.3);">
                <span>🤖</span> GPT-4o-mini + SQL Engine
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Initialize Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"Hello! I am your **TrackingBot AI Assistant**. I have direct access to your **{'PostgreSQL' if platform_option == 'living' else 'MySQL'}** analytics warehouse. You can ask me questions about user dead zones, peak hours, conversion rates, or specific property pages like `/properties/uk/london/apartments-13912`."
            }
        ]

    # Quick Prompt Suggestion Pills
    st.markdown("##### ⚡ Quick Analysis Prompts")
    q_col1, q_col2, q_col3 = st.columns(3)
    preset_clicked = None
    with q_col1:
        if st.button("📉 Lowest user traffic dead zones?", use_container_width=True):
            preset_clicked = "Which time period has the lowest user traffic?"
        if st.button("🏢 Give 7 days report for apartments-13912", use_container_width=True):
            preset_clicked = "properties/uk/london/apartments-13912 give last 7 days report of this property"
    with q_col2:
        if st.button("🔥 What are our peak active hours?", use_container_width=True):
            preset_clicked = "What are our peak active hours?"
        if st.button("📄 What are the top visited pages?", use_container_width=True):
            preset_clicked = "What are the top 5 visited pages?"
    with q_col3:
        if st.button("🌐 Multi-website traffic distribution", use_container_width=True):
            preset_clicked = "Show multi-website traffic distribution"
        if st.button("🎯 Breakdown conversion events (clicks vs views)", use_container_width=True):
            preset_clicked = "Break down conversion events (pageviews vs clicks)"

    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input Handler
    user_prompt = st.chat_input("Ask a question about your tracking data...") or preset_clicked

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing schema & computing metrics..."):
                response_data = ai_chat_service.process_message(
                    message=user_prompt,
                    conversation_history=st.session_state.messages[:-1],
                    platform=platform_option
                )
                answer_text = response_data.get("answer", "No response generated.")
                st.markdown(answer_text)

                # If SQL query or data is attached, display it
                if response_data.get("sql"):
                    with st.expander("🛠️ View Generated SQL Query"):
                        st.code(response_data["sql"], language="sql")

                if response_data.get("chart"):
                    c_info = response_data["chart"]
                    if c_info.get("type") == "bar" and c_info.get("labels"):
                        fig_ai = px.bar(
                            x=c_info["labels"],
                            y=c_info["datasets"][0]["data"],
                            title=c_info.get("title", "AI Generated Chart"),
                            labels={"x": "Dimension", "y": c_info["datasets"][0].get("label", "Value")},
                            color_discrete_sequence=["#38bdf8"]
                        )
                        fig_ai.update_layout(**PLOTLY_DARK_LAYOUT, height=280)
                        st.plotly_chart(fig_ai, use_container_width=True)

        st.session_state.messages.append({"role": "assistant", "content": answer_text})
