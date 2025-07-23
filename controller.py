class SimpleController:

    def __init__(
        self,
        production_groups_level_on=[0, 0.15, 0.3, 0.4, 0.2],
        production_groups_level_off=[1, 0.8, 0.7, 0.75, 0.9],
    ):
        self.max_production_flow = 900
        self.number_of_production_groups = len(production_groups_level_off)
        self.production_groups_status = [True] * self.number_of_production_groups
        self.production_groups_level_on = production_groups_level_on
        self.production_groups_level_off = production_groups_level_off
        self.production_per_group = (
            self.max_production_flow / self.number_of_production_groups
        )

    def update(self, treatment):

        production_groups = {
            "level_on": self.production_groups_level_on,
            "level_off": self.production_groups_level_off,
            "status": self.production_groups_status,
        }

        for number in range(self.number_of_production_groups):
            print(treatment.reservoir_level)
            if (
                production_groups["status"][number]
                and treatment.reservoir_level >= production_groups["level_off"][number]
            ):
                production_groups["status"][number] = False
            elif (
                not production_groups["status"][number]
                and treatment.reservoir_level <= production_groups["level_on"][number]
            ):
                production_groups["status"][number] = True

        if (
            treatment.reservoir_level > 0.1
            and len(treatment.filter_queue["filter"]) > 0
            and not treatment.backwash_active
            and treatment.backwash_buffer_volume - treatment.backwash_buffer > 600
        ):
            treatment.start_backwash()

        return sum(production_groups["status"]) * self.production_per_group


class ControllerMoreAdvanced:

    def __init__(
        self,
        production_groups_level_on=[0, 0.15, 0.3, 0.4, 0.2],
        production_groups_level_off=[1, 0.8, 0.7, 0.75, 0.9],
    ):
        self.max_production_flow = 900
        self.number_of_production_groups = len(production_groups_level_off)
        self.production_groups_status = [True] * self.number_of_production_groups
        self.production_groups_level_on = production_groups_level_on
        self.production_groups_level_off = production_groups_level_off
        self.production_per_group = (
            self.max_production_flow / self.number_of_production_groups
        )

    def update(self, treatment):

        production_groups = {
            "level_on": self.production_groups_level_on,
            "level_off": self.production_groups_level_off,
            "status": self.production_groups_status,
        }

        for number in range(self.number_of_production_groups):
            print(treatment.reservoir_level)
            if (
                production_groups["status"][number]
                and treatment.reservoir_level >= production_groups["level_off"][number]
            ):
                production_groups["status"][number] = False
            elif (
                not production_groups["status"][number]
                and treatment.reservoir_level <= production_groups["level_on"][number]
            ):
                production_groups["status"][number] = True

        night = (
            treatment.step % (24 * 60) < 7 * 60 and treatment.step % (24 * 60) > 2 * 60
        )
        if (
            treatment.reservoir_level > 0.1
            and len(treatment.filter_queue["filter"]) > 0
            and not treatment.backwash_active
            and treatment.backwash_buffer_volume - treatment.backwash_buffer > 1200
            and night
        ):
            treatment.start_backwash()

        return sum(production_groups["status"]) * self.production_per_group
