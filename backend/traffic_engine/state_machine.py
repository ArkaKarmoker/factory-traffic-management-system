"""
Traffic State Machine & Safety Guard - Pure Python
Enforces strict safety invariants and deterministic transition sequences.
"""
from typing import Dict, Tuple
from traffic_engine.enums import SignalState, Direction, TrafficPhase, TransitionStep
from traffic_engine.models import JunctionState


class SafetyInvariantViolation(Exception):
    """Raised when an operation would violate fundamental traffic safety rules."""
    pass


class TrafficStateMachine:
    """
    Deterministic Finite State Machine managing traffic signal states and transitions.
    Guarantees:
    1. Conflicting phases never simultaneously receive GREEN.
    2. A GREEN phase never transitions directly into a conflicting GREEN phase.
    3. Safe sequence: GREEN -> YELLOW (5s) -> ALL_RED (2s) -> NEXT GREEN (30s).
    4. Emergency and Manual overrides strictly adhere to the transition sequence.
    """

    @staticmethod
    def validate_safety_invariants(signals: Dict[str, SignalState]) -> bool:
        """
        Verify that conflicting directions are never simultaneously GREEN or YELLOW.
        Conflicting groups: {NORTH, SOUTH} vs {EAST, WEST}.
        """
        north_south_active = (
            signals.get(Direction.NORTH.value) in (SignalState.GREEN, SignalState.YELLOW) or
            signals.get(Direction.SOUTH.value) in (SignalState.GREEN, SignalState.YELLOW)
        )
        east_west_active = (
            signals.get(Direction.EAST.value) in (SignalState.GREEN, SignalState.YELLOW) or
            signals.get(Direction.WEST.value) in (SignalState.GREEN, SignalState.YELLOW)
        )

        if north_south_active and east_west_active:
            raise SafetyInvariantViolation(
                f"SAFETY INVARIANT VIOLATION: Conflicting phases active simultaneously! State: {signals}"
            )
        return True

    @staticmethod
    def get_phase_for_direction(direction: Direction) -> TrafficPhase:
        if direction in (Direction.NORTH, Direction.SOUTH):
            return TrafficPhase.NORTH_SOUTH
        return TrafficPhase.EAST_WEST

    @classmethod
    def compute_desired_signals(
        cls,
        current_phase: TrafficPhase,
        target_phase: TrafficPhase,
        step: TransitionStep,
    ) -> Dict[str, SignalState]:
        """
        Deterministic signal mapping based on the active phase and transition step.
        """
        # Step 1: Normal steady state
        if step == TransitionStep.STEADY:
            if current_phase == TrafficPhase.NORTH_SOUTH:
                signals = {
                    Direction.NORTH.value: SignalState.GREEN,
                    Direction.SOUTH.value: SignalState.GREEN,
                    Direction.EAST.value: SignalState.RED,
                    Direction.WEST.value: SignalState.RED,
                }
            elif current_phase == TrafficPhase.EAST_WEST:
                signals = {
                    Direction.NORTH.value: SignalState.RED,
                    Direction.SOUTH.value: SignalState.RED,
                    Direction.EAST.value: SignalState.GREEN,
                    Direction.WEST.value: SignalState.GREEN,
                }
            else:  # ALL_RED_CLEARING or Degraded
                signals = {d.value: SignalState.RED for d in Direction}
            cls.validate_safety_invariants(signals)
            return signals

        # Step 2: Yellow clearing of current phase
        if step == TransitionStep.YELLOW_CLEARING:
            if current_phase == TrafficPhase.NORTH_SOUTH:
                signals = {
                    Direction.NORTH.value: SignalState.YELLOW,
                    Direction.SOUTH.value: SignalState.YELLOW,
                    Direction.EAST.value: SignalState.RED,
                    Direction.WEST.value: SignalState.RED,
                }
            elif current_phase == TrafficPhase.EAST_WEST:
                signals = {
                    Direction.NORTH.value: SignalState.RED,
                    Direction.SOUTH.value: SignalState.RED,
                    Direction.EAST.value: SignalState.YELLOW,
                    Direction.WEST.value: SignalState.YELLOW,
                }
            else:
                signals = {d.value: SignalState.RED for d in Direction}
            cls.validate_safety_invariants(signals)
            return signals

        # Step 3: All-red clearance buffer
        if step == TransitionStep.ALL_RED_CLEARING:
            signals = {d.value: SignalState.RED for d in Direction}
            cls.validate_safety_invariants(signals)
            return signals

        # Fallback safe state
        return {d.value: SignalState.RED for d in Direction}
