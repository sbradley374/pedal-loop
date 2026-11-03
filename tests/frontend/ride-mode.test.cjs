const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {Tracker}=require('../../web/ride-tracker.js');
function setup(){
 const elements=new Map(),events={},cleared=[];let success,error;
 const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',hidden:true,checked:false,addEventListener(name,fn){this[name]=fn;},scrollIntoView(){}});return elements.get(id);};
 const document={hidden:false,getElementById:element,addEventListener(name,fn){events[name]=fn;}};
 const window={isSecureContext:true,addEventListener(name,fn){events[name]=fn;}};
 const context=vm.createContext({window,document,PedalTracker:{Tracker},navigator:{geolocation:{watchPosition(s,e){success=s;error=e;return 0;},clearWatch(id){cleared.push(id);}}},performance:{now:()=>100},Date,setInterval:()=>1,clearInterval(){},L:{circleMarker(){return {addTo(){return this;},setLatLng(){}}}}});
 vm.runInContext(fs.readFileSync('web/ride-mode.js','utf8'),context);
 const mode=window.createRideMode({removeLayer(){},panTo(){}});
 const route={coordinates:[[40,-105],[40.001,-105],[40,-105]],navigation_cues:[]};
 return {mode,route,element,events,document,cleared,success:()=>success,error:()=>error};
}
test('hiding the app pauses tracking and resume starts a new watcher',()=>{
 const s=setup();s.mode.start(s.route,false);assert.equal(s.mode.active,true);
 s.document.hidden=true;s.events.visibilitychange();
 assert.deepEqual(s.cleared,[0]);assert.equal(s.element('ride-pause').textContent,'Resume');
 s.document.hidden=false;s.element('ride-pause').click();
 assert.equal(s.element('ride-pause').textContent,'Pause');
});
test('stop removes watcher and ignores queued position callbacks',()=>{
 const s=setup();s.mode.start(s.route,false);const callback=s.success();s.mode.stop();
 callback({timestamp:Date.now(),coords:{latitude:40,longitude:-105,accuracy:5,speed:0}});
 assert.equal(s.mode.active,false);assert.equal(s.element('ride-panel').hidden,true);assert.deepEqual(s.cleared,[0]);
});
test('permission failure pauses and gives a recoverable instruction',()=>{
 const s=setup();s.mode.start(s.route,false);s.error()({code:1});
 assert.match(s.element('ride-message').textContent,/permission denied/);
 assert.equal(s.element('ride-pause').textContent,'Resume');assert.deepEqual(s.cleared,[0]);
});
