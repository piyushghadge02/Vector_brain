<template>
  <aside class="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-white">
    <!-- Branding -->
    <div class="flex items-center gap-2.5 border-b border-slate-100 px-4 py-4">
      <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900">
        <svg viewBox="0 0 24 24" class="h-5 w-5 text-white" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="7" cy="7" r="2.2"/><circle cx="17" cy="7" r="2.2"/>
          <circle cx="7" cy="17" r="2.2"/><circle cx="17" cy="17" r="2.2"/>
          <circle cx="12" cy="12" r="2.2"/>
          <path d="M8.6 8.2l1.8 1.8M15.4 8.2l-1.8 1.8M8.6 15.8l1.8-1.8M15.4 15.8l-1.8-1.8"/>
        </svg>
      </span>
      <div>
        <p class="text-base font-bold leading-tight text-slate-900">VectorBrain</p>
        <p class="text-xs text-slate-500">Research workspace</p>
      </div>
    </div>

    <!-- Upload -->
    <div class="border-b border-slate-100 px-4 py-3">
      <label
        class="flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
        :class="{ 'pointer-events-none opacity-60': documents.uploading }"
      >
        <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 16V4m0 0l-4 4m4-4l4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>
        </svg>
        {{ documents.uploading ? 'Uploading…' : 'Upload PDFs' }}
        <input
          type="file"
          accept=".pdf,application/pdf"
          multiple
          class="hidden"
          :disabled="documents.uploading"
          @change="onFilesChosen"
        />
      </label>
      <p class="mt-1.5 text-xs text-slate-500">
        Questions search across
        <span class="font-medium text-slate-700">{{ documents.processedCount }} processed document{{ documents.processedCount === 1 ? '' : 's' }}</span>.
      </p>
      <div
        v-if="documents.uploadError"
        class="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700"
      >
        {{ documents.uploadError }}
      </div>
    </div>

    <!-- Document list -->
    <div class="flex-1 overflow-y-auto px-3 py-2">
      <div
        v-if="documents.loading && !documents.items.length"
        class="px-2 py-6 text-center text-sm text-slate-500"
      >
        Loading documents…
      </div>
      <div
        v-else-if="documents.error"
        class="mx-1 mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700"
      >
        {{ documents.error }}
        <button class="mt-1 font-medium underline" @click="documents.fetchAll()">Retry</button>
      </div>
      <div
        v-else-if="!documents.items.length"
        class="rounded-xl border border-dashed border-slate-300 px-3 py-8 text-center"
      >
        <p class="text-sm font-medium text-slate-700">No documents yet</p>
        <p class="mt-1 text-xs text-slate-500">Upload PDFs above, then ask anything about them.</p>
      </div>
      <ul v-else class="space-y-1.5">
        <li
          v-for="doc in documents.items"
          :key="doc.id"
          class="group rounded-xl border border-slate-200 bg-slate-50/60 px-3 py-2.5"
        >
          <div class="flex items-start gap-2">
            <svg viewBox="0 0 24 24" class="mt-0.5 h-5 w-5 shrink-0 text-red-500" fill="currentColor">
              <path d="M6 2h9l5 5v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm8 1.5V8h4.5L14 3.5zM8 13h8v1.5H8V13zm0 3.5h8V18H8v-1.5z"/>
            </svg>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-slate-900" :title="doc.original_name">
                {{ doc.original_name }}
              </p>
              <p class="mt-0.5 text-xs text-slate-500">
                {{ formatSize(doc.file_size) }}
                <span v-if="doc.page_count !== null"> · {{ doc.page_count }} pages</span>
                <span v-if="doc.status === 'processed'"> · {{ doc.chunk_count }} chunks</span>
                <span v-if="doc.status === 'processing' || doc.status === 'pending'" class="animate-pulse"> · working…</span>
              </p>
              <p v-if="doc.status === 'failed' && doc.error_message" class="mt-1 text-xs text-red-600">
                {{ doc.error_message }}
              </p>
            </div>
            <button
              v-if="!confirmDeleteId || confirmDeleteId !== doc.id"
              @click="confirmDeleteId = doc.id"
              :disabled="documents.deletingIds.has(doc.id)"
              class="rounded p-1 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
              title="Delete document"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m3 0l-.8 12.2a1 1 0 0 1-1 .8H7.8a1 1 0 0 1-1-.8L6 7"/>
              </svg>
            </button>
            <button
              v-else
              @click="deleteDoc(doc.id)"
              :disabled="documents.deletingIds.has(doc.id)"
              class="shrink-0 rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {{ documents.deletingIds.has(doc.id) ? '…' : 'Sure?' }}
            </button>
          </div>
          <div class="mt-1.5 flex items-center justify-between">
            <StatusBadge :status="doc.status" />
            <button
              v-if="confirmDeleteId === doc.id"
              @click="confirmDeleteId = null"
              class="text-xs text-slate-500 underline"
            >cancel</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Backend status -->
    <div class="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
      <span class="inline-flex items-center gap-1.5">
        <span
          class="h-2 w-2 rounded-full"
          :class="health.error ? 'bg-red-500' : health.status ? 'bg-emerald-500' : 'bg-slate-300'"
        />
        {{ health.error ? 'Backend unreachable' : health.status ? 'Backend connected' : 'Checking backend…' }}
      </span>
      <span v-if="health.status && !health.status.groq_configured" class="mt-1 block text-amber-600">
        AI answers unavailable — Groq key not configured on the server.
      </span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { useDocumentsStore } from '../stores/documents'
import { useHealthStore } from '../stores/health'

const documents = useDocumentsStore()
const health = useHealthStore()
const confirmDeleteId = ref<string | null>(null)

function onFilesChosen(event: Event): void {
  const input = event.target as HTMLInputElement
  if (input.files?.length) {
    void documents.uploadFiles(Array.from(input.files))
  }
  input.value = '' // allow re-selecting the same file
}

async function deleteDoc(id: string): Promise<void> {
  confirmDeleteId.value = null
  try {
    await documents.remove(id)
  } catch (e) {
    documents.uploadError = e instanceof Error ? e.message : 'Delete failed.'
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onMounted(() => {
  void documents.fetchAll()
  void health.refresh()
})
</script>
