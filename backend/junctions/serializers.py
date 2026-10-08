"""
Django REST Framework Serializers for Factory Traffic Management System
Enforces strict input validation, type safety, and clean JSON representations.
"""
from rest_framework import serializers
from junctions.models import (
    Junction,
    VehicleQueueItem,
    ProcessedEvent,
    ControllerCommand,
    AuditLog,
)
from traffic_engine.enums import Direction, VehicleType, SignalState, JunctionMode, ControllerStatus


class VehicleQueueItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleQueueItem
        fields = [
            "id",
            "vehicle_id",
            "vehicle_type",
            "direction",
            "sequence_no",
            "arrived_at",
            "sensor_timestamp",
        ]


class JunctionStatusSerializer(serializers.Serializer):
    junction_id = serializers.CharField()
    name = serializers.CharField()
    mode = serializers.CharField()
    phase = serializers.CharField(source="current_phase")
    target_phase = serializers.CharField(allow_null=True)
    transition_step = serializers.CharField()
    controller_status = serializers.CharField()
    desired_signals = serializers.DictField()
    actual_signals = serializers.DictField()
    queues = serializers.DictField()
    emergency_active = serializers.BooleanField()
    emergency_direction = serializers.CharField(allow_null=True)
    manual_requested_direction = serializers.CharField(allow_null=True)
    pending_command_id = serializers.CharField(allow_null=True)
    phase_started_at = serializers.DateTimeField()
    step_started_at = serializers.DateTimeField()


from drf_spectacular.utils import extend_schema_field


class JunctionSerializer(serializers.ModelSerializer):
    desired_signals = serializers.DictField(read_only=True)
    actual_signals = serializers.DictField(read_only=True)
    queues = serializers.SerializerMethodField()

    class Meta:
        model = Junction
        fields = [
            "junction_id",
            "name",
            "mode",
            "current_phase",
            "target_phase",
            "transition_step",
            "controller_status",
            "desired_signals",
            "actual_signals",
            "queues",
            "emergency_active",
            "emergency_direction",
            "manual_requested_direction",
            "green_duration",
            "yellow_duration",
            "all_red_duration",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.DictField)
    def get_queues(self, obj):
        return obj.get_queues_count()


class SensorEventSerializer(serializers.Serializer):
    """
    Validates vehicle detection events from roadway sensors (Section 4 & 10.2).
    """
    event_id = serializers.CharField(max_length=64, required=True)
    junction_id = serializers.CharField(max_length=16, default="A")
    direction = serializers.ChoiceField(
        choices=[d.value for d in Direction],
        required=True,
    )
    event_type = serializers.ChoiceField(
        choices=["VEHICLE_ARRIVED", "VEHICLE_CLEARED"],
        required=True,
    )
    vehicle_id = serializers.CharField(max_length=64, required=True)
    vehicle_type = serializers.ChoiceField(
        choices=[v.value for v in VehicleType],
        default=VehicleType.EMPLOYEE_VEHICLE.value,
        required=False,
    )
    sequence_no = serializers.IntegerField(default=0, required=False)
    timestamp = serializers.DateTimeField(required=False)


class ManualControlCommandSerializer(serializers.Serializer):
    """
    Validates administrative manual traffic control commands (Section 8 & 10.4).
    """
    command = serializers.ChoiceField(
        choices=["MANUAL_GREEN_REQUEST", "RETURN_TO_AUTOMATIC"],
        required=True,
    )
    direction = serializers.ChoiceField(
        choices=[d.value for d in Direction],
        required=False,
        allow_null=True,
    )
    operator_id = serializers.CharField(max_length=64, required=False, default="ADMIN")

    def validate(self, attrs):
        if attrs.get("command") == "MANUAL_GREEN_REQUEST" and not attrs.get("direction"):
            raise serializers.ValidationError({"direction": "Direction is required for MANUAL_GREEN_REQUEST."})
        return attrs


class ControllerEventSerializer(serializers.Serializer):
    """
    Validates physical signal controller acknowledgements & status events (Section 9 & 10.5).
    """
    command_id = serializers.CharField(max_length=64, required=False, allow_null=True)
    junction_id = serializers.CharField(max_length=16, default="A")
    status = serializers.ChoiceField(
        choices=["ACK", "NACK", "OFFLINE", "ONLINE", "TIMEOUT"],
        default="ACK",
    )
    actual_state = serializers.ChoiceField(
        choices=[s.value for s in SignalState],
        required=False,
        allow_null=True,
    )
    device_type = serializers.CharField(default="SIGNAL_CONTROLLER", required=False)
    direction = serializers.ChoiceField(
        choices=[d.value for d in Direction],
        required=False,
        allow_null=True,
    )
    timestamp = serializers.DateTimeField(required=False)


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Audit log serialization for system event history (Section 11 & 10.6).
    """
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "junction_id",
            "event_type",
            "direction",
            "previous_state",
            "new_state",
            "command_id",
            "details",
            "timestamp",
        ]
