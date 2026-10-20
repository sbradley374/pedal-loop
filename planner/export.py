"""GPX 1.1 track export with escaped metadata and no fabricated elevations."""
import xml.etree.ElementTree as ET


def gpx(route, source):
    ns = 'http://www.topografix.com/GPX/1/1'
    ET.register_namespace('', ns)
    def child(parent, name, text=None, **attrs):
        e = ET.SubElement(parent, '{%s}%s' % (ns,name), attrs)
        if text is not None: e.text = str(text)
        return e
    root = ET.Element('{%s}gpx'%ns, version='1.1', creator='Pedal Loop MVP')
    synthetic = source['source'] == 'synthetic'
    title = ('SYNTHETIC DEMO - DO NOT RIDE - ' if synthetic else '') + route['name']
    metadata = child(root,'metadata')
    child(metadata,'name',title)
    child(metadata,'desc', 'Invented test geometry, not real roads.' if synthetic else 'OSM-derived candidate. Verify access, surfaces, and conditions. Traffic is a road-class proxy; safety is not guaranteed.')
    if not synthetic:
        link = child(metadata,'link',href='https://www.openstreetmap.org/copyright')
        child(link,'text','© OpenStreetMap contributors · ODbL')
        if source.get('elevation'):
            link = child(metadata,'link',href=source['elevation']['attribution_url'])
            child(link,'text','Terrain elevation: Mapzen and source data contributors; estimated ground height, not surveyed road elevation.')
    track = child(root,'trk'); child(track,'name',title)
    segment = child(track,'trkseg')
    for i,(lat,lon) in enumerate(route['coordinates']):
        point = child(segment,'trkpt',lat=f'{lat:.7f}',lon=f'{lon:.7f}')
        if route['elevation'] and route['elevation'][i][1] is not None:
            child(point,'ele',f'{route["elevation"][i][1]:.2f}')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
