import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "loads.db"))
FMCSA_WEB_KEY = os.getenv("FMCSA_WEB_KEY")
FMCSA_BASE_URL = "https://mobile.fmcsa.dot.gov/qc/services"
API_KEY = os.getenv("API_KEY")
