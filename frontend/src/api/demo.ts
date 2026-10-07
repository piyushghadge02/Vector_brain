/**
 * Demo mode for the static preview build ONLY.
 *
 * When `VITE_DEMO_MODE=true` (set at build time for the preview), every API
 * function returns realistic sample data instead of hitting the backend, so
 * the UI can be explored without PostgreSQL/Groq. The production build never
 * sets this flag — it always talks to the real API.
 */
import type { QueryResponse, SourceOut } from './chat'
import type { DocumentListOut, DocumentOut } from './documents'
import type { HealthStatus } from './health'

export const isDemoMode = (): boolean =>
  import.meta.env.VITE_DEMO_MODE === 'true'

const wait = (ms: number): Promise<void> =>
  new Promise((r) => setTimeout(r, ms))

let seq = 100
const uid = (): string => `demo-${seq++}`

const docs = new Map<string, DocumentOut>([
  [
    'demo-1',
    {
      id: 'demo-1',
      original_name: 'zyvorg.pdf',
      mime_type: 'application/pdf',
      file_size: 1904,
      page_count: 1,
      chunk_count: 1,
      status: 'processed',
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
  [
    'demo-2',
    {
      id: 'demo-2',
      original_name: 'tides.pdf',
      mime_type: 'application/pdf',
      file_size: 1875,
      page_count: 1,
      chunk_count: 1,
      status: 'processed',
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
])

function src(
  filename: string,
  chunkId: string,
  pages: number[],
  heading: string,
  snippet: string,
  similarity: number,
): SourceOut {
  return {
    document_id: filename === 'zyvorg.pdf' ? 'demo-1' : 'demo-2',
    filename,
    chunk_id: chunkId,
    pages,
    heading,
    snippet,
    similarity,
  }
}

const ZYVORG_ANSWER =
  'The Zylorg synthesizer was invented in 1974 by Dr. Elena Voss [1].'
const TIDES_ANSWER =
  'Ocean tides are mainly produced by the gravitational pull of the Moon on ' +
  "Earth's oceans, with the Sun adding a smaller effect [1]. The highest " +
  'tides in the world occur in the Bay of Fundy in Canada, reaching up to ' +
  '16 meters.'
const BOTH_ANSWER =
  'The Zylorg synthesizer was invented in 1974 by Dr. Elena Voss [1]. ' +
  'Ocean tides are produced mainly by the gravitational pull of the Moon ' +
  "on Earth's oceans, with the Sun adding a smaller effect [2]."
const NO_INFO_ANSWER =
  "I don't have enough information in the uploaded documents to answer that."

export async function demoGetHealth(): Promise<HealthStatus> {
  await wait(300)
  return {
    status: 'ok',
    service: 'VectorBrain',
    env: 'demo',
    database: 'connected',
    pgvector: 'available',
    embeddings: 'loaded',
    groq_configured: true,
  }
}

export async function demoListDocuments(): Promise<DocumentListOut> {
  await wait(400)
  const items = [...docs.values()]
  return { items, total: items.length, page: 1, size: 100 }
}

export async function demoGetDocument(id: string): Promise<DocumentOut> {
  await wait(200)
  const doc = docs.get(id)
  if (!doc) {
    const e = new Error('Document not found.') as Error & { code?: string; status?: number }
    e.code = 'NOT_FOUND'
    e.status = 404
    throw e
  }
  return doc
}

export async function demoUploadDocuments(files: File[]): Promise<DocumentOut[]> {
  await wait(1500)
  return files.map((f) => {
    const doc: DocumentOut = {
      id: uid(),
      original_name: f.name,
      mime_type: 'application/pdf',
      file_size: f.size,
      page_count: 3,
      chunk_count: 4,
      status: 'processed',
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    docs.set(doc.id, doc)
    return doc
  })
}

export async function demoDeleteDocument(id: string): Promise<void> {
  await wait(300)
  docs.delete(id)
}

export async function demoAskQuestion(question: string): Promise<QueryResponse> {
  await wait(1600)
  const q = question.toLowerCase()
  const aboutZyvorg = /zyvorg|synthesizer|invented|voss/.test(q)
  const aboutTides = /tide|moon|fundy|ocean/.test(q)

  let answer = NO_INFO_ANSWER
  let sources: SourceOut[] = []
  if (aboutZyvorg && aboutTides) {
    answer = BOTH_ANSWER
    sources = [
      src('zyvorg.pdf', 'demo-c1', [1], '', 'The Zylorg synthesizer was invented in 1974 by Dr. Elena Voss in Oslo, Norway.', 0.91),
      src('tides.pdf', 'demo-c2', [1], '', 'Tides are primarily caused by the gravitational pull of the Moon on Earth\'s oceans.', 0.88),
    ]
  } else if (aboutZyvorg) {
    answer = ZYVORG_ANSWER
    sources = [
      src('zyvorg.pdf', 'demo-c1', [1], '', 'The Zylorg synthesizer was invented in 1974 by Dr. Elena Voss in Oslo, Norway.', 0.91),
    ]
  } else if (aboutTides) {
    answer = TIDES_ANSWER
    sources = [
      src('tides.pdf', 'demo-c2', [1], '', 'Tides are primarily caused by the gravitational pull of the Moon on Earth\'s oceans.', 0.88),
    ]
  }
  return { answer, sources, model: 'openai/gpt-oss-120b', latency_ms: 1600 }
}
