'use strict';
window.createRideMode=function(map) {
  const el=id=>document.getElementById(id), miles=m=>(m/1609.344).toFixed(2);
  let tracker=null, watch=null, clock=null, wake=null, dot=null, active=false, paused=false, epoch=0, lastFix=0, elapsed=0, since=0;
  function message(text) { el('ride-message').textContent=text; }
  function clearReadings() { for(const id of ['ride-speed','ride-remaining','ride-next']) el(id).textContent='—'; }
  async function releaseWake() { const lock=wake; wake=null; if(lock) try { await lock.release(); } catch {} }
  function suspend() {
    epoch++;
    if(watch!==null) navigator.geolocation.clearWatch(watch);
    watch=null; clearInterval(clock); clock=null;
    if(since) elapsed+=performance.now()-since;
    since=0; releaseWake(); tracker?.interrupt(); clearReadings();
    if(dot){map.removeLayer(dot);dot=null;}
  }
  async function keepAwake(token) {
    if(!navigator.wakeLock) return;
    try {
      const lock=await navigator.wakeLock.request('screen');
      if(token!==epoch || !active || paused) { await lock.release(); return; }
      wake=lock;
      lock.addEventListener('release',()=>{if(wake===lock)wake=null;});
    } catch { /* The visible keep-screen-open guidance remains applicable. */ }
  }
  function resume() {
    if(!active) return;
    if(!navigator.geolocation || !window.isSecureContext) {
      paused=true;el('ride-pause').textContent='Resume';message('Live GPS needs HTTPS and a browser with location support.'); return;
    }
    paused=false; el('ride-pause').textContent='Pause'; since=performance.now(); lastFix=0;
    const token=++epoch;
    message('Waiting for GPS. Begin at the marked start.');
    keepAwake(token);
    watch=navigator.geolocation.watchPosition(position=>{
      if(token!==epoch || paused || !active) return;
      const c=position.coords;
      const result=tracker.update({lat:c.latitude,lon:c.longitude,accuracy:c.accuracy,speed:c.speed,timestamp:position.timestamp});
      if(result.state==='ignored') return;
      lastFix=Date.now(); clearReadings();
      if(['weak','start'].includes(result.state)) { message(result.message); return; }
      const point=[c.latitude,c.longitude];
      if(!dot) dot=L.circleMarker(point,{radius:8,color:'#fff',weight:3,fillColor:'#247bc1',fillOpacity:1}).addTo(map);
      else dot.setLatLng(point);
      if(el('ride-follow').checked) map.panTo(point,{animate:false});
      el('ride-speed').textContent=result.speed===null?'—':(result.speed*2.236936).toFixed(1)+' mph';
      el('ride-distance').textContent=miles(result.ridden)+' mi';
      if(result.state==='off') { message(result.message); return; }
      el('ride-remaining').textContent=miles(result.remaining)+' mi';
      el('ride-next').textContent=result.next?`${result.next.in_m<160?Math.round(result.next.in_m*3.28084)+' ft':miles(result.next.in_m)+' mi'} · ${result.next.instruction}`:(tracker.cues.length?'No further mapped cues':'This saved route has no cues. Generate a new route for cue preview.');
      message(result.state==='arrived'?'Near the loop finish. End the ride when safely stopped.':`On route · GPS accuracy ±${Math.round(result.accuracy)} m`);
    },error=>{
      if(token!==epoch || !active) return;
      pause(); message(error.code===1?'Location permission denied. Enable location to resume.':'GPS unavailable. Resume when you have a clear signal.');
    },{enableHighAccuracy:true,maximumAge:0,timeout:15000});
    clock=setInterval(()=>{
      const seconds=Math.floor((elapsed+performance.now()-since)/1000);
      el('ride-time').textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
      if(!lastFix || Date.now()-lastFix>15000) {
        clearReadings(); tracker.interrupt(); message('Waiting for a fresh GPS fix. Progress is paused.');
      }
    },1000);
  }
  function pause() { if(!active || paused)return; paused=true;suspend();el('ride-pause').textContent='Resume';message('Paused. Resume while the app is visible.'); }
  function stop() {
    active=false; paused=false;suspend();tracker=null;elapsed=0;
    if(dot){map.removeLayer(dot);dot=null;}
    el('ride-panel').hidden=true; el('start-ride').disabled=false;
  }
  function start(route,synthetic) {
    if(synthetic) { message('Synthetic routes cannot be ridden.');return; }
    stop(); tracker=new PedalTracker.Tracker(route);active=true;
    el('ride-panel').hidden=false;el('ride-distance').textContent='0.00 mi';el('ride-time').textContent='0:00';el('start-ride').disabled=true;
    el('ride-panel').scrollIntoView({block:'center',behavior:'smooth'});resume();
  }
  el('ride-pause').addEventListener('click',()=>paused?resume():pause());
  el('ride-stop').addEventListener('click',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  window.addEventListener('pagehide',stop);
  return {start,stop,get active(){return active;}};
};
