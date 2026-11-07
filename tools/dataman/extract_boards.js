// ゲート付きボード（ROOMY AIO 以外）の全画面を描画して本文・図の数値を取り出す
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');

function modFile(rel) { // パッケージの exports に縛られずに node_modules 内のファイルを探す
  const dirs = [...(require.resolve.paths(rel) || []), ...(process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean)];
  for (const d of dirs) { const p = path.join(d, rel); if (fs.existsSync(p)) return p; }
  throw new Error('not found: ' + rel);
}
const PLAIN = process.argv[2], TEXT = process.argv[3]; const only = process.argv[4];
const CFG = {
  roomy_command: { nav: 'button.mi[data-view]', id: 'data-view' },
  car_signal:    { nav: 'nav#tabs button.tab[data-v]', id: 'data-v' },
  car_deepdive:  { nav: '#nav button.nv[data-v]', id: 'data-v' },
  ucar_signal:   { nav: '#tabs button.tab[data-tab]', id: 'data-tab' },
  ga4_command:   { nav: 'nav#nav button[data-view]', id: 'data-view' },
};
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROME || undefined, args: ['--no-sandbox'] });
  for (let [name, cfg] of Object.entries(CFG)) {
    if (only && only !== name) continue;
    if (!fs.existsSync(path.join(PLAIN, name + '.html'))) { console.log('SKIP', name, '復号できていない'); continue; }
    const out = path.join(TEXT, name); fs.mkdirSync(out, { recursive: true });
    const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, reducedMotion: 'reduce', locale: 'ja-JP', timezoneId: 'Asia/Tokyo' });
    const page = await ctx.newPage(); const errs = [];
    page.on('pageerror', e => errs.push(String(e)));
    await page.route('**/*', r => {
      const u = r.request().url();
      if (u.includes('echarts')) return r.fulfill({ path: modFile('echarts/dist/echarts.min.js'), contentType: 'application/javascript' });
      if (u.includes('d3.min.js')) return r.fulfill({ path: modFile('d3/dist/d3.min.js'), contentType: 'application/javascript' });
      if (u.startsWith('file://')) return r.continue();
      return r.abort();
    });
    await page.goto('file://' + path.join(PLAIN, name + '.html'), { waitUntil: 'load', timeout: 120000 });
    await page.waitForTimeout(3000);
    // 画面の切り替えボタンを探す。決め打ちの場所に無いとき（ボードの作り替え等）は、よくある形を順に試す。
    // それでも無ければ「1枚もの」とみなしてページ全体を1画面として読む（2026-11-07: U-CAR SIGNAL v06 で 0画面になった対策）
    const navOf = (sel, attr) => page.$$eval(sel, (bs, attr) => bs.map(b => ({ id: b.getAttribute(attr), label: b.innerText.replace(/\s+/g, ' ').trim() })), attr);
    const uniq = arr => { const seen = new Set(); return arr.filter(n => n.id && !n.id.includes('${') && !seen.has(n.id) && seen.add(n.id)); };
    let list = uniq(await navOf(cfg.nav, cfg.id));
    let single = false;
    if (list.length === 0) {
      const tries = [['[data-tab]', 'data-tab'], ['[data-view]', 'data-view'], ['[data-v]', 'data-v'], ['[data-page]', 'data-page'],
                     ['[data-target]', 'data-target'], ['[role="tab"][aria-controls]', 'aria-controls'], ['nav a[href^="#"]', 'href']];
      for (const [sel, attr] of tries) {
        const l = uniq(await navOf(sel, attr)).filter(n => n.label);
        if (l.length >= 2) { cfg = { nav: sel, id: attr }; list = l; console.log('AUTO', name, 'nav', sel, l.length); break; }
      }
    }
    if (list.length === 0) {
      single = true;
      list = [{ id: 'main', label: (await page.title()) || name }];
      console.log('AUTO', name, '画面の切り替えが見つからないので、ページ全体を1画面として読む');
    }
    fs.writeFileSync(path.join(out, '_screens.json'), JSON.stringify(list, null, 1));
    let k = 0;
    for (const n of list) {
      k++;
      try {
        if (!single) {
          await page.evaluate(({ sel, attr, id }) => { const b = Array.from(document.querySelectorAll(sel)).find(x => x.getAttribute(attr) === id); b && b.click(); }, { sel: cfg.nav, attr: cfg.id, id: n.id });
          await page.waitForTimeout(1800);
        }
        await page.evaluate(async () => { const st = document.scrollingElement; for (let y = 0; y < st.scrollHeight; y += 800) { st.scrollTop = y; await new Promise(r => setTimeout(r, 50)); } st.scrollTop = 0; });
        await page.waitForTimeout(600);
        const res = await page.evaluate((single) => {
          const vis = el => el && el.offsetParent !== null && el.getClientRects().length > 0;
          const cands = [...document.querySelectorAll('section.view.on, .view.on, #main, main, .content, #content')].filter(vis);
          let root = cands.sort((a, b) => b.innerText.length - a.innerText.length)[0] || document.body;
          const clone = root.cloneNode(true);
          clone.querySelectorAll('nav, aside, script, style').forEach(x => x.remove());
          clone.querySelectorAll('svg').forEach(svg => { const t = Array.from(svg.querySelectorAll('text')).map(x => x.textContent.trim()).filter(Boolean); const rep = document.createElement('div'); rep.textContent = t.length ? '［図の文字］' + t.join(' ／ ') : ''; svg.replaceWith(rep); });
          clone.querySelectorAll('canvas').forEach(c => { const rep = document.createElement('div'); rep.textContent = '［図］'; c.replaceWith(rep); });
          document.body.appendChild(clone); clone.style.position = 'absolute'; clone.style.left = '-99999px'; clone.style.width = '1400px';
          let text = clone.innerText; clone.remove();
          if (single) {
            // 1枚ものとして読むときは、隠れている画面（タブ等）の文字も拾う
            const hidden = [...document.querySelectorAll('section, article, [class*="view"], [class*="panel"], [class*="tab"], [class*="page"]')]
              .filter(el => !vis(el) && (el.textContent || '').trim().length > 80 && !el.closest('script,style,template'));
            const top = hidden.filter(el => !hidden.some(o => o !== el && o.contains(el)));
            for (const el of top.slice(0, 60)) text += '\n\n［非表示の画面］\n' + el.textContent.replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
          }
          // 図の元データ（Chart.js / ECharts）
          const charts = [];
          try { if (window.Chart && Chart.instances) Object.values(Chart.instances).forEach(ch => { if (!vis(ch.canvas)) return; const d = ch.data || {}; const title = (ch.options && ch.options.plugins && ch.options.plugins.title && ch.options.plugins.title.text) || ch.canvas.getAttribute('aria-label') || ch.canvas.id || ''; charts.push({ lib: 'chartjs', title: String(title), type: ch.config.type, labels: (d.labels || []).map(String).slice(0, 400), datasets: (d.datasets || []).map(s => ({ label: String(s.label || ''), data: (s.data || []).slice(0, 400).map(v => (typeof v === 'object' && v !== null) ? (v.y ?? v.v ?? JSON.stringify(v)) : v) })) }); }); } catch (e) {}
          try { if (window.echarts) document.querySelectorAll('[_echarts_instance_]').forEach(el => { if (!vis(el)) return; const inst = echarts.getInstanceByDom(el); if (!inst) return; const o = inst.getOption(); charts.push({ lib: 'echarts', title: ((o.title || [])[0] || {}).text || el.id || '', xAxis: ((o.xAxis || [])[0] || {}).data ? ((o.xAxis || [])[0].data || []).slice(0, 400) : undefined, yAxis: ((o.yAxis || [])[0] || {}).data ? ((o.yAxis || [])[0].data || []).slice(0, 400) : undefined, series: (o.series || []).map(s => ({ name: s.name || '', type: s.type, data: (s.data || []).slice(0, 400).map(v => (v && typeof v === 'object') ? (v.value !== undefined ? (v.name !== undefined ? [v.name, v.value] : v.value) : JSON.stringify(v)) : v) })) }); }); } catch (e) {}
          return { text, charts };
        }, single);
        const fn = `${String(k).padStart(2, '0')}_${n.id.replace(/[^\w-]/g, '_')}`;
        fs.writeFileSync(path.join(out, fn + '.txt'), `# ${n.label}\n\n` + res.text);
        if (res.charts.length) fs.writeFileSync(path.join(out, fn + '.charts.json'), JSON.stringify(res.charts));
        console.log('OK', name, n.id, res.text.length, 'charts', res.charts.length);
      } catch (e) { console.log('FAIL', name, n.id, String(e).slice(0, 160)); }
    }
    fs.writeFileSync(path.join(out, '_errors.txt'), errs.join('\n'));
    console.log(name, 'page errors', errs.length, errs.slice(0, 3).join(' | ').slice(0, 300));
    await ctx.close();
  }
  await browser.close();
})();
