import api from './client'

export async function getIncomingShipments() {
  const { data } = await api.get('/consumer/shipments/incoming')
  return data
}

export async function confirmReceipt(shipmentId, payload) {
  const { data } = await api.post(`/consumer/shipments/${shipmentId}/confirm`, payload)
  return data
}

export async function getInventory() {
  const { data } = await api.get('/consumer/inventory')
  return data
}

export async function updateInventory(payload) {
  const { data } = await api.put('/consumer/inventory', payload)
  return data
}

export async function createStockRequest(payload) {
  const { data } = await api.post('/consumer/stock-requests', payload)
  return data
}

export async function clearStock(payload) {
  const { data } = await api.post('/consumer/inventory/clearance', payload)
  return data
}

export async function getStockClearances() {
  const { data } = await api.get('/consumer/inventory/clearances')
  return data
}

export async function getMyRestockRequests() {
  const { data } = await api.get('/consumer/restock-requests/mine')
  return data
}

export async function resolveRestockRequest(id) {
  const { data } = await api.post(`/consumer/restock-requests/${id}/resolve`)
  return data
}
