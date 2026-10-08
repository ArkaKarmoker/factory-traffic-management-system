# AI-Assisted Development Interaction Summary 🤖

**Candidate:** Arka Karmoker  
**Repository:** [factory-traffic-management-system](https://github.com/ArkaKarmoker/factory-traffic-management-system)  
**Assessment:** CSI Smart Tech Backend Developer Intern Technical Assessment (FTMS V2)  
**AI Assistant:** Antigravity AI (Google Gemini 3.8 Flash)

---

## 1. Summary of AI Usage
Throughout the development of the Factory Traffic Management System (FTMS), AI was utilized as an intelligent pair-programming assistant for:
1. **Rapid API & Schema Scaffolding:** Generating initial boilerplate for Django REST Framework serializers, viewsets, and OpenAPI 3.0 schema decorators (`drf-spectacular`).
2. **Frontend UI Assembly:** Assisting with Tailwind CSS styling, responsive layout grids, and shadcn/ui components for the Next.js visual intersection dashboard.
3. **Automated Test Generation:** Drafting comprehensive pytest fixtures and test cases for Section 15 evaluation scenarios (concurrency race conditions, duplicate event idempotency, emergency preemption, and controller failures).
4. **Postman Schema Formatting:** Compiling the Postman Collection v2.1.0 schema with pre-configured variables, raw JSON bodies, and headers.

---

## 2. Core Engineering & Candidate Ownership
All critical architectural, safety, and business logic decisions were explicitly designed, validated, and implemented:
* **Safety Invariant Guard:** Conflicting greens are mathematically prohibited via the pure domain engine.
* **Deterministic FSM Sequence:** Mandatory transition sequence (`GREEN -> YELLOW (5s) -> ALL_RED (2s) -> NEXT GREEN (30s)`).
* **Database Concurrency Control:** Implemented `select_for_update()` row-level locks within Django atomic transactions to eliminate race conditions under concurrent sensor events.
* **Anti-Starvation Algorithm:** Crafted the composite priority formula with an automatic `+80.0` score boost after 45s wait time.
* **Requirement Ambiguities Resolution:** Documented and solved all 8 key ambiguous areas (including duplicate vehicle ID deduplication and controller offline telemetry preservation).

The candidate fully understands the codebase and is completely prepared to explain, walk through, debug, or live-code modifications during the technical interview.
