import api from './client'

export async function getFlaggedShipments() {
  const { data } = await api.get('/admin/flags')
  return data
}

export async function overrideFlag(shipmentId, justification) {
  // Initiates an override request
  const { data } = await api.post(`/admin/flags/${shipmentId}/override`, { justification })
  return data
}

export async function getOverrideRequests() {
  const { data } = await api.get('/admin/overrides')
  return data
}

export async function getOverrideDetail(overrideId) {
  const { data } = await api.get(`/admin/overrides/${overrideId}`)
  return data
}

export async function voteOnOverride(overrideId, vote) {
  const { data } = await api.post(`/admin/overrides/${overrideId}/vote`, { vote })
  return data
}
