"""
Traffic Domain Models - Pure Python Dataclasses (Zero DB/HTTP dependency)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from traffic_engine.enums import (
    SignalState,
    Direction,
    TrafficPhase,
    VehicleType,
    JunctionMode,
    ControllerStatus,
    TransitionStep,
)


@dataclass
class VehicleItem:
    vehicle_id: str
    vehicle_type: VehicleType
    direction: Direction
    sequence_no: int
    arrived_at: datetime
    sensor_timestamp: Optional[datetime] = None


@dataclass
class JunctionState:
    junction_id: str
    mode: JunctionMode = JunctionMode.AUTOMATIC
    current_phase: TrafficPhase = TrafficPhase.NORTH_SOUTH
    target_phase: Optional[TrafficPhase] = None
    transition_step: TransitionStep = TransitionStep.STEADY
    phase_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    step_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    desired_signals: Dict[str, SignalState] = field(default_factory=lambda: {
        Direction.NORTH.value: SignalState.GREEN,
        Direction.SOUTH.value: SignalState.GREEN,
        Direction.EAST.value: SignalState.RED,
        Direction.WEST.value: SignalState.RED,
    })
    
    actual_signals: Dict[str, SignalState] = field(default_factory=lambda: {
        Direction.NORTH.value: SignalState.GREEN,
        Direction.SOUTH.value: SignalState.GREEN,
        Direction.EAST.value: SignalState.RED,
        Direction.WEST.value: SignalState.RED,
    })
    
    controller_status: ControllerStatus = ControllerStatus.ONLINE
    manual_requested_direction: Optional[Direction] = None
    manual_expires_at: Optional[datetime] = None
    emergency_direction: Optional[Direction] = None
    pending_command_id: Optional[str] = None
    
    # Timing configurations in seconds
    green_duration: float = 30.0
    yellow_duration: float = 5.0
    all_red_duration: float = 2.0
