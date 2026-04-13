<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isAuthPage = computed(() => route.path.startsWith('/login') || route.path.startsWith('/signup'))
const menuItems = computed(() => {
  const role = authStore.role
  return [
    { to: '/dashboard', label: 'Dashboard', roles: ['Applicant', 'Reviewer', 'FinancialAdmin', 'SystemAdmin'] },
    { to: '/wizard', label: 'Application Wizard', roles: ['Applicant'] },
    { to: '/reviewer', label: 'Reviewer Dashboard', roles: ['Reviewer', 'SystemAdmin'] },
    { to: '/financial', label: 'Financial Dashboard', roles: ['FinancialAdmin', 'SystemAdmin'] },
    { to: '/system-admin', label: 'System Admin Dashboard', roles: ['SystemAdmin'] },
    { to: '/user-management', label: 'User Management', roles: ['SystemAdmin'] },
  ].filter((item) => item.roles.includes(role))
})

function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="isAuthPage" class="auth-layout">
    <RouterView />
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <h2 class="brand">Activity Platform</h2>
      <p class="role">Role: {{ authStore.role }}</p>

      <nav class="nav">
        <RouterLink v-for="item in menuItems" :key="item.to" :to="item.to" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>

      <button class="logout-btn" @click="handleLogout">Logout</button>
    </aside>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f8fafc;
}

.auth-layout {
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px 1fr;
}

.sidebar {
  background: #0f172a;
  color: #e2e8f0;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

.brand {
  margin: 0;
  font-size: 1.1rem;
}

.role {
  margin: 0;
  font-size: 0.85rem;
  color: #94a3b8;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.nav-item {
  color: #e2e8f0;
  text-decoration: none;
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
}

.nav-item.router-link-active {
  background: #1e293b;
}

.logout-btn {
  margin-top: auto;
  border: none;
  background: #dc2626;
  color: white;
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
  cursor: pointer;
}

.content {
  padding: 1.1rem;
}
</style>