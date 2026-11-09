function bindBassLab() {
  const host = document.querySelector('#bass-lab');
  if (!host) return;
  const arabic = window.MorsI18n?.language === 'ar';
  const t = (en, ar) => arabic ? ar : en;
  const columns = [
    ['PI', 'Investigator', 'الباحث'],
    ['Test #', 'Test', 'التجربة'],
    ['Date', 'Date', 'التاريخ'],
    ['Fuel Sample Material', 'Fuel sample', 'عينة الوقود'],
    ['Calibrated  initial O2 % by vol ', 'Initial O₂ % vol', 'الأكسجين الابتدائي % حجماً'],
    ['Calibrated final O2 % by vol', 'Final O₂ % vol', 'الأكسجين النهائي % حجماً'],
    ['Initial CO2 % by vol', 'Initial CO₂ % vol', 'ثاني أكسيد الكربون الابتدائي % حجماً'],
    ['Final CO2 % by vol', 'Final CO₂ % vol', 'ثاني أكسيد الكربون النهائي % حجماً']
  ];
  const select = host.querySelector('select');
  const result = host.querySelector('.bass-result');
  request('/combustion/bass-ii').then(data => {
    if (!host.isConnected) return;
    host.querySelector('.bass-status').textContent = t(
      `${data.rows.length} source records loaded. Select two tests to inspect their published values.`,
      `تم تحميل ${data.rows.length} سجلاً من المصدر. اختر تجربتين لفحص قيمهما المنشورة.`
    );
    for (const [index, row] of data.rows.entries()) {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = `${row['PI']} · ${row['Test #']} · ${row['Date']}`;
      select.append(option);
      host.querySelectorAll('select')[1].append(option.cloneNode(true));
    }
    const second = host.querySelectorAll('select')[1];
    select.disabled = second.disabled = false;
    if (data.rows.length > 1) second.value = '1';
    const render = () => {
      const chosen = [data.rows[Number(select.value)], data.rows[Number(second.value)]];
      result.innerHTML = `<div class="table-scroll"><table class="experiment-table"><thead><tr><th scope="col">${t('Recorded field','الحقل المسجل')}</th><th scope="col">${esc(chosen[0]['PI'])} · ${esc(chosen[0]['Test #'])}</th><th scope="col">${esc(chosen[1]['PI'])} · ${esc(chosen[1]['Test #'])}</th></tr></thead><tbody>${columns.map(([key,en,ar])=>`<tr><th scope="row">${t(en,ar)}</th>${chosen.map(row=>`<td><bdi dir="auto">${esc(row[key] || '—')}</bdi></td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    };
    select.addEventListener('change', render);
    second.addEventListener('change', render);
    if (data.rows.length) render();
  }).catch(() => {
    if (host.isConnected) host.querySelector('.bass-status').textContent = t(
      'The BASS-II table is unavailable or failed its integrity check. Reload the page to retry.',
      'تعذر تحميل جدول BASS-II أو فشل فحص سلامته. أعد تحميل الصفحة للمحاولة مجدداً.'
    );
  });
}
