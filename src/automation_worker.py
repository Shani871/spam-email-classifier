"""
Autonomous Background Inbox Monitor & Auto-Triage Worker for SpamGuard AI.
Runs continuously in the background to inspect incoming emails, execute multi-tier
threat intelligence scoring, update security audit logs, and trigger automated triage.
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ai_threat_intelligence import compute_threat_intelligence
from src.gmail_scanner import scan_gmail_inbox

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "threat_audit_log.json")
PROCESSED_FILE = os.path.join(DATA_DIR, "processed_emails.json")

# Built-in simulated scenario pool for automated testing & live SOC simulation
SIMULATED_FEED = [
    {
        "id": "sim-001",
        "sender": "service@paypa1-security-update.com",
        "subject": "CRITICAL: Your PayPal Account will be suspended within 24 hours",
        "body": "Dear customer, unauthorized login detected. Verify your account immediately to prevent permanent termination: http://paypa1-security-update.com/verify",
        "date": "Just now"
    },
    {
        "id": "sim-002",
        "sender": "sarah.jenkins@company.com",
        "subject": "Quarterly Financial Planning Sync Notes & Slide Deck",
        "body": "Hi team, please find attached our Q3 financial performance review and strategy deck for next week's all-hands meeting. Let me know if you have questions.",
        "date": "Just now"
    },
    {
        "id": "sim-003",
        "sender": "winner-rewards@international-lottery.xyz",
        "subject": "Congratulations! You won $2,500,000 in international lottery",
        "body": "You have been randomly selected to win a cash prize of $2,500,000. Claim your reward immediately by replying with your full name and bank wire account details.",
        "date": "Just now"
    },
    {
        "id": "sim-004",
        "sender": "support@chase-fraud-alert.ru",
        "subject": "Unauthorized wire transfer of $1,850 initiated from Chase checking",
        "body": "Security Alert: A wire transfer was requested. If you did not authorize this, click cancel transaction now at http://192.168.1.50/chase/cancel or call immediately.",
        "date": "Just now"
    },
    {
        "id": "sim-005",
        "sender": "newsletter@github.com",
        "subject": "GitHub Explore: Trending repositories and developer tools this week",
        "body": "Check out the top open source Python and Rust projects trending across the community this week. Star your favorites and explore new releases.",
        "date": "Just now"
    }
]


class InboxAutomationWorker:
    """
    Autonomous background worker for continuous email threat surveillance.
    Can operate against real Gmail accounts or automated simulated feeds.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InboxAutomationWorker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        interval_seconds: int = 30,
        email_address: str = "",
        app_password: str = "",
        model_type: str = "svm"
    ):
        if self._initialized:
            return

        self.interval_seconds = max(5, interval_seconds)
        self.email_address = email_address
        self.app_password = app_password
        self.model_type = model_type

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._worker_lock = threading.Lock()
        self._sim_index = 0

        self.stats = {
            "total_scanned": 0,
            "threats_quarantined": 0,
            "spam_flagged": 0,
            "clean_passed": 0,
            "last_scan_time": None,
            "status": "STOPPED"
        }

        self.processed_ids = set()
        self.audit_log: List[Dict[str, Any]] = []

        self._ensure_storage()
        self._load_state()
        self._initialized = True

    def _ensure_storage(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def _load_state(self):
        try:
            if os.path.exists(PROCESSED_FILE):
                with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                    self.processed_ids = set(json.load(f))
        except Exception:
            self.processed_ids = set()

        try:
            if os.path.exists(AUDIT_LOG_FILE):
                with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                    self.audit_log = json.load(f)
                    # Recalculate stats from existing audit logs
                    self.stats["total_scanned"] = len(self.audit_log)
                    self.stats["threats_quarantined"] = sum(1 for e in self.audit_log if e.get("action") == "QUARANTINED")
                    self.stats["spam_flagged"] = sum(1 for e in self.audit_log if e.get("action") == "FLAGGED_SPAM")
                    self.stats["clean_passed"] = sum(1 for e in self.audit_log if e.get("action") == "CLEARED_HAM")
        except Exception:
            self.audit_log = []

    def _save_state(self):
        try:
            with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_ids), f, indent=2)
            with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.audit_log, f, indent=2)
        except Exception as e:
            print(f"[Worker Error] Failed to persist state: {e}")

    def configure_credentials(self, email_address: str, app_password: str):
        with self._worker_lock:
            self.email_address = email_address.strip()
            self.app_password = app_password.strip()

    def set_interval(self, seconds: int):
        with self._worker_lock:
            self.interval_seconds = max(5, seconds)

    def is_running(self) -> bool:
        return self._running

    def start(self):
        with self._worker_lock:
            if self._running:
                return
            self._running = True
            self.stats["status"] = "RUNNING"
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            print(f"[SpamGuard Daemon] Autonomous worker started. Polling interval: {self.interval_seconds}s")

    def stop(self):
        with self._worker_lock:
            if not self._running:
                return
            self._running = False
            self.stats["status"] = "STOPPED"
            print("[SpamGuard Daemon] Autonomous worker stopped.")

    def _fetch_candidate_emails(self) -> List[Dict[str, Any]]:
        """
        Fetches emails from live Gmail if credentials exist,
        otherwise uses simulated incoming email stream.
        """
        if self.email_address and self.app_password:
            try:
                emails = scan_gmail_inbox(
                    email_address=self.email_address,
                    app_password=self.app_password,
                    max_emails=5,
                    only_unread=True,
                    model_type=self.model_type
                )
                return emails
            except Exception as e:
                print(f"[Worker Live Gmail Error] {e}")
                return []
        else:
            # Simulate an incoming email from the test pool
            scenario = SIMULATED_FEED[self._sim_index % len(SIMULATED_FEED)]
            self._sim_index += 1
            # Add dynamic timestamp ID for continuous simulation
            entry_id = f"{scenario['id']}-{int(time.time())}"
            return [{
                "id": entry_id,
                "sender": scenario["sender"],
                "subject": scenario["subject"],
                "full_text": f"Subject: {scenario['subject']}\n\n{scenario['body']}",
                "body_preview": scenario["body"][:160],
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]

    def scan_once(self) -> List[Dict[str, Any]]:
        """
        Executes a single triage pass over candidate emails.
        """
        candidates = self._fetch_candidate_emails()
        new_results = []

        for item in candidates:
            msg_id = str(item.get("id"))
            if msg_id in self.processed_ids:
                continue

            full_text = item.get("full_text") or f"Subject: {item.get('subject', '')}\n\n{item.get('body_preview', '')}"
            report = compute_threat_intelligence(full_text, model_type=self.model_type)

            # Auto-Triage Decision Matrix
            threat_score = report["threat_score"]
            if threat_score >= 75:
                action = "QUARANTINED"
                self.stats["threats_quarantined"] += 1
            elif threat_score >= 50 or report["ml_result"]["is_spam"]:
                action = "FLAGGED_SPAM"
                self.stats["spam_flagged"] += 1
            else:
                action = "CLEARED_HAM"
                self.stats["clean_passed"] += 1

            self.stats["total_scanned"] += 1
            self.processed_ids.add(msg_id)

            audit_entry = {
                "id": msg_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sender": item.get("sender", "Unknown"),
                "subject": item.get("subject", "(No Subject)"),
                "action": action,
                "threat_score": threat_score,
                "threat_level": report["threat_level"],
                "threat_color": report["threat_color"],
                "attack_vector": report["attack_vector"],
                "tactics_detected": report["tactics_detected"],
                "advisories": report["security_advisories"]
            }

            # Insert at top of audit log
            self.audit_log.insert(0, audit_entry)
            new_results.append(audit_entry)

        self.stats["last_scan_time"] = datetime.now().strftime("%H:%M:%S")
        self._save_state()
        return new_results

    def _run_loop(self):
        while self._running:
            try:
                self.scan_once()
            except Exception as e:
                print(f"[SpamGuard Daemon Loop Exception] {e}")

            # Sleep in 1-second chunks for responsive stopping
            for _ in range(self.interval_seconds):
                if not self._running:
                    break
                time.sleep(1)

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)

    def get_recent_audit_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.audit_log[:limit]

    def clear_audit_logs(self):
        with self._worker_lock:
            self.audit_log.clear()
            self.processed_ids.clear()
            self.stats = {
                "total_scanned": 0,
                "threats_quarantined": 0,
                "spam_flagged": 0,
                "clean_passed": 0,
                "last_scan_time": None,
                "status": "RUNNING" if self._running else "STOPPED"
            }
            self._save_state()


def get_global_worker() -> InboxAutomationWorker:
    """Returns singleton instance of InboxAutomationWorker."""
    return InboxAutomationWorker()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SpamGuard AI Background Daemon")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")
    parser.add_argument("--email", type=str, default="", help="Gmail address for live monitoring")
    parser.add_argument("--password", type=str, default="", help="Gmail 16-character App Password")
    args = parser.parse_args()

    worker = InboxAutomationWorker(
        interval_seconds=args.interval,
        email_address=args.email,
        app_password=args.password
    )
    print("=" * 60)
    print("      🛡️ SPAMGUARD AI — AUTONOMOUS INBOX MONITOR DAEMON      ")
    print("=" * 60)
    print(f" Mode: {'Live Gmail (' + args.email + ')' if args.email else 'Continuous Threat Intelligence Simulation'}")
    print(f" Polling Interval: {args.interval}s")
    print(" Press Ctrl+C to terminate daemon.")
    print("-" * 60)

    worker.start()
    try:
        while True:
            time.sleep(2)
            stats = worker.get_stats()
            print(f"\r[Daemon Running] Total Scanned: {stats['total_scanned']} | Quarantined: {stats['threats_quarantined']} | Spam: {stats['spam_flagged']} | Safe: {stats['clean_passed']} | Last Pass: {stats['last_scan_time']}", end="")
    except KeyboardInterrupt:
        print("\nStopping daemon gracefully...")
        worker.stop()
        print("Daemon terminated.")
