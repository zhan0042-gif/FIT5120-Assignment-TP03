import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('../views/OverviewView.vue'),
    },
    {
      path: '/plan',
      name: 'plan-builder',
      component: () => import('../views/PlanBuilderView.vue'),
    },
    {
      path: '/scenarios',
      name: 'scenario-tester',
      component: () => import('../views/ScenarioTesterView.vue'),
    },
    {
      path: '/review',
      name: 'review-reminders',
      redirect: '/',
    },
  ],
})

export default router
