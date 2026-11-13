function bindEarthArchiveFilters(beginRequest, isCurrent) {
  const globe=document.querySelector('#fire-globe');
  const status=document.querySelector('#globe-status');
  if(!globe || !status)return;
  const ar=window.MorsI18n?.language==='ar',t=(en,arabic)=>ar?arabic:en;
  const section=document.createElement('section');
  section.className='earth-archive-filters';
  section.innerHTML=`<h3>${t('Filter archived observations','تصفية الرصدات المؤرشفة')}</h3><p class="small">${t('Dates use UTC. Leave both dates empty for all available archive dates.','التواريخ بتوقيت UTC. اترك التاريخين فارغين لعرض كل التواريخ الموجودة في الأرشيف.')}</p>
  <form class="archive-globe-form"><label>${t('Start date','تاريخ البداية')}<input type="date" name="start"></label><label>${t('End date','تاريخ النهاية')}<input type="date" name="end"></label><label>${t('Product','المنتج')}<select name="product"><option value="">${t('All archived products','كل المنتجات المؤرشفة')}</option>${['VIIRS_SNPP_NRT','VIIRS_SNPP_SP','VIIRS_NOAA20_NRT','VIIRS_NOAA20_SP','VIIRS_NOAA21_NRT','VIIRS_NOAA21_SP','MODIS_NRT','MODIS_SP'].map(value=>`<option value="${value}">${value}</option>`).join('')}</select></label><label class="archive-bounds"><input type="checkbox" name="bounds"> ${t('Use the coordinates below','استخدم الإحداثيات أدناه')}</label><button class="button" type="submit">${t('Show matching observations','اعرض الرصدات المطابقة')}</button></form>
  <p class="small">${t('Region uses the west, south, east and north fields below and is limited to 100 square degrees. The date window is limited to 366 days.','تستخدم المنطقة حقول الغرب والجنوب والشرق والشمال أدناه بحد 100 درجة مربعة. الحد الأقصى للفترة 366 يوماً.')}</p>
  <p class="archive-globe-message" role="status" aria-live="polite"></p><div class="archive-globe-pages"><button class="button secondary archive-globe-prev" type="button" disabled>${t('Previous 500','الـ500 السابقة')}</button><button class="button secondary archive-globe-next" type="button" disabled>${t('Next 500','الـ500 التالية')}</button></div>`;
  status.before(section);
  const form=section.querySelector('form'),message=section.querySelector('.archive-globe-message');
  const previous=section.querySelector('.archive-globe-prev'),next=section.querySelector('.archive-globe-next');
  let offset=0, applied=null;
  const load=async()=>{
    if(!applied)return;
    const id=beginRequest();
    previous.disabled=next.disabled=true;
    message.textContent=t('Loading archived observations…','جارٍ تحميل الرصدات المؤرشفة…');
    const params=new URLSearchParams(applied);params.set('offset',String(offset));params.set('limit','500');
    try{
      const data=await request('/data/fire-observations?'+params);
      if(!globe.isConnected||!isCurrent(id))return;
      plotFirms(data.items,'NASA FIRMS',{total:data.total,archived:true});
      previous.disabled=offset===0;next.disabled=offset+data.items.length>=data.total;
      const range=document.createElement('bdi');range.dir='ltr';
      range.textContent=`${data.items.length?offset+1:0}–${offset+data.items.length}`;
      const total=document.createElement('bdi');total.dir='ltr';total.textContent=String(data.total);
      message.replaceChildren(t('Showing rows ','عرض الصفوف '),range,t(' of ',' من أصل '),total,
        t(' matching archived observations. Ordered by UTC; rotate the globe to see both hemispheres.',' رصداً مؤرشفاً مطابقاً. الترتيب حسب UTC؛ أدر الكرة لرؤية نصفيها.'));
    }catch(error){
      if(!globe.isConnected||!isCurrent(id))return;
      plotFirms([],'NASA FIRMS',{total:0,archived:true});
      message.textContent=t('Could not load observations: ','تعذر تحميل الرصدات: ')+error.message;
    }
  };
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const fields=new FormData(form),start=String(fields.get('start')||''),end=String(fields.get('end')||'');
    if(Boolean(start)!==Boolean(end)){message.textContent=t('Choose both dates, or leave both empty.','اختر التاريخين معاً أو اتركهما فارغين.');return}
    const params=new URLSearchParams();
    if(start){params.set('start_date',start);params.set('end_date',end)}
    if(fields.get('product'))params.set('product',fields.get('product'));
    if(fields.has('bounds'))params.set('bbox',['west','south','east','north'].map(name=>document.querySelector('#firms-'+name).value).join(','));
    applied=params;offset=0;load();
  });
  previous.addEventListener('click',()=>{offset=Math.max(0,offset-500);load()});
  next.addEventListener('click',()=>{offset+=500;load()});
  return {clear(){applied=null;offset=0;previous.disabled=next.disabled=true;message.textContent=''}};
}
