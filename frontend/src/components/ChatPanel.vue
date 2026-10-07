<template>
  <div class="flex h-full flex-col">
    <!-- Header -->
    <header class="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
      <button
        @click="$emit('toggle-sidebar')"
        class="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 md:hidden"
        title="Documents"
      >
        <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
      <div class="min-w-0">
        <h1 class="truncate text-base font-semibold text-slate-900">Ask your documents</h1>
        <p class="truncate text-xs text-slate-500">
          <template v-if="processedCount > 0">
            Searching across {{ processedCount }} processed document{{ processedCount === 1 ? '' : 's' }}
          </template>
          <template v-else>Upload PDFs in the sidebar to get started</template>
        </p>
      </div>
      <button
        v-if="chat.messages.length"
        @click="chat.clear()"
        class="ml-auto shrink-0 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
        title="Clear conversation"
      >
        New chat
      </button>
    </header>

    <!-- Messages -->
    <div ref="scrollArea" class="flex-1 overflow-y-auto bg-slate-50/70 px-4 py-5">
      <div v-if="!chat.messages.length" class="mx-auto mt-10 max-w-md text-center">
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900">
          <svg viewBox="0 0 24 24" class="h-6 w-6 text-white" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
          </svg>
        </div>
        <h2 class="mt-4 text-lg font-semibold text-slate-900">Your second brain is ready</h2>
        <p class="mt-1.5 text-sm text-slate-500">
          Upload PDFs on the left, then ask questions. Every answer is grounded
          in your documents and cites its sources.
        </p>
        <div class="mt-5 space-y-2 text-left">
          <button
            v-for="example in examples"
            :key="example"
            @click="ask(example)"
            :disabled="!chat.canSend"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-slate-700 shadow-sm transition hover:border-slate-300 hover:shadow disabled:opacity-50"
          >
            {{ example }}
          </button>
        </div>
      </div>
      <div v-else class="mx-auto max-w-3xl space-y-4">
        <ChatMessage
          v-for="message in chat.messages"
          :key="message.id"
          :message="message"
          @retry="chat.retry"
        />
      </div>
    </div>

    <!-- Input -->
    <QuestionInput
      :sending="chat.sending"
      :processed-count="processedCount"
      @send="ask"
    />
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import ChatMessage from './ChatMessage.vue'
import QuestionInput from './QuestionInput.vue'
import { useChatStore } from '../stores/chat'
import { useDocumentsStore } from '../stores/documents'
import { storeToRefs } from 'pinia'

defineEmits<{ 'toggle-sidebar': [] }>()

const chat = useChatStore()
const { processedCount } = storeToRefs(useDocumentsStore())
const scrollArea = ref<HTMLElement | null>(null)

const examples = [
  'What are the main topics covered in my documents?',
  'Summarize the key findings across all documents.',
]

function ask(question: string): void {
  void chat.send(question)
}

watch(
  () => chat.messages,
  () => {
    void nextTick(() => {
      const el = scrollArea.value
      if (el) el.scrollTop = el.scrollHeight
    })
  },
  { deep: true },
)
</script>