import client from './client'

export interface User {
  id: string
  email: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: User
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/login', { email, password })
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await client.get<User>('/api/auth/me')
  return data
}
