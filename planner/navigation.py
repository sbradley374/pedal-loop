"""Preview cues from the selected directed path; not a validated instruction engine."""
import math


def bearing(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    delta = math.radians(b[1]-a[1])
    return math.degrees(math.atan2(math.sin(delta)*math.cos(lat2),
                                  math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(delta)))


def cues(graph, edges):
    if not edges: return []
    result=[{'distance_m':0, 'coordinate_index':0, 'instruction':'Start on '+edges[0].name}]
    cumulative=0
    for i, edge in enumerate(edges):
        if i:
            previous=edges[i-1]
            angle=(bearing(graph.nodes[edge.u],graph.nodes[edge.v])-
                   bearing(graph.nodes[previous.u],graph.nodes[previous.v])+180)%360-180
            junction=graph.is_junction(edge.u)
            changed=edge.name!=previous.name
            if changed or (junction and abs(angle)>=25):
                if abs(angle)>=150: action='Route reverses direction'
                elif abs(angle)>=45: action='Turn '+('right' if angle>0 else 'left')
                elif abs(angle)>=25: action='Bear '+('right' if angle>0 else 'left')
                else: action='Continue'
                result.append({'distance_m':round(cumulative,2),'coordinate_index':i,
                               'instruction':action+' onto '+edge.name})
        cumulative+=edge.length
    result.append({'distance_m':round(cumulative,2),'coordinate_index':len(edges),'instruction':'Return to the route start'})
    return result
