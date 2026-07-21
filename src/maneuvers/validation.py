from copy import deepcopy
from dataclasses import asdict, dataclass, field

from src.maneuvers.model import ManeuverStatus, ValidationStatus
from src.risk.reassessment import minimum_pair_distance, secondary_conjunctions_for_agent


@dataclass
class ManeuverValidationResult:
    valid: bool
    reason_code: str
    explanation: str
    evaluated_constraints: dict = field(default_factory=dict)
    estimated_post_maneuver_risk: dict | None = None
    estimated_fuel_cost: float = 0.0
    secondary_risk_findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class ManeuverValidator:
    def validate(self, proposal, world, config):
        evaluated = {}
        risk_event = world.risk_events.get(proposal.risk_event_id)
        agent = world.agents.get(proposal.agent_id)

        if risk_event is None:
            return self._invalid("UNKNOWN_RISK_EVENT", "Maneuver references an unknown risk event.", evaluated, proposal)

        if agent is None or proposal.agent_id not in world.trajectories:
            return self._invalid("UNKNOWN_AGENT", "Maneuver references an unknown agent.", evaluated, proposal)

        evaluated["current_risk_event"] = risk_event.status == "OPEN"
        if risk_event.status != "OPEN":
            return self._invalid("STALE_RISK_EVENT", "Risk event is no longer open.", evaluated, proposal)

        evaluated["before_deadline"] = proposal.proposal_time <= risk_event.decision_deadline
        if proposal.proposal_time > risk_event.decision_deadline:
            return self._invalid("MISSED_DEADLINE", "Maneuver proposal arrived after the decision deadline.", evaluated, proposal)

        evaluated["execution_before_deadline"] = proposal.planned_execution_time <= risk_event.decision_deadline
        if proposal.planned_execution_time > risk_event.decision_deadline:
            return self._invalid("LATE_EXECUTION", "Maneuver execution is after the decision deadline.", evaluated, proposal)

        evaluated["within_delta_v_bounds"] = (
            config.min_delta_v_km_per_step
            <= proposal.delta_v_magnitude_km_per_step
            <= config.max_delta_v_km_per_step
        )
        if not evaluated["within_delta_v_bounds"]:
            return self._invalid("DELTA_V_OUT_OF_BOUNDS", "Delta-v magnitude is outside configured bounds.", evaluated, proposal)

        available_fuel = agent.available_fuel()
        evaluated["sufficient_fuel"] = available_fuel >= proposal.estimated_fuel_cost
        if not evaluated["sufficient_fuel"]:
            return self._invalid("INSUFFICIENT_FUEL", "Agent does not have enough remaining fuel.", evaluated, proposal)

        evaluated["no_active_maneuver"] = agent.state.accepted_maneuver is None
        if not evaluated["no_active_maneuver"]:
            return self._invalid("AGENT_ALREADY_COMMITTED", "Agent already has an accepted maneuver.", evaluated, proposal)

        evaluated["not_duplicate_execution"] = proposal.maneuver_id not in world.maneuvers
        if not evaluated["not_duplicate_execution"]:
            return self._invalid("DUPLICATE_PROPOSAL", "Maneuver proposal already exists.", evaluated, proposal)

        baseline = minimum_pair_distance(
            world.trajectories,
            risk_event.satellite_a,
            risk_event.satellite_b,
            proposal.planned_execution_time + 1,
            config.risk_reassessment_horizon_steps,
        )
        post_trajectories = deepcopy(world.trajectories)
        post_trajectories[proposal.agent_id] = world.trajectories[proposal.agent_id].with_impulse(
            proposal.planned_execution_time,
            proposal.delta_v_vector_km_per_step,
        )
        post = minimum_pair_distance(
            post_trajectories,
            risk_event.satellite_a,
            risk_event.satellite_b,
            proposal.planned_execution_time + 1,
            config.risk_reassessment_horizon_steps,
        )
        secondary = secondary_conjunctions_for_agent(
            post_trajectories,
            proposal.agent_id,
            risk_event.participants(),
            config.secondary_conjunction_threshold_km,
            proposal.planned_execution_time + 1,
            config.risk_reassessment_horizon_steps,
        )

        evaluated["improves_target_risk"] = post["minimum_distance_km"] > baseline["minimum_distance_km"]
        if not evaluated["improves_target_risk"]:
            return ManeuverValidationResult(
                valid=False,
                reason_code="DOES_NOT_IMPROVE_RISK",
                explanation="Maneuver does not improve the targeted conjunction.",
                evaluated_constraints=evaluated,
                estimated_post_maneuver_risk=post,
                estimated_fuel_cost=proposal.estimated_fuel_cost,
                secondary_risk_findings=secondary,
            )

        evaluated["no_immediate_secondary_risk"] = not secondary
        if secondary and not config.allow_secondary_risk:
            return ManeuverValidationResult(
                valid=False,
                reason_code="SECONDARY_RISK_CREATED",
                explanation="Maneuver creates an unacceptable secondary conjunction.",
                evaluated_constraints=evaluated,
                estimated_post_maneuver_risk=post,
                estimated_fuel_cost=proposal.estimated_fuel_cost,
                secondary_risk_findings=secondary,
            )

        return ManeuverValidationResult(
            valid=True,
            reason_code="VALID",
            explanation="Maneuver satisfies configured safety and resource constraints.",
            evaluated_constraints=evaluated,
            estimated_post_maneuver_risk=post,
            estimated_fuel_cost=proposal.estimated_fuel_cost,
            secondary_risk_findings=secondary,
        )

    def apply_result_to_proposal(self, proposal, result):
        proposal.validation_status = ValidationStatus.VALID.value if result.valid else ValidationStatus.INVALID.value
        if result.valid:
            proposal.proposal_status = ManeuverStatus.VALIDATED.value
            proposal.acceptance_reason = result.explanation
        else:
            proposal.proposal_status = ManeuverStatus.REJECTED.value
            proposal.rejection_reason = result.reason_code
        return proposal

    def _invalid(self, reason_code, explanation, evaluated, proposal):
        return ManeuverValidationResult(
            valid=False,
            reason_code=reason_code,
            explanation=explanation,
            evaluated_constraints=evaluated,
            estimated_fuel_cost=proposal.estimated_fuel_cost,
        )
