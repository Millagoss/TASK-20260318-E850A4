<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const applications = ref<any[]>([])
const selectedIds = ref<number[]>([])
const selectedApp = ref<any>(null)
const auditTrail = ref<any[]>([])
const transitionTarget = ref('Approved')
const transitionComment = ref('')
const commentInput = ref('')
const needsCorrectionReason = ref<Record<number, string>>({})
const errorMsg = ref('')
const loading = ref(true)
const actionLoading = ref(false)

async function fetchApplications() {
  loading.value = true
  errorMsg.value = ''
  try {
    const response = await fetch(`${API_BASE}/reviewer/applications`, {
      headers: { Authorization: `Bearer ${authStore.token}` },
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to load applications')
    }
    applications.value = await response.json()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

async function openDetail(id: number) {
  try {
    const [detailRes, auditRes] = await Promise.all([
      fetch(`${API_BASE}/reviewer/applications/${id}`, {
        headers: { Authorization: `Bearer ${authStore.token}` },
      }),
      fetch(`${API_BASE}/reviewer/applications/${id}/audit-trail`, {
        headers: { Authorization: `Bearer ${authStore.token}` },
      }),
    ])
    if (!detailRes.ok) throw new Error('Failed to load details')
    if (!auditRes.ok) throw new Error('Failed to load audit trail')
    selectedApp.value = await detailRes.json()
    auditTrail.value = await auditRes.json()
  } catch (err: any) {
    errorMsg.value = err.message
  }
}

async function transitionOne(id: number) {
  actionLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/reviewer/applications/${id}/transition`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ target_state: transitionTarget.value, comment: transitionComment.value || null }),
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Transition failed')
    }
    await fetchApplications()
    await openDetail(id)
    transitionComment.value = ''
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    actionLoading.value = false
  }
}

async function transitionBatch() {
  if (!selectedIds.value.length) return
  actionLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/reviewer/applications/batch-transition`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        form_ids: selectedIds.value,
        target_state: transitionTarget.value,
        comment: transitionComment.value || null,
      }),
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Batch transition failed')
    }
    selectedIds.value = []
    transitionComment.value = ''
    await fetchApplications()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    actionLoading.value = false
  }
}

async function addComment() {
  if (!selectedApp.value || !commentInput.value.trim()) return
  actionLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/reviewer/applications/${selectedApp.value.id}/comments`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ comment: commentInput.value.trim() }),
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to add comment')
    }
    commentInput.value = ''
    await openDetail(selectedApp.value.id)
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    actionLoading.value = false
  }
}

function clearBatchSelection() {
  selectedIds.value = []
}

async function markNeedsCorrection(checklistId: number) {
  const comment = (needsCorrectionReason.value[checklistId] || '').trim()
  if (!comment) {
    errorMsg.value = 'Enter a reason to open the 72h correction window.'
    return
  }
  actionLoading.value = true
  errorMsg.value = ''
  try {
    const response = await fetch(`${API_BASE}/reviewer/checklists/${checklistId}/needs-correction`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${authStore.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ comment }),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error((err as any).detail || 'Needs correction request failed')
    }
    needsCorrectionReason.value[checklistId] = ''
    if (selectedApp.value) await openDetail(selectedApp.value.id)
    await fetchApplications()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    actionLoading.value = false
  }
}

onMounted(fetchApplications)
</script>

<template>
  <div class="reviewer-layout">
    <div class="left-panel card">
      <h2>Reviewer Dashboard</h2>
      <p v-if="loading">Loading pending applications...</p>
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

      <div v-if="applications.length" class="batch-controls">
        <select v-model="transitionTarget">
          <option>Approved</option>
          <option>Rejected</option>
          <option>Canceled</option>
          <option>Supplemented</option>
          <option>Promoted from Waitlist</option>
        </select>
        <input v-model="transitionComment" placeholder="Optional review note" />
        <button :disabled="selectedIds.length === 0 || selectedIds.length > 50 || actionLoading" @click="transitionBatch">
          {{ actionLoading ? 'Applying...' : 'Batch Apply' }}
        </button>
        <button class="secondary-btn" :disabled="selectedIds.length === 0 || actionLoading" @click="clearBatchSelection">
          Clear
        </button>
      </div>

      <div v-if="applications.length" class="hint">Selected: {{ selectedIds.length }} / 50</div>

      <div v-if="!loading && !errorMsg && applications.length === 0" class="empty-state">
        <h3>No applications to review</h3>
        <p>You are all caught up. New submissions will appear here automatically.</p>
      </div>

      <div v-for="app in applications" :key="app.id" class="app-row" @click="openDetail(app.id)">
        <input type="checkbox" :value="app.id" v-model="selectedIds" @click.stop />
        <div>
          <strong>#{{ app.id }}</strong> - {{ app.applicant.username }}
          <div class="small">ID: {{ app.applicant.id_number || 'N/A' }} | Status: {{ app.status }}</div>
        </div>
      </div>
    </div>

    <div class="right-panel card" v-if="selectedApp">
      <h3>Application #{{ selectedApp.id }}</h3>
      <p><strong>Applicant:</strong> {{ selectedApp.applicant.username }}</p>
      <p><strong>Status:</strong> {{ selectedApp.status }}</p>

      <div class="batch-controls">
        <select v-model="transitionTarget">
          <option>Approved</option>
          <option>Rejected</option>
          <option>Canceled</option>
          <option>Supplemented</option>
          <option>Promoted from Waitlist</option>
        </select>
        <button :disabled="actionLoading" @click="transitionOne(selectedApp.id)">
          {{ actionLoading ? 'Applying...' : 'Apply to this app' }}
        </button>
      </div>

      <h4>Materials</h4>
      <div v-for="item in selectedApp.checklists" :key="item.id" class="material-block">
        <div class="material-item">
          <strong>{{ item.item_name }}</strong>
          <span>{{ item.status }}</span>
        </div>
        <p v-if="item.supplement_expires_at" class="small">
          Supplement window until {{ new Date(item.supplement_expires_at).toLocaleString() }}
        </p>
        <div v-if="!item.supplement_used && !item.supplement_started_at" class="needs-row">
          <input
            v-model="needsCorrectionReason[item.id]"
            class="needs-input"
            placeholder="Reason for correction (required)"
          />
          <button
            type="button"
            class="needs-btn"
            :disabled="actionLoading"
            @click="markNeedsCorrection(item.id)"
          >
            Open 72h correction
          </button>
        </div>
      </div>

      <h4>Review Comment</h4>
      <div class="batch-controls">
        <input v-model="commentInput" placeholder="Add review comment..." />
        <button :disabled="actionLoading || !commentInput.trim()" @click="addComment">
          {{ actionLoading ? 'Saving...' : 'Save Comment' }}
        </button>
      </div>

      <h4>Audit Trail (immutable)</h4>
      <div v-for="entry in auditTrail" :key="entry.id" class="audit-item">
        <div><strong>{{ entry.action }}</strong> (User #{{ entry.actor_user_id }})</div>
        <div class="small">{{ entry.from_state || '-' }} -> {{ entry.to_state || '-' }}</div>
        <div class="small">{{ entry.comment || '' }}</div>
        <div class="small">{{ new Date(entry.created_at).toLocaleString() }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reviewer-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1.2rem; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem; }
.batch-controls { display: flex; gap: 0.5rem; margin: 0.6rem 0; }
.batch-controls input, .batch-controls select { padding: 0.45rem; border: 1px solid #cbd5e1; border-radius: 8px; }
.batch-controls button { border: none; background: #2563eb; color: #fff; border-radius: 8px; padding: 0.45rem 0.7rem; cursor: pointer; }
.batch-controls button:disabled { opacity: 0.6; cursor: not-allowed; }
.secondary-btn { background: #475569 !important; }
.app-row { display: flex; gap: 0.6rem; padding: 0.6rem; border: 1px solid #f1f5f9; border-radius: 10px; margin-bottom: 0.5rem; cursor: pointer; }
.material-block { border: 1px solid #f1f5f9; border-radius: 8px; padding: 0.5rem; margin-bottom: 0.55rem; }
.material-item, .audit-item { display: flex; justify-content: space-between; align-items: center; padding: 0.25rem 0; }
.needs-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.35rem; }
.needs-input { flex: 1; min-width: 140px; padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.85rem; }
.needs-btn { border: none; background: #b45309; color: #fff; border-radius: 8px; padding: 0.4rem 0.65rem; cursor: pointer; font-size: 0.82rem; }
.needs-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.small { font-size: 0.82rem; color: #64748b; }
.hint { font-size: 0.82rem; color: #475569; margin-bottom: 0.6rem; }
.error { color: #dc2626; }
.empty-state { border: 1px dashed #cbd5e1; border-radius: 10px; padding: 1rem; margin-top: 0.75rem; background: #f8fafc; }
.empty-state h3 { margin: 0 0 0.35rem; font-size: 1rem; color: #0f172a; }
.empty-state p { margin: 0; color: #475569; font-size: 0.92rem; }
</style>
