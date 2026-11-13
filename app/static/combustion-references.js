function bindCombustionReferences(){
  const previous=document.querySelector('.cool-flames');if(!previous)return;
  const ar=window.MorsI18n?.language==='ar',t=(en,arabic)=>ar?arabic:en;
  const host=document.createElement('section');host.className='bass-overview combustion-references';
  host.innerHTML=`<header><div><h3>${t('NASA research reading room','مراجع ناسا البحثية')}</h3><p>${t('Research context linked to the investigation, distinct from source-table measurements.','سياق بحثي مرتبط بالدراسة، منفصل عن قياسات جداول المصدر.')}</p></div><label>${t('Investigation','الدراسة')}<select class="references-topic"><option value="">${t('All references','كل المراجع')}</option><option value="bass_ii">BASS-II</option><option value="flame_design">Flame Design</option><option value="cool_flames">CFI-G</option></select></label></header><p class="references-status small" role="status" aria-live="polite"></p><div class="references-list"></div><p class="small">${t('These are curated links and summaries; the full publications are opened on NASA NTRS and are not downloaded by this feature.','هذه روابط وملخصات منتقاة؛ تُفتح المستندات الكاملة على موقع NASA NTRS ولا تُنزّل بهذه الميزة.')}</p>`;
  previous.after(host);const list=host.querySelector('.references-list'),status=host.querySelector('.references-status'),select=host.querySelector('select');let serial=0;
  async function load(){const id=++serial;status.textContent=t('Loading references…','جارٍ تحميل المراجع…');list.replaceChildren();try{
    const data=await request('/combustion/references?topic='+encodeURIComponent(select.value));if(!host.isConnected||id!==serial)return;
    const types={'NASA Technical Memorandum':'مذكرة ناسا فنية','NASA conference poster':'ملصق مؤتمر لناسا','NASA conference abstract':'ملخص مؤتمر لناسا'};
    list.innerHTML=data.items.map(item=>`<article class="reference-card"><div class="reference-meta"><bdi dir="ltr">NASA NTRS ${esc(item.id)}</bdi> · ${esc(ar?(types[item.document_type]||item.document_type):item.document_type)}</div><h4><bdi dir="auto">${esc(item.title)}</bdi></h4><p>${esc(ar?item.scope_ar:item.scope_en)}</p><p class="small"><strong>${t('Limit','الحدود')}:</strong> ${esc(ar?item.limit_ar:item.limit_en)}</p><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${t('Open NASA record','فتح سجل ناسا')} ↗</a></article>`).join('');
    status.textContent=t(`${data.items.length} curated NASA references.`,`${data.items.length} من مراجع ناسا المنتقاة.`);
  }catch{if(host.isConnected&&id===serial)status.textContent=t('References unavailable.','المراجع غير متاحة.')}}
  select.addEventListener('change',load);load();
}
