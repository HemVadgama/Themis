from dataclasses import dataclass


Vector3 = tuple[float, float, float]


def add_vectors(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def scale_vector(vector: Vector3, scalar: float) -> Vector3:
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


@dataclass
class LinearTrajectory:
    satellite_id: str
    reference_time: int
    position_km: Vector3
    velocity_km_per_step: Vector3
    trajectory_kind: str = "simulated_truth"

    def position_at(self, time_step: int) -> Vector3:
        elapsed = time_step - self.reference_time
        return add_vectors(self.position_km, scale_vector(self.velocity_km_per_step, elapsed))

    def position_record_at(self, time_step: int) -> dict:
        x_km, y_km, z_km = self.position_at(time_step)
        return {
            "satellite": self.satellite_id,
            "time": str(time_step),
            "x_km": x_km,
            "y_km": y_km,
            "z_km": z_km,
        }

    def with_impulse(self, time_step: int, delta_v_km_per_step: Vector3) -> "LinearTrajectory":
        new_position = self.position_at(time_step)
        new_velocity = add_vectors(self.velocity_km_per_step, delta_v_km_per_step)
        return LinearTrajectory(
            satellite_id=self.satellite_id,
            reference_time=time_step,
            position_km=new_position,
            velocity_km_per_step=new_velocity,
            trajectory_kind="post_maneuver",
        )

    def to_dict(self) -> dict:
        return {
            "satellite_id": self.satellite_id,
            "reference_time": self.reference_time,
            "position_km": list(self.position_km),
            "velocity_km_per_step": list(self.velocity_km_per_step),
            "trajectory_kind": self.trajectory_kind,
        }
