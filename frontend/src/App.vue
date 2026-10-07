<template>
  <div
    v-if="isDemo"
    class="bg-amber-100 px-4 py-1.5 text-center text-xs font-medium text-amber-800"
  >
    Preview with sample data — run the backend for the live app.
  </div>
  <RouterView />
</template>

<script setup lang="ts">
// Shown only in the static preview build (VITE_DEMO_MODE=true).
const isDemo = import.meta.env.VITE_DEMO_MODE === 'true'
</script>