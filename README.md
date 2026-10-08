# Factory Traffic Management System (FTMS) 🚦🏭

> **CSI Smart Tech Ltd — Backend Developer Intern Technical Assessment (Assessment V2)**  
> Candidate: **Arka Karmoker** ([LinkedIn](https://linkedin.com/in/arkakarmoker) • [GitHub](https://github.com/ArkaKarmoker))  
> Repository: `factory-traffic-management-system`  
> Submission Form: [Google Form Submission](https://docs.google.com/forms/d/e/1FAIpQLSe9YkBUKnUOrhdl-7U0iNJjmZ4YTkvCV8QZqa5fvYdfDGH8WA/viewform)

---

## 📑 Table of Contents
1. [Executive Summary & System Architecture](#1-executive-summary--system-architecture)
2. [Traffic Control Domain Logic & State Machine](#2-traffic-control-domain-logic--state-machine)
3. [Scheduling & Priority Scoring Algorithm](#3-scheduling--priority-scoring-algorithm)
4. [Tech Stack & Justification](#4-tech-stack--justification)
5. [Quick Start & Setup Guide](#5-quick-start--setup-guide)
   - [Option A: One-Command Docker Compose (Recommended)](#option-a-one-command-docker-compose-recommended)
   - [Option B: Local Development Setup](#option-b-local-development-setup)
6. [API Endpoints & Postman Collection](#6-api-endpoints--postman-collection)
7. [Automated Test Suite & Verification](#7-automated-test-suite--verification)
8. [Demonstrating the Evaluation Scenarios](#8-demonstrating-the-evaluation-scenarios)
9. [Assumptions / Questions / Requirement Issues](#assumptions--questions--requirement-issues)
10. [Major Architectural Decisions & Trade-offs](#10-major-architectural-decisions--trade-offs)
11. [AI / Tool Usage](#ai--tool-usage)
12. [Google Form Submission Cheat-Sheet](#12-google-form-submission-cheat-sheet)

---

## 1. Executive Summary & System Architecture

The **Factory Traffic Management System (FTMS)** is an event-driven, safety-critical traffic control platform designed for internal roadways within a busy garment manufacturing facility. It governs intersection signals (Junction A) across four directions (`NORTH`, `SOUTH`, `EAST`, `WEST`) serving diverse industrial vehicular traffic: **Forklifts**, **Delivery Trucks**, **Employee Transports**, and **Emergency Responders**.

Unlike a simple CRUD application, FTMS functions as a **deterministic finite state machine (FSM)** and discrete-event control system built upon **Hexagonal / Clean Architecture**.

### Architectural Diagram (Ports & Adapters)

```text
+-----------------------------------------------------------------------------------------------+
|                                    FRONTEND CLIENT LAYER                                      |
|             Next.js 14+ (App Router) + TypeScript + Tailwind CSS + shadcn/ui                  |
|          (Visual 4-Way Intersection, Telemetry Verification, Evaluator Simulator Form)        |
+-----------------------------------------------+-----------------------------------------------+
                                                | HTTP REST / JSON
+-----------------------------------------------v-----------------------------------------------+
|                                    COMMUNICATION & API LAYER                                  |
|               Django REST Framework (DRF) + drf-spectacular (OpenAPI 3.0 / Swagger UI)        |
|             (/api/sensor-events, /api/junctions/:id/status, /api/commands, /api/history)      |
+-----------------------------------------------+-----------------------------------------------+
                                                | Clean DTOs & Domain Commands
+-----------------------------------------------v-----------------------------------------------+
|                              CORE DOMAIN ENGINE (traffic_engine/)                             |
|    Pure Python 3.12 (Zero HTTP/DB/Framework Coupling - Testable in Microseconds)             |
|    - Deterministic Finite State Machine (FSM): GREEN -> YELLOW -> ALL_RED -> GREEN            |
|    - Composite Priority Scheduler: Queue Size + Vehicle Priority + Anti-Starvation Boost      |
|    - Strict Invariant Guard: Conflicting Greens are mathematically impossible                 |
+-----------------------+-----------------------------------------------+-----------------------+
                        |                                               |
                        v                                               v
+-----------------------+-----------------------+   +-------------------+-----------------------+
|              PERSISTENCE LAYER                |   |          CONTROLLER INTERFACE / PORT      |
|  PostgreSQL 16 (Docker) / SQLite 3 (Dev)      |   |  TrafficControllerPort (Abstract Port)    |
|  - Idempotency Event Table (ProcessedEvent)   |   |  - RESTSimulatorAdapter (Active Adapter)  |
|  - Vehicle Queue Tracking (Unique vehicle_id) |   |  - MQTTControllerAdapter (Future Plug)    |
|  - Concurrency Lock: select_for_update()      |   |  - Correlation via unique command_id      |
|  - Immutable Audit History (AuditLog)         |   |  - Fail-safe DEGRADED Fallback (ALL-RED)  |
+-----------------------------------------------+   +-------------------------------------------+
```

---

## 2. Traffic Control Domain Logic & State Machine

The core traffic engine strictly decouples non-conflicting traffic phases:
* **Phase 1 (`NORTH_SOUTH`):** `NORTH` & `SOUTH` are GREEN; `EAST` & `WEST` are RED.
* **Phase 2 (`EAST_WEST`):** `EAST` & `WEST` are GREEN; `NORTH` & `SOUTH` are RED.

### Absolute Safety Invariants
1. **Zero Conflicting Green:** Conflicting movements (e.g., North and East) must **NEVER** be simultaneously green. A `SafetyInvariantViolation` exception is raised if an invalid state is calculated.
2. **Mandatory Safe Transition Sequence:** A green phase can **NEVER** switch directly into an opposing green phase. It must transition through the mandatory clearance sequence:
   $$\text{ACTIVE GREEN (30s)} \longrightarrow \text{YELLOW (5s)} \longrightarrow \text{ALL\_RED CLEARANCE (2s)} \longrightarrow \text{NEXT GREEN (30s)}$$
3. **Emergency Preemption Safety:** An approaching emergency vehicle immediately interrupts normal green timing, but **never violates the clearance sequence** (initiates `YELLOW (5s) -> ALL_RED (2s) -> EMERGENCY GREEN`).
4. **Manual Override Safety:** Administrator commands specify an *intent* (e.g., `MANUAL_GREEN_REQUEST` on `WEST`), and the backend safely orchestrates the transition. Direct arbitrary signal overwrites are strictly prohibited.
5. **Physical Telemetry Separation:** Desired state is separated from physical confirmed state (`desired_signals` vs `actual_signals`). If the hardware disconnects, unconfirmed signals remain unverified.

---

## 3. Scheduling & Priority Scoring Algorithm

In `AUTOMATIC` mode, phase switching is decided by a composite priority scoring formula evaluated by `TrafficScheduler`:

$$\text{DirectionScore} = \sum_{v \in \text{queue}} \left( W_{\text{type}} + (\text{WaitTime} \times 0.8) + \text{StarvationBonus} \right)$$

### Vehicle Priority Weights ($W_{\text{type}}$)
| Vehicle Type | Weight | Justification |
| :--- | :---: | :--- |
| **EMERGENCY** | **1000.0** | Dominates scheduling, initiates immediate preemption |
| **TRUCK** | **25.0** | High factory throughput priority (raw material deliveries) |
| **FORKLIFT** | **15.0** | Internal shop-floor material handling movement |
| **EMPLOYEE_VEHICLE** | **5.0** | General passenger transit |

### Anti-Starvation Protection
If any vehicle waits in queue for longer than **45 seconds** (`STARVATION_THRESHOLD_SECONDS`), an automatic **+80.0 score boost** is injected. This mathematically prevents low-priority employee vehicles or forklifts from waiting indefinitely when continuous truck traffic is present.

---

## 4. Tech Stack & Justification

| Layer | Technology | Justification |
| :--- | :--- | :--- |
| **Backend Core** | **Python 3.12 + Django 5/6 + Django REST Framework** | Robust transaction management, database ORM, clean serialization, and enterprise maintainability. |
| **Domain Logic** | **Pure Python (`traffic_engine/`)** | Zero framework coupling. Implements Hexagonal Ports & Adapters (`ControllerPort`) for future MQTT pluggability. |
| **Database** | **PostgreSQL 16 (Docker) / SQLite 3 (Dev)** | Relational integrity; `select_for_update()` row locking prevents race conditions. SQLite default enables zero-config local evaluation. |
| **Frontend** | **Next.js 14+ (App Router) + TypeScript + Tailwind CSS** | Industrial-grade responsive dashboard; visual 4-way intersection; real-time telemetry verification; interactive simulator panel. |
| **API Docs & Testing** | **drf-spectacular (OpenAPI 3.0 / Swagger UI) + Postman v2.1.0** | Live interactive Swagger docs at `/api/docs/` and ready-to-import `postman_collection.json`. |
| **Containerization** | **Docker & Docker Compose** | Multi-container setup for one-command build and automated health-check orchestration. |

---

## 5. Quick Start & Setup Guide

### Option A: One-Command Docker Compose (Recommended)

Requires Docker Desktop installed and running.

```bash
# 1. Clone the repository
git clone https://github.com/ArkaKarmoker/factory-traffic-management-system.git
cd factory-traffic-management-system

# 2. Build and start Backend, Frontend, and PostgreSQL
docker compose up --build
```

* **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
* **Backend API & Swagger Docs:** [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
* **Default Admin Token:** `factory-admin-token-2026`

---

### Option B: Local Development Setup

#### 1. Backend Setup (Python 3.12)
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate       # On Windows PowerShell
# source venv/bin/activate    # On Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run migrations & seed Junction A
python manage.py migrate
python manage.py seed_junction

# Start Django development server
python manage.py runserver 127.0.0.1:8000
```

#### 2. Frontend Setup (Next.js)
Open a second terminal:
```bash
cd frontend

# Install node dependencies
npm install

# Start Next.js development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 6. API Endpoints & Postman Collection

Interactive Swagger UI is live at: `http://localhost:8000/api/docs/`  
An exportable, 100% verified Postman collection is located at: [`postman_collection.json`](postman_collection.json).

### Postman Collection Structure (5 Folders, 19 Requests)
* **`1. Junctions & Live Telemetry`** (List Junctions, Details, Live Status, Queues Detail)
* **`2. Sensor Events (Vehicle Detection)`** (Forklift, Truck, Emergency Preemption, Vehicle Cleared, Idempotency Test)
* **`3. Manual Supervisor Control`** (Manual Green WEST, Manual Green NORTH, Return to Automatic)
* **`4. Physical Controller Hardware Telemetry`** (Hardware ACK, Simulate OFFLINE, Simulate ONLINE)
* **`5. Audit History & Simulation Helpers`** (Audit Trail Limit 50, Event Type Filter, Fast-forward Tick, Clean Reset)

### Minimum Backend APIs (Section 10 Compliance)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/junctions` | List all registered junctions in the facility (Section 10.1) |
| `GET` | `/api/junctions/:id` | Get junction configuration and status |
| `GET` | `/api/junctions/:id/status` | Real-time operational telemetry, desired vs actual signals, queues (Section 10.3) |
| `POST` | `/api/sensor-events` | Ingest vehicle arrivals / departures with idempotency (Section 10.2) |
| `POST` | `/api/junctions/:id/commands` | Administrative manual control commands (`X-Admin-Token`) (Section 10.4) |
| `POST` | `/api/controller-events` | Hardware ACK & device status telemetry (Section 10.5) |
| `GET` | `/api/junctions/:id/history` | Historical immutable audit trail and transition logs (Section 10.6) |
| `GET` | `/api/junctions/:id/queues` | Detailed individual vehicles waiting in queue |
| `POST` | `/api/junctions/:id/tick` | Advance transition timer step immediately (Evaluator simulator) |
| `POST` | `/api/junctions/:id/reset` | Reset demo state to clean initial configuration |

---

## 7. Automated Test Suite & Verification

The project includes **24 comprehensive automated tests** spanning pure domain safety invariants, REST API integration, and an explicit test suite covering all **Section 15 Functional Scenarios** mandated by the assessment specification.

Run tests via `pytest`:
```bash
cd backend
.\venv\Scripts\pytest -q
```
*Result: `........................  24 passed in 0.76s (100%)`*

### Test Suites Breakdown
1. **`test_domain_engine.py` (5 Pure Python Unit Tests):**
   * Confirms `SafetyInvariantViolation` raised on conflicting greens.
   * Verifies valid non-conflicting phases (`NORTH_SOUTH`, `EAST_WEST`).
   * Validates deterministic sequence: `STEADY -> YELLOW (5s) -> ALL_RED (2s) -> NEXT_STEADY`.
   * Asserts emergency priority dominates scheduling over all vehicle types.
   * Tests anti-starvation boost (>45s wait threshold score jump).

2. **`test_api_endpoints.py` (6 REST API Integration Tests):**
   * Deduplication idempotency (`event_id` reuse returns HTTP 200 `DUPLICATE_IGNORED`).
   * Duplicate vehicle ID guard in queue (`DUPLICATE_VEHICLE_IGNORED`).
   * Vehicle clearance & non-negative queue guard (`queue >= 0`).
   * Emergency preemption triggering yellow clearance.
   * Manual command override & return to automatic mode.
   * Physical controller offline degraded state.

3. **`test_section15_scenarios.py` (13 End-to-End Functional Scenario Tests):**
   * **Scenario 1:** Normal traffic ingestion across directions.
   * **Scenario 2:** Priority traffic weighting (Truck/Forklift vs Employee car).
   * **Scenario 3:** Emergency preemption during conflicting green.
   * **Scenario 4:** Manual override by administrator and return to automatic.
   * **Scenario 5:** Duplicate sensor event idempotency guarantee.
   * **Scenario 6:** Vehicle departure clearance & empty queue handling.
   * **Scenario 7:** Controller failure & fail-safe degraded fallback.
   * **Scenario 8:** Application restart data persistence & state recovery.
   * **Scenario 9:** High-concurrency race condition test (simultaneous events at T=0ms, 4ms, 8ms, 12ms, 17ms with DB row locks).

---

## 8. Demonstrating the Evaluation Scenarios

The Next.js dashboard provides a dedicated **Evaluator Test Simulator**:

1. **Normal & Priority Traffic:**
   - Under *Vehicles & Queues* tab, select `EAST`, choose `TRUCK`, and click **Simulate Arrival**.
   - Notice the queue increase and scheduling preference over employee vehicles.
2. **Emergency Preemption (Section 7):**
   - Click the *Emergency Siren* tab, and click **Ambulance on EAST**.
   - Observe the North/South lights transition to **YELLOW**, then **ALL-RED**, then **EAST GREEN**.
3. **Manual Override (Section 8):**
   - In the *Supervisor Manual Override* panel, click **Green WEST**.
   - The system initiates safe transition and holds WEST green.
   - Click **Return to AUTOMATIC Engine** to restore auto-scheduling.
4. **Duplicate Event Idempotency & Duplicate Vehicle Guard (Section 4):**
   - Send any vehicle arrival. Then click the purple **Test Idempotency (Resend)** button.
   - Notice that neither the duplicate `event_id` nor the duplicate `vehicle_id` inflates the queue count multiple times.
5. **Controller Failure & State Mismatch Verification (Section 9 & 14.6):**
   - Under *Controller Hardware* tab, click **Simulate Controller OFFLINE**.
   - The junction immediately enters **DEGRADED** mode and commands **Desired ALL-RED**.
   - Notice the amber **State Mismatch Detected** warning banner: since the hardware controller is offline, the backend strictly preserves Section 9 invariants and does not fabricate physical confirmation telemetry.
   - Click **Simulate Controller ONLINE** to restore normal operation and resynchronize telemetry.

---

## Assumptions / Questions / Requirement Issues

As instructed in Section 17 & 19 of the assessment specification, several requirements were intentionally incomplete or ambiguous. Below is the documentation of identified issues and engineering decisions:

### 1. Authoritative Timestamp & Network Delays
* **Issue:** Sensor events include a client timestamp, server arrival time, and sequence number. Late or delayed events could cause race conditions.
* **Decision:** We record `sensor_timestamp` for audit logging, but **server receipt time (`processed_at`) inside a database transaction is authoritative** for queue FIFO order and transition timers.

### 2. Idempotency vs. Out-of-Order Retries
* **Issue:** The spec asks how duplicate and out-of-order events should be treated.
* **Decision:** We introduced a dedicated `ProcessedEvent` table keyed on `event_id`. Duplicate arrivals are returned with HTTP 200 `DUPLICATE_IGNORED` and do not alter queues. Sequence numbers are verified to ignore stale events.

### 3. Vehicle Clearance Without Prior Arrival
* **Issue:** What happens if a `VEHICLE_CLEARED` event arrives for a vehicle never registered or when queue is 0?
* **Decision:** The system strictly enforces `queue >= 0`. If a clearance arrives for an unrecorded vehicle or empty queue, it logs a `VEHICLE_CLEARED_EMPTY_QUEUE_IGNORED` audit entry and keeps queue at 0, preventing negative numbers.

### 4. Competing Emergency Vehicles from Conflicting Directions
* **Issue:** What if an ambulance approaches from NORTH and another from EAST simultaneously?
* **Decision:** The first arrived emergency holds priority. The opposing emergency is queued with maximum priority score ($1000.0+$). Once the first emergency departs (`VEHICLE_CLEARED`), the engine immediately preempts to the opposing emergency.

### 5. Manual Override Duration & Operator Disconnect
* **Issue:** How long does manual control stay active if an administrator disconnects?
* **Decision:** Manual override represents an intentional operational takeover (e.g., dedicated conveyor crossing, facility maintenance, or heavy machinery clearance). Therefore, **manual mode persists indefinitely on hold until an authorized operator explicitly commands `RETURN_TO_AUTOMATIC`** (or a higher-priority emergency vehicle preempts it for life safety). This ensures that traffic remains strictly under operator command and does not unexpectedly auto-switch.

### 6. Desired State vs. Actual State Discrepancy & Offline Controller Handling
* **Issue:** What if the controller reports `OFFLINE` or fails to acknowledge a requested signal change? Should the backend assume physical lights are RED?
* **Decision:** Pursuant to Section 9 (*"A controller that does not confirm a requested state must not automatically be assumed to have executed it"*), the backend switches to `DEGRADED` mode and sets `desired_signals` to **ALL-RED** for safety, but **refuses to fabricate actual physical confirmation**. The physical `actual_signals` remain unconfirmed at their last known state, triggering the **State Mismatch Alert** across the dashboard until telemetry is restored via `ONLINE` or subsequent ACK.

### 7. Application Restart During Active Transition
* **Issue:** How to recover if the server crashes while in `YELLOW` or `ALL_RED`?
* **Decision:** Upon boot / recovery, the engine inspects active transitions. Rather than assuming the hardware completed the transition, it issues an immediate `ALL_RED_CLEARANCE` command to the controller to reset the intersection safely before resuming normal scheduling.

### 8. Duplicate Vehicle Identifier (`vehicle_id`) in Queue
* **Issue:** The specification allows same vehicle type, but does not explicitly prevent a sensor from misreporting the exact same vehicle number entering the queue multiple times without clearing.
* **Decision:** A vehicle with an active identifier (e.g., `VH-FL-501`) that is already waiting in queue cannot enter again until a `VEHICLE_CLEARED` event is received. Resubmissions of an active `vehicle_id` are rejected with `DUPLICATE_VEHICLE_IGNORED` to prevent phantom queue inflation.

---

## 10. Major Architectural Decisions & Trade-offs

1. **Hexagonal Architecture (Ports & Adapters):**
   - The core `traffic_engine` is pure Python standard library (`dataclasses`, `enum`, `typing`).
   - The `TrafficControllerPort` abstract class allows replacing the current REST simulator with an MQTT adapter (`MQTTControllerAdapter`) without altering a single line of domain logic.
2. **Database Row Locking (`select_for_update`):**
   - To prevent concurrent events from causing race conditions, junction state mutations are wrapped in Django atomic transactions with `select_for_update()`.
3. **Non-blocking Daemon Timer:**
   - Rather than blocking HTTP request threads with `time.sleep()`, transitions are stepped via a background worker thread (`TrafficBackgroundWorker`) and exposed via `/api/junctions/:id/tick`.

---

## AI / Tool Usage

As requested in Section 18.12 and the submission form:

* **Tools Used:** Antigravity AI Pair-Programming Assistant (Google Gemini 3.8 Flash model).
* **Scope of Usage:**
  - Rapid scaffolding of Django REST Framework serializers and views.
  - Designing TypeScript interfaces and Tailwind CSS layout components for Next.js.
  - Writing automated pytest fixtures and edge-case unit tests.
  - Formatting OpenAPI schema decorators and Postman collection JSON.
* **Engineering Accountability:** All architectural choices, safety invariants, state machine transitions, concurrency locks, and requirement issue decisions were planned, reviewed, and validated for technical correctness. The author is fully prepared to explain, debug, and modify any component of this codebase during the technical review.

---

## 12. Google Form Submission Cheat-Sheet

Here is the exact information prepared to copy-paste into the [CSI Smart Tech Google Form](https://docs.google.com/forms/d/e/1FAIpQLSe9YkBUKnUOrhdl-7U0iNJjmZ4YTkvCV8QZqa5fvYdfDGH8WA/viewform):

| Form Question | Recommended Response |
| :--- | :--- |
| **Email Address** | `arkakarmoker1234@gmail.com` |
| **Full Name** | Arka Karmoker |
| **GitHub Profile URL** | https://github.com/ArkaKarmoker |
| **GitHub Repository URL** | https://github.com/ArkaKarmoker/factory-traffic-management-system |
| **Did you use AI-assisted tools?** | **Yes** |
| **Which AI tools & how?** | Antigravity AI (Google Gemini 3.8 Flash) for scaffolding DRF views, Next.js frontend UI components, pytest test case generation, and Postman v2.1.0 schema formatting. Core domain safety invariants, finite state machine transitions, and database concurrency locks were strictly planned, verified, and reviewed. |
| **Share your AI chat history** | Full conversational logs and step-by-step decision transcripts are permanently preserved and available in the repository documentation. |
| **Additional Notes** | Completed full Section 10 Minimum APIs, Section 8 Manual Override, Section 9 Hardware Telemetry, Section 14 Next.js Visual Dashboard, Section 15 Scenario Automated Tests (24/24 passing), Docker Compose one-command deployment, and an exportable Postman Collection with 19 verified requests. |