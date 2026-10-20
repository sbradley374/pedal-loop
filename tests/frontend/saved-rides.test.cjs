const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const elements = new Map();
  const pending = [];
  const context = vm.createContext({
    document: {getElementById(id) {
      if (!elements.has(id)) elements.set(id, {value:'', disabled:false});
      return elements.get(id);
    }},
    fetch(url) { return new Promise((resolve, reject) => pending.push({url, resolve, reject})); },
    rendered: [], messages: [],
  });
  const source = fs.readFileSync('web/app.js','utf8').replace(/init\(\);\s*$/, '');
  vm.runInContext(source + `
    status=(message)=>messages.push(message);
    updateLabels=()=>{}; updateStart=()=>{}; setMode=()=>{};
    renderResult=(result)=>rendered.push(result.id);
  `, context);
  return {context, pending, elements, run:code=>vm.runInContext(code,context)};
}
const ride = id => ({id, preferences:{miles:10}, source:{source:'osm'}});
const respond = (request, body) => request.resolve({ok:true,json:async()=>body});

test('only the latest saved ride is rendered when responses arrive out of order', async()=>{
  const s=setup();
  const first=s.run("openRide('first')"), second=s.run("openRide('second')");
  respond(s.pending[1],ride('second')); await second;
  respond(s.pending[0],ride('first')); await first;
  assert.deepEqual([...s.context.rendered],['second']);
});

test('settings changed during saved-ride retrieval are preserved', async()=>{
  const s=setup(), loading=s.run("openRide('first')");
  s.run("revision++; $('miles').value=25;");
  respond(s.pending[0],ride('first')); await loading;
  assert.equal(s.elements.get('miles').value,25);
  assert.equal(s.context.rendered.length,0);
});

test('stale region information cannot replace the active dataset', async()=>{
  const s=setup(), loading=s.run("openRide('first')");
  respond(s.pending[0],{...ride('first'),region_id:'old-region'});
  // Allow result parsing to start the separate dataset request.
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(s.pending[1].url,/old-region/);
  s.run("revision++; activeRegion='new-region';");
  respond(s.pending[1],{active_region:'old-region'}); await loading;
  assert.equal(s.run('activeRegion'),'new-region');
  assert.equal(s.context.rendered.length,0);
});

test('saved rides cannot start while a search submission is pending',async()=>{
  const s=setup();
  s.run("$('generate').disabled=true;");
  await s.run("openRide('first')");
  assert.equal(s.pending.length,0);
});

test('an obsolete request failure does not replace the current status', async()=>{
  const s=setup(), loading=s.run("openRide('first')");
  s.run("revision++; status('New search');");
  s.pending[0].reject(new Error('Old error')); await loading;
  assert.equal(s.context.messages.at(-1),'New search');
});

test('a start preset switches to cached coverage without moving the selected start', async()=>{
  const s=setup();
  s.run(`
    info={regions:[
      {id:'providence',center:[41.8268,-71.4025],radius_m:20000},
      {id:'burlington',center:[44.4759,-73.2121],radius_m:9000}
    ]};
    activeRegion='providence'; $('mode').value='osm';
    $('lat').value=44.48; $('lon').value=-73.21;
    loadRegion=async(id,options)=>rendered.push({id,...options});
  `);
  await s.run('selectCachedRegionForStart()');
  assert.equal(s.context.rendered[0].id,'burlington');
  assert.equal(s.context.rendered[0].preserveStart,true);
  assert.equal(s.elements.get('lat').value,44.48);
});

test('coverage selection retains the current region and never invents coverage',async()=>{
  const s=setup();
  s.run(`
    info={regions:[{id:'current',center:[41.8,-71.4],radius_m:20000}]};
    activeRegion='current'; $('mode').value='osm';
    $('lat').value=41.8; $('lon').value=-71.4;
    loadRegion=async(id)=>rendered.push(id);
  `);
  await s.run('selectCachedRegionForStart()');
  assert.equal(s.context.rendered.length,0);
  s.run("$('lat').value=30;");
  await s.run('selectCachedRegionForStart()');
  assert.equal(s.context.rendered.length,0);
  assert.match(s.context.messages.at(-1),/outside cached coverage/);
});

test('synthetic mode does not select a real dataset', async()=>{
  const s=setup();
  s.run("$('mode').value='synthetic';");
  await s.run('selectCachedRegionForStart()');
  assert.equal(s.pending.length,0);
  assert.equal(s.context.messages.length,0);
});
