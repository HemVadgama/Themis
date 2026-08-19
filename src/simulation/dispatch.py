"""Benchmark-version dispatch without changing either benchmark lifecycle."""

from src.simulation.campaign import run_campaign_scenario
from src.simulation.runner import run_closed_loop_scenario


def run_experiment(configuration):
    if configuration.benchmark == "spacecraft-campaign-v1":
        return run_campaign_scenario(configuration.scenario, configuration.protocol)
    return run_closed_loop_scenario(configuration.scenario, configuration.protocol)


__all__ = ["run_experiment"]
