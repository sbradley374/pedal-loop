import json
from pathlib import Path
import tempfile
import unittest
from planner.storage import seed_data


class SeedTests(unittest.TestCase):
    def test_empty_volume_is_seeded_and_existing_data_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'image';source.mkdir()
            destination=Path(root)/'disk'
            manifest=source/'test.region.json'
            manifest.write_text(json.dumps({'file':'roads.gz'}))
            (source/'roads.gz').write_bytes(b'roads')
            (source/'roads.gz.elevation.json.gz').write_bytes(b'terrain')
            (source/'routes.sqlite3').write_bytes(b'never copy rides')
            seed_data(source,destination)
            self.assertEqual((destination/'roads.gz').read_bytes(),b'roads')
            self.assertEqual((destination/'roads.gz.elevation.json.gz').read_bytes(),b'terrain')
            self.assertTrue((destination/manifest.name).exists())
            self.assertFalse((destination/'routes.sqlite3').exists())
            (destination/'roads.gz').write_bytes(b'updated roads')
            seed_data(source,destination)
            self.assertEqual((destination/'roads.gz').read_bytes(),b'updated roads')
            self.assertFalse(list(destination.glob('.seed-*')))

    def test_manifest_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'image';source.mkdir()
            (source/'bad.region.json').write_text(json.dumps({'file':'../outside'}))
            with self.assertRaises(ValueError):seed_data(source,Path(root)/'disk')
