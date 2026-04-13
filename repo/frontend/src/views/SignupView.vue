<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { API_BASE } from '../config/apiBase'

const email = ref('')
const password = ref('')
const errorMsg = ref('')

const router = useRouter()

function validateEmail(email: string) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

async function handleSignup() {
  errorMsg.value = ''
  
  if (!validateEmail(email.value)) {
    errorMsg.value = 'Please enter a valid email address.'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = 'Password must be at least 6 characters long.'
    return
  }

  try {
    const response = await fetch(`${API_BASE}/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: email.value,
        password: password.value,
        role: 'Applicant'
      })
    })

    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Signup failed')
    }

    // After successful signup, redirect to login
    router.push({ name: 'login' })
  } catch (err: any) {
    errorMsg.value = err.message
  }
}
</script>

<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <div class="auth-header">
        <h1>Create Account</h1>
        <p>Join the Activity Platform</p>
      </div>

      <form @submit.prevent="handleSignup" class="auth-form">
        <div class="form-group">
          <label for="email">Email Address</label>
          <div class="input-wrapper">
            <input 
              id="email"
              v-model="email" 
              type="email" 
              placeholder="name@example.com"
              required 
            />
          </div>
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <div class="input-wrapper">
            <input 
              id="password"
              v-model="password" 
              type="password" 
              placeholder="Min. 6 characters"
              required 
            />
          </div>
        </div>

        <button type="submit" class="btn-primary" :disabled="!validateEmail(email) || password.length < 6">
          Sign Up
        </button>

        <p class="auth-footer">
          Already have an account? <RouterLink to="/login">Sign in</RouterLink>
        </p>

        <Transition name="fade">
          <p v-if="errorMsg" class="error-message">{{ errorMsg }}</p>
        </Transition>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-wrapper {
  min-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: #ffffff;
  padding: 2.5rem;
  border-radius: 16px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
  border: 1px solid #f0f0f0;
}

.auth-header {
  text-align: center;
  margin-bottom: 2rem;
}

.auth-header h1 {
  margin: 0;
  font-size: 1.75rem;
  color: #1a1a1a;
  font-weight: 700;
}

.auth-header p {
  margin: 0.5rem 0 0;
  color: #666;
  font-size: 0.95rem;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #444;
  text-align: left;
}

.input-wrapper input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1.5px solid #e1e1e1;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.input-wrapper input:focus {
  outline: none;
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.btn-primary {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #4338ca;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.auth-footer {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  text-align: center;
  color: #666;
}

.auth-footer a {
  color: #4f46e5;
  text-decoration: none;
  font-weight: 600;
}

.auth-footer a:hover {
  text-decoration: underline;
}

.error-message {
  margin: 0;
  padding: 0.75rem;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 8px;
  font-size: 0.875rem;
  text-align: center;
  border: 1px solid #fee2e2;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>