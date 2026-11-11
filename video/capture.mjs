// Takes the screenshots for the explainer video from the local test environment
// (scratchpad runner on :8095 with test data – no real names or links).
// Usage: node capture.mjs [setup|cockpit|mobile|all]
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const BASE = 'http://localhost:8095';
const OUT = new URL('./public/shots/', import.meta.url).pathname;
fs.mkdirSync(OUT, { recursive: true });
const what = process.argv[2] || 'all';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--lang=de-DE', '--hide-scrollbars'],
});

async function shot(page, name, full = false) {
  await sleep(500);
  await page.screenshot({ path: OUT + name + '.png', fullPage: full });
  console.log('shot', name);
}

async function typeSlow(page, sel, text) {
  await page.click(sel, { clickCount: 3 });
  await page.type(sel, text, { delay: 10 });
}

async function clickText(page, text, sel = 'button, a') {
  const ok = await page.evaluate((text, sel) => {
    const el = [...document.querySelectorAll(sel)].find((x) => x.textContent.replace(/\s+/g, ' ').trim().startsWith(text) && x.offsetParent);
    if (el) { el.click(); return true; }
    return false;
  }, text, sel);
  if (!ok) console.log('not found:', text);
  await sleep(1500);
}

const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 2 };
const PHONE = { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true };

let cookies = null;
if (fs.existsSync(OUT + '../cookies.json')) cookies = JSON.parse(fs.readFileSync(OUT + '../cookies.json', 'utf8'));

if (what === 'setup' || what === 'all') {
  const invite = await (await fetch(BASE + '/__dev/invite?name=Anna%20Beispiel')).json();
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport(DESKTOP);
  await page.goto(invite.link, { waitUntil: 'load' });
  await shot(page, 'setup-01-invite');
  await typeSlow(page, '#invite-first', 'Anna');
  await typeSlow(page, '#invite-last', 'Beispiel');
  await typeSlow(page, '#invite-code', 'Sonnenblume' + Math.floor(Math.random() * 1e6));
  await page.click('#invite-terms');
  await shot(page, 'setup-02-invite-filled');
  await Promise.all([page.waitForNavigation({ waitUntil: 'load' }).catch(() => {}), page.click('#invite-btn')]);
  await sleep(1500);
  console.log('after invite:', page.url());
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, 'setup-03-after-invite', true);
  // Onboarding: WebUntis link
  const field = await page.$('input[name="ical_url"]');
  if (field) {
    await page.type('input[name="ical_url"]', 'https://beispiel.webuntis.com/WebUntis/ical.do?school=beispiel-schule&elemType=2&elemId=123&rpt_sd=2026-11-09&key=7Kq2Xw9LmP4t', { delay: 0 });
    await page.$eval('input[name="ical_url"]', (el) => { el.setSelectionRange(0, 0); el.scrollLeft = 0; });
    await shot(page, 'setup-04-link-pasted', true);
    await page.click('#setup-next');
    await sleep(3000);
    await shot(page, 'setup-05-after-link', true);
    await page.click('#setup-next');
    await sleep(2500);
    console.log('after done:', page.url());
  }
  cookies = await page.cookies();
  fs.writeFileSync(OUT + '../cookies.json', JSON.stringify(cookies));
  await ctx.close();
}

async function cockpitPage(viewport) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport(viewport);
  if (viewport.isMobile) {
    await page.setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1');
  }
  await page.setCookie(...cookies);
  await page.goto(BASE + '/?multiuser=1', { waitUntil: 'load' });
  await sleep(2500);
  return { ctx, page };
}

if (what === 'cockpit' || what === 'all') {
  const { ctx, page } = await cockpitPage(DESKTOP);
  console.log('cockpit url', page.url());
  // Hide the "Dein Cockpit kann noch mehr" hint for the overview shots
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Nicht mehr anzeigen');
    if (b) b.click();
  });
  if (process.env.ADD_TASKS) {
    for (const t of ['Kopien Arbeitsblatt 8b bis Fr', 'Elternbrief Wandertag 7c austeilen', 'Noten 10a eintragen']) {
      const input = await page.$('input[placeholder^="z. B."]');
      await input.click({ clickCount: 3 });
      await input.type(t);
      await page.keyboard.press('Enter');
      await sleep(800);
    }
  }
  await sleep(800);
  await shot(page, 'cockpit-01-heute');
  await shot(page, 'cockpit-01-heute-full', true);
  await clickText(page, 'Woche');
  await shot(page, 'cockpit-02-woche');
  await clickText(page, 'Tag');
  await clickText(page, 'Posteingang', 'nav a, nav button, aside a, aside button');
  await shot(page, 'cockpit-03-posteingang');
  await clickText(page, 'Termine', 'nav a, nav button, aside a, aside button');
  await shot(page, 'cockpit-04-termine');
  await clickText(page, 'Heute', 'nav a, nav button, aside a, aside button');
  await ctx.close();
}

if (what === 'pages') {
  const { ctx, page } = await cockpitPage(DESKTOP);
  await clickText(page, 'Notenrechner', 'nav a, nav button, aside a, aside button');
  const fields = await page.$$('input[placeholder^="z. B. 2"]');
  const grades = ['2 3+ 2- 1 2', '2 1- 2+ 3 2 1'];
  for (let i = 0; i < fields.length && i < 2; i++) await fields[i].type(grades[i], { delay: 20 });
  await page.keyboard.press('Tab');
  await shot(page, 'page-noten');
  await ctx.close();
}

if (what === 'mobile' || what === 'all') {
  const { ctx, page } = await cockpitPage(PHONE);
  await shot(page, 'phone-01-heute');
  await page.evaluate(() => window.scrollTo(0, 560));
  await shot(page, 'phone-02-scrolled');
  await ctx.close();
}

await browser.close();
