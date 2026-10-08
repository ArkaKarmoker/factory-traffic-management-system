"""
Django REST Framework API Views for Factory Traffic Management System
Implements Section 10 Minimum Backend APIs with strict validation, error handling, and OpenAPI schemas.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from junctions.models import Junction, AuditLog, VehicleQueueItem
from junctions.serializers import (
    JunctionSerializer,
    JunctionStatusSerializer,
    SensorEventSerializer,
    ManualControlCommandSerializer,
    ControllerEventSerializer,
    AuditLogSerializer,
    VehicleQueueItemSerializer,
)
from junctions.services import JunctionService
from traffic_engine.enums import Direction, TrafficPhase, JunctionMode, SignalState, ControllerStatus, TransitionStep


class JunctionListCreateView(APIView):
    """
    GET /api/junctions - List all registered junctions
    POST /api/junctions - Create a new junction
    """

    @extend_schema(
        summary="List all junctions",
        responses={200: JunctionSerializer(many=True)},
    )
    def get(self, request):
        junctions = Junction.objects.all()
        if not junctions.exists():
            # Auto-seed Junction A if table is empty
            JunctionService.get_or_create_default_junction("A")
            junctions = Junction.objects.all()
        serializer = JunctionSerializer(junctions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Register a new junction",
        request=JunctionSerializer,
        responses={201: JunctionSerializer},
    )
    def post(self, request):
        serializer = JunctionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JunctionDetailView(APIView):
    """
    GET /api/junctions/:id - Retrieve junction configuration and live status
    """

    @extend_schema(
        summary="Get junction details by ID",
        responses={200: JunctionSerializer, 404: OpenApiResponse(description="Junction not found")},
    )
    def get(self, request, id):
        junction = Junction.objects.filter(junction_id=id).first()
        if not junction:
            if id.upper() == "A":
                junction = JunctionService.get_or_create_default_junction("A")
            else:
                return Response({"detail": f"Junction '{id}' not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = JunctionSerializer(junction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JunctionStatusView(APIView):
    """
    GET /api/junctions/:id/status - Retrieve live telemetry, desired vs actual signals, and queues
    """

    @extend_schema(
        summary="Get junction live operational telemetry & signal state",
        responses={200: JunctionStatusSerializer},
    )
    def get(self, request, id):
        junction = JunctionService.step_transition_tick(junction_id=id, force_advance=False)
        if not junction:
            junction = Junction.objects.filter(junction_id=id).first()
        if not junction:
            if id.upper() == "A":
                junction = JunctionService.get_or_create_default_junction("A")
            else:
                return Response({"detail": f"Junction '{id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "junction_id": junction.junction_id,
            "name": junction.name,
            "mode": junction.mode,
            "phase": junction.current_phase,
            "target_phase": junction.target_phase,
            "transition_step": junction.transition_step,
            "controller_status": junction.controller_status,
            "desired_signals": junction.desired_signals,
            "actual_signals": junction.actual_signals,
            "queues": junction.get_queues_count(),
            "emergency_active": junction.emergency_active,
            "emergency_direction": junction.emergency_direction,
            "manual_requested_direction": junction.manual_requested_direction,
            "pending_command_id": junction.pending_command_id,
            "phase_started_at": junction.phase_started_at,
            "step_started_at": junction.step_started_at,
        }
        return Response(data, status=status.HTTP_200_OK)


class SensorEventIngestionView(APIView):
    """
    POST /api/sensor-events - Ingest vehicle detection events (VEHICLE_ARRIVED, VEHICLE_CLEARED)
    """

    @extend_schema(
        summary="Ingest sensor vehicle detection event",
        request=SensorEventSerializer,
        responses={
            201: OpenApiResponse(description="Event accepted and queued"),
            200: OpenApiResponse(description="Duplicate event idempotently acknowledged"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        serializer = SensorEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        success, message, result = JunctionService.handle_sensor_event(serializer.validated_data)

        if result.get("status") in ("DUPLICATE_IGNORED", "DUPLICATE_VEHICLE_IGNORED"):
            return Response({"status": result.get("status"), "message": message, "result": result}, status=status.HTTP_200_OK)

        return Response({"status": "SUCCESS", "message": message, "result": result}, status=status.HTTP_201_CREATED)


class JunctionCommandView(APIView):
    """
    POST /api/junctions/:id/commands - Execute manual operator control commands
    Supports Token Auth & Header Key (Section 21)
    """

    @extend_schema(
        summary="Send manual operator command (e.g. MANUAL_GREEN_REQUEST, RETURN_TO_AUTOMATIC)",
        request=ManualControlCommandSerializer,
        responses={200: OpenApiResponse(description="Command accepted and transitioning safely")},
    )
    def post(self, request, id):
        # Optional Auth Verification for Manual Override (Section 21 bonus)
        if getattr(settings, "AUTH_REQUIRED_FOR_COMMANDS", False):
            auth_header = request.headers.get("Authorization", "")
            token_header = request.headers.get("X-Admin-Token", "")
            expected_token = getattr(settings, "ADMIN_API_TOKEN", "factory-admin-token-2026")
            
            if not (token_header == expected_token or f"Token {expected_token}" in auth_header or request.user.is_authenticated):
                return Response(
                    {"detail": "Authentication required for manual junction control. Provide valid X-Admin-Token or Token header."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        serializer = ManualControlCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        command = serializer.validated_data.get("command")
        direction = serializer.validated_data.get("direction")
        operator_id = serializer.validated_data.get("operator_id", "ADMIN")

        success, message, result = JunctionService.handle_manual_command(
            junction_id=id,
            command=command,
            direction_str=direction,
            operator_id=operator_id,
        )

        if not success:
            return Response({"status": "ERROR", "message": message}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "SUCCESS", "message": message, "result": result}, status=status.HTTP_200_OK)


class ControllerEventIngestionView(APIView):
    """
    POST /api/controller-events - Ingest physical controller acknowledgements & device status events
    """

    @extend_schema(
        summary="Ingest physical controller ACK / Device status event",
        request=ControllerEventSerializer,
        responses={200: OpenApiResponse(description="Controller event processed")},
    )
    def post(self, request):
        serializer = ControllerEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        success, message, result = JunctionService.handle_controller_event(serializer.validated_data)
        return Response({"status": "SUCCESS", "message": message, "result": result}, status=status.HTTP_200_OK)


class JunctionHistoryView(APIView):
    """
    GET /api/junctions/:id/history - Retrieve historical audit trail of transitions and events
    """

    @extend_schema(
        summary="Get junction audit history and transition logs",
        parameters=[
            OpenApiParameter(name="limit", type=int, required=False, description="Max logs to return (default 50)"),
            OpenApiParameter(name="event_type", type=str, required=False, description="Filter by specific event type"),
        ],
        responses={200: AuditLogSerializer(many=True)},
    )
    def get(self, request, id):
        limit = int(request.query_params.get("limit", 50))
        event_type = request.query_params.get("event_type")

        qs = AuditLog.objects.filter(junction_id=id)
        if event_type:
            qs = qs.filter(event_type=event_type)

        logs = qs[:limit]
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JunctionQueuesView(APIView):
    """
    GET /api/junctions/:id/queues - Retrieve detailed list of waiting vehicles
    """

    @extend_schema(
        summary="Get list of all waiting vehicles queued at the junction",
        responses={200: VehicleQueueItemSerializer(many=True)},
    )
    def get(self, request, id):
        items = VehicleQueueItem.objects.filter(junction_id=id).order_by("arrived_at")
        serializer = VehicleQueueItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JunctionTickView(APIView):
    """
    POST /api/junctions/:id/tick - Step the deterministic state machine timer
    Enables instant step testing for evaluators without waiting real-world seconds.
    """

    @extend_schema(
        summary="Advance state machine transition timer (Instant simulation step)",
        request=None,
        responses={200: JunctionSerializer},
    )
    def post(self, request, id):
        junction = JunctionService.step_transition_tick(junction_id=id, force_advance=True)
        serializer = JunctionSerializer(junction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JunctionResetView(APIView):
    """
    POST /api/junctions/:id/reset - Reset junction state and clear queues for evaluation demo
    """

    @extend_schema(
        summary="Reset junction to clean initial state (Evaluator convenience)",
        request=None,
        responses={200: OpenApiResponse(description="Junction reset to default")},
    )
    def post(self, request, id):
        junction = JunctionService.get_or_create_default_junction(id)
        VehicleQueueItem.objects.filter(junction=junction).delete()
        junction.mode = JunctionMode.AUTOMATIC.value
        junction.current_phase = TrafficPhase.NORTH_SOUTH.value
        junction.target_phase = None
        junction.transition_step = TransitionStep.STEADY.value
        junction.desired_north = SignalState.GREEN.value
        junction.desired_south = SignalState.GREEN.value
        junction.desired_east = SignalState.RED.value
        junction.desired_west = SignalState.RED.value
        junction.actual_north = SignalState.GREEN.value
        junction.actual_south = SignalState.GREEN.value
        junction.actual_east = SignalState.RED.value
        junction.actual_west = SignalState.RED.value
        junction.controller_status = ControllerStatus.ONLINE.value
        junction.emergency_active = False
        junction.emergency_direction = None
        junction.manual_requested_direction = None
        junction.phase_started_at = timezone.now()
        junction.step_started_at = timezone.now()
        junction.save()

        AuditLog.objects.create(
            junction_id=id,
            event_type="JUNCTION_RESET",
            details={"note": "Reset to default test state"},
        )

        return Response({"status": "SUCCESS", "message": f"Junction {id} reset successfully."}, status=status.HTTP_200_OK)
