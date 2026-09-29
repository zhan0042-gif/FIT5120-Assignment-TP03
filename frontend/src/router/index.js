import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  // Each route has one product responsibility: entry, plan editing, status
  // review, or saved-plan scenario testing. Navigation order lives in AppLayout.
  routes: [
    {
      path: '/',
      name: 'welcome',
      component: () => import('../views/WelcomeView.vue'),
    },
    {
      path: '/overview',
      name: 'overview',
      component: () => import('../views/OverviewView.vue'),
    },
    {
      path: '/plan',
      name: 'plan-builder',
      component: () => import('../views/PlanBuilderView.vue'),
    },
    {
      path: '/map',
      name: 'fire-map',
      component: () => import('../views/MapView.vue'),
    },
    {
      path: '/travel-readiness',
      name: 'travel-readiness',
      component: () => import('../views/TravelReadinessView.vue'),
    },
    {
      path: '/scenarios',
      name: 'scenario-tester',
      component: () => import('../views/ScenarioTesterView.vue'),
    },
    {
      path: '/summary',
      redirect: '/overview',
    },
    {
      path: '/review',
      name: 'review-reminders',
      redirect: '/overview',
    },
  ],
})

export default router
