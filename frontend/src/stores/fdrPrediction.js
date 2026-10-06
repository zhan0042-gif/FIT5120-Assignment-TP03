import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client.js'


export const useFdrPredictionStore = defineStore('fdrPrediction', () => {
  const result = ref(null)
  const status = ref('idle')
  const error = ref(null)

  async function predict(district, date) {
    if (!district || !date) {
      result.value = null
      status.value = 'error'
      error.value = 'Please select a fire district and date.'
      return
    }

    status.value = 'loading'
    error.value = null

    try {
      result.value = await api.getFdrPrediction(
        district,
        date,
      )

      status.value = 'success'
    } catch (thrown) {
      result.value = null
      status.value = 'error'
      error.value =
        thrown instanceof Error
          ? thrown.message
          : 'The FDR estimate could not be generated.'
    }
  }

  function reset() {
    result.value = null
    status.value = 'idle'
    error.value = null
  }

  return {
    result,
    status,
    error,
    predict,
    reset,
  }
})