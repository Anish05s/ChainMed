import api from './client'

export async function getIncomingShipments() {
  const { data } = await api.get('/supplier/shipments/incoming')
  return data
}

export async function verifyShipment(shipmentId, payload) {
  const { data } = await api.post(`/supplier/shipments/${shipmentId}/verify`, payload)
  return data
}
export async function getDispatchableBatches() {
  const { data } = await api.get('/supplier/inventory/dispatchable')
  return data
}

export async function dispatchOutbound(payload) {
  const { data } = await api.post('/supplier/shipments/outbound', payload)
  return data
}

export async function getInventory() {
  const { data } = await api.get('/supplier/inventory')
  return data
}

export async function updateInventory(payload) {
  const { data } = await api.put('/supplier/inventory', payload)
  return data
}

export async function createRestockRequest(payload) {
  const { data } = await api.post('/supplier/restock-requests', payload)
  return data
}

export async function getMyRestockRequests() {
  const { data } = await api.get('/supplier/restock-requests/mine')
  return data
}

export async function resolveRestockRequest(id) {
  const { data } = await api.post(`/supplier/restock-requests/${id}/resolve`)
  return data
}
