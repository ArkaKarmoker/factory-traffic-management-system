"""
Database Models for Factory Traffic Management System
Provides persistent state for Junctions, Priority Queues, Idempotency, Commands, and Audit Trail.
"""
from django.db import models
from django.utils import timezone
from traffic_engine.enums import (
    SignalState,
    Direction,
    TrafficPhase,
    VehicleType,
    JunctionMode,
    ControllerStatus,
    TransitionStep,
)


class Junction(models.Model):
    """
    Represents an intersection / traffic junction (e.g., Junction A).
    Survives application restarts and maintains desired vs confirmed states.
    """
    junction_id = models.CharField(max_length=16, primary_key=True, help_text="Unique identifier, e.g., 'A'")
    name = models.CharField(max_length=64, default="Main Factory Intersection A")
    
    # Operational State
    mode = models.CharField(
        max_length=16,
        choices=[(tag.value, tag.name) for tag in JunctionMode],
        default=JunctionMode.AUTOMATIC.value,
    )
    current_phase = models.CharField(
        max_length=32,
        choices=[(tag.value, tag.name) for tag in TrafficPhase],
        default=TrafficPhase.NORTH_SOUTH.value,
    )
    target_phase = models.CharField(
        max_length=32,
        choices=[(tag.value, tag.name) for tag in TrafficPhase],
        blank=True,
        null=True,
    )
    transition_step = models.CharField(
        max_length=32,
        choices=[(tag.value, tag.name) for tag in TransitionStep],
        default=TransitionStep.STEADY.value,
    )
    
    phase_started_at = models.DateTimeField(default=timezone.now)
    step_started_at = models.DateTimeField(default=timezone.now)

    # Desired Signals (What the backend scheduler wants)
    desired_north = models.CharField(max_length=16, default=SignalState.GREEN.value)
    desired_south = models.CharField(max_length=16, default=SignalState.GREEN.value)
    desired_east = models.CharField(max_length=16, default=SignalState.RED.value)
    desired_west = models.CharField(max_length=16, default=SignalState.RED.value)

    # Actual Signals (What the physical controller has acknowledged)
    actual_north = models.CharField(max_length=16, default=SignalState.GREEN.value)
    actual_south = models.CharField(max_length=16, default=SignalState.GREEN.value)
    actual_east = models.CharField(max_length=16, default=SignalState.RED.value)
    actual_west = models.CharField(max_length=16, default=SignalState.RED.value)

    # Hardware & Telemetry
    controller_status = models.CharField(
        max_length=16,
        choices=[(tag.value, tag.name) for tag in ControllerStatus],
        default=ControllerStatus.ONLINE.value,
    )
    pending_command_id = models.CharField(max_length=64, blank=True, null=True)

    # Override tracking
    manual_requested_direction = models.CharField(max_length=16, blank=True, null=True)
    manual_expires_at = models.DateTimeField(blank=True, null=True)
    emergency_direction = models.CharField(max_length=16, blank=True, null=True)
    emergency_active = models.BooleanField(default=False)

    # Configurable Timings
    green_duration = models.FloatField(default=30.0)
    yellow_duration = models.FloatField(default=5.0)
    all_red_duration = models.FloatField(default=2.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Junction {self.junction_id} [{self.mode} - {self.current_phase}]"

    @property
    def desired_signals(self):
        return {
            "NORTH": self.desired_north,
            "SOUTH": self.desired_south,
            "EAST": self.desired_east,
            "WEST": self.desired_west,
        }

    @property
    def actual_signals(self):
        return {
            "NORTH": self.actual_north,
            "SOUTH": self.actual_south,
            "EAST": self.actual_east,
            "WEST": self.actual_west,
        }

    def get_queues_count(self):
        counts = {d.value: 0 for d in Direction}
        for item in self.queue_items.all():
            if item.direction in counts:
                counts[item.direction] += 1
        return counts


class VehicleQueueItem(models.Model):
    """
    Individual vehicles queued at an intersection direction.
    """
    junction = models.ForeignKey(Junction, on_delete=models.CASCADE, related_name="queue_items")
    direction = models.CharField(max_length=16, choices=[(tag.value, tag.name) for tag in Direction])
    vehicle_id = models.CharField(max_length=64)
    vehicle_type = models.CharField(
        max_length=32,
        choices=[(tag.value, tag.name) for tag in VehicleType],
        default=VehicleType.EMPLOYEE_VEHICLE.value,
    )
    sequence_no = models.IntegerField(default=0)
    sensor_timestamp = models.DateTimeField(blank=True, null=True)
    arrived_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["arrived_at"]
        indexes = [
            models.Index(fields=["junction", "direction"]),
            models.Index(fields=["junction", "vehicle_id"]),
        ]

    def __str__(self):
        return f"{self.vehicle_type} {self.vehicle_id} waiting at {self.direction} on Junction {self.junction_id}"


class ProcessedEvent(models.Model):
    """
    Strict Idempotency table.
    Ensures that processing the same event_id more than once never modifies state multiple times.
    """
    event_id = models.CharField(max_length=64, primary_key=True)
    junction_id = models.CharField(max_length=16, db_index=True)
    direction = models.CharField(max_length=16, blank=True, null=True)
    event_type = models.CharField(max_length=32)
    vehicle_id = models.CharField(max_length=64, blank=True, null=True)
    sequence_no = models.IntegerField(default=0)
    processed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Event {self.event_id} ({self.event_type}) @ {self.processed_at.isoformat()}"


class ControllerCommand(models.Model):
    """
    Tracks commands dispatched to physical controllers with unique command_id.
    """
    command_id = models.CharField(max_length=64, primary_key=True)
    junction = models.ForeignKey(Junction, on_delete=models.CASCADE, related_name="commands")
    direction = models.CharField(max_length=16)
    requested_state = models.CharField(max_length=16)
    status = models.CharField(max_length=16, default="PENDING")  # PENDING, ACK, TIMEOUT, FAILED
    actual_state = models.CharField(max_length=16, blank=True, null=True)
    dispatched_at = models.DateTimeField(default=timezone.now)
    acked_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Command {self.command_id}: {self.direction} -> {self.requested_state} [{self.status}]"


class AuditLog(models.Model):
    """
    Comprehensive historical audit log for every state transition, command, preemption, or failure.
    """
    junction_id = models.CharField(max_length=16, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    direction = models.CharField(max_length=16, blank=True, null=True)
    previous_state = models.CharField(max_length=32, blank=True, null=True)
    new_state = models.CharField(max_length=32, blank=True, null=True)
    command_id = models.CharField(max_length=64, blank=True, null=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.junction_id}: {self.event_type}"
