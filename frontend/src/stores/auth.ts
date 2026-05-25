import { defineStore } from 'pinia'
import { loginApi, type UserProfile } from '../api/auth'

interface AuthState {
  token: string
  user: UserProfile | null
}

const TOKEN_KEY = 'jlao_token'
const USER_KEY = 'jlao_user'

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: parseUser(localStorage.getItem(USER_KEY)),
  }),

  getters: {
    isLoggedIn(state) {
      return Boolean(state.token && state.user)
    },
  },

  actions: {
    async login(username: string, password: string) {
      const result = await loginApi(username, password)
      this.token = result.token
      this.user = result.user
      localStorage.setItem(TOKEN_KEY, result.token)
      localStorage.setItem(USER_KEY, JSON.stringify(result.user))
      return result.user
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})

function parseUser(value: string | null): UserProfile | null {
  if (!value) return null
  try {
    return JSON.parse(value) as UserProfile
  } catch {
    return null
  }
}
