import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import { initializeTheme } from './theme'

initializeTheme()
createApp(App).use(createPinia()).use(router).mount('#app')
