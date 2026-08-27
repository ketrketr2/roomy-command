const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const exe = process.env.PW_CHROME;   // サンドボックスでは /opt/pw-browsers/...、GitHub Actionsでは未設定（playwright標準解決）
  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  const errors = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 } });
  page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 200)));
  await page.goto('file://' + path.resolve('plain.html'));
  await page.waitForTimeout(2000);
  const views = ['hq','help','vs','flow','acq','ai','launch','aud','persona','sns','search','market','lab','dict','ulog'];
  const rep = {};
  for (const v of views) {
    await page.evaluate(vv => showView(vv), v);
    await page.waitForTimeout(500);
    rep[v] = await page.evaluate(vv => {
      const sec = document.querySelector(`.view[data-view="${vv}"]`);
      const empt = [...sec.querySelectorAll('canvas')].filter(c => !c.width).length;
      return sec.innerText.length + 'ch/' + sec.querySelectorAll('canvas').length + 'cv' + (empt?'/EMPTY'+empt:'');
    }, v);
  }
  console.log(JSON.stringify(rep));
  const head = await page.evaluate(() => { showView('hq'); return document.querySelector('.top').innerText.replace(/\n+/g,' '); });
  await page.waitForTimeout(600);
  console.log('header:', head.slice(0,140));
  await page.screenshot({ path: 'shot_v52.png', clip:{x:0,y:0,width:1440,height:900} });
  console.log('ERRORS:', errors.length ? errors.slice(0,5) : 'none');
  await browser.close();
})();
