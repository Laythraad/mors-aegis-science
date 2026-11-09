(() => {
  const state = { canvas: null, ctx: null, image: null, texture: null, points: [], product: '', lon: 0, tilt: 0.18, zoom: 1, radius: 0, dragging: false, dragMoved: false, lastX: 0, lastY: 0, selected: null, pointers: new Map(), pinchDistance: 0, observer: null, frame: 0 };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const ar = () => document.documentElement.lang === 'ar';
  const message = (en, arabic) => ar() ? arabic : en;
  function schedule() { if (state.frame) return; state.frame = requestAnimationFrame(() => { state.frame = 0; draw(); }); }
  function zoomBy(factor) { state.zoom = clamp(state.zoom * factor, 0.8, 2.4); const label = document.querySelector('#globe-zoom-level'); if (label) label.textContent = `${Math.round(state.zoom * 100)}%`; schedule(); }
  function init() {
    if (state.observer) state.observer.disconnect();
    if (state.frame) cancelAnimationFrame(state.frame);
    state.frame = 0; state.pointers.clear(); state.selected = null; state.zoom = 1; state.points = []; state.texture = null; state.lon = 0; state.tilt = 0.18;
    state.canvas = document.querySelector('#fire-globe');
    if (!state.canvas) return;
    const canvas = state.canvas;
    state.ctx = state.canvas.getContext('2d', { alpha: false });
    if (!state.ctx) { document.querySelector('#globe-status').textContent = 'This browser cannot create a 2D canvas for the Earth view.'; return; }
    state.image = new Image();
    state.image.onload = () => {
      if (state.canvas !== canvas || !canvas.isConnected) return;
      const source = document.createElement('canvas'); source.width = state.image.naturalWidth; source.height = state.image.naturalHeight;
      source.getContext('2d', { willReadFrequently: true }).drawImage(state.image, 0, 0);
      state.texture = source.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, source.width, source.height);
      draw(); if (state.points.length) updateStatus();
    };
    state.image.onerror = () => { const status = document.querySelector('#globe-status'); if (state.canvas === canvas && canvas.isConnected && status) status.textContent = 'NASA Earth texture did not load. Check that the local app is running.'; };
    state.image.src = '/earth-blue-marble.jpg';
    state.canvas.addEventListener('pointerdown', e => { state.pointers.set(e.pointerId, [e.clientX,e.clientY]); state.dragging = true; if (state.pointers.size === 1) state.dragMoved = false; else state.dragMoved = true; state.lastX = e.clientX; state.lastY = e.clientY; state.canvas.setPointerCapture(e.pointerId); });
    state.canvas.addEventListener('pointermove', e => { if (!state.pointers.has(e.pointerId)) return; state.pointers.set(e.pointerId,[e.clientX,e.clientY]); if (state.pointers.size >= 2) { const pts=[...state.pointers.values()], distance=Math.hypot(pts[0][0]-pts[1][0],pts[0][1]-pts[1][1]); if(state.pinchDistance>0) zoomBy(distance/state.pinchDistance); state.pinchDistance=distance; state.dragMoved=true; return; } const r=state.canvas.getBoundingClientRect(); if(Math.abs(e.clientX-state.lastX)+Math.abs(e.clientY-state.lastY)>2)state.dragMoved=true;state.lon+=(e.clientX-state.lastX)/r.width*Math.PI*2;state.tilt=clamp(state.tilt+(e.clientY-state.lastY)/r.height*Math.PI,-1.25,1.25);state.lastX=e.clientX;state.lastY=e.clientY;schedule(); });
    const endPointer = e => { const wasClick=state.pointers.size===1&&!state.dragMoved;state.pointers.delete(e.pointerId);state.pinchDistance=0;state.dragging=state.pointers.size>0;if(state.dragging){const p=[...state.pointers.values()][0];state.lastX=p[0];state.lastY=p[1];state.dragMoved=true;}try{state.canvas.releasePointerCapture(e.pointerId)}catch{}if(wasClick&&e.type==='pointerup')inspectPoint(e); };
    state.canvas.addEventListener('pointerup',endPointer); state.canvas.addEventListener('pointercancel',endPointer);
    state.canvas.addEventListener('wheel',e=>{e.preventDefault();zoomBy(Math.exp(-clamp(e.deltaY,-100,100)*.002));},{passive:false});
    state.canvas.addEventListener('keydown',e=>{if(e.key==='+'||e.key==='=')zoomBy(1.2);else if(e.key==='-')zoomBy(1/1.2);else if(e.key==='ArrowLeft')state.lon-=.15;else if(e.key==='ArrowRight')state.lon+=.15;else if(e.key==='ArrowUp')state.tilt=clamp(state.tilt+.15,-1.25,1.25);else if(e.key==='ArrowDown')state.tilt=clamp(state.tilt-.15,-1.25,1.25);else return;e.preventDefault();schedule()});
    document.querySelector('#globe-zoom-in')?.addEventListener('click',()=>zoomBy(1.25));
    document.querySelector('#globe-zoom-out')?.addEventListener('click',()=>zoomBy(1/1.25));
    document.querySelector('#globe-reset')?.addEventListener('click',()=>{state.lon=0;state.tilt=.18;state.zoom=1;state.selected=null;document.querySelector('#globe-zoom-level').textContent='100%';document.querySelector('#globe-selection').textContent=message('No location selected.','لم يُحدد موقع.');document.querySelector('#globe-use-selection').disabled=true;schedule()});
    document.querySelector('#globe-use-selection')?.addEventListener('click',()=>{if(!state.selected)return;const {lat,lon}=state.selected;for(const [name,value] of Object.entries({west:Math.max(-180,lon-.5),east:Math.min(180,lon+.5),south:Math.max(-90,lat-.5),north:Math.min(90,lat+.5)}))document.querySelector('#firms-'+name).value=value.toFixed(4);const region=document.querySelector('#firms-region');region.value='area';region.dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#firms-results').textContent=message('Selected coordinates set a 1° × 1° region (clipped at the poles and dateline). Submit the FIRMS form to request observations.','تم ضبط منطقة حول الموقع بعرض درجة واحدة تقريباً. اضغط زر تنزيل بيانات FIRMS لطلب الرصدات.');document.querySelector('#firms-form').scrollIntoView({behavior:'smooth',block:'center'})});
    state.observer=new ResizeObserver(schedule);state.observer.observe(state.canvas);
  }
  function draw() {
    if (!state.ctx || !state.texture || !state.canvas?.isConnected) return;
    const box = state.canvas.getBoundingClientRect(), dpr = Math.max(.5, Math.min(window.devicePixelRatio || 1, 1.5, 1000 / Math.max(box.width, 1), 700 / Math.max(box.height, 1)));
    const w = Math.max(1, Math.round(box.width * dpr)), h = Math.max(1, Math.round(box.height * dpr));
    if (state.canvas.width !== w || state.canvas.height !== h) { state.canvas.width = w; state.canvas.height = h; }
    const ctx = state.ctx, image = state.texture, r = Math.min(w, h) * .44 * state.zoom, cx = w / 2, cy = h / 2;
    state.radius = r / dpr; ctx.fillStyle = '#06121d'; ctx.fillRect(0, 0, w, h);
    const pixels = ctx.createImageData(w, h), out = pixels.data, tw = image.width, th = image.height;
    // putImageData replaces destination pixels; initialize every pixel as opaque to avoid transparent/undefined trails on browsers with alpha:false canvases.
    for (let i=0;i<out.length;i+=4) { out[i]=6; out[i+1]=18; out[i+2]=29; out[i+3]=255; }
    const minX = Math.max(0, Math.floor(cx-r)), maxX = Math.min(w-1, Math.ceil(cx+r));
    const minY = Math.max(0, Math.floor(cy-r)), maxY = Math.min(h-1, Math.ceil(cy+r));
    const ct = Math.cos(state.tilt), st = Math.sin(state.tilt), cl = Math.cos(state.lon), sl = Math.sin(state.lon);
    for (let py = minY; py <= maxY; py++) for (let px = minX; px <= maxX; px++) {
      const nx=(px-cx)/r, ny=(cy-py)/r, rr=nx*nx+ny*ny; if (rr>1) continue;
      const nz=Math.sqrt(1-rr), y=ny*ct-nz*st, z=ny*st+nz*ct;
      let lon=Math.atan2(nx,z)+state.lon; lon=((lon+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;
      const lat=Math.asin(clamp(y,-1,1)), tx=Math.floor((lon+Math.PI)/(2*Math.PI)*(tw-1)), ty=clamp(Math.floor((Math.PI/2-lat)/Math.PI*(th-1)),0,th-1), si=(ty*tw+tx)*4, di=(py*w+px)*4;
      const light=clamp(.57+.43*(nx*-.36+ny*.36+nz*.86),.30,1.05);
      out[di]=image.data[si]*light;out[di+1]=image.data[si+1]*light;out[di+2]=image.data[si+2]*light;out[di+3]=255;
    }
    ctx.putImageData(pixels,0,0);
    const grad=ctx.createRadialGradient(cx-r*.48,cy-r*.55,r*.10,cx,cy,r*1.05);grad.addColorStop(.68,'rgba(45,164,229,0)');grad.addColorStop(.94,'rgba(45,164,229,.08)');grad.addColorStop(1,'rgba(80,190,255,.48)');
    ctx.fillStyle=grad;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill();ctx.strokeStyle='rgba(121,204,255,.62)';ctx.lineWidth=Math.max(1,dpr);ctx.stroke();
    state.points.forEach(p=>{p._visible=false;const lat=Number(p.latitude)*Math.PI/180, dl=Number(p.longitude)*Math.PI/180-state.lon, x=Math.cos(lat)*Math.sin(dl), yy=Math.sin(lat)*ct+Math.cos(lat)*Math.cos(dl)*st, z=-Math.sin(lat)*st+Math.cos(lat)*Math.cos(dl)*ct;if(z<=0)return;const sx=cx+x*r,sy=cy-yy*r;ctx.beginPath();ctx.fillStyle='#ff542f';ctx.arc(sx,sy,Math.max(3,dpr*3.1),0,Math.PI*2);ctx.fill();ctx.strokeStyle='#ffd38a';ctx.lineWidth=dpr;ctx.stroke();p._screen=[sx/dpr,sy/dpr];p._visible=true;});
    if(state.selected){const lat=state.selected.lat*Math.PI/180,dl=state.selected.lon*Math.PI/180-state.lon,x=Math.cos(lat)*Math.sin(dl),y=Math.sin(lat)*ct+Math.cos(lat)*Math.cos(dl)*st,z=-Math.sin(lat)*st+Math.cos(lat)*Math.cos(dl)*ct;if(z>0){ctx.beginPath();ctx.arc(cx+x*r,cy-y*r,8*dpr,0,Math.PI*2);ctx.strokeStyle='#ffffff';ctx.lineWidth=2*dpr;ctx.stroke();}}
  }
  function inspectPoint(e) { const rect=state.canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;let best=null,dist=18;for(const p of state.points){if(!p._visible)continue;const d=Math.hypot(x-p._screen[0],y-p._screen[1]);if(d<dist){best=p;dist=d;}}let lat,lon;if(best){lat=Number(best.latitude);lon=Number(best.longitude);const observed=best.observed_at_utc||`${best.acq_date||''} ${best.acq_time||''} UTC`;const product=best.product||best.source_product||state.product;document.querySelector('#globe-status').textContent=`NASA FIRMS · ${observed} · ${lat.toFixed(4)}°, ${lon.toFixed(4)}° · ${best.satellite||'—'} / ${best.instrument||'—'} · ${message('confidence','الثقة')} ${best.confidence??'—'} · FRP ${best.frp??best.frp_mw??'—'} MW · ${product}${best.raw_sha256?' · SHA-256 '+best.raw_sha256:''}. ${message('Thermal anomaly point; not a fire perimeter.','نقطة شذوذ حراري؛ لا تمثل حدود الحريق.')}`;}else{const nx=(x-rect.width/2)/state.radius,ny=(rect.height/2-y)/state.radius,rr=nx*nx+ny*ny;if(rr>1)return;const nz=Math.sqrt(1-rr),ct=Math.cos(state.tilt),st=Math.sin(state.tilt);lat=Math.asin(clamp(ny*ct-nz*st,-1,1))*180/Math.PI;lon=(Math.atan2(nx,ny*st+nz*ct)+state.lon)*180/Math.PI;lon=((lon+180)%360+360)%360-180;}state.selected={lat,lon};document.querySelector('#globe-selection').textContent=message(`Selected location: ${lat.toFixed(4)}°, ${lon.toFixed(4)}° (latitude, longitude).`,`الموقع المحدد: ${lat.toFixed(4)}°، ${lon.toFixed(4)}° (خط العرض، خط الطول).`);document.querySelector('#globe-use-selection').disabled=false;schedule(); }
  function updateStatus(){const el=document.querySelector('#globe-status');if(!el)return;const n=state.points.length,total=state.total??n;const dates=state.points.map(p=>p.observed_at_utc||p.acq_date||'').filter(Boolean).sort();const range=dates.length?`${dates[0]} → ${dates[dates.length-1]} UTC`:'—';el.textContent=n?message(`Showing ${n} of ${total} ${state.archived?'archived':'retrieved'} FIRMS detections · ${range}. The globe faces the first detection. Select a red point for its source details. Points are thermal anomalies, not fire boundaries.`,`تُعرض ${n} من أصل ${total} من رصدات FIRMS ${state.archived?'المؤرشفة':'المسترجعة'} · ${range}. وُجّهت الكرة نحو أول رصد. اختر نقطة حمراء لعرض بيانات مصدرها. النقاط شذوذات حرارية وليست حدود الحريق.`):message('No observations in this selection. Choose another region, date or product.','لا توجد رصدات في هذا الاختيار. اختر منطقة أو تاريخاً أو منتجاً آخر.');}
  function setData(rows, product, options={}) { if (!state.canvas?.isConnected) return; state.points=rows.filter(p=>p.latitude!=null&&p.longitude!=null&&Number.isFinite(Number(p.latitude))&&Number.isFinite(Number(p.longitude))&&Math.abs(Number(p.latitude))<=90&&Math.abs(Number(p.longitude))<=180).slice(0,10000);state.product=product;state.total=Number.isFinite(Number(options.total))?Number(options.total):state.points.length;state.archived=!!options.archived;state.selected=null;const selection=document.querySelector('#globe-selection');if(selection)selection.textContent=message('No location selected.','لم يُحدد موقع.');const use=document.querySelector('#globe-use-selection');if(use)use.disabled=true;if(state.points.length){state.lon=Number(state.points[0].longitude)*Math.PI/180;state.tilt=clamp(-Number(state.points[0].latitude)*Math.PI/180,-1.25,1.25);state.zoom=1.2;const label=document.querySelector('#globe-zoom-level');if(label)label.textContent='120%';}draw();updateStatus(); }
  window.MorsGlobe={init,setData};
})();
