import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
import requests

from api.config import TWIN_API_KEY, TWIN_GATEWAY_URL, TWIN_ORG_ID, TWIN_TABLE_NAME
from api.database import db_connection
from api.errors import raise_tool_error
from api.models import (
    BookingIntakeRequest,
    BookingIntakeResponse,
    CallLogRequest,
    CallLogResponse,
    CarrierVerificationRequest,
    CarrierVerificationResponse,
    CheckBidRequest,
    CheckBidResponse,
    NegotiationStatusResponse,
    UpdateNegotiationStatusRequest,
    UpdateNegotiationStatusResponse,
)
from api.services import create_booking_reference, verify_carrier_by_mc


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "healthy"}


@router.get("/dashboard", include_in_schema=False)
def dashboard():
    dashboard_path = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"
    return FileResponse(dashboard_path)


@router.get("/dashboard-data", include_in_schema=False)
def dashboard_data():
    if not TWIN_GATEWAY_URL:
        return {
            "source": "fallback",
            "configured": False,
            "rows": [],
            "message": "TWIN_GATEWAY_URL is not configured.",
        }

    headers = {}
    if TWIN_ORG_ID:
        headers["x-org-id"] = TWIN_ORG_ID
    if TWIN_API_KEY:
        headers["Authorization"] = f"Bearer {TWIN_API_KEY}"
        headers["x-api-key"] = TWIN_API_KEY

    base_url = TWIN_GATEWAY_URL.rstrip("/")
    path = f"/twin/tables/{TWIN_TABLE_NAME}/rows"
    url = f"{base_url}{path}"

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"limit": 500},
            timeout=10,
        )
        if response.status_code == 404:
            response = requests.get(
                f"{base_url}/tables/{TWIN_TABLE_NAME}/rows",
                headers=headers,
                params={"limit": 500},
                timeout=10,
            )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {
            "source": "fallback",
            "configured": True,
            "rows": [],
            "message": f"Unable to read Twin rows: {exc}",
        }

    payload = response.json()
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = (
            payload.get("rows")
            or payload.get("data")
            or payload.get("result")
            or []
        )
    else:
        rows = []

    return {
        "source": "twin",
        "configured": True,
        "rows": rows,
    }


@router.get("/loads")
def get_all_loads():
    with db_connection() as conn:
        loads = conn.execute("SELECT * FROM loads").fetchall()

    return [dict(load) for load in loads]

@router.get("/loads/searchbyid")
def search_by_id(
    id: str = Query(..., min_length=1, description="Load reference number"),
):
    load_id = id.strip().upper()
    query = "SELECT * FROM loads WHERE load_id = ?"

    with db_connection() as conn:
        loads = conn.execute(query, (load_id,)).fetchall()

    if not loads:
        raise_tool_error(
            404,
            "LOAD_NOT_FOUND",
            f"No load found for reference number {load_id}.",
            field="id",
            details={"load_id": load_id},
        )

    return {"count": len(loads), "loads": [dict(load) for load in loads]}


@router.get("/loads/search")
@router.get("/loads/searchbykeyword")
def search_loads(
    origin: Optional[str] = Query(default=None),
    destination: Optional[str] = Query(default=None),
    equipment_type: Optional[str] = Query(default=None),
):
    if not any([origin, destination, equipment_type]):
        raise_tool_error(
            400,
            "LOAD_SEARCH_CRITERIA_REQUIRED",
            "Provide at least one search field: origin, destination, or equipment_type.",
            details={
                "accepted_fields": ["origin", "destination", "equipment_type"],
            },
        )

    query = "SELECT * FROM loads WHERE 1=1"
    params = []

    if origin:
        query += " AND LOWER(origin) LIKE LOWER(?)"
        params.append(f"%{origin}%")

    if destination:
        query += " AND LOWER(destination) LIKE LOWER(?)"
        params.append(f"%{destination}%")

    if equipment_type:
        query += " AND LOWER(equipment_type) LIKE LOWER(?)"
        params.append(f"%{equipment_type}%")

    with db_connection() as conn:
        loads = conn.execute(query, params).fetchall()

    if not loads:
        raise_tool_error(
            404,
            "NO_MATCHING_LOADS",
            "No loads matched the requested search criteria.",
            details={
                "origin": origin,
                "destination": destination,
                "equipment_type": equipment_type,
            },
        )

    return {"count": len(loads), "loads": [dict(load) for load in loads]}


@router.get("/loads/{load_id}")
def get_load_by_id(load_id: str):
    normalized_load_id = load_id.strip().upper()

    if not normalized_load_id:
        raise_tool_error(
            422,
            "VALIDATION_ERROR",
            "Load reference number is required.",
            field="load_id",
        )

    with db_connection() as conn:
        load = conn.execute(
            "SELECT * FROM loads WHERE load_id = ?",
            (normalized_load_id,),
        ).fetchone()

    if not load:
        raise_tool_error(
            404,
            "LOAD_NOT_FOUND",
            f"No load found for reference number {normalized_load_id}.",
            field="load_id",
            details={"load_id": normalized_load_id},
        )

    return {"count": 1, "loads": [dict(load)]}


@router.post("/carrier/verify", response_model=CarrierVerificationResponse)
def verify_carrier(request: CarrierVerificationRequest):
    return verify_carrier_by_mc(request.mc_number)


@router.get("/negotiations/status", response_model=NegotiationStatusResponse)
@router.get("/negotiations/{session_id}/{load_id}", response_model=NegotiationStatusResponse)
def get_negotiation_status(
    session_id: str,
    load_id: str,
):
    normalized_load_id = load_id.strip().upper()

    with db_connection() as conn:
        load = conn.execute(
            "SELECT * FROM loads WHERE load_id = ?",
            (normalized_load_id,),
        ).fetchone()

        if not load:
            raise_tool_error(
                404,
                "LOAD_NOT_FOUND",
                f"No load found for reference number {normalized_load_id}.",
                field="load_id",
                details={"load_id": normalized_load_id},
            )

        session = conn.execute(
            """
            SELECT *
            FROM negotiation_sessions
            WHERE session_id = ? AND load_id = ?
            """,
            (session_id, normalized_load_id),
        ).fetchone()

        events = conn.execute(
            """
            SELECT actor, event_type, amount, round_number, metadata, created_at
            FROM negotiation_events
            WHERE session_id = ? AND load_id = ?
            ORDER BY id ASC
            """,
            (session_id, normalized_load_id),
        ).fetchall()

    return {
        "session_id": session_id,
        "load_id": normalized_load_id,
        "status": session["status"] if session else "active",
        "round_count": session["round_count"] if session else 0,
        "last_carrier_offer": session["last_carrier_offer"] if session else None,
        "last_nancy_offer": session["last_nancy_offer"] if session else None,
        "final_rate": session["final_rate"] if session else None,
        "loadboard_rate": load["loadboard_rate"],
        "load": dict(load),
        "events": [dict(event) for event in events],
    }


@router.post("/check-bid", response_model=CheckBidResponse)
@router.post("/check_bid", response_model=CheckBidResponse)
def check_bid(request: CheckBidRequest):
    with db_connection() as conn:
        load = conn.execute(
            "SELECT loadboard_rate FROM loads WHERE load_id = ?",
            (request.load_id,),
        ).fetchone()

        if not load:
            raise_tool_error(
                404,
                "LOAD_NOT_FOUND",
                f"No load found for reference number {request.load_id}.",
                field="load_id",
                details={"load_id": request.load_id},
            )

        session = conn.execute(
            """
            SELECT *
            FROM negotiation_sessions
            WHERE session_id = ? AND load_id = ?
            """,
            (request.session_id, request.load_id),
        ).fetchone()

        if not session:
            conn.execute(
                """
                INSERT INTO negotiation_sessions (
                    session_id,
                    load_id
                )
                VALUES (?, ?)
                """,
                (request.session_id, request.load_id),
            )
            conn.commit()
            session = conn.execute(
                """
                SELECT *
                FROM negotiation_sessions
                WHERE session_id = ? AND load_id = ?
                """,
                (request.session_id, request.load_id),
            ).fetchone()

        loadboard_rate = load["loadboard_rate"]

        if (
            request.carrier_offer is not None
            and request.carrier_offer != session["last_carrier_offer"]
        ):
            round_count = session["round_count"]
            event_round_number = min(round_count + 1, 3)
            conn.execute(
                """
                UPDATE negotiation_sessions
                SET
                    last_carrier_offer = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND load_id = ?
                """,
                (
                    request.carrier_offer,
                    request.session_id,
                    request.load_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO negotiation_events (
                    session_id,
                    load_id,
                    actor,
                    event_type,
                    amount,
                    round_number,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.session_id,
                    request.load_id,
                    "carrier",
                    "carrier_offer",
                    request.carrier_offer,
                    event_round_number,
                    json.dumps({"loadboard_rate": loadboard_rate}),
                ),
            )
            conn.commit()
        else:
            round_count = session["round_count"]

    if request.carrier_offer is None:
        return {
            "accept": False,
            "amount": None,
            "needs_opening_offer": True,
            "can_continue": True,
            "reason": "NO_CARRIER_OFFER",
            "session_id": request.session_id,
            "load_id": request.load_id,
            "round_count": round_count,
            "loadboard_rate": loadboard_rate,
        }

    if request.carrier_offer <= loadboard_rate:
        return {
            "accept": True,
            "amount": request.carrier_offer,
            "needs_opening_offer": False,
            "can_continue": False,
            "reason": "CARRIER_OFFER_WITHIN_RATE",
            "session_id": request.session_id,
            "load_id": request.load_id,
            "round_count": round_count,
            "loadboard_rate": loadboard_rate,
        }

    if round_count >= 3:
        return {
            "accept": False,
            "amount": None,
            "needs_opening_offer": False,
            "can_continue": False,
            "reason": "NEGOTIATION_LIMIT_REACHED",
            "session_id": request.session_id,
            "load_id": request.load_id,
            "round_count": round_count,
            "loadboard_rate": loadboard_rate,
        }

    return {
        "accept": False,
        "amount": None,
        "needs_opening_offer": False,
        "can_continue": True,
        "reason": "CARRIER_OFFER_ABOVE_RATE",
        "session_id": request.session_id,
        "load_id": request.load_id,
        "round_count": round_count,
        "loadboard_rate": loadboard_rate,
    }


@router.post("/update-status", response_model=UpdateNegotiationStatusResponse)
@router.post("/update_status", response_model=UpdateNegotiationStatusResponse)
def update_negotiation_status(request: UpdateNegotiationStatusRequest):
    with db_connection() as conn:
        load = conn.execute(
            "SELECT loadboard_rate FROM loads WHERE load_id = ?",
            (request.load_id,),
        ).fetchone()

        if not load:
            raise_tool_error(
                404,
                "LOAD_NOT_FOUND",
                f"No load found for reference number {request.load_id}.",
                field="load_id",
                details={"load_id": request.load_id},
            )

        session = conn.execute(
            """
            SELECT *
            FROM negotiation_sessions
            WHERE session_id = ? AND load_id = ?
            """,
            (request.session_id, request.load_id),
        ).fetchone()

        if not session:
            raise_tool_error(
                404,
                "NEGOTIATION_SESSION_NOT_FOUND",
                "No negotiation session exists for this call and load.",
                details={
                    "session_id": request.session_id,
                    "load_id": request.load_id,
                },
            )

        loadboard_rate = load["loadboard_rate"]
        round_count = session["round_count"]
        last_carrier_offer = session["last_carrier_offer"]
        last_nancy_offer = session["last_nancy_offer"]

        if request.decision == "ACCEPT":
            if last_carrier_offer is None:
                raise_tool_error(
                    400,
                    "NO_CARRIER_OFFER_TO_ACCEPT",
                    "Cannot accept because no carrier offer has been recorded.",
                    field="decision",
                )

            if last_carrier_offer > loadboard_rate:
                raise_tool_error(
                    400,
                    "CARRIER_OFFER_ABOVE_RATE",
                    "Cannot accept because the carrier offer is above loadboard rate.",
                    field="decision",
                    details={
                        "carrier_offer": last_carrier_offer,
                        "loadboard_rate": loadboard_rate,
                    },
                )

            status = "accepted"
            amount = last_carrier_offer
            event_type = "accepted"
            actor = "nancy"
            reason = "ACCEPTED"
            final_rate = amount
            new_round_count = round_count

        elif request.decision == "COUNTER":
            if request.amount is None:
                raise_tool_error(
                    422,
                    "COUNTER_AMOUNT_REQUIRED",
                    "Counter decisions require an amount.",
                    field="amount",
                )

            if round_count >= 3:
                raise_tool_error(
                    400,
                    "NEGOTIATION_LIMIT_REACHED",
                    "Cannot counter because the negotiation round limit has been reached.",
                    field="decision",
                    details={"round_count": round_count},
                )

            if request.amount > loadboard_rate:
                raise_tool_error(
                    400,
                    "COUNTER_ABOVE_RATE",
                    "Cannot counter above loadboard rate.",
                    field="amount",
                    details={
                        "amount": request.amount,
                        "loadboard_rate": loadboard_rate,
                    },
                )

            if (
                last_carrier_offer is not None
                and last_carrier_offer <= loadboard_rate
            ):
                raise_tool_error(
                    400,
                    "CARRIER_OFFER_ALREADY_ACCEPTABLE",
                    "Cannot counter because the carrier offer is already within loadboard rate.",
                    field="decision",
                    details={
                        "carrier_offer": last_carrier_offer,
                        "loadboard_rate": loadboard_rate,
                    },
                )

            if last_nancy_offer is not None and request.amount < last_nancy_offer:
                raise_tool_error(
                    400,
                    "COUNTER_BELOW_LAST_NANCY_OFFER",
                    "Counter must be at or above Nancy's previous offer.",
                    field="amount",
                    details={
                        "amount": request.amount,
                        "last_nancy_offer": last_nancy_offer,
                    },
                )

            if last_carrier_offer is not None and request.amount >= last_carrier_offer:
                raise_tool_error(
                    400,
                    "COUNTER_NOT_BELOW_CARRIER_OFFER",
                    "Counter must be less than the carrier's latest offer.",
                    field="amount",
                    details={
                        "amount": request.amount,
                        "last_carrier_offer": last_carrier_offer,
                    },
                )

            status = "active"
            amount = request.amount
            event_type = (
                "opening_offer"
                if last_carrier_offer is None and last_nancy_offer is None
                else "nancy_counter"
            )
            actor = "nancy"
            reason = "COUNTER_SAVED"
            final_rate = None
            new_round_count = round_count + 1

        else:
            if round_count < 3 and session["status"] == "active":
                raise_tool_error(
                    400,
                    "REJECT_NOT_ALLOWED",
                    "Reject is only allowed after the round limit is reached or negotiation cannot continue.",
                    field="decision",
                    details={
                        "round_count": round_count,
                        "status": session["status"],
                    },
                )

            status = "rejected"
            amount = request.amount
            event_type = "rejected"
            actor = "nancy"
            reason = "REJECTED"
            final_rate = None
            new_round_count = round_count

        conn.execute(
            """
            UPDATE negotiation_sessions
            SET
                status = ?,
                last_nancy_offer = COALESCE(?, last_nancy_offer),
                final_rate = COALESCE(?, final_rate),
                round_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ? AND load_id = ?
            """,
            (
                status,
                amount if request.decision == "COUNTER" else None,
                final_rate,
                new_round_count,
                request.session_id,
                request.load_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO negotiation_events (
                session_id,
                load_id,
                actor,
                event_type,
                amount,
                round_number,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.session_id,
                request.load_id,
                actor,
                event_type,
                amount,
                new_round_count,
                json.dumps(
                    {
                        "decision": request.decision,
                        "reason": reason,
                        "loadboard_rate": loadboard_rate,
                    }
                ),
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "decision": request.decision,
        "session_id": request.session_id,
        "load_id": request.load_id,
        "status": status,
        "amount": amount,
        "round_count": new_round_count,
        "reason": reason,
    }


@router.post("/booking/intake", response_model=BookingIntakeResponse)
def booking_intake(request: BookingIntakeRequest):
    booking_reference = create_booking_reference()

    with db_connection() as conn:
        load = conn.execute(
            "SELECT load_id FROM loads WHERE load_id = ?",
            (request.load_id,),
        ).fetchone()

        if not load:
            raise_tool_error(
                404,
                "LOAD_NOT_FOUND",
                f"Cannot create booking because load {request.load_id} was not found.",
                field="load_id",
                details={"load_id": request.load_id},
            )

        conn.execute(
            """
            INSERT INTO booking_intakes (
                booking_reference,
                mc_number,
                carrier_name,
                dot_number,
                load_id,
                agreed_rate,
                negotiation_rounds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                booking_reference,
                request.mc_number,
                request.carrier_name,
                request.dot_number,
                request.load_id,
                request.agreed_rate,
                request.negotiation_rounds,
            ),
        )
        conn.commit()

    return {
        "booking_reference": booking_reference,
        "status": "queued_for_sales_rep",
    }


@router.post("/call-log", response_model=CallLogResponse)
def create_call_log(request: CallLogRequest):
    with db_connection() as conn:
        if request.load_id:
            load = conn.execute(
                "SELECT load_id FROM loads WHERE load_id = ?",
                (request.load_id.upper(),),
            ).fetchone()

            if not load:
                raise_tool_error(
                    404,
                    "LOAD_NOT_FOUND",
                    f"Cannot log call against unknown load {request.load_id}.",
                    field="load_id",
                    details={"load_id": request.load_id.upper()},
                )

        conn.execute(
            """
            INSERT INTO call_logs (
                mc_number,
                carrier_name,
                dot_number,
                load_id,
                final_rate,
                outcome,
                sentiment,
                summary,
                transcript,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                request.mc_number,
                request.carrier_name,
                request.dot_number,
                request.load_id,
                request.final_rate,
                request.outcome,
                request.sentiment,
                request.summary,
                request.transcript,
            ),
        )
        conn.commit()

    return {"success": True}
