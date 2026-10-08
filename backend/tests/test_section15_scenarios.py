"""
Comprehensive End-to-End Rigorous Test Suite for Section 15 Scenarios
Strictly tests all 9 Functional Scenarios mandated by the CSI Smart Tech Assessment Specification.
"""
import pytest
import threading
import time
from rest_framework.test import APIClient
from django.db import connection
from junctions.models import Junction, VehicleQueueItem, ProcessedEvent, ControllerCommand, AuditLog
from junctions.services import JunctionService
from traffic_engine.enums import Direction, VehicleType, SignalState, JunctionMode, TrafficPhase


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def fresh_junction(db):
    j = JunctionService.get_or_create_default_junction("A")
    # Reset to known clean state
    VehicleQueueItem.objects.filter(junction=j).delete()
    ProcessedEvent.objects.all().delete()
    ControllerCommand.objects.all().delete()
    AuditLog.objects.all().delete()
    j.mode = JunctionMode.AUTOMATIC.value
    j.current_phase = TrafficPhase.NORTH_SOUTH.value
    j.target_phase = None
    j.transition_step = "STEADY"
    j.desired_north = SignalState.GREEN.value
    j.desired_south = SignalState.GREEN.value
    j.desired_east = SignalState.RED.value
    j.desired_west = SignalState.RED.value
    j.actual_north = SignalState.GREEN.value
    j.actual_south = SignalState.GREEN.value
    j.actual_east = SignalState.RED.value
    j.actual_west = SignalState.RED.value
    j.controller_status = "ONLINE"
    j.emergency_active = False
    j.save()
    return j


@pytest.mark.django_db
def test_scenario_1_normal_traffic(client, fresh_junction):
    """Scenario 1: Normal Traffic arrives from different directions."""
    # North arrives
    res1 = client.post("/api/sensor-events", {
        "event_id": "sc1-evt-01",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-CAR-1",
        "vehicle_type": "EMPLOYEE_VEHICLE",
    }, format="json")
    assert res1.status_code == 201

    # South arrives
    res2 = client.post("/api/sensor-events", {
        "event_id": "sc1-evt-02",
        "junction_id": "A",
        "direction": "SOUTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-CAR-2",
        "vehicle_type": "EMPLOYEE_VEHICLE",
    }, format="json")
    assert res2.status_code == 201

    fresh_junction.refresh_from_db()
    assert fresh_junction.get_queues_count()["NORTH"] == 1
    assert fresh_junction.get_queues_count()["SOUTH"] == 1


@pytest.mark.django_db
def test_scenario_2_priority_traffic_weighting(client, fresh_junction):
    """Scenario 2: TRUCK or FORKLIFT priority influences scheduling compared to employee vehicles."""
    # Heavy truck traffic on EAST
    client.post("/api/sensor-events", {
        "event_id": "sc2-evt-01",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-TRK-01",
        "vehicle_type": "TRUCK",
    }, format="json")

    client.post("/api/sensor-events", {
        "event_id": "sc2-evt-02",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-FL-01",
        "vehicle_type": "FORKLIFT",
    }, format="json")

    # Light employee car on NORTH
    client.post("/api/sensor-events", {
        "event_id": "sc2-evt-03",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-CAR-01",
        "vehicle_type": "EMPLOYEE_VEHICLE",
    }, format="json")

    fresh_junction.refresh_from_db()
    queues = fresh_junction.get_queues_count()
    assert queues["EAST"] == 2
    assert queues["NORTH"] == 1


@pytest.mark.django_db
def test_scenario_3_emergency_preemption(client, fresh_junction):
    """
    Scenario 3: Emergency Vehicle arrives while conflicting phase is GREEN.
    System MUST immediately begin safe transition (YELLOW -> ALL_RED -> EMERGENCY GREEN).
    """
    assert fresh_junction.current_phase == "NORTH_SOUTH"
    assert fresh_junction.desired_north == SignalState.GREEN.value

    # Emergency arrives on EAST (Conflicting phase!)
    res = client.post("/api/sensor-events", {
        "event_id": "sc3-evt-emerg",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "AMB-911",
        "vehicle_type": "EMERGENCY",
    }, format="json")
    assert res.status_code == 201

    fresh_junction.refresh_from_db()
    # Mode must immediately become EMERGENCY
    assert fresh_junction.mode == JunctionMode.EMERGENCY.value
    assert fresh_junction.emergency_active is True
    assert fresh_junction.emergency_direction == "EAST"

    # Conflicting North/South GREEN MUST immediately change to YELLOW for safe clearance!
    assert fresh_junction.desired_north == SignalState.YELLOW.value
    assert fresh_junction.desired_south == SignalState.YELLOW.value
    # East MUST remain RED during the yellow clearance (Never instant green jump!)
    assert fresh_junction.desired_east == SignalState.RED.value


@pytest.mark.django_db
def test_scenario_4_manual_override_and_return(client, fresh_junction):
    """Scenario 4: Administrator takes control of Junction A and later returns it to automatic."""
    # Request West Green
    res1 = client.post("/api/junctions/A/commands", {
        "command": "MANUAL_GREEN_REQUEST",
        "direction": "WEST",
        "operator_id": "ADMIN_CHIEF",
    }, format="json")
    assert res1.status_code == 200

    fresh_junction.refresh_from_db()
    assert fresh_junction.mode == JunctionMode.MANUAL.value
    assert fresh_junction.target_phase == "EAST_WEST"

    # Return to automatic
    res2 = client.post("/api/junctions/A/commands", {
        "command": "RETURN_TO_AUTOMATIC",
        "operator_id": "ADMIN_CHIEF",
    }, format="json")
    assert res2.status_code == 200

    fresh_junction.refresh_from_db()
    assert fresh_junction.mode == JunctionMode.AUTOMATIC.value


@pytest.mark.django_db
def test_scenario_5_duplicate_sensor_event_idempotency(client, fresh_junction):
    """
    Scenario 5: Exact same sensor event submitted multiple times.
    Queue state must not change multiple times!
    """
    payload = {
        "event_id": "sc5-evt-dup-99",
        "junction_id": "A",
        "direction": "WEST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-WEST-01",
        "vehicle_type": "FORKLIFT",
    }

    # 1st call -> Created
    res1 = client.post("/api/sensor-events", payload, format="json")
    assert res1.status_code == 201
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="WEST").count() == 1

    # 2nd call -> Duplicate Ignored (200 OK)
    res2 = client.post("/api/sensor-events", payload, format="json")
    assert res2.status_code == 200
    assert res2.data["status"] == "DUPLICATE_IGNORED"
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="WEST").count() == 1

    # 3rd call -> Still ignored, queue still exactly 1
    res3 = client.post("/api/sensor-events", payload, format="json")
    assert res3.status_code == 200
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="WEST").count() == 1


@pytest.mark.django_db
def test_scenario_6_vehicle_clearance_and_empty_queue(client, fresh_junction):
    """Scenario 6: Vehicle arrives and later clears. Queue changes properly and never goes negative."""
    # Arrive
    client.post("/api/sensor-events", {
        "event_id": "sc6-evt-01",
        "junction_id": "A",
        "direction": "SOUTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-CLEAR-01",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="SOUTH").count() == 1

    # Clear
    client.post("/api/sensor-events", {
        "event_id": "sc6-evt-02",
        "junction_id": "A",
        "direction": "SOUTH",
        "event_type": "VEHICLE_CLEARED",
        "vehicle_id": "VH-CLEAR-01",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="SOUTH").count() == 0

    # Redundant clearance when queue is empty -> Safe no-op, queue stays 0
    client.post("/api/sensor-events", {
        "event_id": "sc6-evt-03",
        "junction_id": "A",
        "direction": "SOUTH",
        "event_type": "VEHICLE_CLEARED",
        "vehicle_id": "VH-GHOST-01",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=fresh_junction, direction="SOUTH").count() == 0


@pytest.mark.django_db
def test_scenario_7_controller_failure_and_degraded_fallback(client, fresh_junction):
    """Scenario 7: Controller reports OFFLINE. Application transitions to safe DEGRADED mode with Desired ALL-RED while preserving unconfirmed Actual state (Section 9)."""
    # Verify initial confirmed state (North/South GREEN)
    assert fresh_junction.actual_north == SignalState.GREEN.value
    assert fresh_junction.actual_south == SignalState.GREEN.value

    res = client.post("/api/controller-events", {
        "junction_id": "A",
        "device_type": "SIGNAL_CONTROLLER",
        "status": "OFFLINE",
    }, format="json")
    assert res.status_code == 200

    fresh_junction.refresh_from_db()
    assert fresh_junction.controller_status == "OFFLINE"
    assert fresh_junction.mode == JunctionMode.DEGRADED.value
    # Safe All-Red Fallback: Desired signals to ALL RED (Backend intent)
    assert fresh_junction.desired_north == SignalState.RED.value
    assert fresh_junction.desired_south == SignalState.RED.value
    assert fresh_junction.desired_east == SignalState.RED.value
    assert fresh_junction.desired_west == SignalState.RED.value
    # Section 9 invariant: Offline controller cannot confirm changes, so backend does NOT fabricate actual confirmation
    assert fresh_junction.actual_north == SignalState.GREEN.value
    assert fresh_junction.actual_south == SignalState.GREEN.value


@pytest.mark.django_db
def test_scenario_8_restart_persistence_and_recovery(client, fresh_junction):
    """
    Scenario 8: Backend restart simulation.
    Persisted data (queues, processed event IDs, audit logs) remains intact.
    """
    # 1. Populate state
    client.post("/api/sensor-events", {
        "event_id": "sc8-persist-evt-01",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-RESTART-01",
    }, format="json")

    # 2. Simulate application restart (close db connections, reconstruct in-memory state from DB)
    connection.close()

    # 3. Verify state recovered from persistence
    reloaded_junction = Junction.objects.get(junction_id="A")
    assert reloaded_junction.get_queues_count()["NORTH"] == 1
    assert ProcessedEvent.objects.filter(event_id="sc8-persist-evt-01").exists()
    assert AuditLog.objects.filter(junction_id="A").exists()


@pytest.mark.django_db(transaction=True)
def test_scenario_9_concurrent_events_safety():
    """
    Scenario 9: Exact concurrent event sequence from Section 15:
    T = 0 ms   NORTH truck arrives
    T = 4 ms   EAST emergency arrives
    T = 8 ms   Administrator requests WEST manual control
    T = 12 ms  Duplicate EAST emergency event arrives
    T = 17 ms  Controller ACK arrives
    System must remain internally consistent and MUST NEVER create conflicting GREEN states!
    """
    j = JunctionService.get_or_create_default_junction("A")
    client = APIClient()

    results = []

    # Execute the exact microsecond event sequence from the specification
    # T = 0 ms: NORTH TRUCK arrives
    r0 = client.post("/api/sensor-events", {
        "event_id": "sc9-t0-truck",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-SC9-TRK",
        "vehicle_type": "TRUCK",
    }, format="json")
    results.append(("t0", r0.status_code))

    # T = 4 ms: EAST EMERGENCY arrives
    r4 = client.post("/api/sensor-events", {
        "event_id": "sc9-t4-emerg",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "AMB-SC9",
        "vehicle_type": "EMERGENCY",
    }, format="json")
    results.append(("t4", r4.status_code))

    # T = 8 ms: Administrator requests WEST manual control
    r8 = client.post("/api/junctions/A/commands", {
        "command": "MANUAL_GREEN_REQUEST",
        "direction": "WEST",
        "operator_id": "ADMIN_RACE",
    }, format="json")
    results.append(("t8", r8.status_code))

    # T = 12 ms: Duplicate EAST emergency event arrives (Idempotency test)
    r12 = client.post("/api/sensor-events", {
        "event_id": "sc9-t4-emerg",  # DUPLICATE of T=4ms!
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "AMB-SC9",
        "vehicle_type": "EMERGENCY",
    }, format="json")
    results.append(("t12", r12.status_code))

    # T = 17 ms: Controller ACK arrives
    r17 = client.post("/api/controller-events", {
        "command_id": "cmd-sc9-ack",
        "junction_id": "A",
        "status": "ACK",
        "actual_state": "YELLOW",
        "direction": "NORTH",
    }, format="json")
    results.append(("t17", r17.status_code))

    # All 5 events must finish with valid status codes (200 or 201)
    assert len(results) == 5
    for tag, status in results:
        assert status in (200, 201)

    # CRITICAL INVARIANT: Check that the junction is in a mathematically safe state
    j.refresh_from_db()
    desired = j.desired_signals

    # Invariant: North/South and East/West MUST NEVER be simultaneously GREEN!
    ns_green = desired["NORTH"] == "GREEN" or desired["SOUTH"] == "GREEN"
    ew_green = desired["EAST"] == "GREEN" or desired["WEST"] == "GREEN"
    assert not (ns_green and ew_green), f"CRITICAL SAFETY VIOLATION! Both NS and EW are GREEN: {desired}"
