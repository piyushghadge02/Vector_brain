<template>
  <div class="flex h-screen overflow-hidden bg-white">
    <!-- Desktop sidebar -->
    <div class="hidden h-full md:block">
      <DocumentSidebar />
    </div>

    <!-- Mobile drawer -->
    <Transition name="drawer">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-40 md:hidden"
      >
        <div class="absolute inset-0 bg-slate-900/40" @click="sidebarOpen = false" />
        <div class="absolute inset-y-0 left-0 h-full">
          <DocumentSidebar />
        </div>
      </div>
    </Transition>

    <!-- Main chat area -->
    <main class="min-w-0 flex-1">
      <ChatPanel @toggle-sidebar="sidebarOpen = !sidebarOpen" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ChatPanel from '../components/ChatPanel.vue'
import DocumentSidebar from '../components/DocumentSidebar.vue'

const sidebarOpen = ref(false)
</script>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active > div:last-child,
.drawer-leave-active > div:last-child {
  transition: transform 0.25s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from > div:last-child,
.drawer-leave-to > div:last-child {
  transform: translateX(-100%);
}
</style>
