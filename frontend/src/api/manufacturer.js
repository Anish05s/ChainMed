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