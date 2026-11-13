function bindCoolFlames() {
  const previous=document.querySelector('.flame-design');
  if(!previous)return;
  const ar=window.MorsI18n?.language==='ar',t=(en,arabic)=>ar?arabic:en;
  const host=document.createElement('section');
  host.className='cool-flames bass-overview';
  host.innerHTML=`<header><div><h3>ACME · CFI-G</h3><p>${t('Cool Flames Investigation with Gases · NASA PSI-159','تحقيق اللهب البارد بالغازات · NASA PSI-159')}</p></div><label>${t('Flame configuration','نوع اللهب')} <select class="cool-mode"><option value="normal">${t('Normal flame','لهب اعتيادي')}</option><option value="inverse">${t('Inverse flame','لهب معكوس')}</option></select></label><label>${t('Fuel from source','الوقود حسب المصدر')} <select class="cool-fuel"><option value="">${t('All fuels','كل أنواع الوقود')}</option></select></label></header><p class="cool-status" role="status" aria-live="polite"></p><div class="cool-content"></div>`;
  previous.after(host);
  const control=host.querySelector('.cool-mode'),fuel=host.querySelector('.cool-fuel'),status=host.querySelector('.cool-status'),content=host.querySelector('.cool-content');
  let serial=0;
  async function load(){
    const id=++serial;
    status.textContent=t('Loading and checking the NASA source…','جارٍ تحميل مصدر ناسا والتحقق منه…');
    content.replaceChildren();
    try {
      const params=new URLSearchParams({configuration:control.value,fuel:fuel.value});const d=await request('/combustion/cool-flames?'+params);
      if(!host.isConnected||id!==serial)return;
      const selection=fuel.value;
      fuel.replaceChildren();
      const all=document.createElement('option');all.value='';all.textContent=t('All fuels','كل أنواع الوقود');fuel.append(all);
      for(const name of d.fuel_options){const option=document.createElement('option');option.value=name;option.textContent=name;fuel.append(option)}
      fuel.value=selection;
      if(!d.pairs.length){status.textContent=t('No numeric pairs available.','لا توجد أزواج رقمية متاحة.');return}
      const w=620,h=305,l=72,r=25,top=20,bottom=55;
      const times=d.pairs.map(v=>v.burn_time_s),temperatures=d.pairs.map(v=>v.peak_burner_c);
      const xMin=Math.min(0,...times),xMax=Math.max(1,...times),yMin=Math.min(0,...temperatures),yMax=Math.max(1,...temperatures);
      const x=v=>l+(v-xMin)/(xMax-xMin)*(w-l-r),y=v=>h-bottom-(v-yMin)/(yMax-yMin)*(h-top-bottom);
      content.innerHTML=`<div class="bass-overview-grid"><div class="bass-figure"><h4>${t('Burn duration and peak burner temperature','مدة الاحتراق ودرجة حرارة الموقد القصوى')}</h4><svg viewBox="0 0 ${w} ${h}" role="group" aria-label="${t('Select a CFI-G test point','اختر نقطة من اختبارات CFI-G')}" direction="ltr">
      ${Array.from({length:5},(_,i)=>{const v=yMin+(yMax-yMin)*i/4;return `<line class="bass-grid" x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}"/><text x="${l-8}" y="${y(v)+4}" text-anchor="end">${Number(v.toPrecision(3))}</text>`}).join('')}
      ${Array.from({length:5},(_,i)=>{const v=xMin+(xMax-xMin)*i/4;return `<text x="${x(v)}" y="${h-bottom+18}" text-anchor="middle">${Number(v.toPrecision(3))}</text>`}).join('')}
      ${d.pairs.map(row=>`<circle class="cool-dot bass-dot" role="button" tabindex="0" data-row="${row.row_index}" cx="${x(row.burn_time_s)}" cy="${y(row.peak_burner_c)}" r="5" aria-label="${esc(row.test)} · ${row.burn_time_s} s · ${row.peak_burner_c} °C"><title>${esc(row.test)} · ${row.burn_time_s} s · ${row.peak_burner_c} °C</title></circle>`).join('')}
      <text x="${w/2}" y="${h-6}" text-anchor="middle">${t('Burn time','مدة الاحتراق')} (s)</text></svg><p class="small">${t('Vertical axis: peak burner temperature (°C).','المحور العمودي: درجة حرارة الموقد القصوى (°C).')}</p><output class="cool-detail bass-point-detail" aria-live="polite">${t('Select a test to inspect its recorded values.','اختر اختباراً لفحص قيمه المسجلة.')}</output></div><div class="bass-figure"><h4>${t('Coverage and source','التغطية والمصدر')}</h4><p>${t('Numeric pairs','الأزواج الرقمية')} <bdi dir="ltr">${d.paired_count} / ${d.selected_records}</bdi></p><p class="small">${t('Nonempty source rows','السجلات غير الفارغة')}: ${d.nonempty_records} · ${t('Completely blank rows','الصفوف الفارغة بالكامل')}: ${d.blank_rows}</p><p class="small">${t('Zero duration and failed ignitions remain in the source. Normal and inverse configurations are separate.','تبقى المدد الصفرية والاشتعالات الفاشلة كما في المصدر. تُعرض الحالتان كلٌ على حدة.')}</p><a href="${esc(d.doi)}" target="_blank" rel="noopener noreferrer">NASA PSI-159 · DOI ↗</a> · <a href="/${esc(d.source_filename)}" download>CSV ↗</a><p class="small"><bdi dir="ltr">SHA-256 ${esc(d.source_sha256)}</bdi></p><details><summary>${t('Selected original row','صف المصدر المحدد')}</summary><pre class="cool-source code-block"></pre></details></div></div><section class="bass-figure section-gap"><h4>${t('Hot ignition · source labels','الاشتعال الساخن · تسميات المصدر')}</h4><p class="small">${t('Counts of literal source labels among nonempty selected rows. Case and blanks are retained; no labels are inferred.','أعداد تسميات المصدر كما وردت في السجلات المحددة غير الفارغة. تُحفظ الأحرف والخانات الفارغة دون استنتاج.')}</p>${d.hot_ignition_categories.map(item=>`<div class="bass-availability"><span><bdi dir="ltr">${esc(item.source_value)}</bdi></span><span class="bass-availability-track"><i style="width:${100*item.count/Math.max(1,d.selected_records)}%"></i></span><strong><bdi dir="ltr">${item.count} / ${d.selected_records}</bdi></strong></div>`).join('')}</section><p class="bass-overview-limit">${t('The source field is burner temperature, not flame temperature. Conditions vary and the chart does not establish causation. Measurement uncertainty is not supplied in the table.','الحقل يقيس درجة حرارة الموقد وليس اللهب. تختلف ظروف الاختبار، ولا يثبت الرسم السببية. لا يتضمن الجدول عدم يقين القياس.')}</p><div class="input-row"><button type="button" class="button secondary cool-export">${t('Export source-backed analysis','تنزيل التحليل ومصدره')}</button><button type="button" class="button secondary cool-replay">${t('Replay analysis','إعادة التحليل')}</button></div><p class="cool-replay-status small" role="status" aria-live="polite"></p>`;
      const distribution=d.duration_distribution;
      const formatBoundary=value=>Number(value.toPrecision(6)).toString();
      const binText=bin=>`${formatBoundary(bin.lower_s)} ≤ t ${bin.upper_inclusive?'≤':'<'} ${formatBoundary(bin.upper_s)} s`;
      content.querySelector('.bass-overview-limit').insertAdjacentHTML('beforebegin',`<section class="bass-figure section-gap cool-duration"><h4>${t('Distribution of recorded burn durations','توزيع مدد الاحتراق المسجلة')}</h4><p class="small">${t('All finite durations, including zero; temperature is not required. Six equal-width bins; the last includes its upper edge. Boundaries are rounded for display.','جميع المدد الرقمية بما فيها الصفر؛ لا يشترط توفر الحرارة. ست فئات متساوية العرض، تشمل الأخيرة حدها الأعلى. الحدود مقربة للعرض.')}</p><p>${t('Available','المتاح')}: <bdi dir="ltr">${distribution.count} / ${d.selected_records}</bdi> · ${t('Missing or nonnumeric','ناقص أو غير رقمي')}: <bdi dir="ltr">${distribution.missing_or_nonnumeric}</bdi> · ${t('Median','الوسيط')}: <bdi dir="ltr">${distribution.median_s===null?'—':distribution.median_s+' s'}</bdi></p><div class="cool-histogram">${distribution.bins.map((bin,i)=>`<button type="button" class="cool-bin" data-bin="${i}" aria-pressed="false"><bdi dir="ltr">${binText(bin)}</bdi><span class="cool-bin-track"><i style="width:${100*bin.count/Math.max(1,...distribution.bins.map(b=>b.count))}%"></i></span><strong>${bin.count}</strong></button>`).join('')}</div><output class="cool-bin-detail bass-point-detail" aria-live="polite">${t('Select a range to inspect its source tests.','اختر فئة لفحص اختباراتها الأصلية.')}</output><p class="small">${t('Descriptive counts only: differing conditions and failed ignitions prevent a causal interpretation.','الأعداد وصفية فقط؛ اختلاف الظروف والاشتعالات الفاشلة يمنع الاستنتاج السببي.')}</p></section>`);
      content.querySelectorAll('.cool-bin').forEach(button=>button.addEventListener('click',()=>{
        const bin=distribution.bins[Number(button.dataset.bin)];if(!bin)return;
        content.querySelectorAll('.cool-bin').forEach(node=>node.setAttribute('aria-pressed',String(node===button)));
        const identifiers=bin.row_indices.map(index=>{const item=d.selected_source_rows.find(row=>row.row_index===index);return item?.source_row.Test || `#${index}`});
        const shown=identifiers.slice(0,10).join(', ');
        content.querySelector('.cool-bin-detail').textContent=`${binText(bin)} · n=${bin.count}${shown?' · '+shown:''}${identifiers.length>10?' …':''}`;
      }));
      const ask=document.createElement('button');ask.type='button';ask.className='button secondary cool-ask';ask.textContent=t('Ask the research copilot about this selection','اسأل المساعد العلمي عن هذا التحديد');
      content.querySelector('.cool-export').before(ask);
      ask.addEventListener('click',()=>{sessionStorage.removeItem('mors-bass-selection');sessionStorage.removeItem('mors-flame-selection');sessionStorage.setItem('mors-cool-selection',JSON.stringify({configuration:d.configuration,fuel:d.fuel}));location.hash='#intelligence'});
      content.querySelector('.cool-export').addEventListener('click',()=>{
        const url=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}));
        const link=document.createElement('a');link.href=url;link.download='mors-cfi-g-analysis.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });
      content.querySelector('.cool-replay').addEventListener('click',async event=>{
        const button=event.currentTarget,output=content.querySelector('.cool-replay-status');
        button.disabled=true;output.textContent=t('Recomputing source and analysis hashes…','جارٍ إعادة حساب بصمة المصدر والتحليل…');
        try{
          const replay=await request('/combustion/cool-flames/replay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({configuration:d.configuration,fuel:d.fuel,source_sha256:d.source_sha256,analysis_sha256:d.analysis_sha256,method_version:d.reproducibility.method_version})});
          if(!host.isConnected||id!==serial)return;
          if(replay.matched)output.textContent=t('Reproduced: source, method and results match. This does not validate the original measurements.','تطابقت بصمة المصدر والطريقة والنتائج عند إعادة الحساب. هذا لا يتحقق من صحة القياسات الأصلية.');
          else {const failed=Object.entries(replay.checks).filter(([,ok])=>!ok).map(([key])=>key).join(', ');output.textContent=t('Replay mismatch: ','اختلاف عند الإعادة: ')+failed}
        }catch{if(host.isConnected&&id===serial)output.textContent=t('Replay unavailable; check the source and retry.','تعذرت الإعادة؛ تحقق من المصدر وحاول مجدداً.')}
        finally{button.disabled=false}
      });
      const detail=host.querySelector('.cool-detail'),source=host.querySelector('.cool-source');
      host.querySelectorAll('.cool-dot').forEach(dot=>{
        const show=()=>{const row=d.pairs.find(item=>item.row_index===Number(dot.dataset.row));if(!row)return;detail.dir='ltr';detail.textContent=`${row.test} · ${row.fuel} · ${row.burn_time_s} s · ${row.peak_burner_c} °C`;source.textContent=JSON.stringify(row.source_row,null,2)};
        dot.addEventListener('click',show);dot.addEventListener('focus',show);
        dot.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}});
      });
      status.textContent=t(`${d.paired_count} numeric pairs from ${d.selected_records} selected nonempty records.`,`${d.paired_count} زوجاً رقمياً من أصل ${d.selected_records} سجلاً محدداً غير فارغ.`);
    }catch{if(host.isConnected&&id===serial)status.textContent=t('Source unavailable. Change configuration to retry.','تعذر تحميل المصدر. غيّر النوع لإعادة المحاولة.')}
  }
  control.addEventListener('change',()=>{fuel.value='';load()});fuel.addEventListener('change',load);load();
}
