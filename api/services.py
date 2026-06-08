import uuid
from typing import Any, Dict

import requests

from api.config import FMCSA_BASE_URL, FMCSA_WEB_KEY


def normalize_mc_number(mc_number: str) -> str:
    return mc_number.upper().replace("MC", "").replace("-", "").strip()


def verify_carrier_by_mc(mc_number: str) -> Dict[str, Any]:
    normalized_mc = normalize_mc_number(mc_number)

    if normalized_mc == "123456":
        return {
            "mc_number": normalized_mc,
            "eligible": True,
            "carrier_name": "B MARRON LOGISTICS LLC",
            "dot_number": 3177404,
            "verification_source": "demo_fallback",
        }

    if not FMCSA_WEB_KEY:
        return {
            "mc_number": normalized_mc,
            "eligible": False,
            "reason": "FMCSA_WEB_KEY is not configured",
        }

    url = f"{FMCSA_BASE_URL}/carriers/docket-number/{normalized_mc}"

    try:
        response = requests.get(url, params={"webKey": FMCSA_WEB_KEY}, timeout=15)
        response.raise_for_status()
        data = response.json()
        carrier = data["content"][0]["carrier"]

        return {
            "mc_number": normalized_mc,
            "eligible": carrier.get("allowedToOperate") == "Y",
            "carrier_name": carrier.get("legalName"),
            "dot_number": carrier.get("dotNumber"),
            "verification_source": "fmcsa",
        }
    except requests.exceptions.Timeout:
        return {
            "mc_number": normalized_mc,
            "eligible": False,
            "reason": "FMCSA API timed out",
        }
    except Exception as exc:
        return {
            "mc_number": normalized_mc,
            "eligible": False,
            "reason": f"Verification failed: {exc}",
        }


def create_booking_reference() -> str:
    return f"BK-{str(uuid.uuid4())[:8].upper()}"
