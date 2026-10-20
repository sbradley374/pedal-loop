# Snapshot provenance

`providence.osm.json.gz` is the compressed, otherwise unmodified Overpass response plus a `pedal_loop` provenance object. It covers qualifying ways within 20,000 metres of `(41.8268, -71.4025)`. Whole ways can extend beyond that circle; routing coverage is not guaranteed at the edge.

- Provider: https://overpass-api.de/api/interpreter
- OSM base timestamp: **2026-10-20T14:56:06Z**
- Source elements: **611,773** nodes and ways
- Eligible routing nodes at initial validation: **295,998**
- Data: **© OpenStreetMap contributors**, https://www.openstreetmap.org/copyright
- License: Open Database License (ODbL) 1.0, https://opendatacommons.org/licenses/odbl/1-0/

Query (the script uses a 180-second server timeout):

```overpass
[out:json][timeout:90];
way(around:20000,41.8268,-71.4025)
  ["highway"~"^(primary|secondary|tertiary|unclassified|residential|living_street|cycleway|service|path|footway)(_link)?$"];
(._;>;);
out body qt;
```

The snapshot does not contain turn-restriction relations. It is not a complete OSM extract for all feature types. It contains no measured traffic or separate elevation raster. The synthetic fixture is generated in `planner/graph.py`; it is not OSM data.

## Terrain and additional regions (v0.2)

Providence now has `providence.osm.json.gz.elevation.json.gz`, with terrain samples for 295,998 eligible nodes. Each elevation sidecar stores the source road file SHA-256, provider, UTC retrieval timestamp, zoom, local raster spacing and estimation method. The original OSM road response is unchanged.

`region-86dc3c4a39ee1d6e.osm.json.gz` covers the 9 km region around Burlington, Vermont `(44.4759, -73.2121)`, prepared for a 10-mile target using the same Overpass query shape. It contains 51,598 eligible road nodes, with a matching elevation sidecar. The exact OSM base timestamp is retained inside each compressed response.

Terrain is Mapzen Terrain Tiles hosted on AWS Open Data, accessed October 20, 2026. It uses zoom-12 Terrarium PNGs and bilinear interpolation. Approximate raster spacing is 28.5 m at Providence and 27.3 m at Burlington; these spacings are not claims of source accuracy. Source terms and attribution: `TERRAIN-ATTRIBUTION.md`, copied from https://github.com/tilezen/joerd/blob/master/docs/attribution.md.

`*.region.json` files are portable cache manifests. `terrain-cache/` contains only elevation raster tiles, not OSM basemap tiles, and is omitted from the distributable source archive. The bundled sidecars support offline elevation routing without those PNGs. Downloading new terrain requires Pillow.
