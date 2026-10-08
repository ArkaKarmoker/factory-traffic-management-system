"""
Traffic Scheduling & Phase Selection Algorithm - Pure Python
Evaluates queues, vehicle priorities, waiting durations, and anti-starvation rules.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from traffic_engine.enums import Direction, TrafficPhase, VehicleType
from traffic_engine.models import VehicleItem


# Priority weights strictly matching section 4 & 5
VEHICLE_PRIORITY_WEIGHTS: Dict[VehicleType, float] = {
    VehicleType.EMERGENCY: 1000.0,
    VehicleType.TRUCK: 25.0,
    VehicleType.FORKLIFT: 15.0,
    VehicleType.EMPLOYEE_VEHICLE: 5.0,
}

# Starvation threshold in seconds
STARVATION_THRESHOLD_SECONDS = 45.0
STARVATION_PENALTY_BOOST = 80.0
WAITING_TIME_WEIGHT = 0.8  # points per second of waiting


class TrafficScheduler:
    """
    Computes priority scores for each traffic direction and selects the optimal next phase.
    """

    @classmethod
    def calculate_direction_score(
        cls,
        vehicles: List[VehicleItem],
        now: datetime,
    ) -> Tuple[float, bool]:
        """
        Calculates priority score for a single direction queue.
        Returns: (score, has_emergency)
        """
        total_score = 0.0
        has_emergency = False

        for v in vehicles:
            p_weight = VEHICLE_PRIORITY_WEIGHTS.get(v.vehicle_type, 5.0)
            wait_seconds = max(0.0, (now - v.arrived_at).total_seconds())

            # Base score + waiting time factor
            score = p_weight + (wait_seconds * WAITING_TIME_WEIGHT)

            # Anti-starvation protection: boost vehicles waiting past threshold
            if wait_seconds >= STARVATION_THRESHOLD_SECONDS:
                score += STARVATION_PENALTY_BOOST

            if v.vehicle_type == VehicleType.EMERGENCY:
                has_emergency = True
                score += 5000.0  # Dominant emergency preemption score

            total_score += score

        return total_score, has_emergency

    @classmethod
    def evaluate_phases(
        cls,
        queues: Dict[Direction, List[VehicleItem]],
        now: Optional[datetime] = None,
    ) -> Dict[TrafficPhase, float]:
        """
        Computes composite scores for NORTH_SOUTH vs EAST_WEST.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        north_score, north_em = cls.calculate_direction_score(queues.get(Direction.NORTH, []), now)
        south_score, south_em = cls.calculate_direction_score(queues.get(Direction.SOUTH, []), now)
        east_score, east_em = cls.calculate_direction_score(queues.get(Direction.EAST, []), now)
        west_score, west_em = cls.calculate_direction_score(queues.get(Direction.WEST, []), now)

        ns_phase_score = north_score + south_score
        ew_phase_score = east_score + west_score

        return {
            TrafficPhase.NORTH_SOUTH: round(ns_phase_score, 2),
            TrafficPhase.EAST_WEST: round(ew_phase_score, 2),
        }

    @classmethod
    def select_next_phase(
        cls,
        current_phase: TrafficPhase,
        queues: Dict[Direction, List[VehicleItem]],
        phase_elapsed_seconds: float,
        min_green_seconds: float = 10.0,
        normal_green_seconds: float = 30.0,
        max_green_seconds: float = 60.0,
        now: Optional[datetime] = None,
    ) -> TrafficPhase:
        """
        Selects the optimal phase to serve next according to Sections 3, 5, 6, and 7.
        - Evaluates vehicle priorities, waiting duration, and anti-starvation.
        - Enforces minimum green dwell (hysteresis) to prevent signal jitter.
        - Automatically cycles phases when normal green duration (~30s) elapses.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Check for emergency preemption first (Section 7)
        east_emergency = any(v.vehicle_type == VehicleType.EMERGENCY for v in queues.get(Direction.EAST, []))
        west_emergency = any(v.vehicle_type == VehicleType.EMERGENCY for v in queues.get(Direction.WEST, []))
        north_emergency = any(v.vehicle_type == VehicleType.EMERGENCY for v in queues.get(Direction.NORTH, []))
        south_emergency = any(v.vehicle_type == VehicleType.EMERGENCY for v in queues.get(Direction.SOUTH, []))

        current_has_emergency = (
            (north_emergency or south_emergency) if current_phase == TrafficPhase.NORTH_SOUTH
            else (east_emergency or west_emergency)
        )
        opposing_has_emergency = (
            (east_emergency or west_emergency) if current_phase == TrafficPhase.NORTH_SOUTH
            else (north_emergency or south_emergency)
        )

        # Competing Emergency Policy (Section 7 & 17):
        # If current phase is actively serving an emergency, HOLD current phase!
        # An in-progress emergency clearance MUST NOT be aborted mid-flight for a competing emergency
        # until the minimum emergency clearance time (15s) has elapsed.
        if current_has_emergency:
            if phase_elapsed_seconds < 15.0 or not opposing_has_emergency:
                return current_phase

        # If opposing phase has an emergency (and current has none or completed minimum dwell), trigger switch
        if opposing_has_emergency:
            return (
                TrafficPhase.EAST_WEST if current_phase == TrafficPhase.NORTH_SOUTH
                else TrafficPhase.NORTH_SOUTH
            )

        # Standard minimum green holding period to avoid jitter (Section 6)
        if phase_elapsed_seconds < min_green_seconds:
            return current_phase

        scores = cls.evaluate_phases(queues, now)
        ns_score = scores[TrafficPhase.NORTH_SOUTH]
        ew_score = scores[TrafficPhase.EAST_WEST]

        opposing_phase = (
            TrafficPhase.EAST_WEST if current_phase == TrafficPhase.NORTH_SOUTH
            else TrafficPhase.NORTH_SOUTH
        )
        current_score = ns_score if current_phase == TrafficPhase.NORTH_SOUTH else ew_score
        opposing_score = ew_score if current_phase == TrafficPhase.NORTH_SOUTH else ns_score

        # Rule 1: Dynamic priority switch before normal green expiration:
        # If opposing score is meaningfully higher (> 10% delta) or current is empty while opposing is waiting
        if opposing_score > current_score * 1.1 or (current_score == 0 and opposing_score > 0):
            return opposing_phase

        # Rule 2: Automatic cycle / Normal green duration elapsed (~30s base cycle, Section 3 & 6):
        if phase_elapsed_seconds >= normal_green_seconds:
            # If opposing direction has any waiting traffic, yield to opposing
            if opposing_score > 0:
                return opposing_phase
            # If both queues are empty (idle intersection), cycle to alternate phase every ~30s
            if current_score == 0 and opposing_score == 0:
                return opposing_phase
            # If current phase still has traffic but opposing is 0, extend green up to max_green (avoid stopping cars for empty road)
            if phase_elapsed_seconds >= max_green_seconds:
                return opposing_phase

        return current_phase

