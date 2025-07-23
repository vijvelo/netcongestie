import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pandas as pd
from datetime import timedelta
import random


class FilterStreet:

    def __init__(
        self,
        name,
        num_filters,  # number of filters
        max_run_volume,  # max run volume
        volume_soft_margin,  # difference of max filter thoughput and the soft cap.
        backwash_programme,  # backwash programme in m3/h per minute step
    ):

        # set name
        self.name = name

        # max volumes throughput per filter
        self.max_run_volume = max_run_volume

        # soft cap filter throughput per filter
        self.soft_cap_volume = max_run_volume - volume_soft_margin

        # instantiate filter volumes (staggered initial)
        self.filter_volumes = np.array(
            [(max_run_volume) / (num_filters) * i for i in range(num_filters)]
        )

        # backwash programme
        self.backwash_programme = backwash_programme

        # filter status (1 = on, 0 = backwash)
        self.filter_status = np.array([1] * num_filters)

        self.results = []

        self.filter_queue = []

    def update(self, volume):
        # calculate volume per filter
        volume_per_filter = volume / sum(self.filter_status)  # in m3/h
        # update filter volumes
        self.filter_volumes += volume_per_filter / 60 * self.filter_status

        self.results.append(
            {
                "filter_volumes": self.filter_volumes.tolist(),
                "filter_status": self.filter_status.tolist(),
            }
        )


class Treatment:

    def __init__(
        self,
        production_factor,  # power consumption per m3/h produced       (kW/m3)
        distribution_factor,  # power consumption per m3/h distributed    (kW/m3)
        backwash_factor,  # power consumption per m3/h backwash       (kW/m3)
        baseload_power,  # baseload power consumption                (kW)
        reservoir_capacity,  # reservoir volume                        (m3)
        reservoir_volume_i,  # reservoir initial volume                (m3)
        # backwash buffer and handling
        backwash_buffer_volume,  # backwash buffer volume                    (m3)
        backwash_drain,  # backwash drain flow                       (m3/h)
        timestamp_i,  # initial timestamp
        initialization_days,  # days used for initalization of the model (days)
    ):

        # store parameters
        self.production_power = production_factor
        self.distribution_power = distribution_factor
        self.backwash_power = backwash_factor
        self.baseload_power = baseload_power
        self.reservoir_capacity = reservoir_capacity
        self.reservoir_volume = reservoir_volume_i
        self.backwash_buffer_volume = backwash_buffer_volume
        self.backwash_drain = backwash_drain

        # instantiate filter streets
        self.filter_streets = []

        # instantiate backwash buffer
        self.backwash_buffer = 0

        # instantiate backwash installation
        self.backwash_active = False  # backwash active
        self.backwash_street = None  # street to backwash
        self.backwash_filter = None  # filter to backwash
        self.backwash_step = 0  # backwash step (minute)

        # instantiate time
        self.time = timestamp_i
        self.step = 0
        self.production_flow = 0

        # set controller
        self.controller = None

        # flag if its the first week where no errors are raised due to initialization
        self.initialization_time_reached = False
        self.initialization_days = initialization_days

        # results
        self.results = []
        self.filter_queue = {"street": [], "filter": []}

    @property
    def reservoir_level(self):
        return self.reservoir_volume / self.reservoir_capacity

    def update_filter_queue(self):
        for street_index, street in enumerate(self.filter_streets):
            for filter_index, volume in enumerate(street.filter_volumes):
                if volume > street.max_run_volume and self.initialization_time_reached:
                    raise ValueError("Max filter throughput is reached")
                elif volume > street.soft_cap_volume and (
                    street_index,
                    filter_index,
                ) not in zip(self.filter_queue["street"], self.filter_queue["filter"]):
                    self.filter_queue["street"].append(street_index)
                    self.filter_queue["filter"].append(filter_index)

    def start_backwash(self):
        if self.backwash_active:
            raise ValueError("Backwash is already active")

        self.backwash_active = True
        self.backwash_street = self.filter_queue["street"].pop(0)
        self.backwash_filter = self.filter_queue["filter"].pop(0)
        print("Backwash started", self.backwash_street, self.backwash_filter)
        self.filter_streets[self.backwash_street].filter_volumes[
            self.backwash_filter
        ] = 0
        self.filter_streets[self.backwash_street].filter_status[
            self.backwash_filter
        ] = 0
        self.backwash_step = 0

    def update_backwash(self):
        backwash_flow = 0
        # update backwash installation
        if self.backwash_active:
            # update backwash flow
            backwash_flow = self.filter_streets[
                self.backwash_street
            ].backwash_programme[self.backwash_step]
            # update backwash buffer
            self.backwash_buffer += backwash_flow / 60
            # update backwash step
            self.backwash_step += 1
            # if backwash step is greater than the length of the backwash programme, deactivate backwash and set filter
            if self.backwash_step >= len(
                self.filter_streets[self.backwash_street].backwash_programme
            ):
                # deactivate backwash
                self.backwash_active = False
                self.backwash_step = 0
                # set backwashed filter to on and reset runvolume
                print("Backwash finished", self.backwash_street, self.backwash_filter)
                self.filter_streets[self.backwash_street].filter_status[
                    self.backwash_filter
                ] = 1

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

        self.update_filter_queue()
        backwash_flow = self.update_backwash()

        # update reservoir volume
        self.reservoir_volume -= distribution_flow / 60 + backwash_flow / 60
        self.reservoir_volume += self.production_flow / 60
        if self.reservoir_volume < 0:
            raise ValueError("Reservoir volume is negative")
        if self.reservoir_volume > self.reservoir_capacity:
            self.reservoir_volume = self.reservoir_capacity  # FIXME: must be an error

        # update backwash buffer
        self.backwash_buffer += backwash_flow / 60 - self.backwash_drain / 60
        self.backwash_buffer = max(0, self.backwash_buffer)  # buffer cannot be negative
        if (
            self.backwash_buffer > self.backwash_buffer_volume
            and self.initialization_time_reached
        ):
            raise ValueError(
                "Backwash buffer is greater than the backwash buffer volume"
            )

        # calculate power consumption
        power_consumption = (
            self.baseload_power
            + self.production_power * self.production_flow
            + self.distribution_power * distribution_flow
            + self.backwash_power * backwash_flow
        )

        if self.step == (self.initialization_days * 24 * 60):
            self.initialization_time_reached = True

        # store state
        self.results.append(
            {
                "time": self.time,
                "reservoir_volume": self.reservoir_volume,
                "reservoir_level": self.reservoir_capacity,
                "backwash_buffer": self.backwash_buffer,
                "backwash_active": self.backwash_active,
                "backwash_step": self.backwash_step,
                "backwash_street": self.backwash_street,
                "backwash_filter": self.backwash_filter,
                "production_flow": self.production_flow,
                "distribution_flow": distribution_flow,
                "backwash_flow": backwash_flow,
                "total_power": power_consumption,
                "production_power": self.production_power * self.production_flow,
                "distribution_power": self.distribution_power * distribution_flow,
                "backwash_power": self.backwash_power * backwash_flow,
                "baseload_power": self.baseload_power,
            }
        )
