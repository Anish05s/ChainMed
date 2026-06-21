import api from './client'

export async function getApprovalLogs(params = {}) {
  const { data } = await api.get('/approval-logs', { params: { limit: 100, ...params } })
  return data
}

export async function getPublicShipment(shipmentId) {
  const { data } = await api.get(`/shared/shipment/${shipmentId}`)
  return data
}

export async function submitShipmentDispute(shipmentId, justification) {
  const { data } = await api.post(`/shared/shipment/${shipmentId}/dispute`, { justification })
  return data
}
