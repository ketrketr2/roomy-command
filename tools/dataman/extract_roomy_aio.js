// ROOMY AIO の全43画面を、表モード（図をデータ表で出す）で描画して本文を取り出す
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');

function modFile(rel) { // パッケージの exports に縛られずに node_modules 内のファイルを探す
  const dirs = [...(require.resolve.paths(rel) || []), ...(process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean)];
  for (const d of dirs) { const p = path.join(d, rel); if (fs.existsSync(p)) return p; }
  throw new Error('not found: ' + rel);
}
const PLAIN = process.argv[2], TEXT = process.argv[3]; const src = path.join(PLAIN, 'roomy_aio.html'); const out = path.join(TEXT, 'roomy_aio');
fs.mkdirSync(out, { recursive: true });
if (!fs.existsSync(src)) { console.log('SKIP roomy_aio: 復号できていない'); process.exit(0); }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROME || undefined, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, reducedMotion: 'reduce', locale: 'ja-JP', timezoneId: 'Asia/Tokyo' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  await page.route('**/*', r => {
    const u = r.request().url();
    if (u.includes('d3.min.js')) return r.fulfill({ path: modFile('d3/dist/d3.min.js'), contentType: 'application/javascript' });
    if (u.startsWith('file://')) return r.continue();
    return r.abort();
  });
  await page.goto('file://' + src, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(3000);
  const screens = await page.evaluate(() => SCREENS.map(s => ({ id: s.id, code: s.code, group: s.group, title: s.title, sub: s.sub, nav: s.nav || '' })));
  fs.writeFileSync(path.join(out, '_screens.json'), JSON.stringify(screens, null, 1));
  // 表モード
  await page.evaluate(() => { try { setState({ tables: true }); applyTables(); } catch (e) {} });
  for (const s of screens) {
    try {
      await page.evaluate(id => { show(id, { initial: true }); }, s.id);
      await page.waitForTimeout(s.id === 'd2' || s.id === 'd1' ? 4000 : 1500);
      // 遅延描画（スクロールで出るブロック）を全部出す
      await page.evaluate(async id => {
        const el = document.getElementById('s-' + id); if (!el) return;
        el.querySelectorAll('.rv').forEach(b => b.classList.add('in'));
        const st = document.scrollingElement; for (let y = 0; y < el.scrollHeight; y += 700) { st.scrollTop = y; await new Promise(r => setTimeout(r, 60)); }
        st.scrollTop = 0;
      }, s.id);
      await page.waitForTimeout(800);
      const txt = await page.evaluate(id => {
        const el = document.getElementById('s-' + id); if (!el) return '';
        // SVG のテキストも拾う（innerText は SVG を含まないことがある）
        const clone = el.cloneNode(true);
        clone.querySelectorAll('svg').forEach(svg => {
          const t = Array.from(svg.querySelectorAll('text')).map(x => x.textContent.trim()).filter(Boolean);
          const rep = document.createElement('div'); rep.textContent = t.length ? '［図の文字］' + t.join(' ／ ') : '';
          svg.replaceWith(rep);
        });
        clone.querySelectorAll('canvas').forEach(c => { const rep = document.createElement('div'); rep.textContent = '［キャンバス図］'; c.replaceWith(rep); });
        document.body.appendChild(clone); clone.style.position = 'absolute'; clone.style.left = '-99999px'; clone.hidden = false;
        const t = clone.innerText; clone.remove(); return t;
      }, s.id);
      fs.writeFileSync(path.join(out, `${s.code}_${s.id}.txt`), txt);
      console.log('OK', s.code, s.id, txt.length);
    } catch (e) { console.log('FAIL', s.id, String(e).slice(0, 200)); }
  }
  fs.writeFileSync(path.join(out, '_errors.txt'), errs.join('\n'));
  console.log('page errors:', errs.length);
  await browser.close();
})();
