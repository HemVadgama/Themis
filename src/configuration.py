"""Validated, dependency-free TOML experiment configuration."""

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from src.protocols.registry import available_protocols
from src.simulation.scenario import ScenarioConfig, load_scenario


class ConfigurationError(ValueError):
    """An actionable error in a user-supplied experiment configuration."""


@dataclass
class ExperimentConfiguration:
    name: str
    seed: int
    protocol: str
    scenario: ScenarioConfig
    output_directory: Path
    metadata: dict = field(default_factory=dict)
    source_path: Path | None = None

    def resolved_dict(self):
        scenario = self.scenario
        return {
            "experiment": {"name": self.name, "seed": self.seed, "metadata": self.metadata},
            "scenario": {
                "preset": "closed_loop_resolved",
                "name": scenario.name,
                "agent_count": scenario.agent_count,
                "duration_steps": scenario.duration_steps,
                "decision_deadline_steps": scenario.decision_deadline_steps,
                "risk_reassessment_horizon_steps": scenario.risk_reassessment_horizon_steps,
                "initial_states": scenario.initial_states,
                "mission_priorities": scenario.mission_priorities,
                "fuel_budgets": scenario.fuel_budgets,
            },
            "network": {
                "latency_steps": scenario.network_latency_steps,
                "packet_loss_rate": scenario.packet_loss_rate,
                "bandwidth_limit_per_agent": scenario.bandwidth_limit_per_agent,
            },
            "protocol": {"name": self.protocol},
            "safety": {
                "conjunction_threshold_km": scenario.conjunction_threshold_km,
                "maneuver_threshold_km": scenario.maneuver_threshold_km,
                "secondary_conjunction_threshold_km": scenario.secondary_conjunction_threshold_km,
                "allow_secondary_risk": scenario.allow_secondary_risk,
            },
            "maneuver": {
                "min_delta_v_km_per_step": scenario.min_delta_v_km_per_step,
                "max_delta_v_km_per_step": scenario.max_delta_v_km_per_step,
                "default_fuel_budget": scenario.default_fuel_budget,
            },
            "execution": {
                "failure_rate": scenario.execution_failure_rate,
                "magnitude_error_fraction": scenario.execution_magnitude_error_fraction,
            },
            "output": {"directory": str(self.output_directory)},
        }


_TOP_LEVEL = {"experiment", "scenario", "network", "protocol", "safety", "maneuver", "execution", "output"}
_FIELDS = {
    "experiment": {"name", "seed", "metadata"},
    "scenario": {"preset", "name", "agent_count", "duration_steps", "decision_deadline_steps", "risk_reassessment_horizon_steps", "initial_states", "mission_priorities", "fuel_budgets"},
    "network": {"latency_steps", "packet_loss_rate", "bandwidth_limit_per_agent"},
    "protocol": {"name"},
    "safety": {"conjunction_threshold_km", "maneuver_threshold_km", "secondary_conjunction_threshold_km", "allow_secondary_risk"},
    "maneuver": {"min_delta_v_km_per_step", "max_delta_v_km_per_step", "default_fuel_budget"},
    "execution": {"failure_rate", "magnitude_error_fraction"},
    "output": {"directory"},
}


def _table(data, name):
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Invalid [{name}] configuration: expected a TOML table.")
    unknown = sorted(set(value) - _FIELDS[name])
    if unknown:
        raise ConfigurationError(f"Invalid [{name}] configuration: unknown field(s): {', '.join(unknown)}.")
    return value


def _number(value, label, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"Invalid {label}: expected a number, got {value!r}.")
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"Invalid {label}: must be >= {minimum}, got {value}.")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"Invalid {label}: must be <= {maximum}, got {value}.")
    return value


def _integer(value, label, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"Invalid {label}: expected an integer, got {value!r}.")
    return _number(value, label, minimum=minimum)


def _validate_initial_states(states, agent_count):
    if not isinstance(states, list):
        raise ConfigurationError("Invalid scenario.initial_states: expected an array of tables.")
    if states and len(states) != agent_count:
        raise ConfigurationError("Invalid scenario.initial_states: length must equal scenario.agent_count.")
    ids = set()
    for index, state in enumerate(states):
        label = f"scenario.initial_states[{index}]"
        if not isinstance(state, dict) or set(state) != {"agent_id", "position_km", "velocity_km_per_step"}:
            raise ConfigurationError(f"Invalid {label}: require agent_id, position_km, and velocity_km_per_step only.")
        if not isinstance(state["agent_id"], str) or not state["agent_id"].strip():
            raise ConfigurationError(f"Invalid {label}.agent_id: expected a non-empty string.")
        if state["agent_id"] in ids:
            raise ConfigurationError(f"Invalid {label}.agent_id: duplicate '{state['agent_id']}'.")
        ids.add(state["agent_id"])
        for vector_name in ("position_km", "velocity_km_per_step"):
            vector = state[vector_name]
            if not isinstance(vector, list) or len(vector) != 3:
                raise ConfigurationError(f"Invalid {label}.{vector_name}: expected exactly three numbers.")
            for component in vector:
                _number(component, f"{label}.{vector_name}")


def _validate_metadata(value, label="experiment.metadata"):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationError(f"Invalid {label}: metadata keys must be strings.")
            _validate_metadata(item, f"{label}.{key}")
        return
    if isinstance(value, list):
        if any(isinstance(item, (dict, list)) for item in value):
            raise ConfigurationError(f"Invalid {label}: metadata arrays may contain scalar values only.")
        for item in value:
            _validate_metadata(item, label)
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    raise ConfigurationError(f"Invalid {label}: unsupported metadata value {value!r}.")


def _validate_agent_mapping(value, label, *, numeric=False):
    if not isinstance(value, dict):
        raise ConfigurationError(f"Invalid {label}: expected a TOML table.")
    for agent_id, item in value.items():
        if not isinstance(agent_id, str) or not agent_id:
            raise ConfigurationError(f"Invalid {label}: agent IDs must be non-empty strings.")
        if numeric:
            _number(item, f"{label}.{agent_id}", minimum=0.0)
        else:
            _integer(item, f"{label}.{agent_id}")


def load_experiment_config(path, overrides=None):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigurationError(f"Configuration file not found: {source}")
    try:
        with source.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"Malformed TOML in {source}: {error}") from error

    for dotted_key, value in (overrides or {}).items():
        parts = dotted_key.split(".")
        if len(parts) != 2:
            raise ConfigurationError(f"Invalid sweep key '{dotted_key}': expected section.field.")
        data.setdefault(parts[0], {})[parts[1]] = value

    unknown = sorted(set(data) - _TOP_LEVEL)
    if unknown:
        raise ConfigurationError(f"Invalid configuration: unknown top-level section(s): {', '.join(unknown)}.")
    experiment = _table(data, "experiment")
    scenario_values = _table(data, "scenario")
    network = _table(data, "network")
    protocol_values = _table(data, "protocol")
    safety = _table(data, "safety")
    maneuver = _table(data, "maneuver")
    execution = _table(data, "execution")
    output = _table(data, "output")

    name = experiment.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigurationError("Invalid experiment.name: a non-empty string is required.")
    seed = _integer(experiment.get("seed", 0), "experiment.seed")
    metadata = experiment.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ConfigurationError("Invalid experiment.metadata: expected a TOML table.")
    _validate_metadata(metadata)
    preset = scenario_values.get("preset", "closed_loop_resolved")
    if not isinstance(preset, str):
        raise ConfigurationError("Invalid scenario.preset: expected a string.")
    try:
        scenario = deepcopy(load_scenario(preset, seed=seed))
    except ValueError as error:
        raise ConfigurationError(f"Invalid scenario.preset: {error}") from error
    scenario.name = scenario_values.get("name", name)
    if not isinstance(scenario.name, str) or not scenario.name.strip():
        raise ConfigurationError("Invalid scenario.name: expected a non-empty string.")
    scenario.seed = seed

    mapping = {
        "agent_count": (scenario_values, "agent_count"),
        "duration_steps": (scenario_values, "duration_steps"),
        "decision_deadline_steps": (scenario_values, "decision_deadline_steps"),
        "risk_reassessment_horizon_steps": (scenario_values, "risk_reassessment_horizon_steps"),
        "network_latency_steps": (network, "latency_steps"),
        "packet_loss_rate": (network, "packet_loss_rate"),
        "bandwidth_limit_per_agent": (network, "bandwidth_limit_per_agent"),
        "conjunction_threshold_km": (safety, "conjunction_threshold_km"),
        "maneuver_threshold_km": (safety, "maneuver_threshold_km"),
        "secondary_conjunction_threshold_km": (safety, "secondary_conjunction_threshold_km"),
        "allow_secondary_risk": (safety, "allow_secondary_risk"),
        "min_delta_v_km_per_step": (maneuver, "min_delta_v_km_per_step"),
        "max_delta_v_km_per_step": (maneuver, "max_delta_v_km_per_step"),
        "default_fuel_budget": (maneuver, "default_fuel_budget"),
        "execution_failure_rate": (execution, "failure_rate"),
        "execution_magnitude_error_fraction": (execution, "magnitude_error_fraction"),
    }
    for attribute, (table, key) in mapping.items():
        if key in table:
            setattr(scenario, attribute, table[key])
    for key in ("initial_states", "mission_priorities", "fuel_budgets"):
        if key in scenario_values:
            setattr(scenario, key, scenario_values[key])

    for attribute in ("agent_count", "duration_steps", "decision_deadline_steps", "risk_reassessment_horizon_steps", "network_latency_steps"):
        _integer(getattr(scenario, attribute), attribute.replace("network_", "network."), minimum=1 if attribute in {"agent_count", "duration_steps", "risk_reassessment_horizon_steps"} else 0)
    if scenario.bandwidth_limit_per_agent is not None:
        _integer(scenario.bandwidth_limit_per_agent, "network.bandwidth_limit_per_agent")
    _number(scenario.packet_loss_rate, "network.packet_loss_rate", minimum=0.0, maximum=1.0)
    for attribute in ("conjunction_threshold_km", "maneuver_threshold_km", "secondary_conjunction_threshold_km", "min_delta_v_km_per_step", "max_delta_v_km_per_step", "default_fuel_budget"):
        _number(getattr(scenario, attribute), attribute, minimum=0.0)
    _number(scenario.execution_failure_rate, "execution.failure_rate", minimum=0.0, maximum=1.0)
    _number(scenario.execution_magnitude_error_fraction, "execution.magnitude_error_fraction", minimum=0.0)
    if scenario.min_delta_v_km_per_step > scenario.max_delta_v_km_per_step:
        raise ConfigurationError("Invalid maneuver configuration: min_delta_v_km_per_step must not exceed max_delta_v_km_per_step.")
    if not isinstance(scenario.allow_secondary_risk, bool):
        raise ConfigurationError("Invalid safety.allow_secondary_risk: expected true or false.")
    _validate_initial_states(scenario.initial_states, scenario.agent_count)
    _validate_agent_mapping(scenario.mission_priorities, "scenario.mission_priorities")
    _validate_agent_mapping(scenario.fuel_budgets, "scenario.fuel_budgets", numeric=True)

    protocol = protocol_values.get("name", "centralized")
    if protocol not in available_protocols():
        raise ConfigurationError(f"Unsupported protocol '{protocol}'. Choose one of: {', '.join(available_protocols())}.")
    directory = output.get("directory", "results")
    if not isinstance(directory, str) or not directory.strip():
        raise ConfigurationError("Invalid output.directory: expected a non-empty path string.")
    output_directory = Path(directory).expanduser()
    if not output_directory.is_absolute():
        output_directory = (source.parent / output_directory).resolve()
    return ExperimentConfiguration(name, seed, protocol, scenario, output_directory, metadata, source)
