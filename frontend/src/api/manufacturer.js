import api from './client'

export async function getBatches() {
  const { data } = await api.get('/manufacturer/batches')
  return data
}

export async function createBatch(payload) {
  const { data } = await api.post('/manufacturer/batches', payload)
  return data
}

export async function dispatchShipment(payload) {
  const { data } = await api.post('/manufacturer/shipments', payload)
  return data
}

export async function createShipment(payload) {
  const { data } = await api.post('/manufacturer/shipments', payload)
  return data
}

export async function searchCatalog(query) {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  const { data } = await api.get(`/shared/catalog/medicines${q}`)
  return data
}

/**
 * Download a compliance PDF for a batch.
 * Uses native fetch (not axios) so we get a proper binary blob.
 * Triggers the browser's native download dialog automatically.
 */
export async function downloadComplianceReport(batchId, batchNumber) {
  const baseURL = import.meta.env.VITE_API_URL
  const token = localStorage.getItem('token')

  const response = await fetch(
    `${baseURL}/manufacturer/batches/${batchId}/compliance-report`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  )

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `HTTP ${response.status}`)
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = `compliance-report-${batchNumber || batchId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}