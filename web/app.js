'use strict';
const $ = id => document.getElementById(id);
let map, marker, tiles, routeLayer, current, selectedIndex = 0, info, revision = 0, importing = false;
const colors = ['#214e3f', '#cb764d', '#7786a5'];
function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function updateLabels() {
  $('miles-value').innerHTML = `${$('miles').value} <small>mi</small>`;
  for (const name of ['traffic', 'stops']) $(name + '-value').textContent = +$(name).value > .65 ? 'High' : +$(name).value > .3 ? 'Medium' : 'Low';
}
function invalidate() {
  revision++;
  current = null;
  $('detail').hidden = true;
  $('routes').replaceChildren();
  routeLayer?.clearLayers();
  status('Settings changed. Find a new loop to update your results.');
}
function updateStart() {
  const lat = +$('lat').value, lon = +$('lon').value;
  if (Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 85 && Math.abs(lon) <= 180) marker?.setLatLng([lat, lon]);
}
function setMode() {
  const synthetic = $('mode').value === 'synthetic';
  if (tiles && map.hasLayer(tiles)) map.removeLayer(tiles);
  if (!synthetic) tiles.addTo(map);
  $('source-badge').textContent = synthetic ? 'SYNTHETIC DEMO · INVENTED ROADS · DO NOT RIDE' : 'OSM ROAD SNAPSHOT · VERIFY BEFORE RIDING';
  $('hill-note').textContent = synthetic ? 'Synthetic elevations demonstrate hill weighting and the profile.' : info.source.elevation ? `Terrain estimates · about ${info.source.elevation.grid_spacing_m} m raster spacing. Bridges/tunnels may differ.` : 'No terrain loaded yet. Load roads + terrain here to enable hill-aware routing.';
  invalidate();
}
function selectRoute(index) {
  selectedIndex = index;
  const route = current.routes[index], synthetic = current.source.source === 'synthetic';
  for (const [i, el] of [...$('routes').children].entries()) {
    el.classList.toggle('active', i === index); el.setAttribute('aria-pressed', i === index ? 'true' : 'false');
  }
  routeLayer.clearLayers();
  current.routes.forEach((r,i) => { if(i !== index) L.polyline(r.coordinates, {color: colors[i], weight: 3, opacity: .45, bubblingMouseEvents: false}).addTo(routeLayer).on('click', () => selectRoute(i)); });
  L.polyline(route.coordinates, {color: '#fffef9', weight: 8, opacity: .9, bubblingMouseEvents: false}).addTo(routeLayer);
  L.polyline(route.coordinates, {color: colors[index], weight: 4.5, opacity: 1, bubblingMouseEvents: false}).addTo(routeLayer);
  marker.setLatLng(current.snapped_start).bindPopup(`Route starts on the network, ${current.snap_distance_m} m from your chosen point.`);
  $('detail').hidden = false;
  $('route-title').textContent = route.name;
  $('distance').textContent = `${route.distance_miles} mi`;
  $('ascent').textContent = route.ascent_ft === null ? 'Unknown' : `${route.ascent_ft.toLocaleString()} ft`;
  $('junctions').textContent = route.junctions;
  $('unknown').textContent = `${route.unknown_surface_pct}%`;
  $('gpx').href = `/api/gpx/${current.id}/${index}`;
  $('gpx').textContent = synthetic ? '↓ Demo GPX · do not ride' : '↓ Download GPX';
  $('descent').textContent = route.descent_ft === null ? 'Descent unavailable' : `↓ ${route.descent_ft.toLocaleString()} ft estimated descent`;
  $('grade').textContent = route.max_grade_pct === null ? 'Grade unavailable' : `~${route.max_grade_pct}% steepest 150 m section`;
  $('terrain-source').textContent = synthetic ? 'Synthetic terrain' : current.source.elevation ? `~${current.source.elevation.grid_spacing_m} m terrain grid` : 'No terrain coverage';
  $('profile').replaceChildren();
  const profile = route.elevation_profile || [];
  $('profile-readout').hidden = !profile.length;
  $('profile-readout').textContent = 'Move over the profile for elevation and distance. Climb totals are smoothed estimates.';
  if (profile.length) {
    const values = profile.map(p => p[1]).filter(v => v !== null), min = Math.min(...values), max = Math.max(...values), range = Math.max(10,max-min);
    const length = profile.at(-1)[0];
    const points = profile.filter(p=>p[1]!==null).map(([x,y]) => `${x/length*800},${85-(y-min)/range*70}`);
    const ns = 'http://www.w3.org/2000/svg';
    const area = document.createElementNS(ns,'polygon'); area.setAttribute('points',`0,100 ${points.join(' ')} 800,100`); area.setAttribute('fill','#e5edcb'); $('profile').append(area);
    const line = document.createElementNS(ns,'polyline'); line.setAttribute('points',points.join(' ')); line.setAttribute('fill','none'); line.setAttribute('stroke','#56743f'); line.setAttribute('stroke-width','2'); $('profile').append(line);
    $('profile-note').textContent = `${synthetic ? 'SYNTHETIC · ' : ''}${Math.round(min*3.28084)}–${Math.round(max*3.28084)} FT · 0–${route.distance_miles} MI`;
    $('profile').style.display = 'block';
    $('profile').onpointermove = event => {
      const bounds = $('profile').getBoundingClientRect();
      const fraction = Math.max(0, Math.min(1, (event.clientX-bounds.left)/bounds.width));
      const sample = profile[Math.round(fraction*(profile.length-1))];
      $('profile-readout').textContent = `${sample[0].toFixed(1)} miles · ${Math.round(sample[1]*3.28084)} ft terrain elevation · smoothed estimate`;
    };
  } else {
    $('profile').style.display = 'none';
    $('profile-note').textContent = `UNAVAILABLE · ${route.elevation_coverage_pct}% SEGMENT COVERAGE`;
  }
  const source = synthetic ? 'Invented roads and elevations. This export is for software testing, not navigation.' : `OSM snapshot: ${current.source.timestamp}. Traffic is inferred from road class, not measured traffic volume. Mapped stops are incomplete; junctions do not necessarily require stopping. Turn restrictions are not yet modeled.`;
  $('confidence').textContent = `${source} ${route.mapped_stops} mapped stops/signals · ${route.repeated_pct}% repeated distance · ${route.distance_error_pct}% from requested distance. Start snapped ${current.snap_distance_m} m to the network; the connecting trip is not included. ${route.unknown_surface_pct}% of route length has no surface tag. ${!profile.length && current.preferences.hills !== 'neutral' ? 'Elevation is incomplete, so the hill preference cannot reliably rank these routes.' : ''} ${current.source.elevation ? 'Elevation is a terrain estimate, sampled bilinearly and smoothed for climb totals; bridges, tunnels, and raster errors can affect it.' : ''}`;
}
async function generate(event) {
  event?.preventDefault();
  if (importing) { status('Wait for the region import to finish before searching.'); return; }
  if (!$('planner').reportValidity()) { status('Check the start coordinates and ride settings.',true); return; }
  if ($('generate').disabled) return;
  const thisRevision = revision;
  $('generate').disabled = true; $('load-region').disabled=true; $('saved-region').disabled=true; $('generate').textContent = 'Searching the road network…'; document.body.classList.add('busy');
  current = null; $('detail').hidden = true; $('routes').replaceChildren(); routeLayer.clearLayers();
  status('Searching loop candidates and comparing distance, road class, junctions, and backtracking…');
  const payload = {mode:$('mode').value,lat:+$('lat').value,lon:+$('lon').value,miles:+$('miles').value,traffic:+$('traffic').value,stops:+$('stops').value,hills:$('hills').value,strict:$('strict').checked};
  try {
    const response = await fetch('/api/routes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result = await response.json();
    if (thisRevision !== revision) { status('Settings changed during the search. Find a new loop with your latest preferences.'); return; }
    if (!response.ok) throw new Error(result.error || 'Route search failed.');
    current = result;
    current.routes.forEach((r,i) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'route-card';
      const name = document.createElement('span'); name.className='name'; name.textContent=`0${i+1} / ${r.name}`;
      const miles = document.createElement('strong'); miles.textContent=r.distance_miles;
      const unit = document.createElement('small'); unit.textContent='miles';
      const sub = document.createElement('span'); sub.className='sub'; sub.textContent=`${r.ascent_ft === null ? 'Climb unknown' : '~'+r.ascent_ft.toLocaleString()+' ft climbing'} · ${r.unknown_surface_pct}% surface unknown`;
      button.append(name,miles,unit,sub); button.addEventListener('click',()=>selectRoute(i)); $('routes').append(button);
    });
    $('map-title').textContent = result.source.source === 'synthetic' ? 'Try the planner. These roads are invented.' : 'Your way out. Your way back.';
    status(`${result.routes.length} loop ${result.routes.length===1?'candidate':'alternatives'} found for your ${payload.miles}-mile ride. ${result.routes[0].distance_error_pct>15?'The closest match is well outside your target; try another distance or start.':'Select a route to explore it.'} ${(result.warnings||[]).join(' ')}`);
    selectRoute(0); fit();
  } catch(error) { status(error.message,true); }
  finally { $('load-region').disabled=!info?.region_import_enabled; $('saved-region').disabled=false; $('generate').disabled=false; $('generate').innerHTML='Find my loop <span>↗</span>'; document.body.classList.remove('busy'); }
}
function fit() { if(current) map.fitBounds(L.latLngBounds(current.routes[selectedIndex].coordinates),{padding:[35,35]}); }

async function refreshInfo() {
  const response = await fetch('/api/info');
  if (!response.ok) throw new Error('Cannot load road dataset information.');
  info = await response.json();
  if (info.osm_available && !$('mode').querySelector('option[value="osm"]')) {
    const option = document.createElement('option'); option.value='osm'; option.textContent='OpenStreetMap · cached roads'; $('mode').prepend(option);
  }
  $('mode').value = info.default_mode;
  $('saved-region').replaceChildren();
  for (const region of info.regions) {
    const option=document.createElement('option'); option.value=region.id;
    option.textContent=`${region.label} · ${Math.round(region.radius_m/1000)} km${region.elevation ? ' · terrain' : ''}`;
    $('saved-region').append(option);
  }
  $('saved-region').value=info.active_region || '';
  $('load-region').disabled=!info.region_import_enabled;
  const active=info.regions.find(r=>r.id===info.active_region);
  $('region-note').textContent=active ? `Loaded: ${active.label}, ${Math.round(active.radius_m/1000)} km radius. New downloads send the selected region to OSM and AWS. Cached regions work offline.` : 'Load a region around your start. Downloads send the selected region to OSM and AWS.';
}
async function loadRegion(regionId=null) {
  if (importing || $('generate').disabled || !$('planner').reportValidity()) return;
  importing=true; invalidate();
  $('load-region').disabled=true; $('generate').disabled=true; $('saved-region').disabled=true;
  $('region-status').textContent='Preparing roads and terrain…';
  const lat=+$('lat').value, lon=+$('lon').value;
  const label=$('place').value==='custom' ? `${lat.toFixed(4)}, ${lon.toFixed(4)}` : $('place').selectedOptions[0].textContent;
  try {
    const response=await fetch('/api/regions/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat,lon,miles:+$('miles').value,label, ...(regionId ? {region_id:regionId} : {})})});
    let job=await response.json();if(!response.ok)throw new Error(job.error || 'Could not start region import.');
    while(job.status==='running') {
      $('region-status').textContent=job.message;
      await new Promise(resolve=>setTimeout(resolve,1500));
      const progress=await fetch(`/api/regions/jobs/${job.id}`);
      if(!progress.ok)throw new Error('Lost import progress. Reload the page to inspect the active region.');
      job=await progress.json();
    }
    if(job.status==='failed')throw new Error(job.message);
    await refreshInfo();setMode();
    if(regionId && info.source.center) {
      [$('lat').value,$('lon').value]=info.source.center;
      $('place').value='custom';updateStart();map.setView(marker.getLatLng(),11);
    }
    $('region-status').textContent=job.message;
    status('Region ready. Choose your settings, then find a loop.');
  } catch(error) { $('region-status').textContent=error.message; }
  finally { importing=false;$('load-region').disabled=!info?.region_import_enabled;$('generate').disabled=false;$('saved-region').disabled=false; }
}

async function init() {
  updateLabels();
  if (!window.L) { status('Local map library missing. Restore web/vendor/leaflet.js from Leaflet 1.9.4.',true); return; }
  map = L.map('map',{zoomControl:false}).setView([41.8268,-71.4025],11); L.control.zoom({position:'topright'}).addTo(map);
  marker = L.marker([41.8268,-71.4025],{icon:L.divIcon({className:'start-icon',iconSize:[18,18],iconAnchor:[9,9]}),keyboard:true,title:'Chosen start'}).addTo(map);
  routeLayer=L.layerGroup().addTo(map);
  map.on('click', e => { $('lat').value=e.latlng.lat.toFixed(6);$('lon').value=e.latlng.lng.toFixed(6);$('place').value='custom';invalidate();updateStart(); });
  $('planner').addEventListener('submit',generate);
  $('generate').addEventListener('click',generate);
  $('planner').addEventListener('input',e => { if(['mode','place','saved-region'].includes(e.target.id))return; updateLabels();invalidate(); if(['lat','lon'].includes(e.target.id)){$('place').value='custom';updateStart();} });
  $('place').addEventListener('change',()=>{if($('place').value!=='custom'){[$('lat').value,$('lon').value]=$('place').value.split(',');updateStart();map.setView(marker.getLatLng(),11);}invalidate();});
  $('mode').addEventListener('change',setMode);
  $('load-region').addEventListener('click',()=>loadRegion());
  $('saved-region').addEventListener('change',()=>{if($('saved-region').value)loadRegion($('saved-region').value);});
  $('fit').addEventListener('click',fit);
  try {
    await refreshInfo();
    if(info.source.center) {
      [$('lat').value,$('lon').value]=info.source.center;
      const preset=[...$('place').options].find(option=>option.value!=='custom' && option.value.split(',').every((v,i)=>Math.abs(+v-info.source.center[i])<.00001));
      $('place').value=preset ? preset.value : 'custom';
      if(info.source.radius_m && info.source.radius_m<15000) {
        $('miles').value=Math.max(5,Math.min(30,Math.floor((info.source.radius_m-2000)/(1609.344*.42))));
        updateLabels();
      }
      updateStart();map.setView(marker.getLatLng(),11);
    }
    tiles=L.tileLayer(info.tile_url,{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
    let tileErrorShown=false;tiles.on('tileerror',()=>{if(!tileErrorShown){tileErrorShown=true;$('source-badge').textContent='BASEMAP UNAVAILABLE · ROUTE GEOMETRY STILL SHOWN';}});
    setMode(); await generate();
  } catch(error) { status(error.message,true); }
}
init();
