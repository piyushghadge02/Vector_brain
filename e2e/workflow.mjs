/** Phase 6 end-to-end workflow for VectorBrain.
 *  Usage: node workflow.mjs [--skip-qa]
 *  Steps: upload 2 PDFs -> verify list -> verify processed+chunks ->
 *         Q&A x4 (needs GROQ_API_KEY on the backend) -> delete doc ->
 *         verify cascade + re-query.
 */
import axios from 'axios';
import FormData from 'form-data';
import fs from 'fs';

const API = 'http://127.0.0.1:8000/api';
const SKIP_QA = process.argv.includes('--skip-qa');
const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
};
const log = (...a) => console.log('      ', ...a);

const client = axios.create({ baseURL: API, timeout: 30000, headers: { 'Content-Type': 'application/json' } });
client.interceptors.response.use(
  (r) => r,
  (error) => {
    const body = error.response?.data;
    const e = new Error(body?.message ?? error.message ?? 'Request failed');
    e.code = body?.code ?? 'NETWORK_ERROR';
    e.status = error.response?.status;
    return Promise.reject(e);
  },
);

async function upload(path, name) {
  const form = new FormData();
  form.append('files', fs.createReadStream(path), name);
  try {
    const r = await client.post('/v1/documents/upload', form, {
      headers: { ...form.getHeaders(), 'Content-Type': undefined },
      timeout: 120000,
    });
    return r.data.documents[0];
  } catch (e) {
    if (e.code === 'DUPLICATE_DOCUMENT') {
      // Already uploaded by an earlier run — reuse the existing document.
      const list = (await client.get('/v1/documents', { params: { size: 100 } })).data;
      const existing = list.items.find((d) => d.original_name === name);
      if (existing) {
        console.log(`       (reusing existing ${name})`);
        return existing;
      }
    }
    throw e;
  }
}

async function waitProcessed(id, label) {
  for (let i = 0; i < 80; i++) {
    const { data } = await client.get(`/v1/documents/${id}`);
    if (data.status === 'processed') return data;
    if (data.status === 'failed') throw new Error(`${label} failed: ${data.error_message}`);
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(`${label} never reached processed`);
}

function hasKeywords(answer, kws) {
  const a = answer.toLowerCase();
  return kws.every((k) => a.includes(k.toLowerCase()));
}

// ── Steps 4-7: upload, list, processed, chunks ─────────────────────────
console.log('== Upload & ingestion ==');
const d1 = await upload('/tmp/zyvorg.pdf', 'zyvorg.pdf');
const d2 = await upload('/tmp/tides.pdf', 'tides.pdf');
check('upload PDF 1 -> 202', !!d1.id, `id=${d1.id.slice(0, 8)} status=${d1.status}`);
check('upload PDF 2 -> 202', !!d2.id, `id=${d2.id.slice(0, 8)} status=${d2.status}`);

const list = (await client.get('/v1/documents', { params: { size: 100 } })).data;
const names = list.items.map((d) => d.original_name);
check('both PDFs appear in document list', names.includes('zyvorg.pdf') && names.includes('tides.pdf'), names.join(', '));

const p1 = await waitProcessed(d1.id, 'zyvorg.pdf');
const p2 = await waitProcessed(d2.id, 'tides.pdf');
check('PDF 1 processed', p1.status === 'processed', `${p1.page_count} pages, ${p1.chunk_count} chunks`);
check('PDF 2 processed', p2.status === 'processed', `${p2.page_count} pages, ${p2.chunk_count} chunks`);

// ── Steps 8-16: Q&A (needs GROQ_API_KEY) ───────────────────────────────
if (!SKIP_QA) {
  console.log('== Q&A ==');
  async function ask(q) {
    const { data } = await client.post('/v1/chat/query', { question: q }, { timeout: 90000 });
    return data;
  }

  let r = await ask('Who invented the Zylorg synthesizer and when?');
  log('Q1 answer:', JSON.stringify(r.answer).slice(0, 220));
  log('Q1 sources:', r.sources.map((s) => `${s.filename} pp.${s.pages}`).join(', '));
  check('Q1 answer correct (Voss, 1974)', hasKeywords(r.answer, ['Voss', '1974']));
  check('Q1 cites zyvorg.pdf', r.sources.some((s) => s.filename === 'zyvorg.pdf'));

  r = await ask('What causes ocean tides, and where are the highest tides in the world?');
  log('Q2 answer:', JSON.stringify(r.answer).slice(0, 220));
  log('Q2 sources:', r.sources.map((s) => `${s.filename} pp.${s.pages}`).join(', '));
  check('Q2 answer correct (Moon, Fundy)', hasKeywords(r.answer, ['Moon', 'Fundy']));
  check('Q2 cites tides.pdf', r.sources.some((s) => s.filename === 'tides.pdf'));

  r = await ask('Who invented the Zylorg synthesizer, and what causes ocean tides?');
  log('Q3 answer:', JSON.stringify(r.answer).slice(0, 260));
  log('Q3 sources:', r.sources.map((s) => `${s.filename} pp.${s.pages}`).join(', '));
  const cited = new Set(r.sources.map((s) => s.filename));
  check('Q3 answer uses both facts', hasKeywords(r.answer, ['Voss', 'Moon']));
  check('Q3 cites BOTH documents', cited.has('zyvorg.pdf') && cited.has('tides.pdf'), [...cited].join(', '));

  r = await ask('What is the boiling point of tungsten?');
  log('Q4 answer:', JSON.stringify(r.answer).slice(0, 220));
  const honest = r.answer.toLowerCase().includes("don't have enough information");
  const hallucinating = /^\d{3,5}\s*°?c|degrees/i.test(r.answer);
  check('Q4 does not hallucinate (says insufficient info)', honest && !hallucinating);
  check('Q4 cites no sources', r.sources.length === 0);

  // ── Steps 17-18: delete + cascade ───────────────────────────────────
  console.log('== Delete & cascade ==');
  const del = await client.delete(`/v1/documents/${d1.id}`);
  check('DELETE zyvorg.pdf -> 204', del.status === 204);
  let gone = false;
  try { await client.get(`/v1/documents/${d1.id}`); } catch (e) { gone = e.status === 404; }
  check('deleted document -> 404', gone);

  r = await ask('Who invented the Zylorg synthesizer?');
  log('post-delete answer:', JSON.stringify(r.answer).slice(0, 200));
  check(
    'after delete, Q1 no longer answered from removed doc',
    r.answer.toLowerCase().includes("don't have enough information") && !r.sources.some((s) => s.filename === 'zyvorg.pdf'),
  );
}

const failed = results.filter((x) => !x).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
