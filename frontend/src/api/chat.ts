import client from './client'
import { demoAskQuestion, isDemoMode } from './demo'

export interface SourceOut {
  document_id: string
  filename: string
  chunk_id: string
  pages: number[]
  heading: string
  snippet: string
  similarity: number
}

export interface QueryResponse {
  answer: string
  sources: SourceOut[]
  model: string
  latency_ms: number
}

/** Ask a question across all processed documents. */
export async function askQuestion(question: string): Promise<QueryResponse> {
  if (isDemoMode()) return demoAskQuestion(question)
  // RAG calls can take a while (retrieval + LLM); allow more than the
  // instance default.
  const { data } = await client.post<QueryResponse>(
    '/v1/chat/query',
    { question },
    { timeout: 90_000 },
  )
  return data
}

/** Turn a backend/normalized error into something a human can act on. */
export function friendlyChatError(e: unknown): string {
  const code = (e as { code?: string })?.code
  switch (code) {
    case 'LLM_NOT_CONFIGURED':
      return (
        "AI answers aren't set up on the server yet (the Groq API key is " +
        'missing). Your documents are still searchable — ask whoever runs ' +
        'the backend to configure it.'
      )
    case 'LLM_UPSTREAM_ERROR':
      return 'The AI service stumbled. Please try again in a moment.'
    case 'RATE_LIMITED':
      return 'Too many questions at once — wait a moment and try again.'
    case 'NETWORK_ERROR':
      return "Couldn't reach the backend. Check that it's running and try again."
    default:
      return e instanceof Error && e.message
        ? e.message
        : 'Something went wrong. Please try again.'
  }
}
