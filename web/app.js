'use strict';
const $ = id => document.getElementById(id);
let map, marker, tiles, routeLayer, current, selectedIndex = 0, info, revision = 0, importing = false, activeJob = null, activeRegion = null, cancelRequested = false, coverageLayer;
let rideMode;
const colors = ['#214e3f', '#cb764d', '#7786a5'];
function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function updateLabels() {
  $('miles-value').innerHTML = `${$('miles').value} <small>mi</small>`;
  for (const name of ['traffic', 'stops']) $(name + '-value').textContent = +$(name).value > .65 ? 'High' : +$(name).value > .3 ? 'Medium' : 'Low';
}
function invalidate() {
  rideMode?.stop();
  revision++;
  if (activeJob) cancelSearch();
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
function coversStart(region, lat, lon) {
  if(!region.center || !region.radius_m) return false;
  const rad=Math.PI/180, [centerLat,centerLon]=region.center;
  const a=Math.sin((lat-centerLat)*rad/2)**2 + Math.cos(lat*rad)*Math.cos(centerLat*rad)*Math.sin((lon-centerLon)*rad/2)**2;
  return 6371000*2*Math.asin(Math.sqrt(Math.min(1,a))) <= region.radius_m;
}
async function selectCachedRegionForStart() {
  if($('mode').value!=='osm' || !info || importing || $('generate').disabled) return;
  const lat=+$('lat').value, lon=+$('lon').value;
  const candidates=info.regions.filter(region=>coversStart(region,lat,lon));
  if(candidates.some(region=>region.id===activeRegion)) return;
  // Prefer the largest available snapshot so longer loops have room to fit.
  candidates.sort((a,b)=>b.radius_m-a.radius_m);
  if(candidates.length) await loadRegion(candidates[0].id,{preserveStart:true});
  else status('This start is outside cached coverage. Choose a cached road region or load roads here when downloads are enabled.',true);
}
function setMode() {
  const synthetic = $('mode').value === 'synthetic';
  if (tiles && map.hasLayer(tiles)) map.removeLayer(tiles);
  if (!synthetic) tiles.addTo(map);
  if(coverageLayer) {
    if(synthetic) map.removeLayer(coverageLayer);
    else coverageLayer.addTo(map);
  }
  $('source-badge').textContent = synthetic ? 'SYNTHETIC DEMO · INVENTED ROADS · DO NOT RIDE' : 'OSM ROAD SNAPSHOT · VERIFY BEFORE RIDING';
  $('hill-note').textContent = synthetic ? 'Synthetic elevations demonstrate hill weighting and the profile.' : info.source.elevation ? `Terrain estimates · about ${info.source.elevation.grid_spacing_m} m raster spacing. Bridges/tunnels may differ.` : 'No terrain loaded yet. Load roads + terrain here to enable hill-aware routing.';
  invalidate();
}
function selectRoute(index) {
  rideMode?.stop();
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
  $('start-ride').disabled = synthetic;
  $('route-title').textContent = route.name;
  $('distance').textContent = `${route.distance_miles} mi`;
  $('ascent').textContent = route.ascent_ft === null ? 'Unknown' : `${route.ascent_ft.toLocaleString()} ft`;
  $('junctions').textContent = route.junctions;
  $('unknown').textContent = `${route.unknown_surface_pct}%`;
  $('road-summary').textContent = `${route.major_road_pct ?? '—'}% primary/secondary roads · ${route.structure_pct ?? '—'}% bridges/tunnels · ${route.distance_error_pct}% distance error`;
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
  const source = synthetic ? 'Invented roads and elevations. This export is for software testing, not navigation.' : `OSM snapshot: ${current.source.timestamp}. Traffic is inferred from road class, not measured traffic volume. Mapped stops are incomplete; junctions do not necessarily require stopping. Supported turn restrictions apply when included in the snapshot; complex restrictions and current conditions still need checking.`;
  $('confidence').textContent = `${source} ${route.mapped_stops} mapped stops/signals · ${route.repeated_pct}% repeated distance · ${route.distance_error_pct}% from requested distance. Start snapped ${current.snap_distance_m} m to the network; the connecting trip is not included. ${route.unknown_surface_pct}% of route length has no surface tag. ${!profile.length && current.preferences.hills !== 'neutral' ? 'Elevation is incomplete, so the hill preference cannot reliably rank these routes.' : ''} ${current.source.elevation ? 'Elevation is a terrain estimate, sampled bilinearly and smoothed for climb totals; bridges, tunnels, and raster errors can affect it.' : ''}`;
}
async function api(path, options) {
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
function renderResult(result, index=0) {
  current = result;
  $('routes').replaceChildren();
  current.routes.forEach((r,i) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'route-card';
    const name = document.createElement('span'); name.className='name'; name.textContent=`0${i+1} / ${r.name}`;
    const miles = document.createElement('strong'); miles.textContent=r.distance_miles;
    const unit = document.createElement('small'); unit.textContent='miles';
    const sub = document.createElement('span'); sub.className='sub';
    sub.textContent=`${r.ascent_ft === null ? 'Climb unknown' : '~'+r.ascent_ft.toLocaleString()+' ft climbing'} · ${r.major_road_pct ?? '—'}% major roads · ${r.distance_error_pct}% distance error`;
    button.append(name,miles,unit,sub); button.addEventListener('click',()=>selectRoute(i)); $('routes').append(button);
  });
  $('map-title').textContent = result.source.source === 'synthetic' ? 'Try the planner. These roads are invented.' : 'Your way out. Your way back.';
  status(`${result.routes.length} loop ${result.routes.length===1?'candidate':'alternatives'} for ${result.preferences.miles} miles. ${result.cached ? 'Reused a matching saved result.' : result.search ? `Search: ${result.search.seconds.toFixed(1)} seconds.` : ''} ${(result.warnings||[]).join(' ')}`);
  selectRoute(Math.max(0,Math.min(result.routes.length-1,index))); fit();
}
async function cancelSearch() {
  cancelRequested = true;
  if (activeJob) {
    try { await api(`/api/route-jobs/${activeJob}`,{method:'DELETE'}); }
    catch(error) { status(`Cancellation could not be confirmed: ${error.message}`,true); }
  }
}
async function generate(event) {
  event?.preventDefault();
  if (importing || $('generate').disabled) return;
  if (!$('planner').reportValidity()) { status('Check the start coordinates and ride settings.',true); return; }
  rideMode?.stop();
  const thisRevision = ++revision;
  cancelRequested=false;
  $('generate').disabled=true; $('load-region').disabled=true; $('saved-region').disabled=true;
  $('cancel').hidden=false; $('generate').textContent='Finding your loop…'; document.body.classList.add('busy');
  current=null; $('detail').hidden=true; $('routes').replaceChildren(); routeLayer.clearLayers();
  status('Comparing loops within your distance and road preferences…');
  const payload = {mode:$('mode').value, region_id:activeRegion, lat:+$('lat').value,lon:+$('lon').value,miles:+$('miles').value,traffic:+$('traffic').value,stops:+$('stops').value,hills:$('hills').value,strict:$('strict').checked,avoid_major:$('avoid-major').checked,tolerance:+$('tolerance').value,max_ascent:$('max-ascent').value===''?null:+$('max-ascent').value};
  const started=performance.now();
  try {
    let job=await api('/api/route-jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    activeJob=job.id;
    if (cancelRequested || thisRevision!==revision) await cancelSearch();
    while (['queued','running'].includes(job.status)) {
      if (!cancelRequested) status(`${job.status==='queued'?'Waiting for a search worker':'Searching the road network'} · ${Math.round((performance.now()-started)/1000)} seconds. You can cancel or change settings.`);
      await new Promise(resolve=>setTimeout(resolve,750));
      job=await api(`/api/route-jobs/${activeJob}`);
    }
    if (job.status==='cancelled' || cancelRequested) { status('Search cancelled. Choose your settings and try again.'); return; }
    if (job.status==='failed') throw new Error(job.error || 'Search failed.');
    const result=await api(`/api/results/${job.result_id}`);
    result.cached=job.cached;
    if (thisRevision!==revision) { status('Settings changed. Find a new loop with your latest preferences.'); return; }
    renderResult(result);
  } catch(error) { status(error.message,true); }
  finally {
    activeJob=null; $('cancel').hidden=true; $('load-region').disabled=!info?.region_import_enabled;
    $('saved-region').disabled=false; $('generate').disabled=false; $('generate').innerHTML='Find my loop <span>↗</span>'; document.body.classList.remove('busy');
  }
}
function savedRides() {
  try { const saved=JSON.parse(localStorage.getItem('pedal-loop-rides') || '[]'); return Array.isArray(saved)?saved:[]; }
  catch { return []; }
}
function updateSaved() {
  $('saved-rides').replaceChildren(new Option('Choose a saved ride',''));
  savedRides().forEach(ride=>$('saved-rides').append(new Option(ride.label,`${ride.id}:${ride.index}`)));
}
async function openRide(id,index=0) {
  if ($('generate').disabled || importing) return;
  const thisRevision=++revision;
  const isCurrent=()=>thisRevision===revision;
  status('Loading saved ride…');
  try {
    const result=await api(`/api/results/${encodeURIComponent(id)}`);
    if(!isCurrent()) return;
    if(result.region_id && !await refreshInfo(result.region_id,isCurrent)) return;
    for(const name of ['lat','lon','miles','traffic','stops','hills','tolerance']) {
      if(result.preferences[name]!==undefined) $(name).value=result.preferences[name];
    }
    $('strict').checked=result.preferences.strict; $('avoid-major').checked=!!result.preferences.avoid_major;
    $('max-ascent').value=result.preferences.max_ascent ?? ''; $('place').value='custom';
    $('mode').value=result.source.source==='synthetic'?'synthetic':'osm';
    updateLabels(); updateStart(); setMode(); renderResult(result,index);
  } catch(error) {
    if(isCurrent()) status(error.message,true);
  }
}
function fit() { if(current) map.fitBounds(L.latLngBounds(current.routes[selectedIndex].coordinates),{padding:[35,35]}); }

async function refreshInfo(regionId=activeRegion, isCurrent=()=>true) {
  const response = await fetch('/api/info'+(regionId ? `?region_id=${encodeURIComponent(regionId)}` : ''));
  if (!response.ok) throw new Error('Cannot load road dataset information.');
  const nextInfo = await response.json();
  if(!isCurrent()) return false;
  info = nextInfo;
  activeRegion=info.active_region;
  if(coverageLayer) map.removeLayer(coverageLayer);
  if(info.source.center && info.source.radius_m) coverageLayer=L.circle(info.source.center,{radius:info.source.radius_m,color:'#56743f',weight:1,dashArray:'6 6',fillOpacity:.025,interactive:false}).addTo(map);
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
  return true;
}
async function loadRegion(regionId=null, {preserveStart=false}={}) {
  if (importing || $('generate').disabled || !$('planner').reportValidity()) return;
  const previousRegion=activeRegion;
  importing=true; invalidate();
  $('load-region').disabled=true; $('generate').disabled=true; $('saved-region').disabled=true;
  $('region-status').textContent='Preparing roads and terrain…';
  const lat=+$('lat').value, lon=+$('lon').value;
  const label=$('place').value==='custom' ? `${lat.toFixed(4)}, ${lon.toFixed(4)}` : $('place').selectedOptions[0].textContent;
  try {
    let message='Cached region ready.';
    if(regionId) { activeRegion=regionId; }
    else {
      let job=await api('/api/regions/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat,lon,miles:+$('miles').value,label})});
      while(job.status==='running') {
        $('region-status').textContent=job.message;
        await new Promise(resolve=>setTimeout(resolve,1500));
        job=await api(`/api/regions/jobs/${job.id}`);
      }
      if(job.status==='failed')throw new Error(job.message);
      activeRegion=job.region_id; message=job.message;
    }
    await refreshInfo();setMode();
    if(regionId && !preserveStart && info.source.center) {
      [$('lat').value,$('lon').value]=info.source.center;
      $('place').value='custom';updateStart();map.setView(marker.getLatLng(),11);
    }
    $('region-status').textContent=message;
    status('Region ready. Choose your settings, then find a loop.');
  } catch(error) { activeRegion=previousRegion; $('saved-region').value=previousRegion || ''; $('region-status').textContent=error.message; }
  finally { importing=false;$('load-region').disabled=!info?.region_import_enabled;$('generate').disabled=false;$('saved-region').disabled=false; }
}

async function init() {
  updateLabels();
  if (!window.L) { status('Local map library missing. Restore web/vendor/leaflet.js from Leaflet 1.9.4.',true); return; }
  map = L.map('map',{zoomControl:false}).setView([41.8268,-71.4025],11); L.control.zoom({position:'topright'}).addTo(map);
  marker = L.marker([41.8268,-71.4025],{icon:L.divIcon({className:'start-icon',iconSize:[18,18],iconAnchor:[9,9]}),keyboard:true,title:'Chosen start'}).addTo(map);
  routeLayer=L.layerGroup().addTo(map);
  rideMode=createRideMode(map);
  $('start-ride').addEventListener('click',()=>{if(current)rideMode.start(current.routes[selectedIndex],current.source.source==='synthetic');});
  map.on('click', e => { if(rideMode?.active)return; $('lat').value=e.latlng.lat.toFixed(6);$('lon').value=e.latlng.lng.toFixed(6);$('place').value='custom';invalidate();updateStart(); });
  $('planner').addEventListener('submit',generate);
  $('cancel').addEventListener('click',cancelSearch);
  $('locate').addEventListener('click',()=>{
    if(!navigator.geolocation) { status('Location is unavailable. Click the map to choose your start.',true); return; }
    navigator.geolocation.getCurrentPosition(position=>{
      $('lat').value=position.coords.latitude.toFixed(6); $('lon').value=position.coords.longitude.toFixed(6);
      $('place').value='custom'; invalidate(); updateStart(); map.setView(marker.getLatLng(),12);
      selectCachedRegionForStart();
    },()=>status('Could not get your location. Click the map or enter coordinates.',true),{timeout:10000});
  });
  updateSaved();
  $('save-ride').addEventListener('click',()=>{
    if(!current)return;
    const ride=current.routes[selectedIndex];
    const saved=[{id:current.id,index:selectedIndex,label:`${ride.distance_miles} mi · ${current.source.region_label || current.source.label} · ${new Date().toLocaleDateString()}`},...savedRides().filter(r=>r.id!==current.id || r.index!==selectedIndex)].slice(0,12);
    try { localStorage.setItem('pedal-loop-rides',JSON.stringify(saved)); updateSaved(); status('Ride saved on this browser. Download GPX to keep it permanently.'); }
    catch { status('Browser storage is unavailable. Download GPX to save this ride.',true); }
  });
  $('share-ride').addEventListener('click',async()=>{
    if(!current)return;
    const url=new URL(location.href); url.search=`ride=${current.id}&route=${selectedIndex}`;
    try { await navigator.clipboard.writeText(url.href); status(location.hostname==='127.0.0.1' || location.hostname==='localhost' ? 'Link copied. This local server link only works on this computer. Share GPX with others.' : 'Link copied. Anyone with it can view the route until it expires.'); }
    catch { status(`Ride link: ${url.href}`); }
  });
  $('saved-rides').addEventListener('change',()=>{
    const [id,index]=$('saved-rides').value.split(':'); if(id) openRide(id,+index).catch(e=>status(e.message,true));
  });
  $('planner').addEventListener('input',e => { if(['mode','place','saved-region'].includes(e.target.id))return; updateLabels();invalidate(); if(['lat','lon'].includes(e.target.id)){$('place').value='custom';updateStart();} });
  $('place').addEventListener('change',()=>{if($('place').value!=='custom'){[$('lat').value,$('lon').value]=$('place').value.split(',');updateStart();map.setView(marker.getLatLng(),11);}invalidate();selectCachedRegionForStart();});
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
    setMode();
    const params=new URLSearchParams(location.search);
    if(params.get('ride')) await openRide(params.get('ride'),Number(params.get('route'))||0);
    else status('Choose your start, distance, and road preferences. The dashed circle shows approximate loaded coverage.');
  } catch(error) { status(error.message,true); }
}
init();
