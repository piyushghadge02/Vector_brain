import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  deleteDocument,
  getDocument,
  listDocuments,
  uploadDocuments,
  type DocumentOut,
  type DocumentStatus,
} from '../api/documents'

const SETTLED: DocumentStatus[] = ['processed', 'failed']

/** Document library state — backed by the real API. */
export const useDocumentsStore = defineStore('documents', () => {
  const items = ref<DocumentOut[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const uploading = ref(false)
  const uploadError = ref<string | null>(null)
  const deletingIds = ref<Set<string>>(new Set())

  const processedCount = computed(
    () => items.value.filter((d) => d.status === 'processed').length,
  )
  const unsettledCount = computed(
    () => items.value.filter((d) => !SETTLED.includes(d.status)).length,
  )

  function upsert(doc: DocumentOut): void {
    const idx = items.value.findIndex((d) => d.id === doc.id)
    if (idx >= 0) items.value[idx] = doc
    else items.value.unshift(doc)
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const list = await listDocuments()
      items.value = list.items
      // Resume watching anything still processing (e.g. after a reload).
      for (const doc of items.value) {
        if (!SETTLED.includes(doc.status)) void watchUntilSettled(doc.id)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load documents'
    } finally {
      loading.value = false
    }
  }

  /** Poll one document until it leaves pending/processing. */
  async function watchUntilSettled(id: string): Promise<void> {
    for (;;) {
      await new Promise((r) => setTimeout(r, 2000))
      try {
        const doc = await getDocument(id)
        upsert(doc)
        if (SETTLED.includes(doc.status)) return
      } catch {
        return // deleted mid-poll, or backend went away — stop quietly
      }
    }
  }

  async function uploadFiles(files: File[]): Promise<void> {
    const pdfs = files.filter(
      (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'),
    )
    uploadError.value = null
    if (!pdfs.length) {
      uploadError.value = 'Please choose PDF files to upload.'
      return
    }
    if (uploading.value) return
    uploading.value = true
    try {
      const docs = await uploadDocuments(pdfs)
      for (const doc of docs) {
        upsert(doc)
        if (!SETTLED.includes(doc.status)) void watchUntilSettled(doc.id)
      }
    } catch (e) {
      const code = (e as { code?: string })?.code
      uploadError.value =
        code === 'DUPLICATE_DOCUMENT' || (e as { status?: number })?.status === 409
          ? 'One of these PDFs was already uploaded.'
          : e instanceof Error
            ? e.message
            : 'Upload failed. Please try again.'
    } finally {
      uploading.value = false
    }
  }

  async function remove(id: string): Promise<void> {
    deletingIds.value.add(id)
    try {
      await deleteDocument(id)
      items.value = items.value.filter((d) => d.id !== id)
    } finally {
      deletingIds.value.delete(id)
    }
  }

  return {
    items,
    loading,
    error,
    uploading,
    uploadError,
    deletingIds,
    processedCount,
    unsettledCount,
    fetchAll,
    uploadFiles,
    remove,
  }
})
