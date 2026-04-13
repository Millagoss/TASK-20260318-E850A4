<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const metrics = ref<any[]>([])
const thresholds = ref<any[]>([])
const alerts = ref<any[]>([])
const whitelist = ref<any[]>([])
const loading = ref(false)
const errorMsg = ref('')

const thresholdForm = ref({ metric_name: 'approval_rate', threshold_value: 80 })
const whitelistForm = ref({ policy_name: '', payload: '' })
const recoveryFileName = ref('')
const batches = ref<any[]>([])
const qcResults = ref<any[]>([])
const batchForm = ref({ batch_name: '', status: 'Open' })
const qcForm = ref({ batch_id: '' as string | number, registration_form_id: '', score: 0, result_status: 'Passed', notes: '' })

async function fetchAdminData() {
  loading.value = true
  errorMsg.value = ''
  try {
    const headers = { Authorization: `Bearer ${authStore.token}` }
    const [mRes, tRes, aRes, wRes, bRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/admin/metrics`, { headers }),
      fetch(`${API_BASE}/admin/thresholds`, { headers }),
      fetch(`${API_BASE}/admin/alerts`, { headers }),
      fetch(`${API_BASE}/admin/whitelist`, { headers }),
      fetch(`${API_BASE}/admin/data-collection/batches`, { headers }),
      fetch(`${API_BASE}/admin/quality-validation/results`, { headers }),
    ])
    metrics.value = await mRes.json()
    thresholds.value = await tRes.json()
    alerts.value = await aRes.json()
    whitelist.value = await wRes.json()
    batches.value = bRes.ok ? await bRes.json() : []
    qcResults.value = qRes.ok ? await qRes.json() : []
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

async function calculateMetrics() {
  await fetch(`${API_BASE}/admin/metrics/calculate`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}` },
  })
  await fetchAdminData()
}

async function saveThreshold() {
  await fetch(`${API_BASE}/admin/thresholds`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      metric_name: thresholdForm.value.metric_name,
      threshold_value: Number(thresholdForm.value.threshold_value),
    }),
  })
  await fetchAdminData()
}

async function saveWhitelist() {
  await fetch(`${API_BASE}/admin/whitelist`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(whitelistForm.value),
  })
  whitelistForm.value = { policy_name: '', payload: '' }
  await fetchAdminData()
}

async function triggerBackup() {
  const r = await fetch(`${API_BASE}/admin/backup`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}` },
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    errorMsg.value = (err as any).detail || 'Backup failed'
  }
}

async function createBatch() {
  if (!batchForm.value.batch_name.trim()) return
  const r = await fetch(`${API_BASE}/admin/data-collection/batches`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(batchForm.value),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    errorMsg.value = (err as any).detail || 'Batch create failed'
    return
  }
  batchForm.value = { batch_name: '', status: 'Open' }
  await fetchAdminData()
}

async function saveQualityResult() {
  const batchId = Number(qcForm.value.batch_id)
  const formId = Number(qcForm.value.registration_form_id)
  if (!batchId || !formId) {
    errorMsg.value = 'Batch ID and registration form ID are required.'
    return
  }
  const r = await fetch(`${API_BASE}/admin/quality-validation/results`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      batch_id: batchId,
      registration_form_id: formId,
      score: Number(qcForm.value.score) || 0,
      result_status: qcForm.value.result_status,
      notes: qcForm.value.notes || null,
    }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    errorMsg.value = (err as any).detail || 'Quality result failed'
    return
  }
  qcForm.value = { batch_id: '', registration_form_id: '', score: 0, result_status: 'Passed', notes: '' }
  await fetchAdminData()
}

async function triggerRecovery() {
  const form = new FormData()
  form.append('file_name', recoveryFileName.value)
  await fetch(`${API_BASE}/admin/recovery`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authStore.token}` },
    body: form,
  })
}

async function openExport(path: string, fileName: string) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${authStore.token}` },
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Export failed')
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    errorMsg.value = err.message
  }
}

onMounted(fetchAdminData)

const criticalAlerts = computed(() => alerts.value.length)

function formatMetricName(metric: string) {
  return metric.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
</script>

<template>
  <div class="admin-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Platform Operations</p>
        <h2>System Admin Dashboard</h2>
      </div>
      <button class="primary-btn" @click="calculateMetrics">Recalculate Metrics</button>
    </header>

    <section class="stats-grid">
      <article class="stat-card">
        <p class="stat-label">Tracked Metrics</p>
        <p class="stat-value">{{ metrics.length }}</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Configured Thresholds</p>
        <p class="stat-value">{{ thresholds.length }}</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Active Alerts</p>
        <p class="stat-value alert">{{ criticalAlerts }}</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Whitelist Policies</p>
        <p class="stat-value">{{ whitelist.length }}</p>
      </article>
    </section>

    <p v-if="loading" class="status-msg">Loading admin data...</p>
    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

    <section class="card">
      <div class="card-head">
        <h3>Operational Metrics</h3>
      </div>
      <div v-if="metrics.length" class="list-grid">
        <div v-for="m in metrics" :key="m.metric_name" class="list-row">
          <span>{{ formatMetricName(m.metric_name) }}</span>
          <strong>{{ m.metric_value }}%</strong>
        </div>
      </div>
      <p v-else class="muted">No metrics available.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Thresholds</h3>
      </div>
      <div class="form-row">
        <select v-model="thresholdForm.metric_name">
          <option value="approval_rate">approval_rate</option>
          <option value="correction_rate">correction_rate</option>
          <option value="overspending_rate">overspending_rate</option>
          <option value="quality_failure_rate">quality_failure_rate</option>
        </select>
        <input type="number" v-model="thresholdForm.threshold_value" />
        <button class="primary-btn" @click="saveThreshold">Save Threshold</button>
      </div>
      <div v-if="thresholds.length" class="list-grid compact">
        <div v-for="t in thresholds" :key="t.metric_name" class="list-row">
          <span>{{ formatMetricName(t.metric_name) }}</span>
          <strong>{{ t.threshold_value }}%</strong>
        </div>
      </div>
      <p v-else class="muted">No threshold rules configured.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Alerts</h3>
      </div>
      <div v-if="alerts.length" class="list-grid">
        <div v-for="a in alerts" :key="a.id" class="alert-row">
          <div>
            <strong>{{ formatMetricName(a.metric_name) }}</strong>
            <p class="muted">Current: {{ a.metric_value }}% · Threshold: {{ a.threshold_value }}%</p>
          </div>
          <span class="badge">{{ a.message }}</span>
        </div>
      </div>
      <p v-else class="muted">No active alerts.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Whitelist Policies</h3>
        <span class="subtle">Encrypted at rest</span>
      </div>
      <div class="form-row">
        <input v-model="whitelistForm.policy_name" placeholder="Policy name" />
        <input v-model="whitelistForm.payload" placeholder="Payload" />
        <button class="primary-btn" @click="saveWhitelist">Save Policy</button>
      </div>
      <div v-if="whitelist.length" class="list-grid compact">
        <div v-for="w in whitelist" :key="w.id" class="list-row">
          <span>{{ w.policy_name }}</span>
          <strong>{{ w.payload }}</strong>
        </div>
      </div>
      <p v-else class="muted">No whitelist policies saved.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Backup & Recovery</h3>
      </div>
      <div class="form-row">
        <button class="primary-btn" @click="triggerBackup">Run Backup</button>
        <input v-model="recoveryFileName" placeholder="backup_YYYYMMDD_HHMMSS.sql" />
        <button class="secondary-btn" @click="triggerRecovery">Recover</button>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Data collection batches</h3>
      </div>
      <div class="form-row">
        <input v-model="batchForm.batch_name" placeholder="Batch name" />
        <select v-model="batchForm.status">
          <option>Open</option>
          <option>Closed</option>
        </select>
        <button class="primary-btn" type="button" @click="createBatch">Create batch</button>
      </div>
      <div v-if="batches.length" class="list-grid compact">
        <div v-for="b in batches" :key="b.id" class="list-row">
          <span>#{{ b.id }} {{ b.batch_name }}</span>
          <strong>{{ b.status }}</strong>
        </div>
      </div>
      <p v-else class="muted">No batches yet.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Quality validation</h3>
      </div>
      <div class="form-row wrap">
        <input v-model="qcForm.batch_id" type="number" placeholder="Batch ID" />
        <input v-model="qcForm.registration_form_id" type="number" placeholder="Registration form ID" />
        <input v-model.number="qcForm.score" type="number" placeholder="Score" />
        <select v-model="qcForm.result_status">
          <option>Passed</option>
          <option>Failed</option>
          <option>Pending</option>
        </select>
        <input v-model="qcForm.notes" placeholder="Notes" />
        <button class="primary-btn" type="button" @click="saveQualityResult">Save result</button>
      </div>
      <div v-if="qcResults.length" class="list-grid compact">
        <div v-for="q in qcResults.slice(0, 20)" :key="q.id" class="list-row">
          <span>Form #{{ q.registration_form_id }} · batch {{ q.batch_id }}</span>
          <strong>{{ q.result_status }} ({{ q.score }})</strong>
        </div>
      </div>
      <p v-else class="muted">No validation rows yet.</p>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>Exports</h3>
      </div>
      <div class="form-row">
        <button class="secondary-btn" @click="openExport('/admin/exports/reconciliation', 'reconciliation.csv')">
          Reconciliation CSV
        </button>
        <button class="secondary-btn" @click="openExport('/admin/exports/audit', 'audit_logs.csv')">Audit Logs CSV</button>
        <button class="secondary-btn" @click="openExport('/admin/exports/compliance', 'compliance_report.csv')">
          Compliance CSV
        </button>
        <button class="secondary-btn" @click="openExport('/admin/exports/whitelist', 'whitelist_policies.csv')">
          Whitelist CSV
        </button>
        <button class="secondary-btn" @click="openExport('/admin/exports/access-audit', 'access_audit.csv')">
          API access audit CSV
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-view {
  background: #f8fafc;
  min-height: 100%;
  padding: 1.25rem;
}

.page-header {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.eyebrow {
  color: #475569;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

h2,
h3 {
  color: #0f172a;
  margin: 0;
}

.stats-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-bottom: 1rem;
}

.stat-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.9rem 1rem;
}

.stat-label {
  color: #64748b;
  font-size: 0.8rem;
  margin: 0 0 0.2rem;
}

.stat-value {
  color: #0f172a;
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0;
}

.stat-value.alert {
  color: #dc2626;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 1rem;
  padding: 1rem;
}

.card-head {
  align-items: baseline;
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.subtle,
.muted {
  color: #64748b;
  font-size: 0.85rem;
}

.list-grid {
  display: grid;
  gap: 0.55rem;
}

.list-grid.compact {
  gap: 0.4rem;
}

.list-row,
.alert-row {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  padding: 0.6rem 0.7rem;
}

.alert-row {
  align-items: flex-start;
  gap: 0.75rem;
}

.badge {
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 999px;
  color: #b91c1c;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  white-space: nowrap;
}

.form-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.form-row.wrap {
  align-items: flex-end;
}

button {
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  padding: 0.5rem 0.8rem;
}

.primary-btn {
  background: #2563eb;
  color: #fff;
}

.primary-btn:hover {
  background: #1d4ed8;
}

.secondary-btn {
  background: #e2e8f0;
  color: #0f172a;
}

.secondary-btn:hover {
  background: #cbd5e1;
}

input,
select {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  min-height: 36px;
  padding: 0.45rem 0.55rem;
}

input {
  min-width: 220px;
}

.status-msg {
  color: #334155;
  margin: 0 0 0.9rem;
}

.error-msg {
  color: #dc2626;
  margin: 0 0 0.9rem;
}
</style>
