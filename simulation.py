import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pandas as pd

class FilterStreet:

  def __init__(self,
               name,
               num_filters = 5,               # number of filters
               max_volume = 1000,             # max run volume
               backwash_programme = [600] * 10 # backwash programme in m3/h per minute step
               ):

    # set name
    self.name = name

    # instantiate filter volumes (staggered initial)
    self.filter_volumes = np.array([(max_volume)/(num_filters) * i for i in range(num_filters)])

    # backwash programme
    self.backwash_programme = backwash_programme

    # filter status (1 = on, 0 = backwash)
    self.filter_status = np.array([1] * num_filters)

    self.results = []
  
  def update(self, volume):
    # calculate volume per filter
    volume_per_filter = volume / sum(self.filter_status) # in m3/h
    # update filter volumes
    self.filter_volumes += volume_per_filter / 60 * self.filter_status 

    self.results.append({
      'filter_volumes': self.filter_volumes.tolist(),
      'filter_status': self.filter_status.tolist(),
    })

class Treatment:

  def __init__(self, 
               production_power = 0.2,          # power consumption per m3/h produced       (kW/m3)
               distribution_power = 0.2,        # power consumption per m3/h distributed    (kW/m3)
               backwash_power = 0.3,            # power consumption per m3/h backwash       (kW/m3)
               baseload_power = 50,             # baseload power consumption                (kW)

               reservoir_capacity = 1000,       # reservoir volume                        (m3) 
               reservoir_volume = 800,          # reservoir initial volume                (m3) 

               # backwash buffer and handling
               backwash_buffer_volume = 500,    # backwash buffer volume                    (m3)
               backwash_drain = 100             # backwash drain flow                       (m3/h)
               ):
    

    # store parameters
    self.production_power = production_power
    self.distribution_power = distribution_power
    self.backwash_power = backwash_power
    self.baseload_power = baseload_power
    self.reservoir_capacity = reservoir_capacity
    self.reservoir_volume = reservoir_volume
    self.backwash_buffer_volume = backwash_buffer_volume
    self.backwash_drain = backwash_drain

    # instantiate filter streets
    self.filter_streets = []

    # instantiate backwash buffer
    self.backwash_buffer = 0

    # instantiate backwash installation
    self.backwash_active = False # backwash active
    self.backwash_street = None # street to backwash
    self.backwash_filter = None # filter to backwash
    self.backwash_step = 0 # backwash step (minute)

    # instantiate time
    self.time = pd.Timestamp('2025-01-01 00:00:00')
    self.step = 0
    self.production_flow = 0

    # set controller
    self.controller = None

    # results
    self.results = []
  
  @property
  def reservoir_level(self):
    return self.reservoir_volume / self.reservoir_capacity
  
  def start_backwash(self, street, filter_index):
    if self.backwash_active:
      raise ValueError('Backwash is already active')
    
    self.backwash_active = True
    self.backwash_street = street
    self.backwash_filter = filter_index
    print('Backwash started', street, filter_index)
    self.filter_streets[street].filter_volumes[filter_index] = 0
    self.filter_streets[street].filter_status[filter_index] = 0
    self.backwash_step = 0
  
  def update_backwash(self):
    backwash_flow = 0
    # update backwash installation
    if self.backwash_active:
      # update backwash flow
      backwash_flow = self.filter_streets[self.backwash_street].backwash_programme[self.backwash_step]
      # update backwash buffer
      self.backwash_buffer += backwash_flow / 60
      # update backwash step
      self.backwash_step += 1
      # if backwash step is greater than the length of the backwash programme, deactivate backwash and set filter 
      if self.backwash_step >= len(self.filter_streets[self.backwash_street].backwash_programme):
        # deactivate backwash
        self.backwash_active = False
        self.backwash_step = 0
        # set backwashed filter to on and reset runvolume
        print('Backwash finished', self.backwash_street, self.backwash_filter)
        self.filter_streets[self.backwash_street].filter_status[self.backwash_filter] = 1
    
    return backwash_flow
  
  def update(self, distribution_flow):
    # update time
    self.step += 1
    self.time = self.time + pd.Timedelta(minutes=1)

    # update controller
    if self.controller is not None:
      self.production_flow = self.controller.update(self)

    # update filter streets
    for street in self.filter_streets:
      street.update(self.production_flow)

    backwash_flow = self.update_backwash()

    # update reservoir volume
    self.reservoir_volume -= (distribution_flow / 60 + backwash_flow / 60 )
    self.reservoir_volume += self.production_flow / 60
    if self.reservoir_volume < 0:
      raise ValueError('Reservoir volume is negative')
    if self.reservoir_volume > self.reservoir_capacity:
      self.reservoir_volume = self.reservoir_capacity

    
    # update backwash buffer
    self.backwash_buffer += backwash_flow / 60 - self.backwash_drain / 60
    self.backwash_buffer = max(0, self.backwash_buffer) # buffer cannot be negative
    if self.backwash_buffer > self.backwash_buffer_volume:
      raise ValueError('Backwash buffer is greater than the backwash buffer volume')


    # calculate power consumption
    power_consumption = self.baseload_power + self.production_power * self.production_flow + self.distribution_power * distribution_flow + self.backwash_power * backwash_flow

    # store state
    self.results.append({
      'time': self.time,
      'reservoir_volume': self.reservoir_volume,
      'backwash_buffer': self.backwash_buffer,
      'backwash_active': self.backwash_active,
      'backwash_step': self.backwash_step,
      'backwash_street': self.backwash_street,
      'backwash_filter': self.backwash_filter,
      'production_flow': self.production_flow,
      'distribution_flow': distribution_flow,
      'backwash_flow': backwash_flow,
      'total_power': power_consumption,
      'production_power': self.production_power * self.production_flow,
      'distribution_power': self.distribution_power * distribution_flow,
      'backwash_power': self.backwash_power * backwash_flow,
      'baseload_power': self.baseload_power,
    })