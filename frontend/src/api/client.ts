import axios from 'axios'

const isViteDev = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && window.location.port === '5173'

const queryApiBase = new URLSearchParams(window.location.search).get('api')
if (queryApiBase) {
  localStorage.setItem('jlao-api-base', queryApiBase)
}

const savedApiBase = localStorage.getItem('jlao-api-base') || ''
const defaultApiBase = 'http://127.0.0.1:8000'

export const API_BASE =
  import.meta.env.VITE_API_BASE || savedApiBase || defaultApiBase
export const WS_BASE = API_BASE.replace(/^http/, 'ws')

export const api = axios.create({
  baseURL: API_BASE,
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
