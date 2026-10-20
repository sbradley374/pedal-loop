"""Cached Mapzen Terrarium terrain samples, provenance, and climb estimation."""
from collections import OrderedDict
from datetime import datetime, timezone
from io import BytesIO
import gzip
import hashlib
import json
import math
from pathlib import Path
from .network import fetch

ZOOM = 12
TEMPLATE = 'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png'
ATTRIBUTION = 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md'


def pixel_coordinates(lat,lon,zoom=ZOOM):
    if not (-85 <= lat <= 85 and -180 <= lon <= 180): raise ValueError('Terrain tiles support latitudes from -85 to 85 degrees.')
    size=256*(2**zoom)
    return (lon+180)/360*size-.5, (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size-.5


def decode_rgb(rgb):
    return rgb[0]*256+rgb[1]+rgb[2]/256-32768


class Terrain:
    def __init__(self,cache,zoom=ZOOM,fetcher=fetch):
        self.cache=Path(cache);self.zoom=zoom;self.fetcher=fetcher
        self.images=OrderedDict()
        try:
            from PIL import Image
        except ImportError:
            raise ValueError('New terrain downloads require Pillow. Run python3 -m pip install -r requirements.txt, then load this region again.')
        self.Image=Image
    def tile(self,x,y):
        x%=2**self.zoom
        if not 0<=y<2**self.zoom: raise ValueError('Terrain tile is outside supported latitude.')
        key=(x,y)
        if key not in self.images:
            path=self.cache/str(self.zoom)/str(x)/f'{y}.png'
            body=path.read_bytes() if path.exists() else self.fetcher(TEMPLATE.format(z=self.zoom,x=x,y=y),timeout=40,limit=2_000_000)
            with self.Image.open(BytesIO(body)) as im:
                if im.size!=(256,256):raise ValueError('Unexpected terrain tile size.')
                image=im.convert('RGB');image.load()
            if not path.exists():
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_suffix('.tmp');temporary.write_bytes(body);temporary.replace(path)
            self.images[key]=image
            while len(self.images)>64:self.images.popitem(last=False)
        self.images.move_to_end(key)
        return self.images[key]
    def sample(self,lat,lon):
        x,y=pixel_coordinates(lat,lon,self.zoom);ix,iy=math.floor(x),math.floor(y)
        dx,dy=x-ix,y-iy
        def value(px,py):
            return decode_rgb(self.tile(px//256,py//256).getpixel((px%256,py%256)))
        values=[value(ix,iy),value(ix+1,iy),value(ix,iy+1),value(ix+1,iy+1)]
        if any(v < -12000 or v>9000 for v in values):return None
        return (values[0]*(1-dx)+values[1]*dx)*(1-dy)+(values[2]*(1-dx)+values[3]*dx)*dy


def sidecar(path):return Path(str(path)+'.elevation.json.gz')

def fingerprint(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def attach(graph,path):
    file=sidecar(path)
    if not file.exists():return False
    with gzip.open(file,'rt') as f:data=json.load(f)
    if data.get('snapshot_sha256')!=fingerprint(path):return False
    graph.elevation={int(n):float(e) for n,e in data['nodes'].items() if int(n) in graph.nodes and math.isfinite(float(e))}
    graph.metadata['elevation']=data['metadata']
    return True


def enrich(graph,path,cache,progress=lambda message:None):
    if attach(graph,path):
        progress('Using cached terrain elevations.');return
    terrain=Terrain(cache)
    # Group geographically so adjacent nodes reuse decoded raster tiles.
    grouped={}
    for n,(lat,lon) in graph.nodes.items():
        x,y=pixel_coordinates(lat,lon);grouped.setdefault((int(x)//256,int(y)//256),[]).append(n)
    if len(grouped)>250:raise ValueError('Terrain region too large for this local importer. Use a smaller road snapshot.')
    values={}
    for i,ids in enumerate(grouped.values()):
        progress(f'Sampling terrain tiles {i+1}/{len(grouped)}…')
        for n in ids:
            value=terrain.sample(*graph.nodes[n])
            if value is not None:values[n]=round(value,2)
    latitude=graph.metadata.get('center',next(iter(graph.nodes.values())))[0]
    metadata={'provider':'Mapzen Terrain Tiles / AWS Open Data','kind':'terrain','zoom':ZOOM,
              'grid_spacing_m':round(156543.03392*math.cos(math.radians(latitude))/2**ZOOM,1),
              'accessed_at':datetime.now(timezone.utc).isoformat(),
              'attribution_url':ATTRIBUTION,'source_url':'https://registry.opendata.aws/terrain-tiles/',
              'method':'Bilinear terrain sampling; climb totals use 30 m resampling, a 90 m moving mean, and 3 m reversal threshold. Terrain can differ from bridge/tunnel riding surfaces.'}
    data={'snapshot_sha256':fingerprint(path),'metadata':metadata,'nodes':values}
    target=sidecar(path);temporary=target.with_suffix('.tmp')
    with gzip.open(temporary,'wt') as f:json.dump(data,f,separators=(',',':'))
    temporary.replace(target)
    graph.elevation=values;graph.metadata['elevation']=metadata


def profile_metrics(profile):
    """profile is ordered [distance metres, height metres]. No gaps interpolated."""
    if len(profile)<2 or any(y is None for x,y in profile):return None
    total=profile[-1][0]
    if total<=0:return None
    distances=[i*30 for i in range(int(total//30)+1)]
    if distances[-1]<total:distances.append(total)
    samples=[];index=0
    for d in distances:
        while index<len(profile)-2 and profile[index+1][0]<d:index+=1
        a,b=profile[index:index+2];fraction=(d-a[0])/max(.00001,b[0]-a[0])
        samples.append(a[1]+fraction*(b[1]-a[1]))
    smoothed=[sum(samples[max(0,i-1):i+2])/len(samples[max(0,i-1):i+2]) for i in range(len(samples))]
    # Hysteresis counts full climbs/descents only after a >=3 m reversal.
    anchor=extreme=smoothed[0];direction=0;up=down=0
    for value in smoothed[1:]:
        if direction==0:
            if abs(value-anchor)>=3:direction=1 if value>anchor else -1;extreme=value
        elif direction==1:
            if value>extreme:extreme=value
            elif extreme-value>=3:up+=extreme-anchor;anchor=extreme;extreme=value;direction=-1
        else:
            if value<extreme:extreme=value
            elif value-extreme>=3:down+=anchor-extreme;anchor=extreme;extreme=value;direction=1
    if direction==1:up+=max(0,extreme-anchor)
    elif direction==-1:down+=max(0,anchor-extreme)
    # Approximate sustained grade over 150 m, not noisy adjacent shape nodes.
    grades=[abs(smoothed[i]-smoothed[i-5])/max(1,distances[i]-distances[i-5])*100 for i in range(5,len(samples))]
    return {'ascent_ft':round(up*3.28084),'descent_ft':round(down*3.28084),
            'max_grade_pct':round(max(grades,default=0),1),
            'profile':[[round(d/1609.344,4),round(y,1)] for d,y in zip(distances,smoothed)]}
