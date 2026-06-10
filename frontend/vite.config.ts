import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined

          if (
            id.includes('/vue/') ||
            id.includes('/vue-router/') ||
            id.includes('/pinia/') ||
            id.includes('/@vue/') ||
            id.includes('/naive-ui/') ||
            id.includes('/vueuc/') ||
            id.includes('/vooks/') ||
            id.includes('/vdirs/') ||
            id.includes('/treemate/') ||
            id.includes('/seemly/') ||
            id.includes('/css-render/') ||
            id.includes('/@css-render/') ||
            id.includes('/evtd/') ||
            id.includes('/async-validator/') ||
            id.includes('/@juggle/resize-observer/')
          ) {
            return 'vendor-framework'
          }

          if (id.includes('/date-fns/') || id.includes('/date-fns-tz/')) {
            return 'vendor-date'
          }

          if (id.includes('/axios/')) {
            return 'vendor-http'
          }

          if (
            id.includes('/lucide-vue-next/') ||
            id.includes('/@vicons/') ||
            id.includes('/ionicons')
          ) {
            return 'vendor-icons'
          }

          return 'vendor-core'
        },
      },
    },
  },
})
