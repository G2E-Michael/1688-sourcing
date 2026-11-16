// 1688 photo search driver.
// The CLI's own `image-search` targets the retired s.1688.com/youyuan upload page
// and fails with STABLE_LOCATOR_NOT_FOUND; this drives the current widget on the
// offer-search page instead.
//
// Usage: node imgsearch.cjs <imagePath> [--max N] [--headed] [--out file.json]
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
}

const imagePath = process.argv[2];
const max = parseInt(arg('max', '40'), 10) || 40;
const headed = arg('headed', false) === true;
const outFile = arg('out', null);

function fail(code, message) {
  const payload = JSON.stringify({ ok: false, code, error: message });
  if (outFile) { fs.writeFileSync(outFile, payload, 'utf8'); }
  process.stdout.write(payload + '\n');
  process.exit(2);
}

if (!imagePath || !fs.existsSync(imagePath)) fail('BAD_INPUT', 'image not found: ' + imagePath);

function resolvePlaywright() {
  const candidates = [];
  if (process.env.BB1688_PLAYWRIGHT) candidates.push(process.env.BB1688_PLAYWRIGHT);
  try { candidates.push(path.join(execSync('npm root -g', { encoding: 'utf8' }).trim(), '1688-cli', 'node_modules', 'playwright-core')); } catch (e) {}
  candidates.push(path.join(process.env.APPDATA || '', 'npm', 'node_modules', '1688-cli', 'node_modules', 'playwright-core'));
  candidates.push(path.join(process.env.APPDATA || '', 'npm', 'node_modules', 'playwright-core'));
  for (const p of candidates) if (p && fs.existsSync(p)) return p;
  throw new Error('playwright-core not found — install 1688-cli globally (npm i -g 1688-cli)');
}

const CARD_SEL = '[class*="offerHoverWrapper"], [class*="offerCard"]';
const EXTRACT = `(() => {
  const cards = [...document.querySelectorAll('${CARD_SEL}')];
  const seen = new Set();
  const rows = [];
  for (const el of cards) {
    const txt = el.innerText || '';
    const title = ((el.querySelector('[class*="titleText"]') || {}).innerText || '').replace(/\\s+/g, ' ').trim();
    const price = ((el.querySelector('[class*="priceItem"]') || {}).innerText || '').replace(/\\s+/g, '');
    const shop = ((el.querySelector('[class*="shopName"]') || {}).innerText || '').trim();
    const years = ((el.querySelector('[class*="tpYear"]') || {}).innerText || '').trim();
    const rep = (txt.match(/回头率\\s*(\\d+)%/) || [])[1] || '';
    const imgEl = el.querySelector('img');
    const image = imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '';
    let offerId = '';
    const extra = el.querySelector('[data-extra*="offerId"]');
    if (extra) { try { offerId = JSON.parse(extra.getAttribute('data-extra')).offerId || ''; } catch (e) {} }
    if (!offerId) { const m = (el.innerHTML || '').match(/offerId["':\\s=]+(\\d{6,})/); if (m) offerId = m[1]; }
    if (!title && !image) continue;
    const key = offerId || title + '|' + image;
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push({ offerId, title, price, supplierName: shop, serviceYears: years, repurchaseRate: rep, image });
  }
  return { url: location.href, count: rows.length, rows };
})()`;

(async () => {
  const pw = require(resolvePlaywright());
  const profile = process.env.BB1688_PROFILE ||
    path.join(process.env.USERPROFILE || process.env.HOME || '.', '.1688', 'profiles', 'default');

  // the CLI daemon holds the profile lock; stop it before taking over
  const cmd = process.env.APPDATA ? path.join(process.env.APPDATA, 'npm', '1688.cmd') : null;
  if (cmd && fs.existsSync(cmd)) {
    try { execSync(`"${cmd}" daemon stop`, { stdio: 'ignore' }); } catch (e) {}
    await new Promise(r => setTimeout(r, 1500));
  }

  const ctx = await pw.chromium.launchPersistentContext(profile, {
    channel: 'chrome',
    headless: !headed,
    viewport: headed ? null : { width: 1600, height: 1000 },
    args: headed ? ['--start-maximized'] : [],
  });

  const result = { ok: false, imageId: null, url: null, rows: [] };
  try {
    const page = await ctx.newPage();
    await page.goto('https://s.1688.com/selloffer/offer_search.htm', { waitUntil: 'domcontentloaded', timeout: 60000 });
    if (/login\.1688\.com/.test(page.url())) throw new Error('NOT_LOGGED_IN: ' + page.url().slice(0, 160));
    await page.waitForSelector('input[type=file]', { timeout: 20000 });
    await page.locator('input[type=file]').first().setInputFiles(imagePath);
    await page.waitForSelector('text=已上传', { timeout: 25000 });
    await page.locator('text=搜索图片').last().click();

    let rows = [];
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(1000);
      if (/x5secdata=|\/punish/.test(page.url())) throw new Error('RISK_CONTROL: ' + page.url().slice(0, 160));
      const r = await page.evaluate(EXTRACT).catch(() => null);
      if (r && r.rows && r.rows.length > 0) { rows = r.rows; result.url = r.url; break; }
    }
    const m = (page.url() || '').match(/imageId=(\d+)/);
    result.imageId = m ? m[1] : null;
    result.url = result.url || page.url();
    result.rows = rows.slice(0, max);
    result.ok = true;
  } catch (e) {
    result.error = e.message || String(e);
  } finally {
    await ctx.close().catch(() => {});
  }

  const json = JSON.stringify(result, null, 1);
  if (outFile) { fs.writeFileSync(outFile, json, 'utf8'); process.stdout.write(json + '\n'); }
  else process.stdout.write(json + '\n');
})();
