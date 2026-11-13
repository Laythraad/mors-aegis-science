// Exported spreadsheet text must not execute as a formula when opened in Excel.
function safeSpreadsheetCell(value) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return typeof value === 'string' && /^[\s\u0000-\u001f]*[=+@-]/.test(text) ? "'" + text : text;
}
// All route names refer to existing application views. No source requests are made here.
const missionTracks = [
  { name:['Combustion','الاحتراق'], question:['What can an image tell us about a flame?','ماذا تخبرنا الصورة عن اللهب؟'],
    detail:['Read the experiment record, inspect a flame image, then check which conclusions the measurements support.','اقرأ سجل التجربة، ثم افحص صورة اللهب وراجع الاستنتاجات التي تسمح بها القياسات.'],
    routes:['experiments','combustion','methodology'] },
  { name:['Earth observation','رصد الأرض'], question:['Where did a satellite record a thermal anomaly?','أين رصد القمر الصناعي شذوذاً حرارياً؟'],
    detail:['Locate a detection on the globe, inspect its acquisition time and sensor, then trace the archived response.','حدّد الرصد على الكرة الأرضية، وافحص وقت الالتقاط والمستشعر، ثم تتبّع ملف المصدر في الأرشيف.'],
    routes:['earth','spacetime','archive'] },
  { name:['Astronomy','الفلك'], question:['How are the catalogued exoplanets distributed?','كيف تتوزع الكواكب الخارجية المفهرسة؟'],
    detail:['Open the gallery, select exoplanets and compare discovery-method counts. Use the source tables to check coverage.','افتح المعرض واختر الكواكب الخارجية وقارن أعدادها حسب طريقة الاكتشاف. راجع جداول المصدر لمعرفة نطاق الفهرس.'],
    routes:['gallery','data'] }
];
const localPair = pair => pair[window.MorsI18n?.language === 'ar' ? 1 : 0];
function missionTrackDetail(index) {
  const track = missionTracks[index];
  const links = track.routes.map(route => {
    const title = navItems.find(([id]) => id === route)[1];
    return `<a href="#${route}">${esc(window.MorsI18n?.text(title) || title)}</a>`;
  });
  return `<h3>${esc(localPair(track.question))}</h3><p>${esc(localPair(track.detail))}</p><div class="track-links">${links.join('')}</div>`;
}
function missionWorkbench() {
  return `<section class="mission-workbench"><div class="track-header"><h2>${localPair(['Choose a research path','اختر مساراً بحثياً'])}</h2><span class="workbench-emblem" aria-hidden="true"></span></div>
    <fieldset class="track-options"><legend class="sr-only">${localPair(['Research path','المسار البحثي'])}</legend>${missionTracks.map((track,i)=>`<label><input type="radio" name="mission-track" value="${i}" ${i===0?'checked':''}><span>${esc(localPair(track.name))}</span></label>`).join('')}</fieldset>
    <div id="track-detail" aria-live="polite">${missionTrackDetail(0)}</div></section>`;
}
function bindMissionWorkbench() {
  document.querySelector('.track-options').addEventListener('change',event=>{
    const index = Number(event.target.value);
    if(missionTracks[index]) document.querySelector('#track-detail').innerHTML = missionTrackDetail(index);
  });
}
function scienceBarChart(rows,labelKey,valueKey,unit) {
  if(!rows?.length) return '<div class="empty">No rows available for this chart.</div>';
  const shown = rows.slice(0,12);
  const max = Math.max(1,...shown.map(row=>Number(row[valueKey])));
  const language = window.MorsI18n?.language || 'en';
  const countUnits = {detections:'رصد',planets:'كوكب',objects:'جرم'};
  const displayUnit = language==='ar' ? countUnits[unit] || unit : unit;
  const bars = shown.map(row=>{
    const value = Number(row[valueKey]);
    const label = row[labelKey] ?? localPair(['Unknown','غير معروف']);
    return `<button class="science-bar-row inspect-bar" type="button" aria-pressed="false" data-count="${value}" data-label="${esc(label)}"><span>${esc(label)}</span><span class="science-bar-track"><i style="width:${100*value/max}%"></i></span><strong>${value.toLocaleString(language)} <small>${esc(displayUnit)}</small></strong></button>`;
  });
  return `<div class="science-bars" data-unit="${esc(displayUnit)}"><p class="compare-note">${localPair(['Collection totals. Select a reference bar, then a second bar to compare counts.','الأعداد تخص المجموعة كاملة. اختر عموداً مرجعياً، ثم عموداً ثانياً لمقارنة العددين.'])}</p>${bars.join('')}<output class="compare-result" aria-live="polite"></output></div>`;
}
function bindBarComparison(host) {
  host.addEventListener('click',event=>{
    const bar = event.target.closest('.inspect-bar');
    if(!bar) return;
    const chart = bar.closest('.science-bars');
    const selected = [...chart.querySelectorAll('[aria-pressed="true"]')];
    const output = chart.querySelector('.compare-result');
    if(selected.length!==1 || selected[0]===bar) {
      selected.forEach(item=>item.setAttribute('aria-pressed','false'));
      if(selected.length===1 && selected[0]===bar) { output.textContent=''; return; }
      bar.setAttribute('aria-pressed','true');
      output.textContent = localPair(['Reference','المرجع'])+' · '+bar.dataset.label+' · '+bar.querySelector('strong').textContent.trim();
      return;
    }
    const reference = selected[0];
    const delta = Number(bar.dataset.count)-Number(reference.dataset.count);
    const diff = delta.toLocaleString(window.MorsI18n?.language || 'en',{signDisplay:'exceptZero'});
    bar.setAttribute('aria-pressed','true');
    const equation = document.createElement('bdi');
    equation.dir = 'ltr';
    equation.textContent = bar.dataset.label+' − '+reference.dataset.label+' = '+diff;
    output.replaceChildren(localPair(['Difference','الفرق'])+' · ', equation, ' '+chart.dataset.unit);
  });
}
