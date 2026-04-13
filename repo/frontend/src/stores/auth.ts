import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const role = ref(localStorage.getItem('role') || '')

  function setToken(newToken: string, newRole: string) {
    token.value = newToken
    role.value = newRole
    localStorage.setItem('token', newToken)
    localStorage.setItem('role', newRole)
  }

  function logout() {
    token.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('role')
  }

  return { token, role, setToken, logout }
})