"""Bounded regional imports, durable catalogs, and atomic active-graph swaps."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import threading
import urllib.parse
import uuid
from collections import OrderedDict
from . import graph, elevation
from .network import fetch

ENDPOINT='https://overpass-api.de/api/interpreter'


def requested_radius(miles):
    return min(30000,max(4000,math.ceil((miles*1609.344*.42+2000)/1000)*1000))


def download(path,lat,lon,radius,endpoint=ENDPOINT,label='',progress=lambda message:None):
    path=Path(path)
    if path.exists():return path
    if not (-85<=lat<=85 and -180<=lon<=180 and 1000<=radius<=30000):raise ValueError('Invalid region coordinates or radius (1–30 km).')
    query=f'''[out:json][timeout:180];way(around:{radius},{lat},{lon})["highway"~"^(primary|secondary|tertiary|unclassified|residential|living_street|cycleway|service|path|footway)(_link)?$"]->.roads;rel(bw.roads)["type"="restriction"]->.restrictions;(.roads;node(w.roads);.restrictions;);out body qt;'''
    progress('Downloading one OSM road region. This can take several minutes…')
    data=json.loads(fetch(endpoint+'?'+urllib.parse.urlencode({'data':query}),timeout=210))
    if data.get('remark') or not data.get('elements'):raise ValueError('OSM provider returned incomplete data. The previous region is still available. Try again later or use a smaller distance.')
    data['pedal_loop']={'center':[lat,lon],'radius_m':radius,'endpoint':endpoint,'restrictions_requested':True,'region_label':label or f'{lat:.4f}, {lon:.4f}'}
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with gzip.open(temp,'wt') as f:json.dump(data,f,separators=(',',':'))
    temp.replace(path);return path


class Regions:
    def __init__(self,directory,initial=None,enabled=True,downloader=download,enricher=elevation.enrich):
        self.directory=Path(directory);self.enabled=enabled
        self.active=None;self.active_id=None
        self.catalog={};self.jobs={};self.mutex=threading.Lock();self.loading=False
        self.downloader=downloader;self.enricher=enricher
        self.loaded=OrderedDict()
        self.load_mutex=threading.Lock()
        for manifest in sorted(self.directory.glob('*.region.json')):
            try:
                record=json.loads(manifest.read_text())
                path=self.directory/record['file']
                if path.parent.resolve()==self.directory.resolve() and path.exists():self.catalog[record['id']]=record
            except (ValueError,KeyError):continue
        if initial and Path(initial).exists() and enabled:
            self.active=graph.load(initial)
            if not self.active.nodes:raise ValueError('Snapshot has no eligible roads.')
            self.active_id=self.register(Path(initial),self.active)
            self.loaded[self.active_id]=self.active

    def get(self,region_id=None):
        """Resolve each request independently; never change the default region."""
        region_id=region_id or self.active_id
        if region_id is None:return None
        if not isinstance(region_id,str):raise ValueError('Invalid region ID.')
        with self.load_mutex:
            if region_id in self.loaded:
                self.loaded.move_to_end(region_id)
                return self.loaded[region_id]
            with self.mutex:record=self.catalog.get(region_id)
            if record is None:raise ValueError('Unknown cached region.')
            candidate=graph.load(Path(record.get('_path',self.directory/record['file'])))
            if not candidate.nodes:raise ValueError('This region contains no eligible roads.')
            self.loaded[region_id]=candidate
            while len(self.loaded)>2:self.loaded.popitem(last=False)
            return candidate
    def register(self,path,g):
        rid=hashlib.sha256(path.name.encode()).hexdigest()[:16]
        record={'id':rid,'file':path.name,'label':g.metadata.get('region_label','Providence / Brown' if path.name=='providence.osm.json.gz' else path.stem),
                'center':g.metadata.get('center'),'radius_m':g.metadata.get('radius_m'),'elevation':bool(g.metadata.get('elevation'))}
        # Custom --data paths remain selectable during this process, but aren't
        # written into this directory's durable catalog as relative paths.
        record['_path']=str(path.resolve())
        with self.mutex:
            for old_id in list(self.catalog):
                if self.catalog[old_id]['file']==path.name and old_id!=rid:
                    del self.catalog[old_id]
            self.catalog[rid]=record
        if path.parent.resolve()==self.directory.resolve():
            saved={k:v for k,v in record.items() if not k.startswith('_')}
            temp=path.with_suffix('.region.tmp');temp.write_text(json.dumps(saved));temp.replace(path.with_suffix('.region.json'))
        return rid
    def info(self):
        with self.mutex:
            return {'active_region':self.active_id,'regions':[{k:v for k,v in r.items() if not k.startswith('_')} for r in self.catalog.values()], 'loading':self.loading,'region_import_enabled':self.enabled}
    def start(self,payload,prefs,activate=True):
        if not self.enabled:raise ValueError('Region downloads are disabled in forced synthetic mode.')
        rid=payload.get('region_id')
        if rid is not None and (not isinstance(rid,str) or rid not in self.catalog):raise ValueError('Unknown cached region.')
        with self.mutex:
            if self.loading:raise ValueError('A region is already loading. Wait for it to finish.')
            self.loading=True
            jobid=uuid.uuid4().hex
            self.jobs[jobid]={'id':jobid,'status':'running','message':'Preparing region…'}
            while len(self.jobs)>20:del self.jobs[next(iter(self.jobs))]
        def update(message):
            with self.mutex:self.jobs[jobid]['message']=message
        def work():
            try:
                if rid:
                    record=self.catalog[rid];path=Path(record.get('_path',self.directory/record['file']))
                    update('Opening the cached road region…')
                else:
                    lat,lon=round(prefs['lat'],4),round(prefs['lon'],4)
                    radius=requested_radius(prefs['miles'])
                    identity=hashlib.sha256(f'v3,{lat},{lon},{radius}'.encode()).hexdigest()[:16]
                    path=self.directory/f'region-{identity}.osm.json.gz'
                    label=str(payload.get('label',''))[:80]
                    self.downloader(path,lat,lon,radius,label=label,progress=update)
                update('Building the routable road network…')
                candidate=graph.load(path)
                if not candidate.nodes:raise ValueError('This region contains no eligible cycling roads. Try another start.')
                warning=None
                try:self.enricher(candidate,path,self.directory/'terrain-cache',update)
                except Exception as e:
                    warning=f'Roads loaded; terrain unavailable: {e}'
                region_id=self.register(path,candidate)
                with self.load_mutex:
                    self.loaded[region_id]=candidate
                    while len(self.loaded)>2:self.loaded.popitem(last=False)
                with self.mutex:
                    if activate:self.active=candidate;self.active_id=region_id
                    self.jobs[jobid].update(status='complete',message=warning or 'Roads and terrain are ready.',warning=warning,region_id=region_id)
            except Exception as e:
                with self.mutex:self.jobs[jobid].update(status='failed',message=f'Region load failed: {e}. Previous region retained.')
            finally:
                with self.mutex:self.loading=False
        threading.Thread(target=work,daemon=True).start()
        return dict(self.jobs[jobid])
    def job(self,jobid):
        with self.mutex:return dict(self.jobs[jobid]) if jobid in self.jobs else None
