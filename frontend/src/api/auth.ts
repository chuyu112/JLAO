import { api } from './client'

export interface UserProfile {
  id: string
  username: string
  display_name: string
  role: string
}

export interface LoginResponse {
  token: string
  user: UserProfile
}

export async function loginApi(username: string, password: string) {
  const { data } = await api.post<LoginResponse>('/api/auth/login', { username, password })
  return data
}

