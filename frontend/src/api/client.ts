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
