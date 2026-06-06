import axios from 'axios'
import { resolveApiBase } from './baseResolver'

const queryApiBase = new URLSearchParams(window.location.search).get('api')
const savedApiBase = localStorage.getItem('jlao-api-base') || ''
const defaultApiBase = 'http://127.0.0.1:8000'
const isProductionShell = window.location.hostname === 'jlao.szkakayiduo.com'
const deployedApiBase = import.meta.env.VITE_API_BASE || window.location.origin

// 优先级：
// 1. URL 参数 ?api=xxx（最高优先级）
// 2. localStorage 保存的配置
// 3. 生产环境默认连接本地后端
// 4. 本地开发使用当前 origin
export const API_BASE = resolveApiBase({
  queryApiBase: queryApiBase || '',
  savedApiBase,
  productionShell: isProductionShell,
  deployedApiBase,
  windowOrigin: window.location.origin,
  defaultApiBase,
})

if (queryApiBase && queryApiBase === API_BASE) {
  localStorage.setItem('jlao-api-base', API_BASE)
} else if (isProductionShell && savedApiBase !== API_BASE) {
  localStorage.setItem('jlao-api-base', API_BASE)
}

export const WS_BASE = API_BASE ? API_BASE.replace(/^http/, 'ws') : `wss://${window.location.host}`

export const api = axios.create({
  baseURL: API_BASE || undefined,
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('jlao_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('jlao_token')
      localStorage.removeItem('jlao_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
