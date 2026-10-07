import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getHealth, type HealthStatus } from '../api/health'

/** Backend connectivity state, polled on app start. */
export const useHealthStore = defineStore('health', () => {
  const status = ref<HealthStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      status.value = await getHealth()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Health check failed'
      status.value = null
    } finally {
      loading.value = false
    }
  }

  return { status, loading, error, refresh }
})
