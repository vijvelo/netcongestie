import streamlit as st
import pandas as pd
import numpy as np
from simulation import Treatment, FilterStreet
from controller import SimpleController, ControllerMoreAdvanced
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# IMPORT DISTRIBUTION PROFILE
year = 2024
week_number = 30

# Load CSV file
df = pd.read_csv("lsr.csv", header=None, names=["timestamp", "flow"])
# Parse timestamp column into datetime objects
df["timestamp"] = pd.to_datetime(df["timestamp"])
# Find Monday of the selected ISO week
monday = datetime.fromisocalendar(year, week_number, 1)
start_time = monday - timedelta(days=2)  # Saturday
end_time = monday + timedelta(days=7)  # one week
# Select time window from Saturday before week to after Sunday
df_week = df[(df["timestamp"] >= start_time) & (df["timestamp"] < end_time)]
# Set timestamp as index for resampling
df_week = df_week.set_index("timestamp")
# Resample to 1-minute frequency and forward-fill flow values
distribution_profile = df_week.resample("1T").ffill()

# DEFINE PARAMETERS
# adjustable parameters
reservoir_volume_max = st.sidebar.number_input(
    "Reservoir volume", value=3000, min_value=0, max_value=10000, step=100
)
backwash_buffer_volume = st.sidebar.number_input(
    "Backwash buffer volume", value=1400, min_value=0, max_value=10000, step=100
)

number_of_filters = st.sidebar.number_input(
    "Number of filters", value=2, min_value=1, max_value=10, step=1
)

backwash_drain = st.sidebar.number_input(
    "Backwash drain", value=200, min_value=0, max_value=1000, step=10
)

# filterstreets
filter_volume_soft_margin = (
    4000  # difference of max filter throughput and the soft cap.
)
par_fs1 = {
    "name": "VF",
    "num_filters": number_of_filters,  # number of filters per street
    "max_run_volume": 30000,  # max run volume of a filter (m3)
    "volume_soft_margin": filter_volume_soft_margin,
    "backwash_programme": [1800] * 5
    + [800] * 6
    + [1800] * 8
    + [0] * 10,  # backwash programme in m3/h per minute step
}
par_fs2 = {
    "name": "VF2",
    "num_filters": number_of_filters,
    "max_run_volume": 30000 / 3,
    "volume_soft_margin": filter_volume_soft_margin,
    "backwash_programme": [
        (x / 3) for x in [1800] * 5 + [800] * 6 + [1800] * 8 + [0] * 10
    ],
}
# treatment
par_treatment = {
    "production_factor": 0.11,  # power consumption per m3/h produced (from fit) (kW/m3)
    "distribution_factor": 0.12,  # power consumption per m3/h distributed (from fit) (kW/m3)
    "backwash_factor": 0.0425,  # power consumption per m3/h backwash (from fit) (kW/m3)
    "baseload_power": 14.5,  # baseload power consumption (from fit) (kW)
    "reservoir_capacity": reservoir_volume_max,  # max reservoir volume (m3)
    "reservoir_volume_i": reservoir_volume_max / 0.8,  # reservoir initial volume (m3)
    "backwash_buffer_volume": backwash_buffer_volume,  # max backwash buffer volume (m3)
    "backwash_drain": backwash_drain,  # backwash drain flow (m3/h)
    "timestamp_i": distribution_profile.index[0],  # initial timestamp
    "initialization_days": 7,  # days used for initalization of the model
}

# SET UP MODEL
treatment = Treatment(**par_treatment)
filters = [
    FilterStreet(**par_fs1),
    FilterStreet(**par_fs2),
]
treatment.filter_streets = filters

# controller = ControllerMoreAdvanced()
controller = SimpleController()
treatment.controller = controller

# RUN SIMULATION
for t in range(len(distribution_profile)):
    treatment.update(distribution_profile.flow[t])

results_full_Range = pd.DataFrame(treatment.results)

results_full_Range.index = results_full_Range["time"].apply(
    lambda x: pd.Timestamp(x, unit="min")
)

# Only keep results from Monday onward for plotting
results = results_full_Range[results_full_Range.index >= monday]

results["total_power_15m"] = results.resample("15min")["total_power"].transform("mean")

# SET UP STREAMLINE INTERFACE
st.title("Netcongestie Simulator")

# PLOT 1
fig_volume = px.line(
    results[["reservoir_volume", "backwash_buffer"]],
    labels={"value": "Volume (m³)", "index": "Tijd"},
    title="Bruikbaar volume van reservoir en backwash buffer",
)
fig_volume.update_layout(yaxis_title="Volume (m³)", xaxis_title="Tijd")
fig_volume.update_layout(legend_title_text=None)

# PLOT 2
fig_flow = px.line(
    results[["production_flow", "distribution_flow", "backwash_flow"]],
    labels={"value": "Debiet (m³/h)", "index": "Tijd"},
    title="Waterdebieten",
)
fig_flow.update_layout(yaxis_title="Debiet (m³/h)", xaxis_title="Tijd")
fig_flow.update_layout(legend_title_text=None)

# PLOT 3
fig_power = go.Figure()
for col in [
    "baseload_power",
    "production_power",
    "backwash_power",
    "distribution_power",
]:
    fig_power.add_trace(
        go.Scatter(
            x=results.index,
            y=results[col],
            stackgroup="one",
            name=col.replace("_", " ").capitalize(),
        )
    )
fig_power.update_layout(
    title="Vermogensverdeling",
    xaxis_title="Tijd",
    yaxis_title="Vermogen (kW)",
)
fig_power.update_layout(legend_title_text=None)

# PLOT 4
fig_quarters = px.line(
    results[["total_power", "total_power_15m"]],
    labels={"value": "Vermogen (kW)", "index": "Tijd"},
    title="Gemeten Vermogen per minuut en kwartier",
)
fig_quarters.update_layout(yaxis_title="Vermogen (kW)", xaxis_title="Tijd")

# PLOT 5

all_volumes = []

for i, f in enumerate(filters):
    results_df = pd.DataFrame(f.results)
    results_df.index = results_full_Range.index  # align time index
    results_df = results_df[results_df.index >= monday]
    # Slice to Monday and onward
    results_df = results_df[results_df.index >= monday]
    volumes = results_df["filter_volumes"].apply(pd.Series)
    volumes.columns = [
        f"F{i}_{j}" for j in range(volumes.shape[1])
    ]  # e.g., F0_0, F0_1, F1_0...
    volumes.index = results.index  # align time index
    all_volumes.append(volumes)

# Combine all into one DataFrame
combined_volumes = pd.concat(all_volumes, axis=1)

fig_run_volumes = px.line(
    combined_volumes,
    labels={"index": "Tijd", "value": "Volume (m³)"},
    title="Filter Loopvolumes over Tijd",
)

fig_run_volumes.update_layout(xaxis_title="Tijd", yaxis_title="Loop volume (m³)")
fig_run_volumes.update_layout(legend_title_text=None)

col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(fig_volume, use_container_width=True)

with col2:
    st.plotly_chart(fig_flow, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.plotly_chart(fig_power, use_container_width=True)

with col4:
    st.plotly_chart(fig_run_volumes, use_container_width=True)


st.plotly_chart(fig_quarters, use_container_width=True)

print(sum(results["production_flow"]))
print(sum(results["backwash_flow"]))
print(sum(results["distribution_flow"]))
