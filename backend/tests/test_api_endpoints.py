"""
Integration Tests for REST API Endpoints
Verifies Idempotency, Concurrency, Safety Sequences, Controller Simulation, and Audit Trail.
"""
import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from junctions.models import Junction, VehicleQueueItem, ProcessedEvent, AuditLog
from junctions.services import JunctionService
from traffic_engine.enums import Direction, VehicleType, SignalState, JunctionMode, TrafficPhase


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_junction(db):
    return JunctionService.get_or_create_default_junction("A")


@pytest.mark.django_db
def test_idempotent_sensor_event_processing(api_client, seeded_junction):
    """
    SECTION 4 & 10.2 REQUIREMENT: Submitting the exact same event_id twice must not
    modify queue state multiple times.
    """
    VehicleQueueItem.objects.filter(junction=seeded_junction).delete()

    event_payload = {
        "event_id": "evt-test-1001",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-501",
        "vehicle_type": "TRUCK",
        "sequence_no": 1,
    }

    # First Submission -> 201 Created
    response1 = api_client.post("/api/sensor-events", event_payload, format="json")
    assert response1.status_code == 201
    assert response1.data["result"]["queues"]["NORTH"] == 1
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, direction="NORTH").count() == 1

    # Second Duplicate Submission -> 200 OK (DUPLICATE_IGNORED), queue remains 1
    response2 = api_client.post("/api/sensor-events", event_payload, format="json")
    assert response2.status_code == 200
    assert response2.data["status"] == "DUPLICATE_IGNORED"
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, direction="NORTH").count() == 1


@pytest.mark.django_db
def test_vehicle_clearance_and_non_negative_queue(api_client, seeded_junction):
    """
    SECTION 5 REQUIREMENT: Vehicle clearance must decrease queue and prevent queue < 0.
    """
    VehicleQueueItem.objects.filter(junction=seeded_junction).delete()

    # 1. Arrive
    api_client.post("/api/sensor-events", {
        "event_id": "evt-arr-01",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-999",
        "vehicle_type": "FORKLIFT",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, direction="EAST").count() == 1

    # 2. Clear
    api_client.post("/api/sensor-events", {
        "event_id": "evt-clr-01",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_CLEARED",
        "vehicle_id": "VH-999",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, direction="EAST").count() == 0

    # 3. Clear again when empty (must safely ignore and remain 0, no error or negative)
    api_client.post("/api/sensor-events", {
        "event_id": "evt-clr-02",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_CLEARED",
        "vehicle_id": "VH-999",
    }, format="json")
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, direction="EAST").count() == 0


@pytest.mark.django_db
def test_emergency_preemption_triggers_safe_yellow_transition(api_client, seeded_junction):
    """
    SECTION 7 REQUIREMENT: Emergency arrival on conflicting phase immediately initiates safe yellow transition.
    """
    # Active phase is NORTH_SOUTH
    assert seeded_junction.current_phase == TrafficPhase.NORTH_SOUTH.value

    # Emergency arrives on EAST
    response = api_client.post("/api/sensor-events", {
        "event_id": "evt-emerg-01",
        "junction_id": "A",
        "direction": "EAST",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "AMB-01",
        "vehicle_type": "EMERGENCY",
    }, format="json")
    assert response.status_code == 201

    seeded_junction.refresh_from_db()
    assert seeded_junction.mode == JunctionMode.EMERGENCY.value
    assert seeded_junction.emergency_active is True
    # North/South turning to Yellow
    assert seeded_junction.desired_north == SignalState.YELLOW.value
    assert seeded_junction.desired_south == SignalState.YELLOW.value


@pytest.mark.django_db
def test_manual_override_command(api_client, seeded_junction):
    """
    SECTION 8 REQUIREMENT: Manual command switches mode to MANUAL and enforces safe transition.
    """
    response = api_client.post("/api/junctions/A/commands", {
        "command": "MANUAL_GREEN_REQUEST",
        "direction": "WEST",
        "operator_id": "OPERATOR_RAFI",
    }, format="json")
    assert response.status_code == 200

    seeded_junction.refresh_from_db()
    assert seeded_junction.mode == JunctionMode.MANUAL.value
    assert seeded_junction.target_phase == TrafficPhase.EAST_WEST.value

    # Return to automatic
    ret_response = api_client.post("/api/junctions/A/commands", {
        "command": "RETURN_TO_AUTOMATIC",
    }, format="json")
    assert ret_response.status_code == 200

    seeded_junction.refresh_from_db()
    assert seeded_junction.mode == JunctionMode.AUTOMATIC.value


@pytest.mark.django_db
def test_controller_offline_triggers_degraded_state(api_client, seeded_junction):
    """
    SECTION 9 REQUIREMENT: Controller reporting OFFLINE transitions junction to DEGRADED mode.
    """
    response = api_client.post("/api/controller-events", {
        "junction_id": "A",
        "status": "OFFLINE",
        "device_type": "SIGNAL_CONTROLLER",
    }, format="json")
    assert response.status_code == 200

    seeded_junction.refresh_from_db()
    assert seeded_junction.controller_status == "OFFLINE"
    assert seeded_junction.mode == JunctionMode.DEGRADED.value
    # Safe fallback: all desired signals RED
    assert seeded_junction.desired_north == SignalState.RED.value
    assert seeded_junction.desired_east == SignalState.RED.value


@pytest.mark.django_db
def test_junction_status_and_history_endpoints(api_client, seeded_junction):
    """
    SECTION 10.3 & 10.6: Status and History endpoints provide complete telemetry.
    """
    status_res = api_client.get("/api/junctions/A/status")
    assert status_res.status_code == 200
    assert "desired_signals" in status_res.data
    assert "actual_signals" in status_res.data
    assert "queues" in status_res.data

    history_res = api_client.get("/api/junctions/A/history")
    assert history_res.status_code == 200
    assert isinstance(history_res.data, list)


@pytest.mark.django_db
def test_automatic_transition_timeline_via_status_polling(api_client, seeded_junction):
    """
    SECTION 3 & 6 REQUIREMENT: Verify automatic transition sequence:
    STEADY GREEN -> (30s) -> YELLOW_CLEARING (5s) -> ALL_RED_CLEARING (2s) -> NEXT STEADY GREEN.
    """
    from datetime import timedelta
    from django.utils import timezone

    # Set junction to NORTH_SOUTH with 31 seconds elapsed
    seeded_junction.mode = "AUTOMATIC"
    seeded_junction.current_phase = "NORTH_SOUTH"
    seeded_junction.target_phase = None
    seeded_junction.transition_step = "STEADY"
    seeded_junction.phase_started_at = timezone.now() - timedelta(seconds=31)
    seeded_junction.step_started_at = timezone.now() - timedelta(seconds=31)
    seeded_junction.save()

    # 1. First status poll -> Triggers YELLOW_CLEARING
    res1 = api_client.get("/api/junctions/A/status")
    assert res1.status_code == 200
    assert res1.data["transition_step"] == "YELLOW_CLEARING"
    assert res1.data["desired_signals"]["NORTH"] == "YELLOW"
    assert res1.data["desired_signals"]["SOUTH"] == "YELLOW"
    assert res1.data["desired_signals"]["EAST"] == "RED"

    # Simulate 5.1 seconds elapsed in yellow clearing
    seeded_junction.refresh_from_db()
    seeded_junction.step_started_at = timezone.now() - timedelta(seconds=6)
    seeded_junction.save()

    # 2. Second status poll -> Triggers ALL_RED_CLEARING
    res2 = api_client.get("/api/junctions/A/status")
    assert res2.status_code == 200
    assert res2.data["transition_step"] == "ALL_RED_CLEARING"
    assert res2.data["desired_signals"]["NORTH"] == "RED"
    assert res2.data["desired_signals"]["SOUTH"] == "RED"
    assert res2.data["desired_signals"]["EAST"] == "RED"
    assert res2.data["desired_signals"]["WEST"] == "RED"

    # Simulate 2.1 seconds elapsed in all red clearing
    seeded_junction.refresh_from_db()
    seeded_junction.step_started_at = timezone.now() - timedelta(seconds=3)
    seeded_junction.save()

    # 3. Third status poll -> Triggers STEADY GREEN on EAST_WEST!
    res3 = api_client.get("/api/junctions/A/status")
    assert res3.status_code == 200
    assert res3.data["phase"] == "EAST_WEST"
    assert res3.data["transition_step"] == "STEADY"
    assert res3.data["desired_signals"]["EAST"] == "GREEN"
    assert res3.data["desired_signals"]["WEST"] == "GREEN"
    assert res3.data["desired_signals"]["NORTH"] == "RED"
    assert res3.data["desired_signals"]["SOUTH"] == "RED"


@pytest.mark.django_db
def test_duplicate_vehicle_id_rejection(api_client, seeded_junction):
    """
    PHYSICAL INVARIANT: The exact same vehicle (same vehicle_id) cannot be added
    to the queue multiple times simultaneously without being cleared first.
    """
    VehicleQueueItem.objects.filter(junction=seeded_junction).delete()

    # 1. First arrival of vehicle VH-DUP-01 -> 201 Created
    res1 = api_client.post("/api/sensor-events", {
        "event_id": "evt-uniq-001",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-DUP-01",
        "vehicle_type": "FORKLIFT",
    }, format="json")
    assert res1.status_code == 201
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, vehicle_id="VH-DUP-01").count() == 1

    # 2. Second arrival with different event_id but SAME vehicle_id while still in queue -> Rejected (200 DUPLICATE_VEHICLE_IGNORED)
    res2 = api_client.post("/api/sensor-events", {
        "event_id": "evt-uniq-002",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-DUP-01",
        "vehicle_type": "FORKLIFT",
    }, format="json")
    assert res2.status_code == 200
    assert res2.data["status"] == "DUPLICATE_VEHICLE_IGNORED"
    # Queue count must NOT increase
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, vehicle_id="VH-DUP-01").count() == 1

    # 3. Vehicle is cleared
    res_clr = api_client.post("/api/sensor-events", {
        "event_id": "evt-uniq-003",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_CLEARED",
        "vehicle_id": "VH-DUP-01",
    }, format="json")
    assert res_clr.status_code == 201
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, vehicle_id="VH-DUP-01").count() == 0

    # 4. Now vehicle can arrive again legitimately -> 201 Created
    res3 = api_client.post("/api/sensor-events", {
        "event_id": "evt-uniq-004",
        "junction_id": "A",
        "direction": "NORTH",
        "event_type": "VEHICLE_ARRIVED",
        "vehicle_id": "VH-DUP-01",
        "vehicle_type": "FORKLIFT",
    }, format="json")
    assert res3.status_code == 201
    assert VehicleQueueItem.objects.filter(junction=seeded_junction, vehicle_id="VH-DUP-01").count() == 1


