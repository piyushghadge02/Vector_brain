/**
 * Shared Axios instance for all VectorBrain API calls.
 *
 * Same-origin `/api` by default: in production the frontend's nginx
 * reverse-proxies `/api/` to the backend, so no build-time URL is needed.
 * Set `VITE_API_BASE_URL` (see frontend/.env.example) only when the API
 * lives on a different origin. In dev, the Vite server proxies `/api`
 * to http://localhost:8000 (see vite.config.ts).
 * No secrets are ever stored here — the Groq API key lives server-side only.
 */
import axios, { type AxiosError } from 'axios'

export interface ApiErrorBody {
  code: string
  message: string
  request_id: string | null
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    // Normalize to the backend's error envelope when available.
    const body = error.response?.data
    const normalized = new Error(
      body?.message ?? error.message ?? 'Request failed',
    ) as Error & { code?: string; status?: number; requestId?: string | null }
    normalized.code = body?.code ?? 'NETWORK_ERROR'
    normalized.status = error.response?.status
    normalized.requestId = body?.request_id ?? null
    return Promise.reject(normalized)
  },
)

export default client
