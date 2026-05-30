import { createRouter, createWebHistory } from 'vue-router'
import LiveDashboard from './pages/LiveDashboard.vue'
import LoginPage from './pages/LoginPage.vue'
import ObservationDashboard from './pages/ObservationDashboard.vue'
import ProductLibrary from './pages/ProductLibrary.vue'
import ReplayReport from './pages/ReplayReport.vue'
import { useAuthStore } from './stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/live' },
    { path: '/login', component: LoginPage },
    { path: '/live', component: LiveDashboard },
    { path: '/observe', component: ObservationDashboard },
    { path: '/products', component: ProductLibrary },
    { path: '/replay', component: ReplayReport },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLoggedIn) {
    return '/login'
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return '/live'
  }
  return true
})
