import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import DashboardView from '../views/DashboardView.vue'
import FormWizardView from '../views/FormWizardView.vue'
import ReviewerDashboardView from '../views/ReviewerDashboardView.vue'
import FinancialDashboardView from '../views/FinancialDashboardView.vue'
import UserManagementView from '../views/UserManagementView.vue'
import SystemAdminDashboardView from '../views/SystemAdminDashboardView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/signup',
      name: 'signup',
      component: SignupView
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true }
    },
    {
      path: '/wizard',
      name: 'wizard',
      component: FormWizardView,
      meta: { requiresAuth: true, roles: ['Applicant'] }
    },
    {
      path: '/reviewer',
      name: 'reviewer',
      component: ReviewerDashboardView,
      meta: { requiresAuth: true, roles: ['Reviewer', 'SystemAdmin'] }
    },
    {
      path: '/financial',
      name: 'financial',
      component: FinancialDashboardView,
      meta: { requiresAuth: true, roles: ['FinancialAdmin', 'SystemAdmin'] }
    },
    {
      path: '/user-management',
      name: 'user-management',
      component: UserManagementView,
      meta: { requiresAuth: true, roles: ['SystemAdmin'] }
    },
    {
      path: '/system-admin',
      name: 'system-admin',
      component: SystemAdminDashboardView,
      meta: { requiresAuth: true, roles: ['SystemAdmin'] }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard'
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const allowedRoles = to.meta.roles as string[] | undefined
  if (to.meta.requiresAuth && !authStore.token) {
    next({ name: 'login' })
  } else if (allowedRoles && !allowedRoles.includes(authStore.role)) {
    next({ name: 'dashboard' })
  } else if (to.name === 'login' && authStore.token) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
