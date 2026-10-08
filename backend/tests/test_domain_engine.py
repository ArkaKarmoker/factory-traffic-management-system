"""
Unit Tests for Pure Python Traffic Domain Engine
Tests Safety Invariants, Finite State Machine, and Scheduling Priority without DB/HTTP.
"""
import pytest
from datetime import datetime, timezone, timedelta

from traffic_engine.enums import (
    SignalState,
    Direction,
    TrafficPhase,
    VehicleType,
    TransitionStep,
)
from traffic_engine.models import VehicleItem
from traffic_engine.state_machine import TrafficStateMachine, SafetyInvariantViolation
from traffic_engine.scheduler import TrafficScheduler


def test_safety_invariant_raises_on_conflicting_greens():
    """
    CRITICAL SAFETY TEST: Conflicting directions (e.g. North and East) must NEVER be green together.
    """
    conflicting_signals = {
        Direction.NORTH.value: SignalState.GREEN,
        Direction.SOUTH.value: SignalState.GREEN,
        Direction.EAST.value: SignalState.GREEN,  # CONFLICT!
        Direction.WEST.value: SignalState.RED,
    }
    with pytest.raises(SafetyInvariantViolation):
        TrafficStateMachine.validate_safety_invariants(conflicting_signals)


def test_safety_invariant_passes_on_valid_phases():
    """Valid non-conflicting pairs must pass validation."""
    ns_signals = {
        Direction.NORTH.value: SignalState.GREEN,
        Direction.SOUTH.value: SignalState.GREEN,
        Direction.EAST.value: SignalState.RED,
        Direction.WEST.value: SignalState.RED,
    }
    assert TrafficStateMachine.validate_safety_invariants(ns_signals) is True

    ew_signals = {
        Direction.NORTH.value: SignalState.RED,
        Direction.SOUTH.value: SignalState.RED,
        Direction.EAST.value: SignalState.GREEN,
        Direction.WEST.value: SignalState.GREEN,
    }
    assert TrafficStateMachine.validate_safety_invariants(ew_signals) is True


def test_deterministic_transition_steps():
    """
    Verify the mandatory sequence: GREEN -> YELLOW -> ALL_RED -> TARGET GREEN
    """
    # 1. Steady NS
    signals_steady = TrafficStateMachine.compute_desired_signals(
        TrafficPhase.NORTH_SOUTH, TrafficPhase.EAST_WEST, TransitionStep.STEADY
    )
    assert signals_steady[Direction.NORTH.value] == SignalState.GREEN
    assert signals_steady[Direction.EAST.value] == SignalState.RED

    # 2. Yellow clearing
    signals_yellow = TrafficStateMachine.compute_desired_signals(
        TrafficPhase.NORTH_SOUTH, TrafficPhase.EAST_WEST, TransitionStep.YELLOW_CLEARING
    )
    assert signals_yellow[Direction.NORTH.value] == SignalState.YELLOW
    assert signals_yellow[Direction.SOUTH.value] == SignalState.YELLOW
    assert signals_yellow[Direction.EAST.value] == SignalState.RED

    # 3. All red clearing
    signals_all_red = TrafficStateMachine.compute_desired_signals(
        TrafficPhase.NORTH_SOUTH, TrafficPhase.EAST_WEST, TransitionStep.ALL_RED_CLEARING
    )
    assert all(state == SignalState.RED for state in signals_all_red.values())


def test_priority_scheduling_emergency_beats_normal():
    """
    Verify that an EMERGENCY vehicle dominates scheduling over regular vehicles.
    """
    now = datetime.now(timezone.utc)
    queues = {
        Direction.NORTH: [
            VehicleItem(vehicle_id="VH-1", vehicle_type=VehicleType.FORKLIFT, direction=Direction.NORTH, sequence_no=1, arrived_at=now),
            VehicleItem(vehicle_id="VH-2", vehicle_type=VehicleType.TRUCK, direction=Direction.NORTH, sequence_no=2, arrived_at=now),
        ],
        Direction.SOUTH: [],
        Direction.EAST: [
            VehicleItem(vehicle_id="EM-1", vehicle_type=VehicleType.EMERGENCY, direction=Direction.EAST, sequence_no=1, arrived_at=now),
        ],
        Direction.WEST: [],
    }

    selected = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.NORTH_SOUTH,
        queues=queues,
        phase_elapsed_seconds=30.0,
        now=now,
    )
    assert selected == TrafficPhase.EAST_WEST


def test_starvation_protection():
    """
    Verify that vehicles waiting past the starvation threshold receive a substantial score boost.
    """
    now = datetime.now(timezone.utc)
    old_arrival = now - timedelta(seconds=60)  # > 45s threshold
    fresh_arrival = now

    old_vehicle = VehicleItem(vehicle_id="OLD-1", vehicle_type=VehicleType.EMPLOYEE_VEHICLE, direction=Direction.EAST, sequence_no=1, arrived_at=old_arrival)
    fresh_vehicle = VehicleItem(vehicle_id="NEW-1", vehicle_type=VehicleType.EMPLOYEE_VEHICLE, direction=Direction.NORTH, sequence_no=2, arrived_at=fresh_arrival)

    old_score, _ = TrafficScheduler.calculate_direction_score([old_vehicle], now)
    fresh_score, _ = TrafficScheduler.calculate_direction_score([fresh_vehicle], now)

    assert old_score > fresh_score * 5.0


def test_automatic_cycle_empty_queues():
    """
    SECTION 3 & 6 REQUIREMENT: In automatic mode with empty queues (idle intersection),
    signals must cycle periodically every ~30s instead of freezing forever on one phase.
    """
    now = datetime.now(timezone.utc)
    empty_queues = {d: [] for d in Direction}

    # 1. Under 30s elapsed -> holds current phase
    holding_ns = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.NORTH_SOUTH,
        queues=empty_queues,
        phase_elapsed_seconds=15.0,
        normal_green_seconds=30.0,
        now=now,
    )
    assert holding_ns == TrafficPhase.NORTH_SOUTH

    # 2. At or over 30s elapsed -> automatically alternates to opposing phase (EAST_WEST)
    cycled_to_ew = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.NORTH_SOUTH,
        queues=empty_queues,
        phase_elapsed_seconds=30.0,
        normal_green_seconds=30.0,
        now=now,
    )
    assert cycled_to_ew == TrafficPhase.EAST_WEST

    # 3. At or over 30s elapsed on EAST_WEST -> automatically alternates back to NORTH_SOUTH
    cycled_to_ns = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.EAST_WEST,
        queues=empty_queues,
        phase_elapsed_seconds=30.0,
        normal_green_seconds=30.0,
        now=now,
    )
    assert cycled_to_ns == TrafficPhase.NORTH_SOUTH


def test_automatic_cycle_opposing_traffic_fair_sharing():
    """
    SECTION 5 & 6 REQUIREMENT: When opposing traffic is waiting, once normal green (30s) expires,
    the system must transition to the opposing phase to prevent starvation.
    """
    now = datetime.now(timezone.utc)
    queues = {
        Direction.NORTH: [
            VehicleItem(vehicle_id="VH-NS-1", vehicle_type=VehicleType.FORKLIFT, direction=Direction.NORTH, sequence_no=1, arrived_at=now),
        ],
        Direction.SOUTH: [],
        Direction.EAST: [
            VehicleItem(vehicle_id="VH-EW-1", vehicle_type=VehicleType.FORKLIFT, direction=Direction.EAST, sequence_no=2, arrived_at=now),
        ],
        Direction.WEST: [],
    }

    # During green (t < 30s), holds current green phase to avoid rapid jitter
    holding = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.NORTH_SOUTH,
        queues=queues,
        phase_elapsed_seconds=20.0,
        normal_green_seconds=30.0,
        now=now,
    )
    assert holding == TrafficPhase.NORTH_SOUTH

    # After normal green (t >= 30s), yields to waiting opposing phase
    switched = TrafficScheduler.select_next_phase(
        current_phase=TrafficPhase.NORTH_SOUTH,
        queues=queues,
        phase_elapsed_seconds=30.0,
        normal_green_seconds=30.0,
        now=now,
    )
    assert switched == TrafficPhase.EAST_WEST

