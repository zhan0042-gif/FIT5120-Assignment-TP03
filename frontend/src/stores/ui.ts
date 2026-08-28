import { defineStore } from 'pinia'
import { ref } from 'vue'

const COLLAPSE_KEY = 'firebreak.sidebar-collapsed.v1'

export const useUiStore = defineStore('ui', () => {
  const sidebarCollapsed = ref(localStorage.getItem(COLLAPSE_KEY) === '1')
  const mobileMenuOpen = ref(false)

  function toggleCollapsed() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem(COLLAPSE_KEY, sidebarCollapsed.value ? '1' : '0')
  }

  function openMobileMenu() {
    mobileMenuOpen.value = true
  }

  function closeMobileMenu() {
    mobileMenuOpen.value = false
  }

  return { sidebarCollapsed, mobileMenuOpen, toggleCollapsed, openMobileMenu, closeMobileMenu }
})
