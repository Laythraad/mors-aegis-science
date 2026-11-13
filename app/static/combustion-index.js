function bindCombustionIndex() {
  const parent=document.querySelector('#combustion-inventory');
  if(!parent)return;
  const ar=window.MorsI18n?.language==='ar',t=(en,arabic)=>ar?arabic:en;
  const host=document.createElement('section');
  host.className='combustion-index bass-overview';
  host.innerHTML=`<h3>${t('Search combustion source records','البحث في سجلات الاحتراق الأصلية')}</h3><p class="small">${t('Search verified nonblank rows across the local source tables. Each result retains its original fields and checksum.','ابحث في الصفوف غير الفارغة من جداول المصدر المحلية المتحقق من بصمتها. يحتفظ كل سجل بحقوله الأصلية.')}</p>
  <form class="combustion-index-form"><label>${t('Collection','المجموعة')}<select name="dataset"><option value="">${t('All collections','كل المجموعات')}</option><option value="bass_ii">BASS-II</option><option value="flame_normal">Flame Design · Normal</option><option value="flame_inverse">Flame Design · Inverse</option><option value="cool_normal">CFI-G · Normal</option><option value="cool_inverse">CFI-G · Inverse</option></select></label><label>${t('Test or fuel','الاختبار أو الوقود')}<input type="search" name="q" maxlength="100"></label><button type="submit" class="button secondary">${t('Search','بحث')}</button></form>
  <p class="combustion-index-status small" role="status" aria-live="polite"></p><div class="combustion-index-results"></div><div class="input-row"><button class="button secondary index-prev" type="button" disabled>${t('Previous','السابق')}</button><button class="button secondary index-next" type="button" disabled>${t('Next','التالي')}</button></div><details class="index-details"><summary>${t('Selected source record','سجل المصدر المحدد')}</summary><p class="index-source"></p><pre class="index-raw code-block"></pre></details>`;
  parent.after(host);
  const form=host.querySelector('form'),status=host.querySelector('.combustion-index-status'),results=host.querySelector('.combustion-index-results');
  const previous=host.querySelector('.index-prev'),next=host.querySelector('.index-next');
  let offset=0,serial=0,applied={dataset:'',q:''};
  async function load(){
    const id=++serial;previous.disabled=next.disabled=true;
    host.querySelector('.index-details').open=false;
    host.querySelector('.index-source').replaceChildren();
    host.querySelector('.index-raw').replaceChildren();
    status.textContent=t('Checking source files and searching the index…','جارٍ التحقق من ملفات المصدر والبحث في الفهرس…');
    try{
      const params=new URLSearchParams({...applied,offset:String(offset),limit:'25'});
      const data=await request('/combustion/index?'+params);
      if(!host.isConnected||id!==serial)return;
      results.innerHTML=data.items.length?`<div class="table-scroll"><table class="experiment-table"><thead><tr><th>${t('Collection','المجموعة')}</th><th>${t('Test','الاختبار')}</th><th>${t('Fuel','الوقود')}</th><th>${t('Source','المصدر')}</th></tr></thead><tbody>${data.items.map((row,i)=>`<tr><td data-label="${t('Collection','المجموعة')}"><bdi dir="ltr">${esc(row.dataset)}</bdi></td><td data-label="${t('Test','الاختبار')}"><bdi dir="auto">${esc(row.test_id||'—')}</bdi></td><td data-label="${t('Fuel','الوقود')}"><bdi dir="auto">${esc(row.fuel||'—')}</bdi></td><td><button type="button" class="button secondary index-inspect" data-index="${i}">${t('Inspect','فحص')}</button></td></tr>`).join('')}</tbody></table></div>`:`<p class="empty">${t('No matching records.','لا توجد سجلات مطابقة.')}</p>`;
      results.querySelectorAll('.index-inspect').forEach(button=>button.addEventListener('click',()=>{
        const item=data.items[Number(button.dataset.index)];if(!item)return;
        host.querySelector('.index-raw').textContent=JSON.stringify(item.source_row,null,2);
        host.querySelector('.index-source').innerHTML=`<a href="${esc(item.doi)}" target="_blank" rel="noopener noreferrer">NASA DOI ↗</a><br><bdi dir="ltr">SHA-256 ${esc(item.source_sha256)}</bdi><br>${t('Zero-based source row','رقم صف المصدر بدءاً من صفر')}: ${item.row_index}`;
        host.querySelector('.index-details').open=true;
      }));
      previous.disabled=offset===0;next.disabled=offset+data.items.length>=data.total;
      status.textContent=t(`${data.items.length} displayed · ${data.total} matching nonblank records.`,`عرض ${data.items.length} · العدد المطابق ${data.total} سجلاً غير فارغ.`);
    }catch(error){if(host.isConnected&&id===serial){results.replaceChildren();status.textContent=t('Index unavailable; source verification may have failed.','الفهرس غير متاح؛ قد يكون فحص المصدر قد فشل.')}}
  }
  form.addEventListener('submit',event=>{event.preventDefault();applied={dataset:form.querySelector('[name=dataset]').value,q:form.querySelector('[name=q]').value.trim()};offset=0;load()});
  previous.addEventListener('click',()=>{offset=Math.max(0,offset-25);load()});
  next.addEventListener('click',()=>{offset+=25;load()});
  load();
}
