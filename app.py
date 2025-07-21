import streamlit as st
import pandas as pd
import numpy as np
from simulation import Treatment, FilterStreet
from controller import SimpleController

st.title('Netcongestie Simulator')

st.sidebar.header('Volumes')
reservoir_volume = st.sidebar.number_input('Reservoir volume', value=1000, min_value=0, max_value=10000, step=100)
backwash_buffer_volume = st.sidebar.number_input('Backwash buffer volume', value=500, min_value=0, max_value=10000, step=100)

number_of_filters = st.sidebar.number_input('Number of filters', value=2, min_value=1, max_value=10, step=1)

backwash_drain = st.sidebar.number_input('Backwash drain', value=100, min_value=0, max_value=1000, step=10)


treatment = Treatment(reservoir_capacity=reservoir_volume, reservoir_volume=reservoir_volume * 0.8, backwash_buffer_volume=backwash_buffer_volume, backwash_drain=backwash_drain)
filters = [FilterStreet('VF', num_filters=number_of_filters)]
treatment.filter_streets = filters

controller = SimpleController()
treatment.controller = controller

for t in range(48*60):
  x = t/1440 * 2 * np.pi
  q = 230 + 100 * (np.sin(x) + 1.3*np.sin(2*x))
  treatment.update(q)

results = pd.DataFrame(treatment.results)
results.index = results['time'].apply(lambda x: pd.Timestamp(x, unit='min'))

results['total_power_15m'] = results.resample('15min')['total_power'].transform('mean')

st.header('Reservoir volume')
st.line_chart(results[['reservoir_volume', 'backwash_buffer']])

st.header('Debieten')
st.line_chart(results[['production_flow', 'distribution_flow', 'backwash_flow']])

st.header('Energieverbruik')
st.area_chart(results[['production_power', 'distribution_power', 'baseload_power', 'backwash_power']], stack=True)

st.header('Kwartierwaarden')
st.line_chart(results[['total_power', 'total_power_15m']])

street_results = pd.DataFrame(filters[0].results)
street_volumes = street_results['filter_volumes'].apply(pd.Series)
street_volumes.index = results.index
street_volumes.columns = ['F{}'.format(i) for i in range(len(street_volumes.columns))]
street_status = street_results['filter_status'].apply(pd.Series)
street_status.index = results.index
street_status.columns = ['F{}'.format(i) for i in range(len(street_status.columns))]

st.header('Loopvolumes')
st.line_chart(street_volumes)
st.line_chart(street_status)



