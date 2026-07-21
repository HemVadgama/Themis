from copy import deepcopy
from math import sqrt

from src.maneuvers.model import ManeuverProposal
from src.risk.reassessment import minimum_pair_distance


def vector_magnitude(vector):
    return float(sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]))


class DeterministicManeuverGenerator:
    def __init__(self, max_delta_v_km_per_step=120.0, min_delta_v_km_per_step=20.0):
        self.max_delta_v_km_per_step = max_delta_v_km_per_step
        self.min_delta_v_km_per_step = min_delta_v_km_per_step

    def generate_candidates(self, agent_id, risk_event, trajectories, current_time, protocol_name, horizon_steps):
        candidates = []
        magnitudes = [
            self.min_delta_v_km_per_step,
            (self.min_delta_v_km_per_step + self.max_delta_v_km_per_step) / 2,
            self.max_delta_v_km_per_step,
        ]
        directions = [
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, -1.0),
        ]
        maneuver_index = 0

        for magnitude in magnitudes:
            for direction in directions:
                delta_v = (
                    direction[0] * magnitude,
                    direction[1] * magnitude,
                    direction[2] * magnitude,
                )
                post_trajectories = deepcopy(trajectories)
                execution_time = current_time + 1
                post_trajectories[agent_id] = trajectories[agent_id].with_impulse(execution_time, delta_v)
                expected = minimum_pair_distance(
                    post_trajectories,
                    risk_event.satellite_a,
                    risk_event.satellite_b,
                    execution_time + 1,
                    horizon_steps,
                )
                maneuver_index += 1
                candidates.append(
                    ManeuverProposal(
                        maneuver_id=f"{risk_event.risk_event_id}:{agent_id}:{maneuver_index}",
                        agent_id=agent_id,
                        risk_event_id=risk_event.risk_event_id,
                        proposal_time=current_time,
                        planned_execution_time=execution_time,
                        maneuver_frame="local_linear_velocity",
                        delta_v_magnitude_km_per_step=vector_magnitude(delta_v),
                        delta_v_vector_km_per_step=delta_v,
                        estimated_fuel_cost=vector_magnitude(delta_v),
                        expected_mission_disruption_score=vector_magnitude(delta_v) * 0.1,
                        expected_post_maneuver_separation_km=expected["minimum_distance_km"],
                        protocol=protocol_name,
                    )
                )

        return sorted(
            candidates,
            key=lambda proposal: (
                -(proposal.expected_post_maneuver_separation_km or 0.0),
                proposal.estimated_fuel_cost,
                proposal.maneuver_id,
            ),
        )

    def best_candidate(self, agent_id, risk_event, trajectories, current_time, protocol_name, horizon_steps):
        candidates = self.generate_candidates(
            agent_id,
            risk_event,
            trajectories,
            current_time,
            protocol_name,
            horizon_steps,
        )
        baseline = minimum_pair_distance(
            trajectories,
            risk_event.satellite_a,
            risk_event.satellite_b,
            current_time + 2,
            horizon_steps,
        )["minimum_distance_km"]

        for candidate in candidates:
            if candidate.expected_post_maneuver_separation_km is not None and candidate.expected_post_maneuver_separation_km > baseline:
                return candidate

        return None
