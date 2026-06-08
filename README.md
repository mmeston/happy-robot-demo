# HappyRobot Carrier Sales Automation

FastAPI backend for an inbound carrier sales proof of concept. The API is designed to be called by a HappyRobot voice agent for carrier verification, load search, negotiation guardrails, booking intake, and call logging.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
python seed_loads.py
uvicorn app:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Environment Variables

Create a `.env` file when needed:

```bash
FMCSA_WEB_KEY=your_fmcsa_key
API_KEY=optional_shared_secret
DB_PATH=/optional/path/to/loads.db
```

If `API_KEY` is set, protected endpoints require this header:

```bash
x-api-key: your_shared_secret
```

`/health`, `/docs`, `/openapi.json`, and `/redoc` remain public.

## Core Endpoints

- `GET /health`
- `GET /loads`
- `GET /loads/search?origin=Chicago&destination=Dallas&equipment_type=Dry%20Van`
- `GET /loads/searchbyid?id=L1001`
- `GET /loads/L1001`
- `POST /carrier/verify`
- `POST /check-bid`
- `GET /negotiations/status?session_id=call-123&load_id=L1001`
- `POST /update-status`
- `POST /booking/intake`
- `POST /call-log`

Negotiation state is stored in two simple tables:

- `negotiation_sessions`: current state for one `session_id` + `load_id`
- `negotiation_events`: append-only event history for analytics and audit

Nancy can check whether a carrier bid is immediately acceptable with:

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

Nancy can retrieve negotiation memory with:

```text
GET /negotiations/status?session_id=call-123&load_id=L1001
```

Nancy writes her decision through:

```text
POST /update-status
```

Counter decision:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "COUNTER",
  "amount": 1850
}
```

Acceptance decision:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "ACCEPT"
}
```

Rejection decision:

```json
{
  "session_id": "call-123",
  "load_id": "L1001",
  "decision": "REJECT"
}
```

The backend uses `session_id` and `load_id` to track negotiation history per load.
`check-bid` records the carrier's latest offer and tells Nancy whether it can be accepted.
`update-status` validates Nancy's final decision before updating the current session and event history.

## Validation and Error Responses

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

## Demo Carrier

`MC-123456` always returns an eligible carrier for demo stability if the FMCSA API is unavailable.

## Docker

```bash
docker build -t happyrobot-carrier-sales .
docker run --env-file .env -p 8000:8000 happyrobot-carrier-sales
```
