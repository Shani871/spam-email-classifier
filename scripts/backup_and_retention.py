"""Retention clean-up, database backups and safe restores.

    python scripts/backup_and_retention.py                 # purge expired rows, then back up
    python scripts/backup_and_retention.py restore FILE    # restore a backup (see docs/DEPLOYMENT.md)
    python scripts/backup_and_retention.py export-deletions FILE | reapply-deletions FILE

Backups:
  - SQLite: a consistent copy made with SQLite's online backup API (spamguard_<time>.sqlite3).
  - PostgreSQL: `pg_dump --format=custom` (spamguard_<time>.dump); needs pg_dump/pg_restore of the
    same major version as the server on PATH (checked before running).
  The newest 7 are kept.

Restores never bring back deleted accounts: the deletion markers present before the
restore are re-applied afterwards, together with those in the backup.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import db, user_storage  # noqa: E402

BACKUPS_DIR = Path(os.environ.get("SPAMGUARD_BACKUP_DIR", ROOT / "data" / "backups"))
BACKUP_PREFIX = "spamguard_"


def purge_expired_user_records() -> int:
    """Delete expired history and feedback now. Returns the number of rows removed."""
    return user_storage.purge_expired_records(force=True)


def _sqlite_path(url: str) -> Path:
    return Path(url.split("///", 1)[-1])


def _pg_url(url: str) -> str:
    """libpq URL for pg_dump/pg_restore (without the SQLAlchemy driver suffix)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def check_pg_tool_version(tool: str) -> None:
    """Stop with a clear message if pg_dump/pg_restore and the server differ in major version.

    Dumps from newer tools can contain settings an older server rejects (for example
    pg_dump 17 writes `SET transaction_timeout`, which PostgreSQL 16 does not know).
    """
    import re
    from sqlalchemy import text
    output = subprocess.run([tool, "--version"], check=True, capture_output=True, text=True).stdout
    found = re.search(r"(\d+)(?:\.\d+)?", output)
    if not found:
        raise RuntimeError(f"Could not read the version of {tool}: {output.strip()}")
    client_major = int(found.group(1))
    with db.get_engine().connect() as connection:
        server_major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
    if client_major != server_major:
        raise RuntimeError(f"{tool} is version {client_major} but the database server is PostgreSQL {server_major}. "
                           f"Use {tool} {server_major}, for example by running it inside the database container.")


def create_backup_archive(max_backups: int = 7, backups_dir: Optional[Path] = None) -> Path:
    target = Path(backups_dir or BACKUPS_DIR)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    url = db.database_url()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    db.get_engine()  # make sure the schema exists before copying
    if db.is_sqlite(url):
        backup_file = target / f"{BACKUP_PREFIX}{stamp}.sqlite3"
        source = sqlite3.connect(_sqlite_path(url))
        destination = sqlite3.connect(backup_file)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    else:
        backup_file = target / f"{BACKUP_PREFIX}{stamp}.dump"
        check_pg_tool_version("pg_dump")
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", f"--file={backup_file}", _pg_url(url)], check=True)
    os.chmod(backup_file, 0o600)

    backups = sorted(target.glob(f"{BACKUP_PREFIX}*"), key=lambda p: p.stat().st_mtime)
    while len(backups) > max_backups:
        backups.pop(0).unlink(missing_ok=True)
    return backup_file


def restore_backup_archive(backup_file: Path) -> bool:
    """Replace the database contents with a backup, then re-apply all account deletions."""
    backup_file = Path(backup_file)
    url = db.database_url()
    deletions_before = set(user_storage.deleted_account_ids())
    if db.is_sqlite(url):
        db.reset_engines()
        source = sqlite3.connect(backup_file)
        destination = sqlite3.connect(_sqlite_path(url))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    else:
        check_pg_tool_version("pg_restore")
        db.reset_engines()
        subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--single-transaction",
                        f"--dbname={_pg_url(url)}", str(backup_file)], check=True)
    db.reset_engines()  # reconnect and apply any migrations newer than the backup
    user_storage.apply_account_deletions(deletions_before | set(user_storage.deleted_account_ids()))
    return True


def export_deletions(path: Path) -> int:
    ids = user_storage.deleted_account_ids()
    Path(path).write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")
    return len(ids)


def reapply_deletions(path: Path) -> int:
    ids = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if len(line.strip()) == 64]
    return user_storage.apply_account_deletions(set(ids) | set(user_storage.deleted_account_ids()))


def main(argv) -> None:
    if len(argv) >= 3 and argv[1] == "export-deletions":
        print(f"Exported {export_deletions(Path(argv[2]))} deletion markers to {argv[2]}.")
        return
    if len(argv) >= 3 and argv[1] == "reapply-deletions":
        print(f"Re-applied deletions; {reapply_deletions(Path(argv[2]))} rows removed.")
        return
    if len(argv) >= 3 and argv[1] == "restore":
        restore_backup_archive(Path(argv[2]))
        print(f"Restored {argv[2]}; account deletions re-applied.")
        return
    purged = purge_expired_user_records()
    backup_path = create_backup_archive()
    print(f"Retention clean-up: {purged} expired rows removed.")
    print(f"Backup written: {backup_path}")


if __name__ == "__main__":
    main(sys.argv)
