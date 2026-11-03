const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Tracker}=require('../../web/ride-tracker.js');
const route={coordinates:[[40,-105],[40.001,-105],[40.001,-104.999],[40,-104.999],[40,-105]],navigation_cues:[{distance_m:111,instruction:'Turn right onto Test Street'}]};
const now=100000;
function fix(lat=40,lon=-105,timestamp=now,more={}){return {lat,lon,timestamp,accuracy:5,speed:4,...more};}
test('closed-loop start cannot match the finish',()=>{
 const tracker=new Tracker(route),r=tracker.update(fix(),now);
 assert.equal(r.state,'on');assert.equal(r.progress,0);assert.ok(r.remaining>300);
 assert.equal(r.next.instruction,'Turn right onto Test Street');
});
test('movement updates GPS mileage and distance remaining',()=>{
 const tracker=new Tracker(route);tracker.update(fix(),now);
 const r=tracker.update(fix(40.0002,-105,now+5000),now+5000);
 assert.equal(r.state,'on');assert.ok(r.ridden>20 && r.ridden<23);assert.ok(r.progress>20);assert.equal(r.speed,4);
});
test('weak, old, and impossible fixes never advance progress',()=>{
 const tracker=new Tracker(route);tracker.update(fix(),now);
 assert.equal(tracker.update(fix(40.01,-105,now+1000),now+1000).state,'weak');
 assert.equal(tracker.progress,0);
 assert.equal(tracker.update(fix(40,-105,now,{accuracy:100}),now).state,'weak');
 assert.equal(tracker.update(fix(),now+20000).state,'weak');
 assert.equal(tracker.update(fix(40,-105,now,{lat:NaN}),now).state,'weak');
});
test('starting far along the route requires returning to start',()=>{
 const tracker=new Tracker(route);
 assert.equal(tracker.update(fix(40.001,-104.999),now).state,'start');assert.equal(tracker.ridden,0);
});
test('GPS jitter does not accumulate stationary mileage',()=>{
 const tracker=new Tracker(route);
 for(let i=0;i<10;i++)tracker.update(fix(40+(i%2)*.00001,-105,now+i*1000),now+i*1000);
 assert.equal(tracker.ridden,0);
});
test('pause or a GPS gap does not bridge missing mileage',()=>{
 const tracker=new Tracker(route);tracker.update(fix(),now);tracker.interrupt();
 let r=tracker.update(fix(40.0004,-105,now+30000),now+30000);
 assert.equal(r.ridden,0);
 r=tracker.update(fix(40.0006,-105,now+60000),now+60000);assert.equal(r.ridden,0);
});
test('off-route fixes suppress remaining distance and cues',()=>{
 const tracker=new Tracker(route);tracker.update(fix(),now);
 const r=tracker.update(fix(39.9995,-105,now+5000),now+5000);
 assert.equal(r.state,'off');assert.equal(r.next,undefined);assert.equal(r.remaining,undefined);
});
test('full loop replay reaches finish only after traversing every side',()=>{
 const tracker=new Tracker(route);let t=now,r=tracker.update(fix(),t);
 for(let i=0;i<4;i++)for(let n=1;n<=10;n++){
  const a=route.coordinates[i],b=route.coordinates[i+1];t+=3000;
  r=tracker.update(fix(a[0]+(b[0]-a[0])*n/10,a[1]+(b[1]-a[1])*n/10,t),t);
 }
 assert.equal(r.state,'arrived');assert.ok(r.ridden>350);assert.ok(r.remaining<20);
});
