import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "loads.db"))
FMCSA_WEB_KEY = os.getenv("FMCSA_WEB_KEY")
FMCSA_BASE_URL = "https://mobile.fmcsa.dot.gov/qc/services"
API_KEY = os.getenv("API_KEY")
TWIN_GATEWAY_URL = os.getenv("TWIN_GATEWAY_URL")
TWIN_ORG_ID = os.getenv("TWIN_ORG_ID")
TWIN_API_KEY = os.getenv("TWIN_API_KEY")
TWIN_TABLE_NAME = os.getenv("TWIN_TABLE_NAME", "carrier_call_history")
