/**
 * Type-safe API Client for Factory Traffic Management System
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

export interface JunctionStatus {
  junction_id: string;
  name: string;
  mode: "AUTOMATIC" | "MANUAL" | "EMERGENCY" | "DEGRADED";
  phase: "NORTH_SOUTH" | "EAST_WEST" | "ALL_RED_CLEARING";
  target_phase: string | null;
  transition_step: "STEADY" | "YELLOW_CLEARING" | "ALL_RED_CLEARING";
  controller_status: "ONLINE" | "OFFLINE" | "DEGRADED" | "UNKNOWN";
  desired_signals: Record<string, "RED" | "YELLOW" | "GREEN">;
  actual_signals: Record<string, "RED" | "YELLOW" | "GREEN">;
  queues: Record<string, number>;
  emergency_active: boolean;
  emergency_direction: string | null;
  manual_requested_direction: string | null;
  pending_command_id: string | null;
  phase_started_at: string;
  step_started_at: string;
}

export interface AuditLogItem {
  id: number;
  junction_id: string;
  event_type: string;
  direction?: string | null;
  previous_state?: string | null;
  new_state?: string | null;
  command_id?: string | null;
  details: Record<string, any>;
  timestamp: string;
}

export interface QueueVehicle {
  id: number;
  vehicle_id: string;
  vehicle_type: "FORKLIFT" | "TRUCK" | "EMPLOYEE_VEHICLE" | "EMERGENCY";
  direction: "NORTH" | "SOUTH" | "EAST" | "WEST";
  sequence_no: number;
  arrived_at: string;
}

async function safeFetchJson(url: string, options?: RequestInit) {
  const res = await fetch(url, options);
  const text = await res.text();
  let json: any = null;
  try {
    json = JSON.parse(text);
  } catch (err) {
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    throw new Error("Invalid response format received from server.");
  }

  if (!res.ok) {
    const errorMsg = json?.detail || json?.message || JSON.stringify(json);
    throw new Error(errorMsg);
  }
  return json;
}

export const api = {
  async getStatus(junctionId = "A"): Promise<JunctionStatus> {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/status`, {
      cache: "no-store",
    });
  },

  async getHistory(junctionId = "A", limit = 30): Promise<AuditLogItem[]> {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/history?limit=${limit}`, {
      cache: "no-store",
    });
  },

  async getQueues(junctionId = "A"): Promise<QueueVehicle[]> {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/queues`, {
      cache: "no-store",
    });
  },

  async postSensorEvent(payload: {
    event_id: string;
    junction_id?: string;
    direction: string;
    event_type: "VEHICLE_ARRIVED" | "VEHICLE_CLEARED";
    vehicle_id: string;
    vehicle_type?: string;
    sequence_no?: number;
  }) {
    return safeFetchJson(`${API_BASE_URL}/sensor-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async postManualCommand(
    junctionId: string,
    command: "MANUAL_GREEN_REQUEST" | "RETURN_TO_AUTOMATIC",
    direction?: string,
    token = "factory-admin-token-2026"
  ) {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/commands`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Token": token,
        Authorization: `Token ${token}`,
      },
      body: JSON.stringify({
        command,
        direction,
        operator_id: "DASHBOARD_OPERATOR",
      }),
    });
  },

  async postControllerEvent(payload: {
    command_id?: string;
    junction_id?: string;
    status: "ACK" | "NACK" | "OFFLINE" | "ONLINE" | "TIMEOUT";
    actual_state?: string;
    device_type?: string;
    direction?: string;
  }) {
    return safeFetchJson(`${API_BASE_URL}/controller-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async postTick(junctionId = "A") {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/tick`, {
      method: "POST",
    });
  },

  async postReset(junctionId = "A") {
    return safeFetchJson(`${API_BASE_URL}/junctions/${junctionId}/reset`, {
      method: "POST",
    });
  },
};
