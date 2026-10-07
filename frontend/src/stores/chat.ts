import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import {
  askQuestion,
  friendlyChatError,
  type SourceOut,
} from '../api/chat'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceOut[]
  model?: string
  latencyMs?: number
  error?: string | null
  pending?: boolean
}

function uid(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2)
}

/** Conversation state — every question hits the real RAG API. */
export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sending = ref(false)

  const canSend = computed(() => !sending.value)

  async function send(rawQuestion: string): Promise<void> {
    const question = rawQuestion.trim()
    if (!question || sending.value) return

    messages.value.push({ id: uid(), role: 'user', content: question, sources: [] })
    // reactive() — not a plain object: later mutations must go through the
    // proxy, otherwise Vue never re-renders the reply (raw object mutation
    // after push() is invisible to reactivity).
    const reply = reactive<ChatMessage>({
      id: uid(),
      role: 'assistant',
      content: '',
      sources: [],
      pending: true,
    })
    messages.value.push(reply)
    sending.value = true
    try {
      const res = await askQuestion(question)
      reply.pending = false
      reply.content = res.answer
      reply.sources = res.sources
      reply.model = res.model
      reply.latencyMs = res.latency_ms
    } catch (e) {
      reply.pending = false
      reply.error = friendlyChatError(e)
    } finally {
      sending.value = false
    }
  }

  /** Re-ask the question that produced an errored reply. */
  function retry(messageId: string): void {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx <= 0) return
    const question = messages.value[idx - 1]
    if (question.role !== 'user') return
    messages.value.splice(idx, 1) // drop the errored reply
    void send(question.content)
  }

  function clear(): void {
    messages.value = []
  }

  return { messages, sending, canSend, send, retry, clear }
})
