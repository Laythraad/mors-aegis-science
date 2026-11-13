const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const nodes = {}, queue = [];
const ctx = {fillRect(){},createImageData(w,h){return {data:new Uint8ClampedArray(w*h*4)}},putImageData(){},createRadialGradient(){return {addColorStop(){}}},beginPath(){},arc(){},fill(){},stroke(){},drawImage(){},getImageData(){return {width:8,height:4,data:new Uint8ClampedArray(8*4*4)}}};
function element(id) {return nodes[id] ||= {id,events:{},textContent:'',disabled:false,value:'',isConnected:true,addEventListener(name,fn){this.events[name]=fn},dispatchEvent(e){this.events[e.type]?.(e)},scrollIntoView(){},getBoundingClientRect(){return {left:0,top:0,width:200,height:200}},setPointerCapture(){},releasePointerCapture(){},getContext(){return ctx}}}
const canvas=element('#fire-globe');
const doc={documentElement:{lang:'en'},querySelector:element,createElement(){return {width:8,height:4,getContext(){return ctx}}}};
class FakeImage {constructor(){this.naturalWidth=8;this.naturalHeight=4}set src(_){this.onload()}}
class Observer {observe(){} disconnect(){}}
const win={devicePixelRatio:1};
const context={document:doc,window:win,Image:FakeImage,ResizeObserver:Observer,requestAnimationFrame(fn){queue.push(fn);return queue.length},cancelAnimationFrame(){},Event:class{constructor(type){this.type=type}},Math,Number,Map,Uint8ClampedArray};
vm.runInNewContext(fs.readFileSync('app/static/earth-globe.js','utf8'),context);
win.MorsGlobe.init();
nodes['#globe-zoom-in'].events.click();
assert.equal(nodes['#globe-zoom-level'].textContent,'125%');
while(queue.length)queue.shift()();
canvas.events.pointerdown({pointerId:1,clientX:100,clientY:100});
canvas.events.pointerup({pointerId:1,clientX:100,clientY:100,type:'pointerup'});
assert.match(nodes['#globe-selection'].textContent,/Selected location:/);
assert.equal(nodes['#globe-use-selection'].disabled,false);
nodes['#globe-use-selection'].events.click();
assert.ok(Number(nodes['#firms-west'].value)<Number(nodes['#firms-east'].value));
assert.ok(Number(nodes['#firms-south'].value)<Number(nodes['#firms-north'].value));
nodes['#globe-reset'].events.click();
assert.equal(nodes['#globe-zoom-level'].textContent,'100%');
assert.equal(nodes['#globe-use-selection'].disabled,true);
const archived=[{latitude:34,longitude:-118,observed_at_utc:'2026-11-07T09:34:00Z',product:'VIIRS_NOAA20_NRT',frp_mw:1.2,raw_sha256:'source-checksum'}];
win.MorsGlobe.setData(archived,'NASA FIRMS',{total:39915,archived:true});
assert.equal(archived[0]._visible,true,'map faces the loaded archived point');
assert.match(nodes['#globe-status'].textContent,/Showing 1 of 39915 archived/);
canvas.events.pointerdown({pointerId:2,clientX:100,clientY:100});
canvas.events.pointerup({pointerId:2,clientX:100,clientY:100,type:'pointerup'});
assert.match(nodes['#globe-status'].textContent,/VIIRS_NOAA20_NRT/);
assert.match(nodes['#globe-status'].textContent,/source-checksum/);
assert.match(nodes['#globe-status'].textContent,/1\.2 MW/);
console.log('Globe zoom, selection, archive focus and observation details verified');
