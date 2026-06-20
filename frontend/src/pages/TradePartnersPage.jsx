import { useState, useEffect } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function TradePartnersPage() {
  const { user } = useAuth()
  const [partnerships, setPartnerships] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  
  const [newPartnerId, setNewPartnerId] = useState('')
  const [requestError, setRequestError] = useState('')
  const [requestSuccess, setRequestSuccess] = useState('')

  async function loadPartnerships() {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/shared/partnerships')
      setPartnerships(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load partnerships')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPartnerships()
  }, [])

  async function handleRequest(e) {
    e.preventDefault()
    setRequestError('')
    setRequestSuccess('')
    if (!newPartnerId.trim()) return
    
    try {
      await api.post('/shared/partnerships/request', { partner_entity_id: newPartnerId.trim() })
      setRequestSuccess('Partnership request sent!')
      setNewPartnerId('')
      loadPartnerships()
    } catch (err) {
      setRequestError(err.response?.data?.detail || 'Failed to send request')
    }
  }

  async function handleAccept(id) {
    try {
      await api.post(`/shared/partnerships/${id}/accept`)
      loadPartnerships()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to accept')
    }
  }

  async function handleReject(id) {
    try {
      await api.post(`/shared/partnerships/${id}/reject`)
      loadPartnerships()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reject')
    }
  }

  async function handleRevoke(id) {
    if (!confirm("Are you sure you want to revoke this partnership? You will not be able to dispatch to them anymore.")) return
    try {
      await api.delete(`/shared/partnerships/${id}`)
      loadPartnerships()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to revoke')
    }
  }

  if (loading) return <div className="p-8 text-center" style={{ color: 'var(--text-muted)' }}>Loading network...</div>

  // Separate pending incoming from active/others
  const pendingIncoming = partnerships.filter(
    (p) => p.status === 'pending' && p.requested_by !== user?.entity_id
  )
  
  const pendingOutgoing = partnerships.filter(
    (p) => p.status === 'pending' && p.requested_by === user?.entity_id
  )
  
  const activePartners = partnerships.filter(
    (p) => p.status === 'active'
  )

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-base)' }}>Trade Network Management</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-light)' }}>
          Manage your verified partnerships. Only active partners can send or receive shipments.
        </p>
      </div>

      {/* Request Form */}
      <div className="p-6 rounded-2xl shadow-sm border border-slate-200/10" style={{ background: 'var(--bg-panel)' }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-base)' }}>Request New Partner</h2>
        <form onSubmit={handleRequest} className="flex gap-4">
          <input
            type="text"
            className="flex-1 px-4 py-2 rounded-xl border text-sm"
            style={{ 
              background: 'var(--bg-base)', 
              borderColor: 'var(--border)', 
              color: 'var(--text-base)' 
            }}
            placeholder="Enter Partner Entity ID (e.g. mfg-001 or sup-001)"
            value={newPartnerId}
            onChange={(e) => setNewPartnerId(e.target.value)}
          />
          <button
            type="submit"
            className="px-6 py-2 rounded-xl text-white font-semibold text-sm hover:opacity-90 transition-opacity"
            style={{ background: 'var(--cyan)' }}
          >
            Send Request
          </button>
        </form>
        {requestError && <p className="text-red-500 text-sm mt-2">{requestError}</p>}
        {requestSuccess && <p className="text-green-500 text-sm mt-2">{requestSuccess}</p>}
      </div>

      {/* Pending Incoming */}
      {pendingIncoming.length > 0 && (
        <div className="p-6 rounded-2xl shadow-sm border border-amber-500/20" style={{ background: 'rgba(245, 158, 11, 0.05)' }}>
          <h2 className="text-lg font-bold text-amber-500 mb-4 flex items-center gap-2">
            <span>⚠️</span> Pending Incoming Requests ({pendingIncoming.length})
          </h2>
          <div className="space-y-3">
            {pendingIncoming.map(p => {
              const partnerId = p.from_entity_id === user?.entity_id ? p.to_entity_id : p.from_entity_id
              const partnerType = p.from_entity_id === user?.entity_id ? p.to_entity_type : p.from_entity_type
              return (
                <div key={p.id} className="flex items-center justify-between p-4 rounded-xl border" style={{ background: 'var(--bg-panel)', borderColor: 'var(--border)' }}>
                  <div>
                    <p className="font-semibold" style={{ color: 'var(--text-base)' }}>{partnerId}</p>
                    <p className="text-xs uppercase font-medium" style={{ color: 'var(--text-muted)' }}>{partnerType}</p>
                  </div>
                  <div className="flex gap-3">
                    <button 
                      onClick={() => handleAccept(p.id)}
                      className="px-4 py-1.5 rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 text-sm font-semibold transition-colors"
                    >
                      Accept
                    </button>
                    <button 
                      onClick={() => handleReject(p.id)}
                      className="px-4 py-1.5 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 text-sm font-semibold transition-colors"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Pending Outgoing */}
      {pendingOutgoing.length > 0 && (
        <div className="p-6 rounded-2xl shadow-sm border border-slate-200/10" style={{ background: 'var(--bg-panel)' }}>
          <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-base)' }}>Outgoing Requests (Awaiting Approval)</h2>
          <div className="space-y-3">
            {pendingOutgoing.map(p => {
              const partnerId = p.from_entity_id === user?.entity_id ? p.to_entity_id : p.from_entity_id
              return (
                <div key={p.id} className="flex items-center justify-between p-4 rounded-xl border" style={{ background: 'var(--bg-base)', borderColor: 'var(--border)' }}>
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                    <span className="font-medium" style={{ color: 'var(--text-base)' }}>{partnerId}</span>
                  </div>
                  <button onClick={() => handleRevoke(p.id)} className="text-xs text-red-500 hover:underline">Cancel</button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Active Partners */}
      <div className="p-6 rounded-2xl shadow-sm border border-slate-200/10" style={{ background: 'var(--bg-panel)' }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-base)' }}>Active Partners</h2>
        {activePartners.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No active partnerships found.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activePartners.map(p => {
              const partnerId = p.from_entity_id === user?.entity_id ? p.to_entity_id : p.from_entity_id
              const partnerType = p.from_entity_id === user?.entity_id ? p.to_entity_type : p.from_entity_type
              return (
                <div key={p.id} className="p-5 rounded-xl border flex justify-between items-start" style={{ background: 'var(--bg-base)', borderColor: 'var(--border)' }}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                      <p className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>{partnerId}</p>
                    </div>
                    <p className="text-xs uppercase font-semibold" style={{ color: 'var(--text-muted)' }}>{partnerType}</p>
                  </div>
                  <button 
                    onClick={() => handleRevoke(p.id)}
                    className="text-xs text-red-500 hover:underline px-2 py-1 rounded hover:bg-red-500/10 transition-colors"
                  >
                    Revoke
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
}
