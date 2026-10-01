"""Local public-catalog snapshots only; deliberately excludes push recovery."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid


class OpsError(ValueError):
    """A backup or restore failed a safety check."""


_FORMAT = "sakurano-public-catalog-v1"
_BUNDLE_NAME = re.compile(r"catalog-backup-\d{8}T\d{12}Z-[0-9a-f]{32}")
_COLUMNS = (
    ("cache_key", "TEXT", 0, None, 1),
    ("source_id", "TEXT", 1, None, 0),
    ("grade", "TEXT", 1, None, 0),
    ("scanned_at", "TEXT", 1, None, 0),
    ("payload_json", "TEXT", 1, None, 0),
    ("updated_at", "REAL", 1, None, 0),
)
_FILES = {"catalog.sqlite3", "manifest.json"}


def _regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise OpsError("input must be an existing regular file, not a symlink")


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def _catalog_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA trusted_schema=OFF")
    objects = connection.execute("SELECT type, name, tbl_name FROM sqlite_schema").fetchall()
    if any("push" in name.lower() or "subscription" in name.lower() for _, name, _ in objects):
        raise OpsError("push/subscription databases are refused; recovery requires fresh consent")
    if not objects or any(
        not (kind == "table" and name == "catalog_results")
        and not (kind == "index" and table == "catalog_results")
        for kind, name, table in objects
    ):
        raise OpsError("only the dedicated public catalog_results database is supported")
    columns = tuple(tuple(row[1:]) for row in connection.execute("PRAGMA table_info(catalog_results)"))
    if columns != _COLUMNS:
        raise OpsError("unsupported public catalog schema")


def _integrity(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise OpsError("SQLite integrity check failed")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _manifest(bundle: Path) -> dict:
    if not _BUNDLE_NAME.fullmatch(bundle.name) or bundle.is_symlink() or not bundle.is_dir():
        raise OpsError("backup must be a managed catalog backup directory")
    if {item.name for item in bundle.iterdir()} != _FILES:
        raise OpsError("backup bundle must contain exactly the database and manifest")
    for name in _FILES:
        _regular_file(bundle / name)
    manifest_path = bundle / "manifest.json"
    if manifest_path.stat().st_size > 8192:
        raise OpsError("invalid backup manifest")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpsError("invalid backup manifest") from exc
    if (
        not isinstance(data, dict)
        or data.get("format") != _FORMAT
        or data.get("bundle") != bundle.name
        or data.get("database") != "catalog.sqlite3"
        or data.get("schema") != "catalog_results-v1"
        or data.get("integrity_check") != "ok"
        or type(data.get("size_bytes")) is not int
        or data["size_bytes"] <= 0
        or not isinstance(data.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
        or not isinstance(data.get("created_at"), str)
    ):
        raise OpsError("invalid backup manifest")
    return data


def _validate_snapshot(path: Path, manifest: dict) -> None:
    if path.stat().st_size != manifest["size_bytes"] or _digest(path) != manifest["sha256"]:
        raise OpsError("backup manifest size/checksum mismatch")
    with closing(_connect_readonly(path)) as connection:
        _catalog_schema(connection)
        _integrity(connection)


def _prune(directory: Path, keep: int) -> None:
    """Only intact, recognized direct-child bundles are eligible for deletion."""
    managed = []
    for candidate in directory.iterdir():
        if not _BUNDLE_NAME.fullmatch(candidate.name):
            continue
        try:
            manifest = _manifest(candidate)
            _validate_snapshot(candidate / "catalog.sqlite3", manifest)
        except (OpsError, OSError, sqlite3.Error):
            continue  # Unknown, incomplete, modified and symlinked data belongs to the operator.
        managed.append(candidate)
    for candidate in sorted(managed, key=lambda path: path.name, reverse=True)[keep:]:
        # Never recursively delete: no other files or subdirectories are owned here.
        if {item.name for item in candidate.iterdir()} != _FILES:
            continue
        for name in sorted(_FILES):
            (candidate / name).unlink()
        candidate.rmdir()
    _sync_directory(directory)


def backup_catalog(database: Path, destination: Path, *, keep: int = 7) -> Path:
    """Publish a consistent catalog snapshot bundle and retain 1..100 valid bundles."""
    if type(keep) is not int or not 1 <= keep <= 100:
        raise OpsError("keep must be between 1 and 100")
    database = Path(database).expanduser().absolute()
    destination = Path(destination).expanduser().absolute()
    _regular_file(database)
    if "push" in database.name.lower() or "subscription" in database.name.lower():
        raise OpsError("push/subscription databases are refused; recovery requires fresh consent")
    if destination.is_symlink():
        raise OpsError("backup destination must not be a symlink")
    destination = destination.resolve()
    if database.resolve().is_relative_to(destination):
        raise OpsError("live database must be outside the backup directory")
    with closing(_connect_readonly(database)) as source:
        # Check before creating any snapshot, then check again on the consistent copy.
        source.execute("BEGIN")
        _catalog_schema(source)
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc)
        name = f"catalog-backup-{stamp.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}"
        bundle = destination / name
        temporary = Path(tempfile.mkdtemp(prefix=".catalog-backup-", dir=destination))
        try:
            snapshot = temporary / "catalog.sqlite3"
            descriptor = os.open(snapshot, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            deadline = time.monotonic() + 30

            def progress(_status: int, _remaining: int, _total: int) -> None:
                if time.monotonic() > deadline:
                    raise OpsError("online backup timed out; retry after resolving database contention")

            with closing(sqlite3.connect(snapshot)) as target:
                source.backup(target, pages=256, progress=progress, sleep=0.05)
                target.execute("PRAGMA journal_mode=DELETE")
                _catalog_schema(target)
                _integrity(target)
                # Purge free pages; this is still only for a dedicated public-catalog DB.
                target.execute("VACUUM")
                _integrity(target)
            snapshot.chmod(0o600)
            manifest = {
                "format": _FORMAT,
                "bundle": name,
                "database": "catalog.sqlite3",
                "schema": "catalog_results-v1",
                "created_at": stamp.isoformat(),
                "size_bytes": snapshot.stat().st_size,
                "sha256": _digest(snapshot),
                "integrity_check": "ok",
            }
            manifest_path = temporary / "manifest.json"
            with manifest_path.open("x", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(manifest, stream, indent=2)
                stream.write("\n")
            _sync_file(snapshot)
            _sync_file(manifest_path)
            _sync_directory(temporary)
            os.rename(temporary, bundle)  # Same filesystem: DB and manifest appear together.
            _sync_directory(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)  # Only the private mkdtemp directory created above.
    _prune(destination, keep)
    return bundle


def _new_destination(destination: Path) -> None:
    if not destination.parent.is_dir():
        raise OpsError("restore destination parent directory must already exist")
    for path in (destination, *(Path(str(destination) + suffix) for suffix in ("-wal", "-shm", "-journal"))):
        if os.path.lexists(path):
            raise OpsError("restore requires a new destination with no existing database or SQLite sidecars")


def restore_catalog(backup: Path, destination: Path) -> Path:
    """Validate a bundle and publish to a new path, atomically without replacing anything."""
    backup = Path(backup).expanduser().absolute()
    destination = Path(destination).expanduser().absolute()
    _new_destination(destination)
    if destination.resolve().is_relative_to(backup.resolve()):
        raise OpsError("restore destination must be outside the backup bundle")
    manifest = _manifest(backup)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".catalog-restore-", dir=destination.parent)
    temporary = Path(temporary_name)
    os.close(descriptor)
    try:
        shutil.copyfile(backup / "catalog.sqlite3", temporary)
        temporary.chmod(0o600)
        _validate_snapshot(temporary, manifest)  # Validate the actual bytes to be published.
        _sync_file(temporary)
        _new_destination(destination)
        # link() is an atomic no-clobber publish, including if the DB appears after the check.
        os.link(temporary, destination)
        _sync_directory(destination.parent)
    finally:
        temporary.unlink()
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(temporary) + suffix).unlink(missing_ok=True)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="back up a dedicated public catalog DB")
    backup.add_argument("--database", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True, help="explicit backup directory")
    backup.add_argument("--keep", type=int, default=7, help="number of valid bundles retained (1..100)")
    restore = commands.add_parser("restore", help="restore a bundle to a new database path")
    restore.add_argument("--backup", type=Path, required=True, help="published backup bundle directory")
    restore.add_argument("--destination", type=Path, required=True, help="new database filename")
    args = parser.parse_args(argv)
    try:
        result = (
            backup_catalog(args.database, args.destination, keep=args.keep)
            if args.command == "backup" else restore_catalog(args.backup, args.destination)
        )
    except OpsError as exc:
        print(f"ops: {exc}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error):
        print("ops: filesystem or SQLite operation failed; check permissions, free space and database integrity", file=sys.stderr)
        return 1
    print(json.dumps({"operation": args.command, "destination": str(result)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
