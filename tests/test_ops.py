from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sakurano_line_notifier.ops import OpsError, backup_catalog, restore_catalog


class CatalogOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.database = self.root / "catalog.sqlite3"
        self.backups = self.root / "backups"
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                """CREATE TABLE catalog_results (
                    cache_key TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )
            connection.execute(
                "INSERT INTO catalog_results VALUES (?, ?, ?, ?, ?, ?)",
                ("school\0全学年", "school", "全学年", "2026-10-01T00:00:00Z", '{"notices":[]}', 1.0),
            )
            connection.commit()

    def test_backup_restore_round_trip_manifest_integrity_and_permissions(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        manifest = json.loads((bundle / "manifest.json").read_text())
        snapshot = bundle / "catalog.sqlite3"
        self.assertEqual(manifest["sha256"], hashlib.sha256(snapshot.read_bytes()).hexdigest())
        self.assertEqual(manifest["size_bytes"], snapshot.stat().st_size)
        self.assertEqual(manifest["integrity_check"], "ok")
        self.assertNotIn(str(self.database), (bundle / "manifest.json").read_text())
        restored = restore_catalog(bundle, self.root / "recovered.sqlite3")
        for path in (snapshot, bundle / "manifest.json", restored):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o700)
        with closing(sqlite3.connect(restored)) as recovered, closing(sqlite3.connect(self.database)) as original:
            self.assertEqual(recovered.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(
                recovered.execute("SELECT * FROM catalog_results").fetchall(),
                original.execute("SELECT * FROM catalog_results").fetchall(),
            )

    def test_online_backup_includes_committed_wal_and_excludes_uncommitted_writer(self) -> None:
        with closing(sqlite3.connect(self.database)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("UPDATE catalog_results SET updated_at=2")
            writer.commit()
            self.assertGreater(Path(str(self.database) + "-wal").stat().st_size, 0)
            writer.execute("UPDATE catalog_results SET updated_at=3")
            bundle = backup_catalog(self.database, self.backups)
            with closing(sqlite3.connect(bundle / "catalog.sqlite3")) as snapshot:
                self.assertEqual(snapshot.execute("SELECT updated_at FROM catalog_results").fetchone(), (2.0,))
                self.assertEqual(snapshot.execute("PRAGMA journal_mode").fetchone(), ("delete",))
            writer.rollback()
        self.assertEqual({item.name for item in bundle.iterdir()}, {"manifest.json", "catalog.sqlite3"})

    def test_restore_never_overwrites_file_or_dangling_symlink(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        destination = self.root / "existing.sqlite3"
        destination.write_bytes(b"operator data")
        with self.assertRaisesRegex(OpsError, "new destination"):
            restore_catalog(bundle, destination)
        self.assertEqual(destination.read_bytes(), b"operator data")
        link = self.root / "dangling.sqlite3"
        link.symlink_to(self.root / "missing.sqlite3")
        with self.assertRaisesRegex(OpsError, "new destination"):
            restore_catalog(bundle, link)
        self.assertTrue(link.is_symlink())

    def test_restore_rejects_leftover_sidecars(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                destination = self.root / ("recovered" + suffix + ".sqlite3")
                sidecar = Path(str(destination) + suffix)
                sidecar.write_bytes(b"unrelated state")
                with self.assertRaisesRegex(OpsError, "sidecars"):
                    restore_catalog(bundle, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(sidecar.read_bytes(), b"unrelated state")

    def test_restore_publication_race_does_not_overwrite(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        destination = self.root / "raced.sqlite3"
        link = os.link

        def competing_link(source: Path, target: Path) -> None:
            target.write_bytes(b"another process")
            link(source, target)

        with patch("sakurano_line_notifier.ops.os.link", side_effect=competing_link):
            with self.assertRaises(FileExistsError):
                restore_catalog(bundle, destination)
        self.assertEqual(destination.read_bytes(), b"another process")
        self.assertFalse(list(self.root.glob(".catalog-restore-*")))

    def test_restore_rejects_tampering_and_missing_manifest(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        snapshot = bundle / "catalog.sqlite3"
        snapshot.write_bytes(snapshot.read_bytes() + b"tampered")
        with self.assertRaisesRegex(OpsError, "checksum"):
            restore_catalog(bundle, self.root / "recovered.sqlite3")
        self.assertFalse((self.root / "recovered.sqlite3").exists())
        (bundle / "manifest.json").unlink()
        with self.assertRaises(OpsError):
            restore_catalog(bundle, self.root / "recovered.sqlite3")

    def test_restore_checks_sqlite_integrity_even_with_matching_checksum(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        snapshot = bundle / "catalog.sqlite3"
        payload = bytearray(snapshot.read_bytes())
        # Corrupt the B-tree page type while preserving sqlite_schema and file length.
        with closing(sqlite3.connect(snapshot)) as connection:
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            root_page = connection.execute("SELECT rootpage FROM sqlite_schema WHERE name='catalog_results'").fetchone()[0]
        payload[(root_page - 1) * page_size] = 0
        snapshot.write_bytes(payload)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"] = hashlib.sha256(payload).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises((OpsError, sqlite3.DatabaseError)):
            restore_catalog(bundle, self.root / "recovered.sqlite3")
        self.assertFalse((self.root / "recovered.sqlite3").exists())
        self.assertFalse(list(self.root.glob(".catalog-restore-*")))

    def test_backup_refuses_push_table_even_in_mixed_or_renamed_database(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE push_subscriptions(endpoint TEXT, p256dh TEXT, auth TEXT)")
            connection.execute("INSERT INTO push_subscriptions VALUES ('https://secret.test', 'key', 'secret')")
            connection.commit()
        with self.assertRaisesRegex(OpsError, "push/subscription"):
            backup_catalog(self.database, self.backups)
        self.assertFalse(self.backups.exists())

    def test_backup_refuses_sensitive_filename_unknown_tables_and_extra_columns(self) -> None:
        sensitive = self.root / "push_subscriptions.sqlite3"
        sensitive.write_bytes(self.database.read_bytes())
        with self.assertRaisesRegex(OpsError, "push/subscription"):
            backup_catalog(sensitive, self.backups)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE parents(name TEXT)")
            connection.commit()
        with self.assertRaisesRegex(OpsError, "dedicated public"):
            backup_catalog(self.database, self.backups)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DROP TABLE parents")
            connection.execute("ALTER TABLE catalog_results ADD COLUMN auth TEXT")
            connection.commit()
        with self.assertRaisesRegex(OpsError, "schema"):
            backup_catalog(self.database, self.backups)
        self.assertFalse(self.backups.exists())

    def test_restore_refuses_push_snapshot_even_with_updated_manifest(self) -> None:
        bundle = backup_catalog(self.database, self.backups)
        snapshot = bundle / "catalog.sqlite3"
        with closing(sqlite3.connect(snapshot)) as connection:
            connection.execute("CREATE TABLE push_subscriptions(auth TEXT)")
            connection.commit()
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(size_bytes=snapshot.stat().st_size, sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(OpsError, "push/subscription"):
            restore_catalog(bundle, self.root / "recovered.sqlite3")
        self.assertFalse((self.root / "recovered.sqlite3").exists())

    def test_retention_keeps_newest_and_never_deletes_unrelated_data(self) -> None:
        first = backup_catalog(self.database, self.backups, keep=2)
        unrelated = self.backups / "operator-notes.txt"
        unrelated.write_text("keep me")
        lookalike = self.backups / ("catalog-backup-20000101T000000000000Z-" + "a" * 32)
        lookalike.mkdir()
        (lookalike / "important.txt").write_text("not owned")
        link = self.backups / ("catalog-backup-20000101T000000000000Z-" + "b" * 32)
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "important.txt").write_text("outside")
        link.symlink_to(outside, target_is_directory=True)
        second = backup_catalog(self.database, self.backups, keep=2)
        third = backup_catalog(self.database, self.backups, keep=2)
        self.assertFalse(first.exists())
        self.assertTrue(second.is_dir())
        self.assertTrue(third.is_dir())
        self.assertEqual(unrelated.read_text(), "keep me")
        self.assertEqual((lookalike / "important.txt").read_text(), "not owned")
        self.assertTrue(link.is_symlink())
        self.assertEqual((outside / "important.txt").read_text(), "outside")
        self.assertTrue(self.database.exists())

    def test_retention_skips_modified_bundle_and_preserves_other_backup_directories(self) -> None:
        other = backup_catalog(self.database, self.root / "other-backups", keep=1)
        modified = backup_catalog(self.database, self.backups, keep=1)
        (modified / "notes.txt").write_text("operator attachment")
        newest = backup_catalog(self.database, self.backups, keep=1)
        self.assertTrue(other.is_dir())
        self.assertTrue(modified.is_dir())
        self.assertTrue(newest.is_dir())

    def test_failed_backup_is_not_published_and_does_not_prune(self) -> None:
        original = backup_catalog(self.database, self.backups, keep=1)
        with patch("sakurano_line_notifier.ops._integrity", side_effect=OpsError("integrity failed")):
            with self.assertRaises(OpsError):
                backup_catalog(self.database, self.backups, keep=1)
        self.assertEqual(list(self.backups.iterdir()), [original])

    def test_bad_inputs_do_not_create_source_or_modify_existing_database(self) -> None:
        before = self.database.read_bytes()
        for keep in (0, 101):
            with self.assertRaises(OpsError):
                backup_catalog(self.database, self.backups, keep=keep)
        with self.assertRaises(OpsError):
            backup_catalog(self.root / "missing.sqlite3", self.backups)
        with self.assertRaises(OpsError):
            backup_catalog(self.database, self.root)
        symlink = self.root / "backup-link"
        symlink.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OpsError):
            backup_catalog(self.database, symlink)
        self.assertFalse((self.root / "missing.sqlite3").exists())
        self.assertEqual(self.database.read_bytes(), before)

    def test_cli_backup_restore_and_redacted_failure(self) -> None:
        command = [sys.executable, "-m", "sakurano_line_notifier.ops"]
        result = subprocess.run(command + ["backup", "--database", str(self.database), "--destination", str(self.backups)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = json.loads(result.stdout)["destination"]
        restored = self.root / "cli.sqlite3"
        result = subprocess.run(command + ["restore", "--backup", bundle, "--destination", str(restored)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command + ["restore", "--backup", bundle, "--destination", str(restored)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("new destination", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"private endpoint and secret auth; not SQLite")
        result = subprocess.run(command + ["backup", "--database", str(corrupt), "--destination", str(self.backups)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("secret auth", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
