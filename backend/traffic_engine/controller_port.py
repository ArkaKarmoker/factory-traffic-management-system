"""
Controller Interface & Adapters (Hexagonal Architecture / Ports & Adapters)
Decouples domain traffic engine from physical controller communication (REST Simulator or MQTT).
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime, timezone
import uuid
from traffic_engine.enums import SignalState, Direction, ControllerStatus


class TrafficControllerPort(ABC):
    """
    Hexagonal Port interface for physical signal controller interactions.
    """

    @abstractmethod
    def dispatch_signal_command(
        self,
        command_id: str,
        junction_id: str,
        direction: Direction,
        requested_state: SignalState,
    ) -> bool:
        """Dispatches an actuation command to the controller."""
        pass

    @abstractmethod
    def process_acknowledgement(
        self,
        command_id: str,
        junction_id: str,
        status: str,
        actual_state: SignalState,
    ) -> Dict[str, any]:
        """Correlates and processes controller ACK / NACK."""
        pass


class RESTControllerSimulatorAdapter(TrafficControllerPort):
    """
    Active REST simulator adapter.
    Tracks outgoing commands and correlates incoming /api/controller-events.
    """

    def __init__(self):
        self.dispatched_commands: Dict[str, dict] = {}

    def dispatch_signal_command(
        self,
        command_id: str,
        junction_id: str,
        direction: Direction,
        requested_state: SignalState,
    ) -> bool:
        self.dispatched_commands[command_id] = {
            "command_id": command_id,
            "junction_id": junction_id,
            "direction": direction.value,
            "requested_state": requested_state.value,
            "status": "PENDING",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        return True

    def process_acknowledgement(
        self,
        command_id: str,
        junction_id: str,
        status: str,
        actual_state: SignalState,
    ) -> Dict[str, any]:
        record = self.dispatched_commands.get(command_id, {
            "command_id": command_id,
            "junction_id": junction_id,
        })
        record["status"] = status
        record["actual_state"] = actual_state.value
        record["acked_at"] = datetime.now(timezone.utc).isoformat()
        return record


class MQTTControllerAdapter(TrafficControllerPort):
    """
    Future-ready MQTT adapter conforming to the same ControllerPort.
    Can be seamlessly plugged in without modifying domain engine logic.
    """

    def __init__(self, broker_url: str = "mqtt://localhost:1883"):
        self.broker_url = broker_url

    def dispatch_signal_command(
        self,
        command_id: str,
        junction_id: str,
        direction: Direction,
        requested_state: SignalState,
    ) -> bool:
        # Placeholder for paho-mqtt publish to topic: factory/junctions/{junction_id}/signals/{direction}
        return True

    def process_acknowledgement(
        self,
        command_id: str,
        junction_id: str,
        status: str,
        actual_state: SignalState,
    ) -> Dict[str, any]:
        return {
            "command_id": command_id,
            "status": status,
            "actual_state": actual_state.value,
        }
