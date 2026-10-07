import {
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router'
import WorkspaceView from '../views/WorkspaceView.vue'

const isDemoPreview = import.meta.env.VITE_DEMO_MODE === 'true'

const router = createRouter({
  // Demo preview builds are opened as static files (including file://),
  // where the History API is unavailable — hash routing keeps them working.
  history: isDemoPreview ? createWebHashHistory() : createWebHistory(),
  routes: [
    { path: '/', name: 'workspace', component: WorkspaceView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
