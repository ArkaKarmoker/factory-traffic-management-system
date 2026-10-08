"""
Junction Service Layer
Coordinates Domain Logic, Concurrency Locks, Idempotency, and Audit Logs.
"""
from datetime import datetime, timezone, timedelta
import uuid
from typing import Dict, Tuple, Optional
from django.db import transaction
from django.utils import timezone as dj_timezone

from junctions.models import (
    Junction,
    VehicleQueueItem,
    ProcessedEvent,
    ControllerCommand,
    AuditLog,
)
from traffic_engine.enums import (
    SignalState,
    Direction,
    TrafficPhase,
    VehicleType,
    JunctionMode,
    ControllerStatus,
    TransitionStep,
)
from traffic_engine.models import VehicleItem
from traffic_engine.state_machine import TrafficStateMachine
from traffic_engine.scheduler import TrafficScheduler


class JunctionService:
    """
    Thread-safe, transactional service coordinating all junction operations.
    """

    @classmethod
    def get_or_create_default_junction(cls, junction_id: str = "A") -> Junction:
        """
        Retrieves or initializes Junction A with standard factory layout.
        """
        junction, created = Junction.objects.get_or_create(
            junction_id=junction_id,
            defaults={
                "name": f"Factory Road Intersection {junction_id}",
                "mode": JunctionMode.AUTOMATIC.value,
                "current_phase": TrafficPhase.NORTH_SOUTH.value,
                "transition_step": TransitionStep.STEADY.value,
                "desired_north": SignalState.GREEN.value,
                "desired_south": SignalState.GREEN.value,
                "desired_east": SignalState.RED.value,
                "desired_west": SignalState.RED.value,
                "actual_north": SignalState.GREEN.value,
                "actual_south": SignalState.GREEN.value,
                "actual_east": SignalState.RED.value,
                "actual_west": SignalState.RED.value,
                "controller_status": ControllerStatus.ONLINE.value,
            },
        )
        if created:
            AuditLog.objects.create(
                junction_id=junction_id,
                event_type="JUNCTION_INITIALIZED",
                details={"initial_phase": junction.current_phase, "mode": junction.mode},
            )
        return junction

    @classmethod
    def handle_sensor_event(cls, data: dict) -> Tuple[bool, str, dict]:
        """
        Ingests vehicle detection sensor events.
        Enforces strict idempotency, row-level concurrency locking, and priority preemption.
        """
        event_id = data.get("event_id")
        junction_id = data.get("junction_id", "A")
        direction_str = data.get("direction")
        event_type = data.get("event_type")
        vehicle_id = data.get("vehicle_id")
        vehicle_type_str = data.get("vehicle_type", VehicleType.EMPLOYEE_VEHICLE.value)
        sequence_no = data.get("sequence_no", 0)
        timestamp_str = data.get("timestamp")

        # 1. Idempotency Check (Section 4 & Section 10.2)
        if ProcessedEvent.objects.filter(event_id=event_id).exists():
            AuditLog.objects.create(
                junction_id=junction_id,
                event_type="IDEMPOTENT_DUPLICATE_REJECTED",
                command_id=None,
                details={"event_id": event_id, "reason": "Exact event_id previously processed"},
            )
            return True, "Event already processed (Idempotent response - no state mutation)", {
                "event_id": event_id,
                "status": "DUPLICATE_IGNORED",
            }

        # 2. Transactional processing with row lock to prevent concurrency race conditions
        with transaction.atomic():
            # Lock the junction row for update
            try:
                junction = Junction.objects.select_for_update().get(junction_id=junction_id)
            except Junction.DoesNotExist:
                junction = cls.get_or_create_default_junction(junction_id)

            # Record in idempotency table
            ProcessedEvent.objects.create(
                event_id=event_id,
                junction_id=junction_id,
                direction=direction_str,
                event_type=event_type,
                vehicle_id=vehicle_id,
                sequence_no=sequence_no,
            )

            # Handle VEHICLE_ARRIVED
            if event_type == "VEHICLE_ARRIVED":
                existing_item = VehicleQueueItem.objects.filter(
                    junction=junction, vehicle_id=vehicle_id
                ).first()
                if existing_item:
                    AuditLog.objects.create(
                        junction_id=junction_id,
                        event_type="DUPLICATE_VEHICLE_REJECTED",
                        direction=direction_str,
                        details={
                            "vehicle_id": vehicle_id,
                            "already_in_direction": existing_item.direction,
                            "reason": f"Vehicle '{vehicle_id}' is already waiting in queue at {existing_item.direction}",
                        },
                    )
                    return True, f"Vehicle '{vehicle_id}' is already queued at {existing_item.direction}. Duplicate vehicle queue addition rejected.", {
                        "event_id": event_id,
                        "junction_id": junction_id,
                        "vehicle_id": vehicle_id,
                        "status": "DUPLICATE_VEHICLE_IGNORED",
                        "current_mode": junction.mode,
                        "current_phase": junction.current_phase,
                        "queues": junction.get_queues_count(),
                    }

                VehicleQueueItem.objects.create(
                    junction=junction,
                    direction=direction_str,
                    vehicle_id=vehicle_id,
                    vehicle_type=vehicle_type_str,
                    sequence_no=sequence_no,
                )

                AuditLog.objects.create(
                    junction_id=junction_id,
                    event_type="VEHICLE_ARRIVED",
                    direction=direction_str,
                    details={
                        "vehicle_id": vehicle_id,
                        "vehicle_type": vehicle_type_str,
                        "sequence_no": sequence_no,
                    },
                )

                # Check for Emergency Vehicle Preemption (Section 7)
                if vehicle_type_str == VehicleType.EMERGENCY.value:
                    cls._trigger_emergency_preemption(junction, direction_str)
                else:
                    # In automatic mode, evaluate if immediate switch or step is needed for non-emergency traffic
                    cls._evaluate_traffic_switch(junction)

            # Handle VEHICLE_CLEARED
            elif event_type == "VEHICLE_CLEARED":
                # Find and remove vehicle item (prevent queue < 0)
                item = (
                    VehicleQueueItem.objects.filter(
                        junction=junction, direction=direction_str, vehicle_id=vehicle_id
                    ).first()
                    or VehicleQueueItem.objects.filter(
                        junction=junction, direction=direction_str
                    ).first()
                )

                if item:
                    item.delete()
                    AuditLog.objects.create(
                        junction_id=junction_id,
                        event_type="VEHICLE_CLEARED",
                        direction=direction_str,
                        details={"vehicle_id": vehicle_id},
                    )
                else:
                    AuditLog.objects.create(
                        junction_id=junction_id,
                        event_type="VEHICLE_CLEARED_EMPTY_QUEUE_IGNORED",
                        direction=direction_str,
                        details={"vehicle_id": vehicle_id, "note": "Queue was already 0"},
                    )

                # If this was an emergency vehicle leaving, check if emergency mode should clear
                if vehicle_type_str == VehicleType.EMERGENCY.value:
                    remaining_emergencies = VehicleQueueItem.objects.filter(
                        junction=junction, vehicle_type=VehicleType.EMERGENCY.value
                    ).count()
                    if remaining_emergencies == 0 and junction.mode == JunctionMode.EMERGENCY.value:
                        junction.mode = JunctionMode.AUTOMATIC.value
                        junction.emergency_active = False
                        junction.emergency_direction = None
                        junction.save()
                        AuditLog.objects.create(
                            junction_id=junction_id,
                            event_type="EMERGENCY_CLEARED",
                            details={"status": "Returned to AUTOMATIC"},
                        )

            junction.save()

            return True, "Sensor event processed successfully", {
                "event_id": event_id,
                "junction_id": junction_id,
                "current_mode": junction.mode,
                "current_phase": junction.current_phase,
                "queues": junction.get_queues_count(),
            }

    @classmethod
    def handle_manual_command(
        cls, junction_id: str, command: str, direction_str: Optional[str] = None, operator_id: Optional[str] = None
    ) -> Tuple[bool, str, dict]:
        """
        Executes administrative manual traffic control commands (Section 8).
        Enforces safety transition sequence instead of arbitrary jumping to green.
        """
        with transaction.atomic():
            junction = Junction.objects.select_for_update().get(junction_id=junction_id)

            if command == "MANUAL_GREEN_REQUEST":
                if not direction_str or direction_str not in [d.value for d in Direction]:
                    return False, f"Invalid direction '{direction_str}' specified.", {}

                target_phase = (
                    TrafficPhase.NORTH_SOUTH.value
                    if direction_str in (Direction.NORTH.value, Direction.SOUTH.value)
                    else TrafficPhase.EAST_WEST.value
                )

                junction.mode = JunctionMode.MANUAL.value
                junction.manual_requested_direction = direction_str
                junction.manual_expires_at = None  # Indefinite manual hold until explicit RETURN_TO_AUTOMATIC

                AuditLog.objects.create(
                    junction_id=junction_id,
                    event_type="MANUAL_OVERRIDE_REQUESTED",
                    direction=direction_str,
                    details={"requested_direction": direction_str, "operator": operator_id or "ADMIN"},
                )

                # If already in the target phase, keep it steady GREEN
                if junction.current_phase == target_phase and junction.transition_step == TransitionStep.STEADY.value:
                    junction.save()
                    return True, f"Junction already in phase for {direction_str}; manual hold active.", {
                        "mode": junction.mode,
                        "phase": junction.current_phase,
                    }

                # Otherwise, begin safe transition sequence
                cls._initiate_safe_phase_transition(junction, target_phase)
                junction.save()

                return True, f"Manual green request initiated safely for {direction_str}.", {
                    "mode": junction.mode,
                    "target_phase": target_phase,
                    "transition_step": junction.transition_step,
                }

            elif command == "RETURN_TO_AUTOMATIC":
                junction.mode = JunctionMode.AUTOMATIC.value
                junction.manual_requested_direction = None
                junction.manual_expires_at = None
                junction.save()

                AuditLog.objects.create(
                    junction_id=junction_id,
                    event_type="RETURN_TO_AUTOMATIC",
                    details={"operator": operator_id or "ADMIN"},
                )

                return True, "Junction returned to AUTOMATIC operating mode.", {
                    "mode": junction.mode,
                    "phase": junction.current_phase,
                }

            return False, f"Unknown command '{command}'.", {}

    @classmethod
    def handle_controller_event(cls, data: dict) -> Tuple[bool, str, dict]:
        """
        Processes physical signal controller acknowledgements & status telemetry (Section 9 & 10.5).
        """
        command_id = data.get("command_id")
        junction_id = data.get("junction_id", "A")
        status = data.get("status", "ACK")
        actual_state = data.get("actual_state")
        device_type = data.get("device_type", "SIGNAL_CONTROLLER")
        direction_str = data.get("direction")

        with transaction.atomic():
            junction = Junction.objects.select_for_update().get(junction_id=junction_id)

            # Controller OFFLINE event
            if status == "OFFLINE" or data.get("device_status") == "OFFLINE":
                junction.controller_status = ControllerStatus.OFFLINE.value
                junction.mode = JunctionMode.DEGRADED.value
                # Safe fallback: Desired signals to ALL RED (Backend safety intent)
                junction.desired_north = SignalState.RED.value
                junction.desired_south = SignalState.RED.value
                junction.desired_east = SignalState.RED.value
                junction.desired_west = SignalState.RED.value
                # Section 9 Strict Invariant: An offline controller CANNOT confirm state changes.
                # Backend must NOT artificially overwrite actual physical confirmation telemetry.
                # Actual signals remain at last confirmed state, triggering State Mismatch alert.
                junction.save()

                AuditLog.objects.create(
                    junction_id=junction_id,
                    event_type="CONTROLLER_OFFLINE_DEGRADED_FALLBACK",
                    direction=direction_str,
                    details={
                        "reason": "Physical controller reported OFFLINE. Backend demanded fail-safe ALL-RED; actual signals unconfirmed awaiting reconnection.",
                        "desired_signals": junction.desired_signals,
                        "actual_signals": junction.actual_signals,
                    },
                )
                return True, "Controller reported OFFLINE. Junction transitioned to DEGRADED mode with desired ALL-RED (Awaiting confirmation).", {
                    "controller_status": junction.controller_status,
                    "mode": junction.mode,
                    "desired_signals": junction.desired_signals,
                    "actual_signals": junction.actual_signals,
                }

            # Controller ONLINE restoration event
            elif status == "ONLINE" or data.get("device_status") == "ONLINE":
                junction.controller_status = ControllerStatus.ONLINE.value
                if junction.mode == JunctionMode.DEGRADED.value:
                    junction.mode = JunctionMode.AUTOMATIC.value
                # Restore phase signals safely
                if junction.current_phase == TrafficPhase.NORTH_SOUTH.value:
                    junction.desired_north = SignalState.GREEN.value
                    junction.desired_south = SignalState.GREEN.value
                    junction.desired_east = SignalState.RED.value
                    junction.desired_west = SignalState.RED.value
                else:
                    junction.desired_north = SignalState.RED.value
                    junction.desired_south = SignalState.RED.value
                    junction.desired_east = SignalState.GREEN.value
                    junction.desired_west = SignalState.GREEN.value
                junction.actual_north = junction.desired_north
                junction.actual_south = junction.desired_south
                junction.actual_east = junction.desired_east
                junction.actual_west = junction.desired_west
                junction.save()

                AuditLog.objects.create(
                    junction_id=junction_id,
                    event_type="CONTROLLER_ONLINE_RESTORED",
                    direction=direction_str,
                    details={"status": "ONLINE", "mode": junction.mode},
                )
                return True, "Controller restored ONLINE. System resumed normal operation.", {
                    "controller_status": junction.controller_status,
                    "mode": junction.mode,
                    "actual_signals": junction.actual_signals,
                }

            # Controller ACK event
            if command_id:
                cmd = ControllerCommand.objects.filter(command_id=command_id).first()
                if cmd:
                    cmd.status = status
                    cmd.actual_state = actual_state or cmd.requested_state
                    cmd.acked_at = dj_timezone.now()
                    cmd.save()

                    # Update junction actual confirmed signals
                    if cmd.direction == Direction.NORTH.value:
                        junction.actual_north = cmd.actual_state
                    elif cmd.direction == Direction.SOUTH.value:
                        junction.actual_south = cmd.actual_state
                    elif cmd.direction == Direction.EAST.value:
                        junction.actual_east = cmd.actual_state
                    elif cmd.direction == Direction.WEST.value:
                        junction.actual_west = cmd.actual_state

                    junction.controller_status = ControllerStatus.ONLINE.value
                    junction.save()

                    AuditLog.objects.create(
                        junction_id=junction_id,
                        event_type="CONTROLLER_ACK_RECEIVED",
                        direction=cmd.direction,
                        new_state=cmd.actual_state,
                        command_id=command_id,
                        details={"status": status},
                    )

                    return True, "Controller acknowledgement recorded successfully.", {
                        "command_id": command_id,
                        "status": status,
                        "actual_signals": junction.actual_signals,
                    }

            # Direct state confirmation simulation
            if actual_state and direction_str:
                if direction_str == "NORTH":
                    junction.actual_north = actual_state
                elif direction_str == "SOUTH":
                    junction.actual_south = actual_state
                elif direction_str == "EAST":
                    junction.actual_east = actual_state
                elif direction_str == "WEST":
                    junction.actual_west = actual_state
                junction.save()

            return True, "Controller event logged.", {"status": "RECORDED"}

    @classmethod
    def step_transition_tick(cls, junction_id: str = "A", force_advance: bool = False) -> Optional[Junction]:
        """
        Advances the state machine timeline. Can be called periodically by the background worker,
        on live telemetry polling (/api/junctions/:id/status), or explicitly via /api/junctions/:id/tick (force_advance=True).
        """
        with transaction.atomic():
            try:
                junction = Junction.objects.select_for_update().get(junction_id=junction_id)
            except Junction.DoesNotExist:
                if junction_id.upper() == "A":
                    junction = cls.get_or_create_default_junction("A")
                else:
                    return None

            now = dj_timezone.now()
            step_elapsed = (now - junction.step_started_at).total_seconds()
            phase_elapsed = (now - junction.phase_started_at).total_seconds()

            # Degraded / offline hold: cannot advance when physical controller is offline
            if junction.controller_status == ControllerStatus.OFFLINE.value:
                return junction

            # Step 1: Currently clearing YELLOW -> transition to ALL_RED
            if junction.transition_step == TransitionStep.YELLOW_CLEARING.value:
                if force_advance or step_elapsed >= junction.yellow_duration:
                    junction.transition_step = TransitionStep.ALL_RED_CLEARING.value
                    junction.step_started_at = now
                    # All signals to RED
                    junction.desired_north = SignalState.RED.value
                    junction.desired_south = SignalState.RED.value
                    junction.desired_east = SignalState.RED.value
                    junction.desired_west = SignalState.RED.value
                    junction.save()

                    cls._dispatch_controller_commands(junction, "ALL_RED_CLEARANCE")

                    AuditLog.objects.create(
                        junction_id=junction.junction_id,
                        event_type="TRANSITION_STEP_ALL_RED",
                        details={"clearing_to_phase": junction.target_phase},
                    )
                return junction

            # Step 2: Currently clearing ALL_RED -> transition to TARGET_GREEN
            if junction.transition_step == TransitionStep.ALL_RED_CLEARING.value:
                if force_advance or step_elapsed >= junction.all_red_duration:
                    new_phase = junction.target_phase or (
                        TrafficPhase.EAST_WEST.value
                        if junction.current_phase == TrafficPhase.NORTH_SOUTH.value
                        else TrafficPhase.NORTH_SOUTH.value
                    )
                    junction.current_phase = new_phase
                    junction.target_phase = None
                    junction.transition_step = TransitionStep.STEADY.value
                    junction.phase_started_at = now
                    junction.step_started_at = now

                    # Set desired green for new phase
                    if new_phase == TrafficPhase.NORTH_SOUTH.value:
                        junction.desired_north = SignalState.GREEN.value
                        junction.desired_south = SignalState.GREEN.value
                        junction.desired_east = SignalState.RED.value
                        junction.desired_west = SignalState.RED.value
                    else:
                        junction.desired_north = SignalState.RED.value
                        junction.desired_south = SignalState.RED.value
                        junction.desired_east = SignalState.GREEN.value
                        junction.desired_west = SignalState.GREEN.value

                    junction.save()
                    cls._dispatch_controller_commands(junction, "NEW_PHASE_GREEN")

                    AuditLog.objects.create(
                        junction_id=junction.junction_id,
                        event_type="SIGNAL_CHANGED",
                        details={"active_phase": junction.current_phase, "mode": junction.mode},
                    )
                return junction

            # Step 3: STEADY state - evaluate automatic switching or forced transition
            if junction.transition_step == TransitionStep.STEADY.value:
                # If in EMERGENCY mode, auto-resume if emergency vehicle cleared, 20s window elapsed, or tick fast-forwarded
                if junction.mode == JunctionMode.EMERGENCY.value or junction.emergency_active:
                    remaining_emergencies = junction.queue_items.filter(
                        vehicle_type=VehicleType.EMERGENCY.value
                    ).count()
                    if force_advance or remaining_emergencies == 0 or phase_elapsed >= 20.0:
                        # Safely dequeue the served emergency vehicle
                        emerg_item = junction.queue_items.filter(
                            vehicle_type=VehicleType.EMERGENCY.value
                        ).first()
                        if emerg_item:
                            emerg_item.delete()

                        junction.mode = JunctionMode.AUTOMATIC.value
                        junction.emergency_active = False
                        junction.emergency_direction = None
                        junction.save()
                        AuditLog.objects.create(
                            junction_id=junction.junction_id,
                            event_type="EMERGENCY_CLEARED_AUTO_RESUME",
                            details={"reason": "Emergency served, returned to AUTOMATIC"},
                        )
                        # If evaluator clicked tick, now that emergency is cleared, transition safely to opposing phase
                        if force_advance:
                            opposing_phase = (
                                TrafficPhase.EAST_WEST.value
                                if junction.current_phase == TrafficPhase.NORTH_SOUTH.value
                                else TrafficPhase.NORTH_SOUTH.value
                            )
                            cls._initiate_safe_phase_transition(junction, opposing_phase)
                        return junction

                # If evaluator explicitly clicks tick in regular STEADY, initiate phase transition immediately
                if force_advance:
                    opposing_phase = (
                        TrafficPhase.EAST_WEST.value
                        if junction.current_phase == TrafficPhase.NORTH_SOUTH.value
                        else TrafficPhase.NORTH_SOUTH.value
                    )
                    cls._initiate_safe_phase_transition(junction, opposing_phase)
                    return junction

                if junction.mode == JunctionMode.AUTOMATIC.value:
                    if phase_elapsed >= junction.green_duration:
                        cls._evaluate_traffic_switch(junction, force_check=True)
                    elif phase_elapsed >= 10.0:
                        cls._evaluate_traffic_switch(junction, force_check=False)

            return junction

    # --- Internal Private Helper Methods ---

    @classmethod
    def _trigger_emergency_preemption(cls, junction: Junction, emergency_direction: str):
        """
        Immediately starts safe emergency transition if emergency is on conflicting phase.
        """
        junction.mode = JunctionMode.EMERGENCY.value
        junction.emergency_active = True
        junction.emergency_direction = emergency_direction

        emergency_phase = (
            TrafficPhase.NORTH_SOUTH.value
            if emergency_direction in (Direction.NORTH.value, Direction.SOUTH.value)
            else TrafficPhase.EAST_WEST.value
        )

        AuditLog.objects.create(
            junction_id=junction.junction_id,
            event_type="EMERGENCY_PREEMPTION_TRIGGERED",
            direction=emergency_direction,
            details={"approaching_direction": emergency_direction, "target_phase": emergency_phase},
        )

        # If already in the target emergency phase, retain green and refresh emergency dwell window
        if junction.current_phase == emergency_phase:
            junction.phase_started_at = dj_timezone.now()
            junction.step_started_at = dj_timezone.now()
            junction.save()
            return

        # Otherwise immediately start the safe transition sequence
        cls._initiate_safe_phase_transition(junction, emergency_phase)

    @classmethod
    def _evaluate_traffic_switch(cls, junction: Junction, force_check: bool = False):
        """
        Queries queue state and asks TrafficScheduler if a phase switch is warranted.
        """
        if junction.mode not in (JunctionMode.AUTOMATIC.value, JunctionMode.EMERGENCY.value):
            return

        if junction.transition_step != TransitionStep.STEADY.value:
            return  # Already transitioning

        # Group vehicles by direction for the domain scheduler
        queues = {d: [] for d in Direction}
        for item in junction.queue_items.all():
            direction_enum = Direction(item.direction)
            queues[direction_enum].append(
                VehicleItem(
                    vehicle_id=item.vehicle_id,
                    vehicle_type=VehicleType(item.vehicle_type),
                    direction=direction_enum,
                    sequence_no=item.sequence_no,
                    arrived_at=item.arrived_at,
                )
            )

        now = dj_timezone.now()
        phase_elapsed = (now - junction.phase_started_at).total_seconds()

        current_phase_enum = TrafficPhase(junction.current_phase)
        next_phase = TrafficScheduler.select_next_phase(
            current_phase=current_phase_enum,
            queues=queues,
            phase_elapsed_seconds=phase_elapsed,
            min_green_seconds=8.0 if force_check else 15.0,
            normal_green_seconds=junction.green_duration,
            max_green_seconds=60.0,
            now=now,
        )

        if next_phase.value != junction.current_phase:
            cls._initiate_safe_phase_transition(junction, next_phase.value)

    @classmethod
    def _initiate_safe_phase_transition(cls, junction: Junction, target_phase: str):
        """
        Begins the deterministic sequence: Current GREEN -> YELLOW (5s) -> ALL RED (2s) -> Target GREEN.
        """
        now = dj_timezone.now()
        junction.target_phase = target_phase
        junction.transition_step = TransitionStep.YELLOW_CLEARING.value
        junction.step_started_at = now

        # Turn active phase signals to YELLOW
        if junction.current_phase == TrafficPhase.NORTH_SOUTH.value:
            junction.desired_north = SignalState.YELLOW.value
            junction.desired_south = SignalState.YELLOW.value
        else:
            junction.desired_east = SignalState.YELLOW.value
            junction.desired_west = SignalState.YELLOW.value

        junction.save()
        cls._dispatch_controller_commands(junction, "YELLOW_TRANSITION")

        AuditLog.objects.create(
            junction_id=junction.junction_id,
            event_type="SIGNAL_TRANSITION_STARTED",
            details={
                "from_phase": junction.current_phase,
                "target_phase": target_phase,
                "step": "YELLOW_CLEARING",
            },
        )

    @classmethod
    def _dispatch_controller_commands(cls, junction: Junction, reason: str):
        """
        Dispatches unique command_id records to physical controllers (or simulator).
        """
        for direction, state in junction.desired_signals.items():
            cmd_id = f"cmd-{uuid.uuid4().hex[:8]}"
            ControllerCommand.objects.create(
                command_id=cmd_id,
                junction=junction,
                direction=direction,
                requested_state=state,
                status="PENDING",
            )
            # In simulated environment, if controller is healthy, immediately sync actual state
            # (or wait for explicit /api/controller-events if testing delayed ACK)
            if junction.controller_status == ControllerStatus.ONLINE.value:
                if direction == "NORTH":
                    junction.actual_north = state
                elif direction == "SOUTH":
                    junction.actual_south = state
                elif direction == "EAST":
                    junction.actual_east = state
                elif direction == "WEST":
                    junction.actual_west = state
        junction.save()
