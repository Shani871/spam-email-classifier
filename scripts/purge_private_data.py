"""Optional scheduled maintenance for expired private records."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.user_storage import purge_expired_records
purge_expired_records()
