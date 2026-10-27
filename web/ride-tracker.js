'use strict';
// Pure GPS/progress calculation shared by the browser and deterministic replay tests.
(function(root) {
  const rad=Math.PI/180, R=6371000;
  function distance(a,b) {
    const h=Math.sin((b[0]-a[0])*rad/2)**2+Math.cos(a[0]*rad)*Math.cos(b[0]*rad)*Math.sin((b[1]-a[1])*rad/2)**2;
    return 2*R*Math.asin(Math.sqrt(Math.min(1,h)));
  }
  class Tracker {
    constructor(route) {
      this.points=route.coordinates; this.cues=route.navigation_cues || [];
      this.cumulative=[0];
      for(let i=1;i<this.points.length;i++) this.cumulative.push(this.cumulative[i-1]+distance(this.points[i-1],this.points[i]));
      this.total=this.cumulative.at(-1); this.progress=0; this.ridden=0; this.started=false;
      this.last=null; this.anchor=null;
    }
    interrupt() { this.last=null; this.anchor=null; }
    update(fix, now=Date.now()) {
      const {lat,lon,accuracy,timestamp}=fix;
      if(![lat,lon,accuracy,timestamp].every(Number.isFinite) || Math.abs(lat)>85 || Math.abs(lon)>180 || accuracy<0 || accuracy>40 || now-timestamp>15000 || timestamp>now+1000) {
        this.interrupt(); return {state:'weak',message:'GPS is weak or stale. Progress is paused.'};
      }
      if(this.last && timestamp<=this.last.timestamp) return {state:'ignored'};
      const point=[lat,lon], dt=this.last?(timestamp-this.last.timestamp)/1000:null;
      const moved=this.last?distance(this.last.point,point):0;
      if(dt && dt<=15 && moved>35*dt+accuracy+this.last.accuracy) {
        return {state:'weak',message:'GPS jump detected. Waiting for a stable position.'};
      }
      if(!this.started && distance(point,this.points[0])>60) {
        return {state:'start',message:'Go to the marked route start before starting this loop.'};
      }
      this.started=true;
      let speed=Number.isFinite(fix.speed) && fix.speed>=0 && fix.speed<=35 ? fix.speed : null;
      if(!this.anchor || !dt || dt>15) this.anchor={point,timestamp};
      else {
        const traveled=distance(this.anchor.point,point), seconds=(timestamp-this.anchor.timestamp)/1000;
        if(seconds>15) this.anchor={point,timestamp};
        else if(traveled>=Math.max(6,accuracy*.75)) {
          this.ridden+=traveled;
          if(speed===null) speed=traveled/seconds;
          this.anchor={point,timestamp};
        }
      }
      this.last={point,timestamp,accuracy};
      // Limit forward matching so crossings/repeated sections cannot finish a loop early.
      const forward=Math.max(75,Math.min(15,dt || 0)*25), scaleX=R*rad*Math.cos(lat*rad), scaleY=R*rad;
      let best=null;
      for(let i=0;i<this.points.length-1;i++) {
        const start=this.cumulative[i], length=this.cumulative[i+1]-start;
        if(start>this.progress+forward || start+length<this.progress-30 || !length) continue;
        const a=this.points[i], b=this.points[i+1];
        const ax=(a[1]-lon)*scaleX, ay=(a[0]-lat)*scaleY;
        const dx=(b[1]-a[1])*scaleX, dy=(b[0]-a[0])*scaleY;
        const t=Math.max(0,Math.min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy)));
        const along=start+t*length;
        if(along>this.progress+forward || along<this.progress-30) continue;
        const away=Math.hypot(ax+t*dx,ay+t*dy);
        const score=away+Math.abs(along-this.progress)*.02;
        if(!best || score<best.score) best={along,away,score};
      }
      if(!best || best.away>Math.max(35,accuracy*1.5))
        return {state:'off',speed,ridden:this.ridden,message:'Off route or position uncertain. Stop safely and check the map; no automatic rerouting.'};
      this.progress=Math.max(this.progress,best.along);
      const remaining=Math.max(0,this.total-this.progress);
      const next=this.cues.find(c=>c.distance_m>0 && c.distance_m>=this.progress-5);
      return {state:remaining<20?'arrived':'on',speed,ridden:this.ridden,progress:this.progress,remaining,
              next:next?{...next,in_m:Math.max(0,next.distance_m-this.progress)}:null,accuracy};
    }
  }
  root.PedalTracker={Tracker,distance};
  if(typeof module!=='undefined') module.exports=root.PedalTracker;
})(typeof globalThis==='undefined'?this:globalThis);
