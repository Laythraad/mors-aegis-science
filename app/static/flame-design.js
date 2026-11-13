function bindFlameDesign() {
  const lab=document.querySelector('#bass-lab');
  if(!lab) return;
  const ar=window.MorsI18n?.language==='ar';
  const t=(en,arabic)=>ar?arabic:en;
  const host=document.createElement('section');
  host.className='flame-design bass-overview';
  host.innerHTML=`<header><div><h3>ACME · Flame Design</h3><p>${t('NASA PSI-10 · source experiment tables','جداول التجارب الأصلية من NASA PSI-10')}</p></div><label>${t('Flame configuration','نوع اللهب')} <select><option value="normal">${t('Normal flame','لهب اعتيادي')}</option><option value="inverse">${t('Inverse flame','لهب معكوس')}</option></select></label></header><p class="flame-status" role="status" aria-live="polite"></p><div class="flame-content"></div><section class="flame-records"><h4>${t('Search all source records','البحث في جميع سجلات المصدر')}</h4><form class="flame-search input-row"><label>${t('Test, fuel or recorded value','التجربة أو الوقود أو القيمة المسجلة')} <input type="search" maxlength="100"></label><button class="button secondary" type="submit">${t('Search','بحث')}</button></form><p class="flame-records-status small" role="status" aria-live="polite"></p><div class="flame-records-table"></div><div class="input-row"><button class="button secondary flame-previous" type="button" disabled>${t('Previous','السابق')}</button><button class="button secondary flame-next" type="button" disabled>${t('Next','التالي')}</button></div><details><summary>${t('Selected source row','صف المصدر المحدد')}</summary><pre class="flame-row-details code-block"></pre></details><button class="button secondary flame-ask" type="button" disabled>${t('Ask about selected record','اسأل عن السجل المحدد')}</button></section>`;
  lab.after(host);
  const select=host.querySelector('select'),status=host.querySelector('.flame-status'),content=host.querySelector('.flame-content');
  let serial=0;
  const form=host.querySelector('.flame-search'), rowStatus=host.querySelector('.flame-records-status');
  const table=host.querySelector('.flame-records-table'), previous=host.querySelector('.flame-previous'), next=host.querySelector('.flame-next');
  let rowSerial=0, offset=0, query='', selectedRow=null;
  const ask=host.querySelector('.flame-ask');
  const choose=index=>{selectedRow=index;ask.disabled=false};
  ask.addEventListener('click',()=>{if(selectedRow===null)return;try{sessionStorage.setItem('mors-flame-selection',JSON.stringify({configuration:select.value,row_index:selectedRow}));sessionStorage.removeItem('mors-bass-selection');sessionStorage.removeItem('mors-cool-selection')}catch{}location.hash='#intelligence'});
  async function loadRows() {
    const id=++rowSerial;
    previous.disabled=next.disabled=true;
    rowStatus.textContent=t('Loading source records…','جارٍ تحميل سجلات المصدر…');
    try {
      const params=new URLSearchParams({configuration:select.value,q:query,offset:String(offset),limit:'25'});
      const data=await request('/combustion/flame-design/records?'+params);
      if(!host.isConnected||id!==rowSerial)return;
      table.innerHTML=data.items.length?`<div class="table-scroll"><table class="experiment-table"><thead><tr><th scope="col">${t('Test','الاختبار')}</th><th scope="col">${t('Day','اليوم')}</th><th scope="col">mtot (mg/s)</th><th scope="col">pmean (atm)</th><th scope="col">${t('Source row','صف المصدر')}</th></tr></thead><tbody>${data.items.map(item=>`<tr><td><bdi>${esc(item.source_row.Test)}</bdi></td><td>${esc(item.source_row.Day)}</td><td><bdi>${esc(item.source_row['mtot (mg/s)']||'—')}</bdi></td><td><bdi>${esc(item.source_row['pmean (atm)']||'—')}</bdi></td><td><button type="button" class="button secondary flame-row" data-index="${item.row_index}">${t('Inspect','فحص')}</button></td></tr>`).join('')}</tbody></table></div>`:`<p class="empty">${t('No matching records.','لا توجد سجلات مطابقة.')}</p>`;
      table.querySelectorAll('.flame-row').forEach(button=>button.addEventListener('click',()=>{
        const item=data.items.find(row=>row.row_index===Number(button.dataset.index));
        if(!item)return;
        choose(item.row_index);
        host.querySelector('.flame-row-details').textContent=JSON.stringify(item.source_row,null,2);
        const details=host.querySelector('.flame-row-details').parentElement;
        details.open=true;details.scrollIntoView({behavior:'smooth',block:'nearest'});
      }));
      previous.disabled=offset===0;next.disabled=offset+data.items.length>=data.total;
      rowStatus.textContent=t(`Showing ${data.items.length} of ${data.total} matching rows; missing values are retained.`,`عرض ${data.items.length} من أصل ${data.total} سجلاً مطابقاً، مع إبقاء القيم المفقودة.`);
    } catch { if(host.isConnected&&id===rowSerial)rowStatus.textContent=t('Could not load records. Search again to retry.','تعذر تحميل السجلات. أعد البحث للمحاولة مجدداً.'); }
  }
  const clearSelection=()=>{selectedRow=null;ask.disabled=true;host.querySelector('.flame-row-details').textContent=''};
  form.addEventListener('submit',event=>{event.preventDefault();clearSelection();query=form.querySelector('input').value.trim();offset=0;loadRows()});
  previous.addEventListener('click',()=>{clearSelection();offset=Math.max(0,offset-25);loadRows()});
  next.addEventListener('click',()=>{clearSelection();offset+=25;loadRows()});
  async function load(){
    const requestId=++serial;
    status.textContent=t('Loading and verifying the NASA table…','جارٍ تحميل جدول ناسا والتحقق منه…');
    content.replaceChildren();
    try {
      const d=await request('/combustion/flame-design?configuration='+encodeURIComponent(select.value));
      if(!host.isConnected||requestId!==serial)return;
      if(!d.pairs.length){status.textContent=t('No numeric pairs in this source table.','لا توجد أزواج رقمية في جدول المصدر.');return}
      const width=620,height=300,left=75,right=25,top=20,bottom=55;
      const flows=d.pairs.map(p=>p.flow_mg_s),pressures=d.pairs.map(p=>p.pressure_atm);
      const xMin=Math.min(0,...flows),xMax=Math.max(1,...flows),yMin=Math.min(...pressures),yMax=Math.max(...pressures),yPad=Math.max((yMax-yMin)*.08,.001);
      const x=v=>left+(v-xMin)/(xMax-xMin)*(width-left-right);
      const y=v=>height-bottom-(v-(yMin-yPad))/(yMax-yMin+2*yPad)*(height-top-bottom);
      const ticks=Array.from({length:5},(_,i)=>yMin-yPad+(yMax-yMin+2*yPad)*i/4);
      content.innerHTML=`<div class="bass-overview-grid"><div class="bass-figure"><h4>${t('Recorded pressure and total mass flow','الضغط والتدفق الكتلي المسجّلان')}</h4><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${t('Select a test point','اختر نقطة اختبار')}" direction="ltr">
      ${ticks.map(v=>`<line class="bass-grid" x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left-8}" y="${y(v)+4}" text-anchor="end">${Number(v.toPrecision(4))}</text>`).join('')}
      ${Array.from({length:5},(_,i)=>{const v=xMin+(xMax-xMin)*i/4;return `<text x="${x(v)}" y="${height-bottom+18}" text-anchor="middle">${Number(v.toPrecision(3))}</text>`}).join('')}
      ${d.pairs.map(p=>`<circle class="flame-dot bass-dot" role="button" tabindex="0" data-row="${p.row_index}" cx="${x(p.flow_mg_s)}" cy="${y(p.pressure_atm)}" r="5" aria-label="${esc(p.test)}: ${p.flow_mg_s} mg/s, ${p.pressure_atm} atm"><title>${esc(p.test)} · ${p.flow_mg_s} mg/s · ${p.pressure_atm} atm</title></circle>`).join('')}
      <text x="${width/2}" y="${height-6}" text-anchor="middle">mtot (mg/s)</text></svg><p class="small">${t('Vertical axis: pmean (atm). Horizontal axis starts at zero.','المحور العمودي: pmean بوحدة atm. يبدأ المحور الأفقي من الصفر.')}</p><output class="flame-detail bass-point-detail" aria-live="polite">${t('Select a point to inspect the original test row.','اختر نقطة لفحص صف التجربة الأصلي.')}</output></div>
      <div class="bass-figure"><h4>${t('Source and coverage','المصدر والتغطية')}</h4><p>${t('Paired numeric records','الأزواج الرقمية المكتملة')} <bdi dir="ltr">${d.paired_count} / ${d.records}</bdi></p><p class="small">${t('Normal and inverse configurations are shown separately. The vertical axis is expanded to show the recorded pressure range.','يُعرض اللهب الاعتيادي والمعكوس كلٌ على حدة. مقياس الضغط موسّع لإظهار نطاق القيم المسجلة.')}</p><a href="${esc(d.doi)}" target="_blank" rel="noopener noreferrer">NASA PSI-10 · DOI ↗</a> · <a href="/${esc(d.source_filename)}" download>CSV ↗</a><p class="small"><bdi dir="ltr">SHA-256 ${esc(d.source_sha256)}</bdi></p><details><summary>${t('Original selected row','الصف الأصلي المحدد')}</summary><pre class="flame-source code-block"></pre></details></div></div>
      <p class="bass-overview-limit">${t('Test conditions vary. The chart is descriptive and does not establish cause or a validated model. Measurement uncertainties are not included in the table.','تختلف ظروف الاختبار بين السجلات. الرسم وصفي ولا يثبت السببية أو يقدّم نموذجاً متحققاً منه. لا يتضمن الجدول عدم يقين القياسات.')}</p>`;
      const detail=content.querySelector('.flame-detail'),source=content.querySelector('.flame-source');
      content.querySelectorAll('.flame-dot').forEach(dot=>{
        const show=()=>{const row=d.pairs.find(p=>p.row_index===Number(dot.dataset.row));if(!row)return;choose(row.row_index);detail.textContent=`${row.test} · day ${row.day} · ${row.flow_mg_s} mg/s · ${row.pressure_atm} atm`;source.textContent=JSON.stringify(row.source_row,null,2)};
        dot.addEventListener('focus',show);dot.addEventListener('click',show);
        dot.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}});
      });
      status.textContent=t(`${d.paired_count} complete pairs in ${d.records} source records.`,`${d.paired_count} زوجاً مكتملاً ضمن ${d.records} سجلاً أصلياً.`);
    }catch{if(host.isConnected&&requestId===serial)status.textContent=t('Source table unavailable. Change configuration to retry.','تعذر تحميل جدول المصدر. غيّر النوع لإعادة المحاولة.')}
  }
  select.addEventListener('change',()=>{clearSelection();offset=0;query='';form.querySelector('input').value='';load();loadRows()});
  load();loadRows();
}

function bindCombustionInventory() {
  const host=document.querySelector('#combustion-inventory');
  if(!host)return;
  const ar=window.MorsI18n?.language==='ar',t=(en,arabic)=>ar?arabic:en;
  request('/combustion/sources').then(data=>{
    if(!host.isConnected)return;
    host.innerHTML=`<p class="small">${t('Verified local NASA source tables, separate from the Earth and astronomy SQLite catalog.','جداول ناسا المحلية المتحقق من بصمتها، محفوظة بشكل مستقل عن فهرس الأرض والفلك SQLite.')}</p><div class="grid three-col">${data.sources.map(item=>item.status==='verified'?`<article class="list-card"><div class="meta">${item.records} ${t('SOURCE ROWS','صفاً من المصدر')}</div><h3>${esc(item.name)}</h3>${item.blank_rows?`<p class="small">${item.blank_rows} ${t('completely blank rows omitted from the count','صفاً فارغاً بالكامل مستبعداً من العدد')}</p>`:''}<p class="small"><bdi dir="ltr">SHA-256 ${esc(item.sha256)}</bdi></p><a href="${esc(item.doi)}" target="_blank" rel="noopener noreferrer">NASA DOI ↗</a></article>`:`<article class="list-card"><h3>${esc(item.id)}</h3><p>${t('Source unavailable or integrity check failed.','المصدر غير متاح أو فشل فحص سلامته.')}</p></article>`).join('')}</div><p><a href="#combustion">${t('Open the combustion lab ↗','افتح مختبر الاحتراق ↗')}</a></p>`;
  }).catch(()=>{if(host.isConnected)host.textContent=t('Combustion source inventory unavailable.','تعذر تحميل فهرس مصادر الاحتراق.')});
}
