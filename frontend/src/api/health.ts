import client from './client'
import { demoGetHealth, isDemoMode } from './demo'

export interface HealthStatus {
  status: 'ok' | 'degraded'
  service: string
  env: string
  database: string
  pgvector: string
  embeddings: string
  groq_configured: boolean
}

export async function getHealth(): Promise<HealthStatus> {
  if (isDemoMode()) return demoGetHealth()
  const { data } = await client.get<HealthStatus>('/health')
  return data
}
