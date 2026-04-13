<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'
import FileUpload from '../components/FileUpload.vue'

const authStore = useAuthStore()
const registrationForm = ref<any>(null)
const errorMsg = ref('')
const loading = ref(true)

const now = ref(new Date())

function submittedCount() {
  if (!registrationForm.value?.checklists) return 0
  return registrationForm.value.checklists.filter((item: any) => item.status === 'Submitted').length
}

function totalCount() {
  return registrationForm.value?.checklists?.length ?? 0
}

function progressPercent() {
  const total = totalCount()
  if (!total) return 0
  return Math.round((submittedCount() / total) * 100)
}

function totalSizeMB() {
  if (!registrationForm.value?.checklists) return 0
  let bytes = 0
  registrationForm.value.checklists.forEach((item: any) => {
    if (item.versions) {
      item.versions.forEach((v: any) => {
        bytes += v.file_size || 0
      })
    }
  })
  return (bytes / (1024 * 1024)).toFixed(2)
}

function isItemLocked(item: any) {
  const isOverallPassed = registrationForm.value.deadline && new Date(registrationForm.value.deadline) < now.value
  const hasCorrectionWindow = item.correction_deadline && new Date(item.correction_deadline) > now.value
  
  if (isOverallPassed && !hasCorrectionWindow) return true
  return false
}

async function fetchForm() {
  try {
    loading.value = true
    const response = await fetch(`${API_BASE}/registration-form`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to fetch form')
    }

    registrationForm.value = await response.json()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchForm()
})
</script>

<template>
  <div class="wizard-container">
    <div class="hero">
      <h2>Application Wizard</h2>
      <p>Upload required materials and track completion in real time.</p>
    </div>
    
    <div v-if="loading" class="loading">Loading your application...</div>
    <div v-else-if="errorMsg" class="error">{{ errorMsg }}</div>
    
    <div v-else-if="registrationForm">
      <div class="status-banner">
        <div>
          <p><strong>Application Status:</strong> {{ registrationForm.status }}</p>
          <p><strong>Created:</strong> {{ new Date(registrationForm.created_at).toLocaleString() }}</p>
          <p v-if="registrationForm.deadline">
            <strong>Deadline:</strong> {{ new Date(registrationForm.deadline).toLocaleString() }}
            <span v-if="new Date(registrationForm.deadline) < now" class="badge error">Passed</span>
          </p>
          <p><strong>Total Upload Size:</strong> {{ totalSizeMB() }} MB / 200 MB</p>
        </div>
        <div class="progress-wrap">
          <p class="progress-label">{{ submittedCount() }}/{{ totalCount() }} submitted ({{ progressPercent() }}%)</p>
          <div class="progress-track">
            <div class="progress-bar" :style="{ width: `${progressPercent()}%` }"></div>
          </div>
        </div>
      </div>

      <div class="checklist-section">
        <h3>Required Materials</h3>
        <div v-for="item in registrationForm.checklists" :key="item.id" class="checklist-item">
          <div class="item-header">
            <h4>{{ item.item_name }}</h4>
            <div class="badges">
              <span class="badge" :class="{ submitted: item.status === 'Submitted', correction: item.status === 'Needs Correction' }">
                {{ item.status }}
              </span>
              <span v-if="isItemLocked(item)" class="badge locked">Locked</span>
              <span v-if="item.correction_deadline && new Date(item.correction_deadline) > now" class="badge timer">
                Correction ends: {{ new Date(item.correction_deadline).toLocaleString() }}
              </span>
            </div>
          </div>
          
          <div v-if="item.correction_reason" class="reason-display">
            <strong>Applicant Reason:</strong> {{ item.correction_reason }}
          </div>
          
          <FileUpload v-if="!isItemLocked(item)" :checklist-id="item.id" :status="item.status" @upload-success="fetchForm" />
          <div v-else class="locked-msg">
            Uploads are currently locked for this item.
          </div>

          <div v-if="item.versions && item.versions.length > 0" class="versions-list">
            <p><strong>Uploaded Versions (max 3):</strong></p>
            <ul>
              <li v-for="version in item.versions" :key="version.id">
                {{ version.file_name }} ({{ new Date(version.uploaded_at).toLocaleString() }})
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-container {
  max-width: 920px;
  margin: 40px auto;
  padding: 2rem;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
}
.hero h2 {
  margin: 0 0 0.4rem;
}
.hero p {
  margin: 0 0 1.2rem;
  color: #64748b;
}
.status-banner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  background-color: #f8fafc;
  padding: 1rem;
  border-radius: 10px;
  margin-bottom: 2rem;
}
.progress-wrap {
  align-self: center;
}
.progress-label {
  margin: 0 0 0.35rem;
  font-size: 0.9rem;
  color: #0f172a;
}
.progress-track {
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #06b6d4);
}
.checklist-item {
  border: 1px solid #e2e8f0;
  padding: 1rem;
  border-radius: 10px;
  margin-bottom: 1.1rem;
  text-align: left;
  background: #fcfdff;
}
.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.badges {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.badge {
  background-color: #334155;
  color: white;
  padding: 0.3rem 0.6rem;
  border-radius: 999px;
  font-size: 0.8rem;
}
.badge.submitted {
  background: #15803d;
}
.badge.correction {
  background: #d97706;
}
.badge.locked {
  background: #dc2626;
}
.badge.timer {
  background: #0284c7;
}
.badge.error {
  background: #dc2626;
  margin-left: 0.5rem;
}
.reason-display {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #fdf6e3;
  border-left: 4px solid #fbbf24;
  font-size: 0.9rem;
  color: #92400e;
}
.locked-msg {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: #dc2626;
  font-style: italic;
}
.versions-list {
  margin-top: 1rem;
  font-size: 0.9rem;
  background-color: #f1f5f9;
  padding: 0.7rem;
  border-radius: 8px;
}
.loading {
  color: #334155;
}
.error {
  color: #b91c1c;
}
</style>