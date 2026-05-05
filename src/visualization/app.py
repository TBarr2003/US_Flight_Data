from gevent import monkey
monkey.patch_all()

import streamlit as st
import pandas as pd
import plotly.express as px
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from config.settings import settings

st.set_page_config(
    page_title="US Flight Delay Analytics",
    page_icon="✈️",
    layout="wide"
)


@st.cache_resource
def get_session():
    cluster = Cluster(
        [settings.cassandra_host],
        port=settings.cassandra_port,
        load_balancing_policy=RoundRobinPolicy(),
        protocol_version=4
    )
    return cluster.connect(settings.cassandra_keyspace)


@st.cache_data
def load_carrier_performance():
    session = get_session()
    rows = session.execute("SELECT * FROM carrier_performance_monthly")
    return pd.DataFrame(rows)


@st.cache_data
def load_route_delays():
    session = get_session()
    rows = session.execute("SELECT * FROM route_delay_summary")
    return pd.DataFrame(rows)


@st.cache_data
def load_seasonal_delays():
    session = get_session()
    rows = session.execute("SELECT * FROM seasonal_delay_by_state")
    return pd.DataFrame(rows)


# ── Header
st.title("✈️ US Flight Delay Analytics")
st.markdown("Analyzing 12M+ domestic flights from 2023–2024")

# ── Sidebar filters
st.sidebar.header("Filters")
selected_year = st.sidebar.selectbox("Year", [2023, 2024, "Both"])

# ── Tab layout
tab1, tab2, tab3 = st.tabs([
    "📊 Carrier Reliability",
    "🛫 Route Delays",
    "🌦️ Seasonal Patterns"
])

# ── Tab 1: Carrier Reliability
with tab1:
    st.header("Which carriers are most reliable?")
    df_carrier = load_carrier_performance()

    if selected_year != "Both":
        df_carrier = df_carrier[df_carrier["year"] == selected_year]

    df_carrier["year_month"] = df_carrier["year"].astype(str) + "-" + df_carrier["month"].astype(str).str.zfill(2)
    df_carrier = df_carrier.sort_values("year_month")

    airlines = st.multiselect(
        "Select Airlines",
        options=sorted(df_carrier["airline"].unique()),
        default=sorted(df_carrier["airline"].unique())[:5]
    )

    df_filtered = df_carrier[df_carrier["airline"].isin(airlines)]

    fig1 = px.line(
        df_filtered,
        x="year_month",
        y="on_time_rate",
        color="airline",
        title="On-Time Rate by Carrier Over Time (%)",
        labels={"year_month": "Month", "on_time_rate": "On-Time Rate (%)"},
        markers=True
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("Average Arrival Delay by Carrier")
    avg_delay = df_carrier.groupby("airline")["avg_arr_delay"].mean().reset_index()
    avg_delay = avg_delay.sort_values("avg_arr_delay", ascending=False)
    fig2 = px.bar(
        avg_delay,
        x="airline",
        y="avg_arr_delay",
        title="Average Arrival Delay by Carrier (minutes)",
        labels={"airline": "Airline", "avg_arr_delay": "Avg Arrival Delay (min)"},
        color="avg_arr_delay",
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig2, use_container_width=True)


# ── Tab 2: Route Delays
with tab2:
    st.header("Which routes have the worst delays?")
    df_routes = load_route_delays()

    if selected_year != "Both":
        df_routes = df_routes[df_routes["year"] == selected_year]

    min_flights = st.slider("Minimum flights on route", 100, 5000, 500)
    df_routes = df_routes[df_routes["total_flights"] >= min_flights]

    df_routes["route"] = df_routes["origin"] + " → " + df_routes["dest"]
    top_routes = df_routes.nlargest(20, "avg_arr_delay")

    fig3 = px.bar(
        top_routes,
        x="avg_arr_delay",
        y="route",
        orientation="h",
        title="Top 20 Routes by Average Arrival Delay",
        labels={"avg_arr_delay": "Avg Arrival Delay (min)", "route": "Route"},
        color="avg_arr_delay",
        color_continuous_scale="Oranges"
    )
    fig3.update_layout(height=600)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Delay Cause Breakdown for Top Routes")
    delay_causes = top_routes[["route", "avg_weather_delay", "avg_carrier_delay", "avg_nas_delay"]].melt(
        id_vars="route",
        var_name="cause",
        value_name="minutes"
    )
    fig4 = px.bar(
        delay_causes,
        x="minutes",
        y="route",
        color="cause",
        orientation="h",
        title="Delay Causes for Top 20 Routes",
        labels={"minutes": "Avg Delay (min)", "route": "Route"},
        barmode="stack"
    )
    fig4.update_layout(height=600)
    st.plotly_chart(fig4, use_container_width=True)


# ── Tab 3: Seasonal Patterns
with tab3:
    st.header("How do delays shift seasonally across states?")
    df_seasonal = load_seasonal_delays()

    if selected_year != "Both":
        df_seasonal = df_seasonal[df_seasonal["year"] == selected_year]

    quarter_map = {1: "Q1 (Winter)", 2: "Q2 (Spring)", 3: "Q3 (Summer)", 4: "Q4 (Fall)"}
    df_seasonal["quarter_label"] = df_seasonal["quarter"].map(quarter_map)

    selected_quarter = st.selectbox(
        "Select Quarter",
        options=["All"] + list(quarter_map.values())
    )

    if selected_quarter != "All":
        q_num = [k for k, v in quarter_map.items() if v == selected_quarter][0]
        df_seasonal = df_seasonal[df_seasonal["quarter"] == q_num]

    state_avg = df_seasonal.groupby("origin_state")["avg_weather_delay"].mean().reset_index()

    fig5 = px.choropleth(
        state_avg,
        locations="origin_state",
        locationmode="USA-states",
        color="avg_weather_delay",
        scope="usa",
        title="Average Weather Delay by State",
        color_continuous_scale="Blues",
        labels={"avg_weather_delay": "Avg Weather Delay (min)"}
    )
    st.plotly_chart(fig5, use_container_width=True)

    st.subheader("Cancellation Rate by State and Quarter")
    pivot = df_seasonal.groupby(["origin_state", "quarter_label"])["cancellation_rate"].mean().reset_index()
    fig6 = px.density_heatmap(
        pivot,
        x="quarter_label",
        y="origin_state",
        z="cancellation_rate",
        title="Cancellation Rate Heatmap by State and Season",
        labels={"quarter_label": "Quarter", "origin_state": "State", "cancellation_rate": "Cancellation Rate (%)"}
    )
    fig6.update_layout(height=800)
    st.plotly_chart(fig6, use_container_width=True)