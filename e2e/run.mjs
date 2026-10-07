/** Local E2E for the VectorBrain frontend (Phase 5). Drives the real
 *  Chromium at /opt/meta-chromium/chrome against local dev servers.
 *  Prints PASS/FAIL per check plus all console errors. Exits nonzero on failure.
 */
import { chromium } from 'playwright-core';

const FRONTEND = 'http://127.0.0.1:5173/';
const PDF = '/home/hatch/workspace/vectorbrain/e2e/test-doc.pdf';
const shot = (p, name) => p.screenshot({ path: `/home/hatch/workspace/vectorbrain/e2e/${name}.png` });

const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
};

const browser = await chromium.launch({
  executablePath: '/opt/meta-chromium/chrome',
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests',
  ],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));

// 1. Load
await page.goto(FRONTEND, { waitUntil: 'networkidle' });
check('page loads, branding visible', await page.getByText('VectorBrain').first().isVisible());
await shot(page, '01-desktop');

// 2. Upload PDF, wait for processed
await page.locator('input[type="file"]').setInputFiles(PDF);
const docRow = page.locator('li', { hasText: 'test-doc.pdf' });
await docRow.waitFor({ timeout: 15000 });
check('uploaded doc appears in sidebar', true);
await page.waitForFunction(
  () => document.body.innerText.includes('processed'),
  { timeout: 240000 },
);
const rowText = await docRow.first().innerText();
check('doc reaches processed status', rowText.includes('processed'), rowText.replace(/\n/g, ' | ').slice(0, 120));
await shot(page, '02-doc-processed');

// 3. Ask a question (no Groq key -> graceful 503 error expected)
await page.getByPlaceholder('Ask anything about your documents…').fill('What is photosynthesis?');
await page.getByTitle('Send question').click();
await page.waitForSelector('text=Searching your documents…', { timeout: 10000 }).catch(() => {});
await page.waitForFunction(
  () => !document.body.innerText.includes('Searching your documents…'),
  { timeout: 90000 },
);
const chatText = await page.locator('main').innerText();
check(
  'graceful error for unconfigured LLM (no crash)',
  chatText.includes("AI answers aren't set up") || chatText.includes('Groq'),
  chatText.slice(0, 160).replace(/\n/g, ' '),
);
check('try-again button shown on error', await page.getByText('Try again').first().isVisible());
await shot(page, '03-chat-error');

// 4. Empty input -> send disabled
await page.getByPlaceholder('Ask anything about your documents…').fill('');
check('send disabled on empty input', await page.getByTitle('Send question').isDisabled());

// 5. Delete the document (two-click confirm)
await docRow.first().hover();
await docRow.first().getByTitle('Delete document').click();
await docRow.first().getByText('Sure?').click();
await page.waitForFunction(() => !document.body.innerText.includes('test-doc.pdf'), { timeout: 15000 });
check('document deleted from sidebar', true);

// 6. Mobile viewport + drawer
await page.setViewportSize({ width: 390, height: 844 });
await page.reload({ waitUntil: 'networkidle' });
const hamburger = page.getByTitle('Documents');
check('hamburger visible on mobile', await hamburger.isVisible());
check('sidebar hidden on mobile', !(await page.getByText('Upload PDFs').isVisible()));
await hamburger.click();
await page.waitForTimeout(400);
check('drawer opens with upload button', await page.getByText('Upload PDFs').isVisible());
await shot(page, '04-mobile-drawer');

// 7. Console errors
const realErrors = consoleErrors.filter((e) => !e.includes('favicon'));
check('no console errors', realErrors.length === 0, realErrors.slice(0, 3).join(' || '));

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
