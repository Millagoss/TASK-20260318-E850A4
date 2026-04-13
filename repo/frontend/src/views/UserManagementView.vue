<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const users = ref<any[]>([])
const loading = ref(false)
const errorMsg = ref('')
const showEditModal = ref(false)
const editUser = ref<any>(null)
const form = ref({ username: '', role: 'Applicant' })

async function fetchUsers() {
  loading.value = true
  errorMsg.value = ''
  try {
    const response = await fetch(`${API_BASE}/admin/users`, {
      headers: { Authorization: `Bearer ${authStore.token}` },
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to fetch users')
    }
    users.value = await response.json()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

function openEditModal(user: any) {
  editUser.value = user
  form.value = { username: user.username, role: user.role }
  showEditModal.value = true
}

async function saveEdit() {
  if (!editUser.value) return
  loading.value = true
  try {
    const response = await fetch(`${API_BASE}/admin/users/${editUser.value.id}`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(form.value),
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to update user')
    }
    showEditModal.value = false
    await fetchUsers()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

async function toggleBlock(user: any) {
  loading.value = true
  try {
    const endpoint = user.is_blocked ? 'unblock' : 'block'
    const response = await fetch(`${API_BASE}/admin/users/${user.id}/${endpoint}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authStore.token}` },
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || `Failed to ${endpoint} user`)
    }
    await fetchUsers()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div class="wrap">
    <h2>User & Role Management</h2>
    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    <div v-if="loading" class="loading">Loading...</div>

    <div class="card">
      <table class="users-table">
        <thead>
          <tr>
            <th>UserName</th>
            <th>Role</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.username }}</td>
            <td>{{ user.role }}</td>
            <td>
              <span :class="user.is_blocked ? 'blocked' : 'active'">{{ user.is_blocked ? 'Blocked' : 'Active' }}</span>
            </td>
            <td class="actions">
              <button @click="openEditModal(user)">Edit</button>
              <button :class="user.is_blocked ? 'success' : 'danger'" @click="toggleBlock(user)">
                {{ user.is_blocked ? 'Unblock' : 'Block' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showEditModal" class="modal-backdrop">
      <div class="modal">
        <h3>Edit User</h3>
        <div class="field">
          <label>UserName</label>
          <input v-model="form.username" />
        </div>
        <div class="field">
          <label>Role</label>
          <select v-model="form.role">
            <option value="Applicant">Applicant</option>
            <option value="Reviewer">Reviewer</option>
            <option value="FinancialAdmin">FinancialAdmin</option>
            <option value="SystemAdmin">SystemAdmin</option>
          </select>
        </div>
        <div class="actions">
          <button @click="saveEdit">Save</button>
          <button class="secondary" @click="showEditModal = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 1rem; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; }
.users-table { width: 100%; border-collapse: collapse; }
.users-table th, .users-table td { border-bottom: 1px solid #e2e8f0; padding: 0.65rem; text-align: left; }
.actions { display: flex; gap: 0.5rem; }
button { border: none; background: #2563eb; color: #fff; border-radius: 8px; padding: 0.4rem 0.65rem; cursor: pointer; }
.danger { background: #dc2626; }
.success { background: #16a34a; }
.secondary { background: #64748b; }
.active { color: #16a34a; font-weight: 600; }
.blocked { color: #dc2626; font-weight: 600; }
.loading { color: #334155; }
.error { color: #dc2626; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.5); display: grid; place-items: center; }
.modal { width: 440px; max-width: 95vw; background: #fff; border-radius: 10px; padding: 1rem; }
.field { display: flex; flex-direction: column; gap: 0.25rem; margin-bottom: 0.8rem; }
input, select { padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 8px; }
</style>
