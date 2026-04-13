<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="dashboard">
    <h2>Dashboard</h2>
    <p>Welcome! Your role is: <strong>{{ authStore.role }}</strong></p>
    
    <div class="actions" v-if="authStore.role === 'Applicant'">
      <RouterLink to="/wizard" class="btn">Go to Application Wizard</RouterLink>
    </div>
    <div class="actions" v-if="authStore.role === 'Reviewer'">
      <RouterLink to="/reviewer" class="btn">Go to Reviewer Dashboard</RouterLink>
    </div>

  </div>
</template>

<style scoped>
.dashboard {
  max-width: 600px;
}
.actions {
  margin: 2rem 0;
}
.btn {
  display: inline-block;
  padding: 0.5rem 1rem;
  background-color: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}
.logout-btn {
  background-color: #dc3545;
}
</style>