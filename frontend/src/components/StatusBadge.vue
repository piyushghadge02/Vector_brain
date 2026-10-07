<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="classes"
  >
    {{ status }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DocumentStatus } from '../api/documents'

const props = defineProps<{ status: DocumentStatus }>()

const classes = computed(() => {
  const map: Record<DocumentStatus, string> = {
    pending: 'bg-slate-100 text-slate-600',
    processing: 'bg-amber-100 text-amber-700',
    processed: 'bg-emerald-100 text-emerald-700',
    failed: 'bg-red-100 text-red-700',
  }
  return map[props.status]
})
</script>
