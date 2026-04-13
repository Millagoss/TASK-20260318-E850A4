<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { API_BASE } from '../config/apiBase'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const accounts = ref<any[]>([])
const selectedAccountId = ref<number | null>(null)
const transactions = ref<any[]>([])
const categoryAgg = ref<any[]>([])
const monthAgg = ref<any[]>([])
const errorMsg = ref('')
const loading = ref(false)
const showWarningModal = ref(false)
const warningText = ref('')
const pendingPayload = ref<any>(null)
const confirmOverride = ref(false)

const createForm = ref({ registration_form_id: '', total_budget: '' })
const txForm = ref({ transaction_type: 'expense', category: '', amount: '', note: '' })
const invoiceFile = ref<File | null>(null)

async function fetchAccounts() {
  const response = await fetch(`${API_BASE}/financial/accounts`, {
    headers: { Authorization: `Bearer ${authStore.token}` },
  })
  accounts.value = await response.json()
}

async function fetchDetails() {
  if (!selectedAccountId.value) return
  const [txRes, catRes, monthRes] = await Promise.all([
    fetch(`${API_BASE}/financial/transactions?funding_account_id=${selectedAccountId.value}`, { headers: { Authorization: `Bearer ${authStore.token}` } }),
    fetch(`${API_BASE}/financial/aggregates/by-category?funding_account_id=${selectedAccountId.value}`, { headers: { Authorization: `Bearer ${authStore.token}` } }),
    fetch(`${API_BASE}/financial/aggregates/by-month?funding_account_id=${selectedAccountId.value}`, { headers: { Authorization: `Bearer ${authStore.token}` } }),
  ])
  transactions.value = await txRes.json()
  categoryAgg.value = await catRes.json()
  monthAgg.value = await monthRes.json()
}

async function createAccount() {
  loading.value = true
  errorMsg.value = ''
  try {
    const response = await fetch(`${API_BASE}/financial/accounts`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authStore.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        registration_form_id: Number(createForm.value.registration_form_id),
        total_budget: Number(createForm.value.total_budget),
      }),
    })
    if (!response.ok) throw new Error((await response.json()).detail || 'Failed to create account')
    createForm.value = { registration_form_id: '', total_budget: '' }
    await fetchAccounts()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

function onInvoiceChange(e: Event) {
  const target = e.target as HTMLInputElement
  invoiceFile.value = target.files?.[0] || null
}

async function submitTransaction(override = false) {
  if (!selectedAccountId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const form = new FormData()
    form.append('funding_account_id', String(selectedAccountId.value))
    form.append('transaction_type', txForm.value.transaction_type)
    form.append('category', txForm.value.category)
    form.append('amount', txForm.value.amount)
    form.append('note', txForm.value.note)
    form.append('override_budget_warning', String(override))
    if (invoiceFile.value) form.append('invoice', invoiceFile.value)

    const response = await fetch(`${API_BASE}/financial/transactions`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authStore.token}` },
      body: form,
    })

    if (!response.ok) {
      const err = await response.json()
      if (response.status === 409 && err?.detail?.code === 'BUDGET_WARNING') {
        warningText.value = err.detail.message
        pendingPayload.value = true
        showWarningModal.value = true
        return
      }
      throw new Error(err.detail?.message || err.detail || 'Failed to create transaction')
    }

    txForm.value = { transaction_type: 'expense', category: '', amount: '', note: '' }
    invoiceFile.value = null
    await fetchDetails()
  } catch (err: any) {
    errorMsg.value = err.message
  } finally {
    loading.value = false
  }
}

async function confirmBudgetOverride() {
  if (!confirmOverride.value || !pendingPayload.value) return
  showWarningModal.value = false
  pendingPayload.value = null
  await submitTransaction(true)
}

onMounted(fetchAccounts)
</script>

<template>
  <div class="fin-wrap">
    <h2>Financial Dashboard</h2>
    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

    <div class="card">
      <h3>Create Funding Account</h3>
      <div class="row">
        <input v-model="createForm.registration_form_id" placeholder="Registration Form ID" />
        <input v-model="createForm.total_budget" placeholder="Total Budget" />
        <button :disabled="loading" @click="createAccount">Create</button>
      </div>
    </div>

    <div class="card">
      <h3>Funding Accounts</h3>
      <div class="row">
        <select v-model="selectedAccountId" @change="fetchDetails">
          <option :value="null">Select account</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">#{{ acc.id }} (form {{ acc.registration_form_id }}, budget {{ acc.total_budget }})</option>
        </select>
      </div>
    </div>

    <div v-if="selectedAccountId" class="card">
      <h3>Record Income/Expense</h3>
      <div class="row">
        <select v-model="txForm.transaction_type">
          <option value="income">income</option>
          <option value="expense">expense</option>
        </select>
        <input v-model="txForm.category" placeholder="Category" />
        <input v-model="txForm.amount" placeholder="Amount" type="number" />
        <input v-model="txForm.note" placeholder="Note" />
        <input type="file" accept=".pdf,.jpg,.jpeg,.png" @change="onInvoiceChange" />
        <button :disabled="loading" @click="submitTransaction()">{{ loading ? 'Saving...' : 'Save Transaction' }}</button>
      </div>
    </div>

    <div v-if="selectedAccountId" class="grid">
      <div class="card">
        <h3>By Category</h3>
        <div v-for="item in categoryAgg" :key="item.dimension">{{ item.dimension }}: {{ item.total_amount }}</div>
      </div>
      <div class="card">
        <h3>By Month</h3>
        <div v-for="item in monthAgg" :key="item.dimension">{{ item.dimension }}: {{ item.total_amount }}</div>
      </div>
    </div>

    <div v-if="selectedAccountId" class="card">
      <h3>Transactions</h3>
      <div v-for="tx in transactions" :key="tx.id">
        #{{ tx.id }} | {{ tx.transaction_type }} | {{ tx.category }} | {{ tx.amount }} | {{ new Date(tx.created_at).toLocaleString() }}
      </div>
    </div>

    <div v-if="showWarningModal" class="modal-backdrop">
      <div class="modal">
        <h3>Budget Warning</h3>
        <p>{{ warningText }}</p>
        <label class="row"><input type="checkbox" v-model="confirmOverride" /> I confirm I want to override this warning.</label>
        <div class="row">
          <button :disabled="!confirmOverride" @click="confirmBudgetOverride">Confirm & Submit</button>
          <button class="secondary" @click="showWarningModal = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fin-wrap { padding: 1rem; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
.row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
input, select, button { padding: 0.5rem; border-radius: 8px; border: 1px solid #cbd5e1; }
button { background: #2563eb; color: white; border: none; cursor: pointer; }
.secondary { background: #475569; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.error { color: #dc2626; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.5); display: grid; place-items: center; }
.modal { background: #fff; border-radius: 10px; padding: 1rem; width: 520px; max-width: 95vw; }
</style>
