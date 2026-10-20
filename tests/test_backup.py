from pathlib import Path
import sqlite3
import tempfile
import unittest
from scripts.backup_results import backup
from planner.service import ResultStore


class BackupTests(unittest.TestCase):
    def test_live_wal_backup_restores_completed_ride(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'rides.sqlite3'
            saved=Path(directory)/'backup.sqlite3'
            store=ResultStore(source)
            # Keep a live connection so WAL contents cannot rely on closing/checkpointing.
            with sqlite3.connect(source) as live:
                self.assertEqual(live.execute('PRAGMA journal_mode').fetchone()[0],'wal')
                store.put('key',{'id':'ride','routes':[{'distance_miles':10}]})
                self.assertEqual(live.execute('select count(*) from results').fetchone()[0],1)
                self.assertTrue(Path(str(source)+'-wal').exists())
                backup(source,saved)
                self.assertEqual(ResultStore(saved).get('ride')['routes'][0]['distance_miles'],10)
            with self.assertRaises(ValueError): backup(source,saved)
            self.assertEqual(saved.stat().st_mode & 0o777,0o600)

    def test_missing_source_does_not_create_an_empty_database(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'missing.sqlite3'
            with self.assertRaises(ValueError): backup(source,Path(directory)/'backup.sqlite3')
            self.assertFalse(source.exists())
