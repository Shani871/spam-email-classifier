"""Automated backup and retention cleanup script for SpamGuard AI.

Can be run via cron (e.g. daily at midnight) or invoked by a deployment orchestrator:
- Enforces user retention expiration on history.json and feedback.json.
- Creates a timestamped archive of application data (excluding logs and secrets).
- Retains the last 7 backup archives and prunes older ones.
- Restores archives safely while honoring user account deletion tombstones so
  restoring an older snapshot never resurrects deleted personal data.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from typing import Optional, Set

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
USERS_DIR = DATA_DIR / "users"
BACKUPS_DIR = DATA_DIR / "backups"


def record_account_deletion_tombstone(digest: str, users_dir: Optional[Path] = None) -> None:
    """Records an account deletion tombstone so restored backups never resurrect deleted data."""
    target_users = users_dir or USERS_DIR
    target_users.mkdir(parents=True, exist_ok=True, mode=0o700)
    tombstone_file = target_users / ".deleted_accounts.json"
    records = []
    if tombstone_file.exists():
        try:
            records = json.loads(tombstone_file.read_text(encoding="utf-8"))
        except Exception:
            records = []
    if digest not in records:
        records.append(digest)
        tombstone_file.write_text(json.dumps(records, indent=2), encoding="utf-8")


def purge_expired_user_records(users_dir: Optional[Path] = None) -> int:
    """Purges expired records across all user stores."""
    target_users = users_dir or USERS_DIR
    if not target_users.exists():
        return 0
    now = datetime.now(timezone.utc).isoformat()
    purged_count = 0

    for path in target_users.glob("*/*.json"):
        if path.name not in {"history.json", "feedback.json"}:
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                continue
            kept = [row for row in rows if not isinstance(row, dict) or row.get("expires_at", now) >= now]
            if len(kept) != len(rows):
                purged_count += len(rows) - len(kept)
                fd, temp_file = tempfile.mkstemp(dir=path.parent)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(kept, handle, ensure_ascii=False, indent=2)
                os.replace(temp_file, path)
        except (json.JSONDecodeError, OSError):
            continue

    return purged_count


def create_backup_archive(max_backups: int = 7, data_dir: Optional[Path] = None, backups_dir: Optional[Path] = None) -> Path:
    """Creates a compressed archive of data/ excluding temporary files, logs, and secrets."""
    target_data = data_dir or DATA_DIR
    target_backups = backups_dir or BACKUPS_DIR
    target_backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_file = target_backups / f"spamguard_backup_{timestamp}.tar.gz"

    with tarfile.open(backup_file, "w:gz") as tar:
        if target_data.exists():
            for item in target_data.iterdir():
                if item.name in {"backups", "logs", ".DS_Store"} or item.suffix in {".tmp", ".lock"}:
                    continue
                tar.add(item, arcname=f"data/{item.name}")

    # Prune older backups
    all_backups = sorted(target_backups.glob("spamguard_backup_*.tar.gz"), key=os.path.getmtime)
    while len(all_backups) > max_backups:
        oldest = all_backups.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass

    return backup_file


def restore_backup_archive(backup_file: Path, target_data_dir: Optional[Path] = None) -> bool:
    """Restores application data from a backup archive with privacy guarantees.
    
    Privacy safeguards:
    - Re-applies account deletion tombstones so that restoring an older backup
      snapshot NEVER resurrects accounts deleted by users.
    - Preserves access protection modes.
    """
    dest = target_data_dir or DATA_DIR
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Pre-restore tombstones
    tombstones: Set[str] = set()
    current_tombstones = dest / "users" / ".deleted_accounts.json"
    if current_tombstones.exists():
        try:
            tombstones.update(json.loads(current_tombstones.read_text(encoding="utf-8")))
        except Exception:
            pass

    with tarfile.open(backup_file, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.startswith("data/"):
                rel_name = member.name[5:]
                if not rel_name or ".." in rel_name:
                    continue
                tar.extract(member, path=dest.parent)

    # Post-restore account deletion enforcement
    restored_users = dest / "users"
    if restored_users.exists():
        restored_tombstones = restored_users / ".deleted_accounts.json"
        if restored_tombstones.exists():
            try:
                tombstones.update(json.loads(restored_tombstones.read_text(encoding="utf-8")))
            except Exception:
                pass
        # Ensure any deleted account in tombstone list is erased
        for digest in tombstones:
            acct_dir = restored_users / digest
            if acct_dir.exists():
                shutil.rmtree(acct_dir)
        restored_tombstones.write_text(json.dumps(sorted(list(tombstones)), indent=2), encoding="utf-8")

    return True


if __name__ == "__main__":
    purged = purge_expired_user_records()
    backup_path = create_backup_archive()
    print(f"Retention cleanup complete: {purged} expired records purged.")
    print(f"Backup archive created: {backup_path}")
