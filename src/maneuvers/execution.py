from src.maneuvers.model import ManeuverStatus


class ManeuverExecutor:
    def __init__(self, random_source):
        self.random_source = random_source

    def execute(self, proposal, world, config):
        if proposal.execution_status == ManeuverStatus.EXECUTED.value:
            return {
                "executed": False,
                "reason_code": "DUPLICATE_EXECUTION",
                "explanation": "Maneuver has already been executed.",
            }

        agent = world.agents[proposal.agent_id]

        if agent.state.fuel_budget < proposal.estimated_fuel_cost:
            proposal.execution_status = ManeuverStatus.FAILED.value
            proposal.actual_execution_error = "INSUFFICIENT_FUEL_AT_EXECUTION"
            return {
                "executed": False,
                "reason_code": "INSUFFICIENT_FUEL_AT_EXECUTION",
                "explanation": "Fuel budget was insufficient at execution time.",
            }

        if self.random_source.random() < config.execution_failure_rate:
            proposal.execution_status = ManeuverStatus.FAILED.value
            proposal.actual_execution_time = world.current_time
            proposal.actual_delta_v_vector_km_per_step = (0.0, 0.0, 0.0)
            proposal.actual_execution_error = "EXECUTION_FAILURE"
            return {
                "executed": False,
                "reason_code": "EXECUTION_FAILURE",
                "explanation": "Configured execution uncertainty caused maneuver failure.",
            }

        actual_delta_v = tuple(
            component * (1.0 + config.execution_magnitude_error_fraction)
            for component in proposal.delta_v_vector_km_per_step
        )
        world.trajectories[proposal.agent_id] = world.trajectories[proposal.agent_id].with_impulse(
            world.current_time,
            actual_delta_v,
        )
        agent.state.fuel_budget -= proposal.estimated_fuel_cost
        agent.state.fuel_budget = max(0.0, agent.state.fuel_budget)
        agent.state.accepted_maneuver = None
        agent.state.maneuver_history.append(proposal.maneuver_id)

        proposal.execution_status = ManeuverStatus.EXECUTED.value
        proposal.proposal_status = ManeuverStatus.EXECUTED.value
        proposal.actual_execution_time = world.current_time
        proposal.actual_delta_v_vector_km_per_step = actual_delta_v
        proposal.actual_execution_error = None

        return {
            "executed": True,
            "reason_code": "EXECUTED",
            "explanation": "Maneuver executed and simulated trajectory was updated.",
        }
