<template>
  <div class="border-t border-slate-200 bg-white px-4 py-3">
    <form @submit.prevent="submit" class="mx-auto flex max-w-3xl items-end gap-2">
      <textarea
        ref="input"
        v-model="draft"
        rows="1"
        placeholder="Ask anything about your documents…"
        :disabled="sending"
        @keydown.enter.exact.prevent="submit"
        @input="autosize"
        class="max-h-36 flex-1 resize-none rounded-xl border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:bg-white focus:outline-none disabled:opacity-60"
      />
      <button
        type="submit"
        :disabled="!canSubmit"
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        title="Send question"
      >
        <svg v-if="!sending" viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 19V5m0 0l-6 6m6-6l6 6"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" class="h-5 w-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M12 3a9 9 0 1 0 9 9"/>
        </svg>
      </button>
    </form>
    <p class="mx-auto mt-1.5 max-w-3xl text-center text-xs text-slate-400">
      Enter to send · Shift+Enter for a new line · searches all {{ processedCount }} processed document{{ processedCount === 1 ? '' : 's' }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

const props = defineProps<{ sending: boolean; processedCount: number }>()
const emit = defineEmits<{ send: [question: string] }>()

const draft = ref('')
const input = ref<HTMLTextAreaElement | null>(null)

const canSubmit = computed(() => draft.value.trim().length > 0 && !props.sending)

function submit(): void {
  const q = draft.value.trim()
  if (!q || props.sending) return
  emit('send', q)
  draft.value = ''
  void nextTick(autosize)
}

function autosize(): void {
  const el = input.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

defineExpose({ focus: () => input.value?.focus() })
</script>