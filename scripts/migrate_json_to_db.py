"""Copy data from the old JSON storage (data/users/<account>/*.json) into the database.

    python scripts/migrate_json_to_db.py [--legacy-dir data/users] [--dry-run]

Safe to run more than once: feedback is matched by id, history by (account, time,
assessment), and sender rules are upserted. Accounts listed in the old deletion
markers (.deleted_accounts.json) are not copied and are recorded as deleted.
The JSON files are left in place; delete them yourself once you have checked the result.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import insert, select  # noqa: E402

from src import db, user_storage  # noqa: E402

ACCOUNT_DIR_LENGTH = 64  # sha256 hex digest


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _time(value, fallback):
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return fallback


def migrate(legacy_dir: Path, dry_run: bool = False) -> dict:
    report = {"accounts": 0, "skipped_deleted_accounts": 0, "history": 0, "feedback": 0, "sender_rules": 0,
              "deletion_markers": 0, "already_present": 0, "unreadable_rows": 0}
    if not legacy_dir.exists():
        return report
    deleted = set(_read(legacy_dir / ".deleted_accounts.json", []))
    now = datetime.now(timezone.utc)
    engine = db.get_engine()
    with engine.connect() as connection:
        transaction = connection.begin()
        existing_deleted = {r[0] for r in connection.execute(select(db.deleted_accounts.c.account_id))}
        for account in sorted(deleted - existing_deleted):
            report["deletion_markers"] += 1
            if not dry_run:
                connection.execute(insert(db.deleted_accounts).values(account_id=account, deleted_at=now))
        for folder in sorted(p for p in legacy_dir.iterdir() if p.is_dir() and len(p.name) == ACCOUNT_DIR_LENGTH):
            account = folder.name
            if account in deleted or account in existing_deleted:
                report["skipped_deleted_accounts"] += 1
                continue
            report["accounts"] += 1

            for row in _read(folder / "history.json", []):
                if not isinstance(row, dict) or not row.get("assessment"):
                    report["unreadable_rows"] += 1
                    continue
                created = _time(row.get("timestamp"), now)
                values = dict(account_id=account, created_at=created, expires_at=_time(row.get("expires_at"), created + timedelta(days=7)),
                              assessment=str(row["assessment"])[:40], score=row.get("score"), category=str(row.get("category", "General message"))[:40])
                exists = connection.execute(select(db.history.c.id).where(db.history.c.account_id == account, db.history.c.created_at == created,
                                                                          db.history.c.assessment == values["assessment"])).first()
                if exists:
                    report["already_present"] += 1
                    continue
                report["history"] += 1
                if not dry_run:
                    connection.execute(insert(db.history).values(**values))

            for row in _read(folder / "feedback.json", []):
                if not isinstance(row, dict) or not row.get("id") or row.get("user_label") not in {"ham", "spam"} or not row.get("text"):
                    report["unreadable_rows"] += 1
                    continue
                if connection.execute(select(db.feedback.c.id).where(db.feedback.c.id == str(row["id"]))).first():
                    report["already_present"] += 1
                    continue
                consent = row.get("consent_given") is True
                status = "approved" if row.get("approved") and consent else "rejected" if row.get("rejected") \
                    else "withdrawn" if row.get("status") == "withdrawn" else "pending"
                created = _time(row.get("timestamp"), now)
                report["feedback"] += 1
                if not dry_run:
                    connection.execute(insert(db.feedback).values(
                        id=str(row["id"])[:64], account_id=account, created_at=created,
                        expires_at=_time(row.get("expires_at"), created + timedelta(days=30)), text=str(row["text"]),
                        predicted_label=str(row.get("predicted_label", ""))[:16], user_label=row["user_label"],
                        user_comment=str(row.get("user_comment", "")), consent_given=consent, status=status,
                        rejection_reason=str(row.get("rejection_reason", ""))))

            rules = _read(folder / "sender_rules.json", {})
            if isinstance(rules, dict):
                for rule, key in (("trust", "whitelist"), ("block", "blacklist")):
                    for address in rules.get(key, []) or []:
                        clean = str(address).lower().strip()[:320]
                        if not clean:
                            continue
                        found = connection.execute(select(db.sender_rules.c.rule).where(
                            db.sender_rules.c.account_id == account, db.sender_rules.c.address == clean)).first()
                        if found:
                            report["already_present"] += 1
                            continue
                        report["sender_rules"] += 1
                        if not dry_run:
                            connection.execute(insert(db.sender_rules).values(account_id=account, address=clean, rule=rule, created_at=now))
        if dry_run:
            transaction.rollback()
        else:
            transaction.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--legacy-dir", default=str(user_storage.LEGACY_ROOT))
    parser.add_argument("--dry-run", action="store_true", help="report what would be copied without writing")
    args = parser.parse_args()
    report = migrate(Path(args.legacy_dir), dry_run=args.dry_run)
    print(("Dry run: " if args.dry_run else "Migrated: ") + json.dumps(report))
    print("Database:", db.database_url().split("@")[-1])


if __name__ == "__main__":
    main()
