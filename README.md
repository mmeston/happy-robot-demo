# HappyRobot Carrier Sales Automation

FastAPI backend and operational dashboard for an inbound carrier sales proof of concept built on the HappyRobot platform.

The workflow lets a carrier call in, verify their MC number, search available loads, negotiate pricing with guardrails, mock-transfer accepted bookings, and write post-call reporting data for a brokerage-facing dashboard.

## Architecture

- `FastAPI` serves the HappyRobot tool endpoints and dashboard.
- `SQLite` stores demo loads, negotiation state, booking intake rows, and dashboard reporting rows.
- `HappyRobot Twin` is used as agent memory for future personalization.
- The dashboard reads from this API's reporting database, not from Twin.
- Render provides the deployed HTTPS API URL used by the HappyRobot workflow.

Twin and reporting are intentionally separate:

- Twin answers: "What should the agent remember about this carrier next time?"
- Reporting answers: "What should the brokerage know about call performance and operations?"

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

The app initializes the database and seeds demo loads on startup.

Local API:

```text
http://127.0.0.1:8000
```

## Environment Variables

Create a `.env` file:

```bash
FMCSA_WEB_KEY=your_fmcsa_key
API_KEY=your_shared_secret
DB_PATH=/optional/path/to/loads.db
```

If `API_KEY` is set, protected endpoints require:

```http
x-api-key: your_shared_secret
```

Public endpoints:

- `GET /health`
- `GET /docs`
- `GET /openapi.json`
- `GET /redoc`
- `GET /dashboard`
- `GET /dashboard-data`

Render provides HTTPS for the deployed API.

## HappyRobot Tool Endpoints

Load search:

- `GET /loads`
- `GET /loads/search?origin=Chicago&destination=Dallas&equipment_type=Dry%20Van`
- `GET /loads/searchbyid?id=L1001`
- `GET /loads/L1001`

Carrier verification:

- `POST /carrier/verify`

Negotiation:

- `POST /check-bid`
- `GET /negotiations/status?session_id=call-123&load_id=L1001`
- `POST /update-status`

Post-negotiation:

- `POST /booking/intake`
- `POST /reporting/call`
- `POST /call-log`

`/call-log` is retained as a simple audit endpoint. The dashboard uses `/reporting/call`.

## Negotiation Flow

Nancy, the negotiation advisor, uses three backend tools.

First, check whether the carrier offer is immediately acceptable:

```text
POST /check-bid
```

Opening price request:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "carrier_offer": null
}
```

Carrier price request:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "carrier_offer": 1800
}
```

Then retrieve negotiation memory:

```text
GET /negotiations/status?session_id=call-123&load_id=L1001
```

Finally, write Nancy's decision:

```text
POST /update-status
```

Counter:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "COUNTER",
  "amount": 1850
}
```

Accept:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "ACCEPT"
}
```

Reject:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "REJECT"
}
```

The backend stores negotiation state in:

- `negotiation_sessions`: current state for one `session_id` + `load_id`
- `negotiation_events`: append-only event history for auditability

## Reporting Endpoint

After the HappyRobot Extract step and after writing carrier memory to Twin, the workflow should call:

```text
POST /reporting/call
```

Example body:

```json
{
  "session_id": "call-123",
  "mc_number": "MC-123456",
  "carrier_name": "B MARRON LOGISTICS LLC",
  "load_id": "L1001",
  "origin": "Chicago, IL",
  "destination": "Dallas, TX",
  "equipment_type": "Dry Van",
  "offered_rate": 1700,
  "carrier_requested_rate": 1900,
  "final_rate": 1850,
  "outcome": "booked",
  "summary": "Carrier booked Chicago to Dallas dry van at $1850 after one counter.",
  "mood": "Friendly",
  "letterboard_rate": 1850,
  "last_offered_rate": 1850,
  "call_duration_seconds": 210,
  "negotiation_rounds": 2,
  "tool_call_count": 8,
  "call_status": "completed",
  "call_end_event": "agent_ended",
  "transfer_completed": true
}
```

Notes:

- `letterboard_rate` is stored for dashboard pricing analytics.
- `loadboard_rate` is also accepted as a backup field name.
- `call_status` is the platform/run status, such as `completed`, `failed`, or `in-progress`.
- `outcome` is the business result, such as `booked`, `rate_decline`, `no_match`, or `carrier_not_eligible`.
- The endpoint upserts by `session_id`, so retries update the same call row instead of creating duplicates.

## Dashboard

Dashboard:

```text
GET /dashboard
```

Data API:

```text
GET /dashboard-data
```

The dashboard shows a curated demo dataset plus any live rows written to `reporting_calls`. This keeps the dashboard useful for a recorded demo while still showing the most recent test call after the HappyRobot workflow runs.

Use this URL for demo-only data:

```text
/dashboard?source=demo
```

Current dashboard sections include:

- Top-level call metrics
- Workflow Health
- Negotiation Outcomes
- Follow-Up Opportunities
- Compact Call Database with summaries

## Demo Carrier

`MC-123456` always returns an eligible carrier for demo stability if the FMCSA API is unavailable.

## Docker

The challenge asks for the solution to be containerized. Docker is not strictly required for Render to run the app, but it makes the runtime reproducible.

```bash
docker build -t happyrobot-carrier-sales .
docker run --env-file .env -p 8000:8000 happyrobot-carrier-sales
```

## Deployment

The API is deployed on Render from the GitHub repository. Render supplies HTTPS and redeploys from the `main` branch.

When code changes are pushed to GitHub, Render redeploys the latest version. Because the app uses SQLite without a persistent disk, demo data is seeded at startup and reporting rows are treated as lightweight demo persistence rather than long-term storage.

## Error Responses

Business errors return structured JSON so the HappyRobot agent can explain what went wrong and recover in conversation.

Example:

```json
{
  "ok": false,
  "error_code": "LOAD_NOT_FOUND",
  "message": "No load found for reference number L9999.",
  "field": "load_id",
  "details": {
    "load_id": "L9999"
  }
}
```

Validation errors use `error_code: "VALIDATION_ERROR"` and include field-level details.
