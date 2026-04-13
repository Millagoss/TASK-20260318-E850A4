<script setup lang="ts">
import { ref } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{
  checklistId: number
  status: string
}>()

const emit = defineEmits<{
  (e: 'upload-success'): void
}>()

const file = ref<File | null>(null)
const reason = ref('')
const uploadStatus = ref('')
const uploading = ref(false)
const authStore = useAuthStore()

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    const selected = target.files[0]
    
    // Front-end validation
    const ext = selected.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'jpg', 'jpeg', 'png'].includes(ext || '')) {
      uploadStatus.value = 'Error: Only PDF, JPG, and PNG files are allowed.'
      file.value = null
      target.value = ''
      return
    }
    if (selected.size > 20 * 1024 * 1024) {
      uploadStatus.value = 'Error: File size exceeds the 20MB limit.'
      file.value = null
      target.value = ''
      return
    }
    
    file.value = selected
    uploadStatus.value = ''
  }
}

async function uploadFile() {
  if (!file.value) {
    uploadStatus.value = 'Please select a file first.'
    return
  }
  
  if (props.status === 'Needs Correction' && !reason.value.trim()) {
    uploadStatus.value = 'Error: A reason for correction is required.'
    return
  }

  const formData = new FormData()
  formData.append('file', file.value)
  if (reason.value.trim()) {
    formData.append('reason', reason.value.trim())
  }

  uploadStatus.value = 'Uploading...'
  uploading.value = true

  try {
    const response = await fetch(`${API_BASE}/upload/${props.checklistId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      body: formData
    })

    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Upload failed')
    }

    uploadStatus.value = 'Upload successful!'
    file.value = null
    emit('upload-success')
  } catch (err: any) {
    uploadStatus.value = `Error: ${err.message}`
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="file-upload">
    <div class="upload-controls">
      <label class="file-label">
        <input type="file" @change="handleFileChange" accept=".pdf,.jpg,.jpeg,.png" class="file-input" />
        <span>{{ file ? file.name : 'Choose file' }}</span>
      </label>
      <button @click="uploadFile" :disabled="!file || uploading" class="upload-btn">
        {{ uploading ? 'Uploading...' : 'Upload' }}
      </button>
    </div>
    
    <div v-if="props.status === 'Needs Correction'" class="correction-box">
      <label for="reason">Reason for correction (required):</label>
      <textarea id="reason" v-model="reason" placeholder="Explain your corrections..." rows="2"></textarea>
    </div>

    <p v-if="uploadStatus" :class="{ success: uploadStatus.includes('successful'), error: uploadStatus.includes('Error') }">
      {{ uploadStatus }}
    </p>
  </div>
</template>

<style scoped>
.file-upload {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.75rem;
}
.upload-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.correction-box {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #fffbeb;
  padding: 0.75rem;
  border: 1px solid #fde68a;
  border-radius: 8px;
}
.correction-box label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #92400e;
}
.correction-box textarea {
  border: 1px solid #fcd34d;
  border-radius: 4px;
  padding: 0.5rem;
  resize: vertical;
}
.file-label {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 0.55rem 0.9rem;
  background: #f8fafc;
  cursor: pointer;
  color: #334155;
}
.file-input {
  display: none;
}
.upload-btn {
  border: none;
  border-radius: 10px;
  padding: 0.55rem 0.9rem;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.success {
  color: #15803d;
}
.error {
  color: #b91c1c;
}
</style>