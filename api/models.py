from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _strip_required(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} is required")
    return stripped


class CarrierVerificationRequest(BaseModel):
    mc_number: str = Field(..., description="Carrier MC number, e.g. MC-123456")

    @field_validator("mc_number")
    @classmethod
    def validate_mc_number(cls, value: str) -> str:
        return _strip_required(value, "mc_number")


class CarrierVerificationResponse(BaseModel):
    mc_number: str
    eligible: bool
    carrier_name: Optional[str] = None
    dot_number: Optional[int] = None
    verification_source: Optional[str] = None
    reason: Optional[str] = None


class NegotiationEventResponse(BaseModel):
    actor: str
    event_type: str
    amount: Optional[int] = None
    round_number: Optional[int] = None
    metadata: Optional[str] = None
    created_at: str


class NegotiationStatusResponse(BaseModel):
    session_id: str
    load_id: str
    status: str
    round_count: int
    last_carrier_offer: Optional[int] = None
    last_nancy_offer: Optional[int] = None
    final_rate: Optional[int] = None
    loadboard_rate: int
    load: Dict[str, Any]
    events: List[NegotiationEventResponse]


class CheckBidRequest(BaseModel):
    session_id: str
    load_id: str
    carrier_offer: Optional[int] = Field(default=None, gt=0)

    @field_validator("load_id")
    @classmethod
    def validate_load_id(cls, value: str) -> str:
        return _strip_required(value, "load_id").upper()

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return _strip_required(value, "session_id")


class CheckBidResponse(BaseModel):
    accept: bool
    amount: Optional[int] = None
    needs_opening_offer: bool = False
    can_continue: bool
    reason: str
    session_id: str
    load_id: str
    round_count: int
    loadboard_rate: int


class UpdateNegotiationStatusRequest(BaseModel):
    session_id: str
    load_id: str
    decision: str
    amount: Optional[int] = Field(default=None, gt=0)

    @field_validator("load_id")
    @classmethod
    def validate_load_id(cls, value: str) -> str:
        return _strip_required(value, "load_id").upper()

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return _strip_required(value, "session_id")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        decision = _strip_required(value, "decision").upper()
        if decision not in {"ACCEPT", "COUNTER", "REJECT"}:
            raise ValueError("decision must be ACCEPT, COUNTER, or REJECT")

        return decision


class UpdateNegotiationStatusResponse(BaseModel):
    ok: bool
    decision: str
    session_id: str
    load_id: str
    status: str
    amount: Optional[int] = None
    round_count: int
    reason: str


class BookingIntakeRequest(BaseModel):
    mc_number: str
    carrier_name: str
    dot_number: int = Field(..., gt=0)
    load_id: str
    agreed_rate: int = Field(..., gt=0)
    negotiation_rounds: int = Field(..., ge=1, le=3)

    @field_validator("mc_number")
    @classmethod
    def validate_booking_mc_number(cls, value: str) -> str:
        return _strip_required(value, "mc_number")

    @field_validator("carrier_name")
    @classmethod
    def validate_carrier_name(cls, value: str) -> str:
        return _strip_required(value, "carrier_name")

    @field_validator("load_id")
    @classmethod
    def validate_booking_load_id(cls, value: str) -> str:
        return _strip_required(value, "load_id").upper()


class BookingIntakeResponse(BaseModel):
    booking_reference: str
    status: str


class CallLogRequest(BaseModel):
    mc_number: Optional[str] = None
    carrier_name: Optional[str] = None
    dot_number: Optional[int] = Field(default=None, gt=0)
    load_id: Optional[str] = None
    final_rate: Optional[int] = Field(default=None, gt=0)
    outcome: str
    sentiment: str
    summary: str
    transcript: Optional[str] = None

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        return _strip_required(value, "outcome")

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, value: str) -> str:
        return _strip_required(value, "sentiment")

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        return _strip_required(value, "summary")

    @field_validator("mc_number", "carrier_name", "load_id", "transcript")
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        stripped = value.strip()
        return stripped or None

class CallLogResponse(BaseModel):
    success: bool


class ReportingCallRequest(BaseModel):
    session_id: str
    mc_number: Optional[str] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    equipment_type: Optional[str] = None
    offered_rate: Optional[int] = Field(default=None, gt=0)
    carrier_requested_rate: Optional[int] = Field(default=None, gt=0)
    final_rate: Optional[int] = Field(default=None, gt=0)
    outcome: str
    summary: Optional[str] = None
    mood: Optional[str] = None
    letterboard_rate: Optional[int] = Field(default=None, gt=0)
    loadboard_rate: Optional[int] = Field(default=None, gt=0)
    last_offered_rate: Optional[int] = Field(default=None, gt=0)
    call_duration_seconds: Optional[int] = Field(default=None, ge=0)
    negotiation_rounds: Optional[int] = Field(default=None, ge=0, le=3)
    tool_call_count: Optional[int] = Field(default=None, ge=0)
    call_status: Optional[str] = None
    call_end_event: Optional[str] = None
    transfer_completed: bool = False

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        return _strip_required(value, "session_id")

    @field_validator("outcome")
    @classmethod
    def validate_reporting_outcome(cls, value: str) -> str:
        return _strip_required(value, "outcome")

    @field_validator(
        "mc_number",
        "carrier_name",
        "load_id",
        "origin",
        "destination",
        "equipment_type",
        "summary",
        "mood",
        "call_status",
        "call_end_event",
    )
    @classmethod
    def strip_optional_reporting_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        stripped = value.strip()
        return stripped or None

    @field_validator("load_id")
    @classmethod
    def normalize_reporting_load_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        stripped = value.strip()
        return stripped.upper() or None


class ReportingCallResponse(BaseModel):
    success: bool
    session_id: str
