<template>
  <!-- User question -->
  <div v-if="message.role === 'user'" class="flex justify-end">
    <div class="max-w-[85%] rounded-2xl rounded-br-md bg-slate-900 px-4 py-2.5 text-sm text-white">
      <p class="whitespace-pre-wrap">{{ message.content }}</p>
    </div>
  </div>

  <!-- Assistant answer -->
  <div v-else class="flex justify-start">
    <div class="max-w-[92%] rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <!-- Loading state -->
      <div v-if="message.pending" class="flex items-center gap-2 py-1 text-sm text-slate-500">
        <span class="flex gap-1">
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" style="animation-delay: 0ms" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" style="animation-delay: 150ms" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" style="animation-delay: 300ms" />
        </span>
        Searching your documents…
      </div>

      <!-- Error state -->
      <div v-else-if="message.error" class="text-sm">
        <p class="text-red-700">{{ message.error }}</p>
        <button
          @click="$emit('retry', message.id)"
          class="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Try again
        </button>
      </div>

      <!-- Answer -->
      <div v-else class="text-sm leading-relaxed text-slate-800">
        <p class="whitespace-pre-wrap"><template v-for="(part, i) in parts" :key="i"><a
          v-if="part.cite !== undefined"
          :href="`#source-${message.id}-${part.cite}`"
          class="mx-0.5 rounded bg-slate-100 px-1 py-0.5 text-xs font-semibold text-slate-700 no-underline hover:bg-slate-200"
        >[{{ part.cite }}]</a><template v-else>{{ part.text }}</template></template></p>

        <!-- Sources -->
        <div v-if="message.sources.length" class="mt-3 border-t border-slate-100 pt-2.5">
          <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Sources · {{ message.sources.length }}
          </p>
          <ul class="mt-1.5 space-y-1.5">
            <li
              v-for="(source, i) in message.sources"
              :key="source.chunk_id"
              :id="`source-${message.id}-${i + 1}`"
              class="scroll-mt-24 rounded-lg bg-slate-50 px-3 py-2"
            >
              <p class="flex items-baseline justify-between gap-2 text-xs">
                <span class="font-medium text-slate-800">
                  <span class="mr-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-slate-200 px-1 text-[10px] font-bold text-slate-600">{{ i + 1 }}</span>{{ source.filename }}
                </span>
                <span class="shrink-0 text-slate-500">{{ pageLabel(source.pages) }}</span>
              </p>
              <p v-if="source.heading" class="mt-0.5 truncate text-[11px] text-slate-500">
                {{ source.heading }}
              </p>
              <p class="mt-1 line-clamp-2 text-xs italic text-slate-600">“{{ source.snippet }}…”</p>
            </li>
          </ul>
        </div>

        <p v-if="message.latencyMs !== undefined" class="mt-2 text-[11px] text-slate-400">
          {{ formatLatency(message.latencyMs) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '../stores/chat'

const props = defineProps<{ message: ChatMessage }>()
defineEmits<{ retry: [id: string] }>()

interface Part { text: string; cite?: number }

/** Split answer text so [n] citations render as highlighted chips.
 *  Some models emit 【n】 (CJK brackets) instead — highlight those too. */
const parts = computed<Part[]>(() => {
  const out: Part[] = []
  const re = /\[(\d+)\]|【(\d+)】/g
  let last = 0
  let m: RegExpExecArray | null
  const text = props.message.content
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) })
    out.push({ text: m[0], cite: Number(m[1] ?? m[2]) })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last) })
  return out
})

function pageLabel(pages: number[]): string {
  if (!pages.length) return ''
  if (pages.length === 1) return `p. ${pages[0]}`
  return `pp. ${pages[0]}–${pages[pages.length - 1]}`
}

function formatLatency(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}
</script>
