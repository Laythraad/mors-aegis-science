const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/app.js', 'utf8');
const timelineCode = source.slice(source.indexOf('function lineChart()'), source.indexOf('function committeeView()'));
const timelineContext = {state:{experiments:[{year:2000},{year:2001},{year:2010}]}, Map, Number, Math};
vm.runInNewContext(timelineCode,timelineContext);
const coords=[...timelineContext.lineChart().matchAll(/<circle class="chart-point"[^>]* cx="([\d.]+)"/g)].map(m=>Number(m[1]));
assert.equal(coords.length,3);
assert.ok(Math.abs((coords[1]-coords[0])*10-(coords[2]-coords[0]))<1e-8,'year axis reflects actual elapsed years');
const chart = source.slice(source.indexOf('function renderDailyChart(rows)'), source.indexOf('function renderFRPScatter(items)'));
const host = { innerHTML: '' };
const context = { $: () => host, esc: String, attachChartInspector: () => {}, Date, Math, Number, Set };
vm.runInNewContext(chart, context);
context.renderDailyChart([{day_utc:'2026-01-01',product:'A',n:1},{day_utc:'2026-01-01',product:'B',n:2},{day_utc:'2026-01-11',product:'A',n:3}]);
const x = [...host.innerHTML.matchAll(/<rect class="chart-point"[^>]* x="([\d.]+)"/g)].map(m=>Number(m[1]));
assert.equal(x.length, 3);
assert.ok(x[1] > x[0], 'same-day products have separate bars');
assert.ok(x[2] - x[0] > 10 * (x[1] - x[0]), 'date gaps occupy proportional horizontal space');
const scatterCode=source.slice(source.indexOf('function renderFRPScatter(items)'),source.indexOf('function bindSpaceTimeView()'));
vm.runInNewContext(scatterCode,context);
context.renderFRPScatter([{bright_ti4_k:300,frp_mw:5,observed_at_utc:'2026-01-01',product:'VIIRS'},{bright_ti4_k:400,frp_mw:25,observed_at_utc:'2026-01-02',product:'VIIRS'}]);
assert.match(host.innerHTML,/>300\.0<\/text>/);
assert.match(host.innerHTML,/>400\.0<\/text>/);
assert.match(host.innerHTML,/>25\.0<\/text>/);
assert.match(source, /Only the current page of up to 200 records is plotted/);
assert.match(source, /pitchPublications\.textContent=Number\(c\.publications\)/);
console.log('Frontend chart and live-count checks passed');

const timePosition = source.slice(source.indexOf('function timeSeriesX('), source.indexOf('function bindDataView()'));
const timeContext = {Date, Number};
vm.runInNewContext(timePosition, timeContext);
const irregular = [{timestamp:'2025-01-01T00:00:00Z',elapsed_seconds:0},
                   {timestamp:'2025-01-01T00:00:01Z',elapsed_seconds:1},
                   {timestamp:'2025-01-01T00:00:10Z',elapsed_seconds:10}];
assert.equal(timeContext.timeSeriesX(irregular[1], irregular), 86);
assert.equal(timeContext.timeSeriesX(irregular[2], irregular), 680);

const compareContext = {
  window: { MorsI18n: { language: 'en' } },
  esc: value => String(value).replaceAll('<', '&lt;'),
  document: { createElement: () => ({ textContent: '' }) }
};
vm.runInNewContext(fs.readFileSync('app/static/workbench.js', 'utf8'), compareContext);
assert.equal(compareContext.safeSpreadsheetCell('=1+1'), "'=1+1");
assert.equal(compareContext.safeSpreadsheetCell('  @SUM(1)'), "'  @SUM(1)");
assert.equal(compareContext.safeSpreadsheetCell(-118.5), '-118.5');
assert.equal(compareContext.safeSpreadsheetCell('VIIRS'), 'VIIRS');
const markup = compareContext.scienceBarChart([{product:'<source', count:2}], 'product', 'count', 'detections');
assert.ok(markup.includes('&lt;source') && !markup.includes('="<source'));
const output = { replaceChildren(...pieces) { this.textContent = pieces.map(x=>x.textContent ?? x).join(''); } };
const chartHost = {
  dataset: { unit: 'detections' },
  querySelector: () => output,
  querySelectorAll: () => controls.filter(control=>control.pressed)
};
const controls = [12, 5].map((count,index)=>({
  pressed:false, dataset:{label:String.fromCharCode(65+index),count:String(count)},
  closest(selector){ return selector==='.inspect-bar'?this:chartHost; },
  setAttribute(name,value){ this.pressed=value==='true'; },
  querySelector(){return {textContent:String(count)+' detections'};}
}));
let onClick;
compareContext.bindBarComparison({addEventListener(event,callback){onClick=callback;}});
const selectBar = index => onClick({target:controls[index]});
selectBar(0); selectBar(1);
assert.equal(output.textContent,'Difference · B − A = -7 detections');
selectBar(1); selectBar(1);
assert.equal(output.textContent,'');
assert.ok(controls.every(control=>!control.pressed));
console.log('Catalog bar reference, signed difference, clear and escaping verified');

async function verifyDetachedSpaceTime(failed) {
  let settle;
  const nodes = new Map();
  const select = selector => {
    if (!nodes.has(selector)) nodes.set(selector,{
      isConnected:true, value:'', replaceChildren(){}, addEventListener(){}
    });
    return nodes.get(selector);
  };
  let plots = 0;
  const sandbox = {$:select, URLSearchParams,
    loadPreventionCards(){}, renderDailyChart(){plots++;}, renderFRPScatter(){plots++;},
    request:()=>new Promise((resolve,reject)=>{
      settle=()=>failed?reject(new Error('offline')):resolve({items:[],time_series:[]});
    })
  };
  const code = source.slice(source.indexOf('function bindSpaceTimeView()'),source.indexOf('function initializeFireGlobe()'));
  vm.runInNewContext(code,sandbox);
  sandbox.bindSpaceTimeView();
  select('#space-query').isConnected=false;
  const statusBefore = select('#space-query-status').textContent;
  settle();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(plots,0);
  assert.equal(select('#space-query-status').textContent,statusBefore);
}
Promise.all([verifyDetachedSpaceTime(false),verifyDetachedSpaceTime(true)])
  .then(()=>console.log('Late space-time success and failure ignored after navigation'))
  .catch(error=>{console.error(error);process.exitCode=1;});
