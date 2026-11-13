function bindVisionLab() {
  const input=document.querySelector('#image-upload'), out=document.querySelector('#vision-result');
  if(!input || !out) return;
  const ar=window.MorsI18n?.language==='ar';
  const t=(en,arabic)=>ar?arabic:en;
  const controls=document.createElement('div');
  controls.className='vision-controls';
  controls.innerHTML=`<label for="vision-red">${t('Minimum red channel','الحد الأدنى للقناة الحمراء')} <output id="vision-red-value">150</output></label><input id="vision-red" type="range" min="0" max="255" step="1" value="150"><button class="button secondary vision-run" type="button" disabled>${t('Run analysis','تشغيل التحليل')}</button><p class="small">${t('The selected threshold is an RGB pixel rule. It is not a temperature or confidence value.','العتبة المختارة قاعدة لقيم RGB، وليست درجة حرارة أو مستوى ثقة.')}</p>`;
  out.before(controls);
  const slider=controls.querySelector('#vision-red'), button=controls.querySelector('.vision-run');
  const valueLabel=controls.querySelector('#vision-red-value');
  let active=0, originalURL=null;
  slider.addEventListener('input',()=>{valueLabel.textContent=slider.value});
  async function run() {
    const file=input.files?.[0];
    if(!file)return;
    const revision=++active, threshold=Number(slider.value);
    button.disabled=true;
    out.innerHTML=`<div class="empty" role="status">${t('Analyzing image…','جارٍ تحليل الصورة…')}</div>`;
    const form=new FormData();form.append('file',file);
    try {
      const data=await request('/vision/analyze?red_min='+threshold,{method:'POST',body:form});
      if(!out.isConnected || revision!==active)return;
      if(originalURL)URL.revokeObjectURL(originalURL);
      originalURL=URL.createObjectURL(file);
      const max=Math.max(1,...data.threshold_sensitivity.map(x=>x.warm_pixel_count));
      out.innerHTML=`<div class="source-note">${t('Exploratory RGB heuristic. Temperature and physical size are unavailable without calibration.','تحليل استكشافي لقيم RGB. لا تتوفر درجة الحرارة والأبعاد الفيزيائية دون معايرة.')}</div>
      <div class="grid two-col section-gap"><figure class="vision-figure"><img class="vision-original" alt="${t('Original image','الصورة الأصلية')}"><figcaption>${t('Original image','الصورة الأصلية')}</figcaption></figure><figure class="vision-figure"><img alt="Exploratory warm-pixel overlay" src="data:image/png;base64,${data.overlay_png_base64}"><figcaption>${t('Warm-pixel overlay','تراكب البكسلات الدافئة')}</figcaption></figure></div>
      <div class="vision-summary"><div><span>${t('Selected pixels','البكسلات المحددة')}</span><strong>${data.warm_pixel_count.toLocaleString()}</strong></div><div><span>${t('Fraction of analyzed image','النسبة من الصورة المحللة')}</span><strong>${(100*data.warm_pixel_fraction).toFixed(2)}%</strong></div><div><span>${t('Analysis resolution','دقة التحليل')}</span><strong><bdi dir="ltr">${data.analysis_resolution_px.width} × ${data.analysis_resolution_px.height} px</bdi></strong></div></div>
      <section class="bass-figure section-gap"><h3>${t('Sensitivity to the red-channel threshold','تأثير عتبة القناة الحمراء')}</h3><p class="small">${t('The same image and color rules at five thresholds. Select a bar to rerun that threshold.','الصورة نفسها وقواعد الألوان نفسها عند خمس عتبات. اختر عموداً لإعادة التحليل.')}</p>
      ${data.threshold_sensitivity.map(item=>`<button type="button" class="bass-plot-bar vision-threshold" data-value="${item.red_min_exclusive}"><span><bdi dir="ltr">R &gt; ${item.red_min_exclusive} · ${item.warm_pixel_count.toLocaleString()} px</bdi></span><span class="bass-track"><i style="width:${100*item.warm_pixel_count/max}%;background:var(--theme-accent)"></i></span></button>`).join('')}</section>
      <details class="section-gap"><summary>${t('Processing record','سجل المعالجة')}</summary><p class="small"><bdi dir="ltr">SHA-256 ${esc(data.source_sha256)}</bdi></p><p class="small">${t('Bounding box in analysis pixels','الصندوق المحيط ببكسلات التحليل')}: <bdi dir="ltr">${data.bounding_box_px ? esc(JSON.stringify(data.bounding_box_px)) : t('none','غير متاح')}</bdi></p><pre class="code-block">${esc(JSON.stringify(data.parameters,null,2))}</pre><p class="small">${t('Pixel counts refer to the analysis resolution. Classification accuracy and measurement uncertainty have not been evaluated.','أعداد البكسلات تخص دقة التحليل. لم تُقيّم دقة التصنيف أو عدم يقين القياس.')}</p></details>
      <button type="button" class="button secondary vision-export">${t('Export processing record','تنزيل سجل المعالجة')}</button>`;
      out.querySelector('.vision-original').src=originalURL;
      out.querySelectorAll('.vision-threshold').forEach(item=>item.addEventListener('click',()=>{
        slider.value=item.dataset.value;valueLabel.textContent=slider.value;run();
      }));
      out.querySelector('.vision-export').addEventListener('click',()=>{
        const {overlay_png_base64, ...record}=data;
        const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
        const link=document.createElement('a');link.href=url;link.download='mors-vision-analysis.json';link.click();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
      });
    } catch(error) {
      if(out.isConnected&&revision===active)out.innerHTML=`<div class="source-note" role="alert">${t('Analysis failed:','تعذر التحليل:')} ${esc(error.message)}</div>`;
    } finally {if(out.isConnected&&revision===active)button.disabled=false}
  }
  input.addEventListener('change',()=>{
    if(input.files?.length){button.disabled=false;run()}
    else{++active;button.disabled=true;out.replaceChildren();if(originalURL){URL.revokeObjectURL(originalURL);originalURL=null}}
  });
  button.addEventListener('click',run);
}
