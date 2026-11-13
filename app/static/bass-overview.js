function bindBassOverview() {
  const lab = document.querySelector('#bass-lab');
  if (!lab) return;
  const ar = window.MorsI18n?.language === 'ar';
  const t = (en, arabic) => ar ? arabic : en;
  const section = document.createElement('section');
  section.className = 'bass-overview';
  section.innerHTML = `<details class="bass-nasa-image"><summary>${t('View NASA representative flame image','عرض صورة اللهب التمثيلية من ناسا')}</summary><figure><img src="/bass-ii-nasa-representative.jpg" loading="lazy" alt="${t('NASA BASS-II representative flame test image','صورة تمثيلية لاختبار لهب BASS-II من ناسا')}"><figcaption>${t('NASA PSI-25 representative image, version 4. The source does not identify the specific selected table rows for this image.','صورة تمثيلية من NASA PSI-25، الإصدار 4. لا يحدد المصدر ارتباطها بصفوف الجدول المختارة.')} <a href="https://doi.org/10.60555/4qc4-de67" target="_blank" rel="noopener noreferrer">NASA PSI-25 ↗</a><br><bdi dir="ltr">SHA-256 aa0bf2369cf77833e95e353519e634ab5cbb5b2918db08849e9bde82267aade3</bdi></figcaption></figure><button type="button" class="button secondary bass-analyze-image">${t('Analyze this image','حلّل هذه الصورة')}</button><span class="bass-image-status" role="status"></span></details><header><div><h3>${t('Explore the BASS-II source table','استكشف جدول BASS-II')}</h3><p>${t('Each point is one recorded test. Select a point to inspect its conditions.','كل نقطة تمثل اختباراً مسجلاً. اختر نقطة لفحص ظروفها.')}</p></div><label>${t('Measurement','القياس')} <select class="bass-measure"><option value="oxygen">${t('Oxygen','الأكسجين')}</option><option value="carbon_dioxide">${t('Carbon dioxide','ثاني أكسيد الكربون')}</option><option value="carbon_monoxide">${t('Carbon monoxide','أول أكسيد الكربون')}</option></select></label></header>
  <div class="bass-overview-status" role="status" aria-live="polite"></div><div class="bass-overview-content"></div>`;
  lab.append(section);
  section.querySelector('.bass-analyze-image').addEventListener('click', async event => {
    const button=event.currentTarget, output=section.querySelector('.bass-image-status');
    button.disabled=true;
    output.textContent=t('Preparing the NASA image…','جارٍ تجهيز صورة ناسا…');
    try {
      const response=await fetch('/bass-ii-nasa-representative.jpg',{credentials:'same-origin'});
      if (!response.ok) throw new Error('Image unavailable');
      const file=new File([await response.blob()],'NASA-PSI-25-representative.jpg',{type:'image/jpeg'});
      if (!section.isConnected) return;
      const transfer=new DataTransfer(); transfer.items.add(file);
      const input=document.querySelector('#image-upload');
      input.files=transfer.files;
      input.dispatchEvent(new Event('change',{bubbles:true}));
      output.textContent=t('Image sent to the exploratory RGB analysis below.','أُرسلت الصورة إلى تحليل RGB الاستكشافي أدناه.');
      input.scrollIntoView({behavior:'smooth',block:'center'});
    } catch {
      if(section.isConnected) output.textContent=t('Image unavailable. Retry.','تعذر تحميل الصورة. حاول مجدداً.');
    } finally { button.disabled=false; }
  });
  const control = section.querySelector('select');
  const status = section.querySelector('.bass-overview-status');
  const content = section.querySelector('.bass-overview-content');
  let serial = 0;
  const load = async () => {
    const id = ++serial;
    status.textContent = t('Loading source values…','جارٍ تحميل قيم المصدر…');
    content.replaceChildren();
    try {
      const data = await request('/combustion/bass-ii/overview?measure='+encodeURIComponent(control.value));
      if (!section.isConnected || serial !== id) return;
      const width=620, height=310, left=70, right=26, top=20, bottom=55;
      const values=data.pairs.flatMap(row=>[row.initial,row.final]);
      const minimum=Math.min(0,...values), maximum=Math.max(1,...values);
      const span=maximum-minimum;
      const x=value=>left+(value-minimum)/span*(width-left-right);
      const y=value=>height-bottom-(value-minimum)/span*(height-top-bottom);
      const ticks=Array.from({length:5},(_,i)=>minimum+span*i/4);
      const circles=data.pairs.map(row=>{
        const detail=`${row.investigator} · ${row.test} · ${row.date} · ${row.fuel} · ${t('initial','ابتدائي')} ${row.initial} · ${t('final','نهائي')} ${row.final} ${data.unit}`;
        return `<circle class="bass-dot" tabindex="0" role="button" data-row="${row.row_index}" aria-label="${esc(detail)}" cx="${x(row.initial)}" cy="${y(row.final)}" r="5"><title>${esc(detail)}</title></circle>`;
      }).join('');
      const availability=[['Initial','الابتدائي',data.initial_count],['Final','النهائي',data.final_count],['Complete pairs','الأزواج المكتملة',data.paired_count]];
      content.innerHTML=`<div class="bass-overview-grid"><div class="bass-figure"><h4>${t('Initial and final values','القيم الابتدائية والنهائية')}</h4><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${t('Paired values. Use Tab to inspect points.','القيم المقترنة. استخدم Tab لفحص النقاط.')}" direction="ltr">
      ${ticks.map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="${top}" y2="${height-bottom}" class="bass-grid"/><line x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}" class="bass-grid"/><text x="${x(v)}" y="${height-bottom+18}" text-anchor="middle">${Number(v.toPrecision(3))}</text><text x="${left-8}" y="${y(v)+4}" text-anchor="end">${Number(v.toPrecision(3))}</text>`).join('')}
      <line class="bass-equality" x1="${x(minimum)}" y1="${y(minimum)}" x2="${x(maximum)}" y2="${y(maximum)}"/> ${circles}<text x="${width/2}" y="${height-6}" text-anchor="middle">${t('Initial','ابتدائي')} (${esc(data.unit)})</text></svg>
      <p class="small">${t('Vertical axis: final value. Dashed line: initial = final.','المحور العمودي: القيمة النهائية. الخط المتقطع: الابتدائية = النهائية.')}</p><output class="bass-point-detail" aria-live="polite">${t('Select a point to see its source row.','اختر نقطة لعرض سجلها.')}</output></div>
      <div class="bass-figure"><h4>${t('Source field availability','توفر حقول المصدر')}</h4><p class="small">${t('Finite numeric entries among','القيم الرقمية الصالحة من أصل')} ${data.total} ${t('records','سجلاً')}</p>
      ${availability.map(([en,arabic,count])=>`<div class="bass-availability"><span>${t(en,arabic)}</span><span class="bass-availability-track"><i style="width:${100*count/data.total}%"></i></span><strong><bdi dir="ltr">${count} / ${data.total}</bdi></strong></div>`).join('')}
      <p class="small">${t('Blank or nonnumeric fields are excluded, not converted to zero.','تُستبعد الخانات الفارغة أو غير الرقمية من الأزواج.')}</p><a href="${esc(data.doi)}" target="_blank" rel="noopener noreferrer">NASA PSI-25 · DOI ↗</a></div></div>
      <p class="bass-overview-limit">${t('These records span different fuels and conditions. The chart is descriptive and does not establish causation. Source calibration uncertainty is not supplied.','تختلف أنواع الوقود والظروف بين السجلات. الرسم وصفي ولا يثبت السببية. عدم يقين المعايرة غير متاح في الجدول.')}</p>`;
      const out=content.querySelector('.bass-point-detail');
      content.querySelectorAll('.bass-dot').forEach(dot=>{
        const show=()=>{const row=data.pairs.find(item=>item.row_index===Number(dot.dataset.row));if(row)out.textContent=`${row.investigator} · ${row.test} · ${row.date} · ${row.fuel} · ${row.initial} → ${row.final} ${data.unit}`};
        dot.addEventListener('click',show);dot.addEventListener('focus',show);
        dot.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}});
      });
      status.textContent=t(`${data.paired_count} complete pairs from ${data.total} source records.`,`${data.paired_count} زوجاً مكتملاً من أصل ${data.total} سجلاً.`);
    } catch {
      if(section.isConnected && serial===id) status.textContent=t('Source values unavailable. Change measurement to retry.','تعذر تحميل البيانات. غيّر القياس لإعادة المحاولة.');
    }
  };
  control.addEventListener('change',load);
  load();
}
