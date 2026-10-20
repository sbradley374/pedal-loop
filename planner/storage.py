"""Seed a new persistent volume without replacing existing datasets or rides."""
import json
import os
from pathlib import Path
import shutil
import tempfile


def seed_data(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination: return
    destination.mkdir(parents=True, exist_ok=True)
    for manifest in sorted(source.glob('*.region.json')):
        record = json.loads(manifest.read_text())
        name = record['file']
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('Seed manifest must reference a filename inside its data directory.')
        road = source/name
        if not road.is_file(): raise ValueError(f'Missing seed snapshot: {name}')
        # Copy dependencies first; a manifest never advertises an incomplete copy.
        files = [road]
        terrain = source/(name+'.elevation.json.gz')
        if terrain.exists(): files.append(terrain)
        files.append(manifest)
        for original in files:
            target = destination/original.name
            if target.exists(): continue
            fd, temp_name = tempfile.mkstemp(prefix='.seed-', dir=destination)
            temporary = Path(temp_name)
            try:
                with os.fdopen(fd, 'wb') as output, original.open('rb') as input_file:
                    shutil.copyfileobj(input_file, output)
                try: os.link(temporary, target)
                except FileExistsError: pass
            finally:
                temporary.unlink(missing_ok=True)
