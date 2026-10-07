/** API-integration check: replicates EXACTLY what the Vue frontend's
 *  api/ layer does (same endpoints, same multipart semantics, same error
 *  envelope handling), against the real backend. No browser needed.
 */
import axios from 'axios';
import FormData from 'form-data';
import fs from 'fs';

const API = 'http://127.0.0.1:8000/api';
const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
};

// Same normalization as frontend/src/api/client.ts
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
const norm = async (p) => { try { return await p; } catch (e) { return { __err: e }; } };

// 1. Health (sidebar status dot)
{
  const r = await client.get('/health');
  check('GET /health ok', r.data.status === 'ok', `groq_configured=${r.data.groq_configured}`);
}

// 2. List documents (sidebar initial load)
{
  const r = await client.get('/v1/documents', { params: { size: 100 } });
  check('GET /v1/documents returns items array', Array.isArray(r.data.items), `total=${r.data.total}`);
}

// 3. Upload PDF exactly like the frontend: FormData, no explicit Content-Type
let docId;
{
  const form = new FormData();
  form.append('files', fs.createReadStream('/home/hatch/workspace/vectorbrain/e2e/test-doc.pdf'), 'test-doc.pdf');
  const r = await client.post('/v1/documents/upload', form, {
    headers: { ...form.getHeaders(), 'Content-Type': undefined },
    timeout: 120000,
  });
  const doc = r.data.documents[0];
  docId = doc.id;
  check('POST /v1/documents/upload -> 202 with document', r.status === 202 && doc.original_name === 'test-doc.pdf', `status=${doc.status}`);
}

// 4. Poll until settled (frontend watchUntilSettled)
{
  let doc, tries = 0;
  do {
    await new Promise((r) => setTimeout(r, 3000));
    doc = (await client.get(`/v1/documents/${docId}`)).data;
    if (++tries > 80) break;
  } while (doc.status === 'pending' || doc.status === 'processing');
  check('document reaches processed', doc.status === 'processed', `status=${doc.status}, pages=${doc.page_count}, chunks=${doc.chunk_count}`);
}

// 5. Duplicate upload -> 409 (frontend shows "already uploaded")
{
  const form = new FormData();
  form.append('files', fs.createReadStream('/home/hatch/workspace/vectorbrain/e2e/test-doc.pdf'), 'test-doc.pdf');
  const r = await norm(client.post('/v1/documents/upload', form, { headers: { ...form.getHeaders(), 'Content-Type': undefined } }));
  check('duplicate upload -> 409', r.__err?.status === 409, `code=${r.__err?.code}`);
}

// 6. Chat without Groq key -> 503 envelope (frontend shows friendly message)
{
  const r = await norm(client.post('/v1/chat/query', { question: 'What is photosynthesis?' }, { timeout: 90000 }));
  const ok = r.__err?.status === 503 && r.__err?.code === 'LLM_NOT_CONFIGURED';
  check('POST /v1/chat/query -> 503 LLM_NOT_CONFIGURED (no key)', ok, r.__err?.message?.slice(0, 60));
}

// 7. Chat validation -> 422
{
  const r = await norm(client.post('/v1/chat/query', { question: 'ab' }));
  check('short question -> 422', r.__err?.status === 422);
}

// 8. Delete document (sidebar delete flow)
{
  const r = await client.delete(`/v1/documents/${docId}`);
  check('DELETE /v1/documents/:id -> 204', r.status === 204);
  const g = await norm(client.get(`/v1/documents/${docId}`));
  check('deleted doc -> 404', g.__err?.status === 404);
}

// 9. Non-PDF upload rejected (defense in depth; UI filters first)
{
  const form = new FormData();
  form.append('files', Buffer.from('not a pdf'), { filename: 'evil.txt', contentType: 'text/plain' });
  const r = await norm(client.post('/v1/documents/upload', form, { headers: { ...form.getHeaders(), 'Content-Type': undefined } }));
  check('non-PDF upload rejected', !!r.__err, `status=${r.__err?.status}`);
}

const failed = results.filter((x) => !x).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
