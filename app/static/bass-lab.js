function bindBassLab() {
  const host = document.querySelector('#bass-lab');
  if (!host) return;
  const ar = window.MorsI18n?.language === 'ar';
  const t = (en, arabic) => ar ? arabic : en;
  const status = host.querySelector('.bass-status');
  const [first, second] = host.querySelectorAll('select');
  const result = host.querySelector('.bass-result');
  let sequence = 0, latest = null;
  const compare = async () => {
    const requestNumber = ++sequence;
    latest = null;
    result.replaceChildren();
    if (first.value === second.value) {
      status.textContent = t('Select two distinct tests.', 'اختر تجربتين مختلفتين.');
      return;
    }
    status.textContent = t('Checking source values…', 'جارٍ فحص قيم المصدر…');
    try {
      const analysis = await request('/combustion/bass-ii/compare', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({first_index:Number(first.value), second_index:Number(second.value)})
      });
      if (!host.isConnected || requestNumber !== sequence) return;
      latest = analysis;
      const labels = [
        ['oxygen','Oxygen','الأكسجين'],
        ['carbon_dioxide','Carbon dioxide','ثاني أكسيد الكربون'],
        ['carbon_monoxide','Carbon monoxide','أول أكسيد الكربون']
      ];
      const columns = [
        [t('Fuel sample','عينة الوقود'), test=>test.sample],
        [t('Flow restrictor','محدد التدفق'), test=>test.flow_restrictor],
        [t('Fan display','قراءة المروحة'), test=>test.fan_display],
        [t('Air display','قراءة الهواء'), test=>test.air_display]
      ];
      const textValue = value => esc(value || '—');
      const pairValue = measurement => {
        const delta = measurement.change === null ? t('unavailable','غير متاح') :
          `${measurement.change > 0 ? '+' : ''}${measurement.change} ${measurement.unit}`;
        return `${textValue(measurement.initial_source)} → ${textValue(measurement.final_source)} <small>(Δ ${esc(delta)})</small>`;
      };
      const bars = analysis.tests.flatMap((test, testIndex) => {
        const oxygen = test.measurements.oxygen;
        return [['initial', t('Initial','ابتدائي')], ['final', t('Final','نهائي')]].map(([key, label]) => {
          const value = oxygen[key];
          if (value === null || value < 0 || value > 100) return '';
          const caption = `${test.test} · ${label} · ${value} % vol`;
          return `<button type="button" class="bass-plot-bar" data-detail="${esc(test.investigator + ' · ' + test.test + ' · ' + test.date + ' · ' + label + ' · ' + value + ' % vol')}" aria-label="${esc(caption)}"><span>${esc(caption)}</span><span class="bass-track"><i style="width:${value}%;background:${testIndex ? '#dba941' : '#8bb8dc'}"></i></span></button>`;
        });
      }).join('');
      const conditionLabels={
        sample_description:t('Fuel description','وصف الوقود'),
        flow_restrictor:t('Flow restrictor','محدد التدفق'),
        fan_display:t('Fan display','قراءة المروحة'),
        air_display:t('Air display','قراءة الهواء'),
        initial_oxygen:t('Initial O₂ (% vol)','الأكسجين الابتدائي (% حجماً)')
      };
      const conditionOutcomes={
        same_source_text:t('Same source text','النص المسجل متماثل'),
        different_source_text:t('Different source text','النص المسجل مختلف'),
        same_recorded_value:t('Same recorded value','القيمة المسجلة متماثلة'),
        different_recorded_value:t('Different recorded value','القيمة المسجلة مختلفة'),
        unavailable:t('Missing or nonnumeric','مفقود أو غير رقمي')
      };
      const conditionsSummary={
        recorded_differences:t('Recorded conditions or labels differ.','توجد اختلافات في القيم أو التسميات المسجلة.'),
        incomplete_metadata:t('Some checked conditions are missing or nonnumeric.','بعض الظروف التي فُحصت مفقودة أو غير رقمية.'),
        no_recorded_differences:t('No differences were found in the checked fields.','لم تظهر اختلافات في الحقول التي فُحصت.')
      };
      result.innerHTML = `
        <div class="source-note"><strong>${conditionsSummary[analysis.condition_status]||t('Condition status unavailable.','حالة الظروف غير متاحة.')}</strong><br>${t('Physical comparability remains unverified. Values are shown side by side; do not interpret their difference as an effect of a single condition.','قابلية المقارنة الفيزيائية غير مثبتة. تُعرض القيم جنباً إلى جنب؛ لا تفسّر اختلافها على أنه أثر شرط واحد.')}</div>
        <section class="bass-condition-check"><h3>${t('Check the recorded conditions','فحص الظروف المسجلة')}</h3><p class="small">${t('Text matches show matching labels only. Different wording can describe similar material; matching labels do not prove equivalent conditions.','تطابق النص يعني تطابق التسمية فقط. قد يصف نص مختلف مادة متشابهة، ولا يثبت تطابق التسميات تكافؤ الظروف.')}</p>
        ${analysis.condition_checks.map(check=>`<div class="bass-condition-row"><span>${conditionLabels[check.criterion]}</span><strong class="bass-condition-${check.outcome.startsWith('different')?'different':check.outcome==='unavailable'?'unknown':'same'}">${conditionOutcomes[check.outcome]}</strong><small><bdi dir="auto">${esc(check.values[0]||'—')}</bdi> · <bdi dir="auto">${esc(check.values[1]||'—')}</bdi></small></div>`).join('')}</section>
        <div class="table-scroll"><table class="experiment-table"><thead><tr><th scope="col">${t('Recorded field','الحقل المسجل')}</th>${analysis.tests.map(x=>`<th scope="col"><bdi>${esc(x.investigator)} · ${esc(x.test)} · ${esc(x.date)}</bdi></th>`).join('')}</tr></thead>
        <tbody>${columns.map(([name,value])=>`<tr><th scope="row">${name}</th>${analysis.tests.map(x=>`<td><bdi dir="auto">${textValue(value(x))}</bdi></td>`).join('')}</tr>`).join('')}
        ${labels.map(([key,en,arabic])=>`<tr><th scope="row">${t(en,arabic)}<br><small>${esc(analysis.tests[0].measurements[key].unit)}</small></th>${analysis.tests.map(x=>`<td><bdi dir="ltr">${pairValue(x.measurements[key])}</bdi></td>`).join('')}</tr>`).join('')}</tbody></table></div>
        <p class="small">${t('Δ = final − initial within each test. Values are reproduced from the NASA table.','التغير = القيمة النهائية − الابتدائية داخل كل تجربة. القيم من جدول ناسا الأصلي.')}</p>
        <section class="bass-plot" aria-label="${t('Recorded oxygen values','قيم الأكسجين المسجلة')}"><h3>${t('Recorded oxygen values','قيم الأكسجين المسجلة')}</h3><p class="small">${t('Scale 0–100 % by volume. Select a bar for its source record.','المقياس من ٠ إلى ١٠٠٪ حجماً. اختر عموداً لعرض بيانات سجله.')}</p>${bars || `<p>${t('No plottable values in this selection.','لا توجد قيم قابلة للرسم في هذا الاختيار.')}</p>`}<output class="bass-plot-detail" aria-live="polite"></output></section>
        <details><summary>${t('Inspect the complete original source rows','عرض صفوف المصدر الأصلية كاملة')}</summary>${analysis.tests.map(test=>`<h4><bdi>${esc(test.investigator)} · ${esc(test.test)}</bdi></h4><div class="table-scroll"><table class="experiment-table"><tbody>${Object.entries(test.source_row).map(([key,value])=>`<tr><th scope="row"><bdi dir="auto">${esc(key)}</bdi></th><td><bdi dir="auto">${esc(value || '—')}</bdi></td></tr>`).join('')}</tbody></table></div>`).join('')}</details>
        <div class="input-row"><button class="button secondary bass-export" type="button">${t('Export analysis JSON','تنزيل التحليل JSON')}</button><button class="button secondary bass-replay" type="button">${t('Replay analysis','إعادة التحليل')}</button><button class="button secondary bass-ask" type="button">${t('Ask the research assistant','اسأل المساعد العلمي')}</button></div><p class="bass-replay-status small" role="status" aria-live="polite"></p>`;
      result.querySelectorAll('.bass-plot-bar').forEach(button => {
        const show = () => { result.querySelector('.bass-plot-detail').textContent = button.dataset.detail; };
        button.addEventListener('click', show); button.addEventListener('focus', show);
      });
      result.querySelector('.bass-export').addEventListener('click', () => {
        const url = URL.createObjectURL(new Blob([JSON.stringify(latest, null, 2)],{type:'application/json'}));
        const link = document.createElement('a'); link.href=url; link.download='mors-bass-ii-analysis.json'; link.click();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
      });
      result.querySelector('.bass-replay').addEventListener('click', async event => {
        const button = event.currentTarget, output = result.querySelector('.bass-replay-status');
        const original = latest, requestAtStart = sequence;
        button.disabled = true;
        output.textContent = t('Re-running the source check and calculation…','جارٍ إعادة فحص المصدر والحساب…');
        try {
          const [a,b] = original.reproducibility.row_indices_zero_based;
          const replay = await request('/combustion/bass-ii/compare', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({first_index:a,second_index:b})});
          if (!host.isConnected || requestAtStart !== sequence) return;
          output.textContent = JSON.stringify(replay) === JSON.stringify(original)
            ? t('Reproduced. Source checksum, parameters and calculated results match.', 'تمت إعادة الإنتاج. تطابقت بصمة المصدر والمدخلات والنتائج المحسوبة.')
            : t('Results differ. Review the source checksum, selected rows and method version in the exported records.', 'اختلفت النتائج. راجع بصمة المصدر والصفوف المحددة وإصدار الطريقة في السجلات المصدّرة.');
        } catch {
          if (host.isConnected && requestAtStart === sequence) output.textContent = t('Replay failed. Check the source table and retry.', 'تعذرت إعادة التحليل. تحقق من جدول المصدر وحاول مجدداً.');
        } finally { button.disabled = false; }
      });
      result.querySelector('.bass-ask').addEventListener('click', () => {
        try { sessionStorage.setItem('mors-bass-selection', JSON.stringify(latest.reproducibility.row_indices_zero_based)); sessionStorage.removeItem('mors-flame-selection'); sessionStorage.removeItem('mors-cool-selection'); } catch {}
        location.hash = '#intelligence';
      });
      status.textContent = t('Source values loaded. Choose different tests to recalculate.', 'تم تحميل قيم المصدر. اختر تجربتين أخريين لإعادة الحساب.');
    } catch (error) {
      if (host.isConnected && requestNumber === sequence) status.textContent = t('Comparison unavailable. Try again.', 'تعذرت المقارنة. حاول مجدداً.');
    }
  };
  request('/combustion/bass-ii').then(data => {
    if (!host.isConnected) return;
    status.textContent = t(`${data.rows.length} source records loaded.`, `تم تحميل ${data.rows.length} سجلاً من المصدر.`);
    if (data.rows.length < 2) { status.textContent = t('At least two source records are required.', 'يلزم توفر سجلين على الأقل.'); return; }
    const searchLabel = document.createElement('label');
    searchLabel.textContent = t('Search tests, investigator or fuel', 'البحث برقم التجربة أو الباحث أو الوقود');
    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = t('For example B1 or PMMA', 'مثلاً B1 أو PMMA');
    search.setAttribute('aria-label', searchLabel.textContent);
    searchLabel.append(search);
    host.insertBefore(searchLabel, host.querySelector('.input-row'));
    const populate = () => {
      const query = search.value.trim().toLocaleLowerCase();
      const matches = data.rows.map((row,index)=>({row,index})).filter(({row}) =>
        [row['PI'],row['Test #'],row['Date'],row['Fuel Sample Material']].some(value=>String(value || '').toLocaleLowerCase().includes(query)));
      const oldFirst=first.value, oldSecond=second.value;
      first.replaceChildren(); second.replaceChildren();
      for (const {row,index} of matches) {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = `${row['PI']} · ${row['Test #']} · ${row['Date']}`;
        first.append(option); second.append(option.cloneNode(true));
      }
      if (matches.length < 2) {
        first.disabled = second.disabled = true;
        ++sequence; latest=null; result.replaceChildren();
        status.textContent = t('Fewer than two matching tests. Broaden the search.', 'توجد أقل من تجربتين مطابقتين. وسّع البحث.');
        return;
      }
      first.disabled = second.disabled = false;
      first.value = matches.some(x=>String(x.index)===oldFirst) ? oldFirst : String(matches[0].index);
      second.value = matches.some(x=>String(x.index)===oldSecond && String(x.index)!==first.value) ? oldSecond : String(matches.find(x=>String(x.index)!==first.value).index);
      compare();
    };
    first.addEventListener('change', compare); second.addEventListener('change', compare);
    search.addEventListener('input', populate);
    populate();
  }).catch(() => {
    if (host.isConnected) status.textContent = t('The source table is unavailable or failed its integrity check. Reload to retry.', 'تعذر تحميل جدول المصدر أو فشل فحص سلامته. أعد تحميل الصفحة للمحاولة مجدداً.');
  });
}
