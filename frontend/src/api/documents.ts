import client from './client'
import {
  demoDeleteDocument,
  demoGetDocument,
  demoListDocuments,
  demoUploadDocuments,
  isDemoMode,
} from './demo'

export type DocumentStatus = 'pending' | 'processing' | 'processed' | 'failed'

export interface DocumentOut {
  id: string
  original_name: string
  mime_type: string
  file_size: number
  page_count: number | null
  chunk_count: number
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentListOut {
  items: DocumentOut[]
  total: number
  page: number
  size: number
}

export async function listDocuments(
  status?: DocumentStatus,
): Promise<DocumentListOut> {
  if (isDemoMode()) return demoListDocuments()
  const { data } = await client.get<DocumentListOut>('/v1/documents', {
    params: { status, size: 100 },
  })
  return data
}

export async function getDocument(id: string): Promise<DocumentOut> {
  if (isDemoMode()) return demoGetDocument(id)
  const { data } = await client.get<DocumentOut>(`/v1/documents/${id}`)
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  if (isDemoMode()) return demoDeleteDocument(id)
  await client.delete(`/v1/documents/${id}`)
}

export interface UploadResponse {
  documents: DocumentOut[]
}

/** Upload one or more PDFs. The instance default Content-Type (JSON) must be
 * cleared so the browser sets the multipart boundary itself. */
export async function uploadDocuments(files: File[]): Promise<DocumentOut[]> {
  if (isDemoMode()) return demoUploadDocuments(files)
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  const { data } = await client.post<UploadResponse>('/v1/documents/upload', form, {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    headers: { 'Content-Type': undefined } as any,
    timeout: 120_000,
  })
  return data.documents
}
