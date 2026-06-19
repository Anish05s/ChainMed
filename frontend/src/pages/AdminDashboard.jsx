import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { 
  getFlaggedShipments, 
  overrideFlag, 
  getOverrideRequests, 
  getOverrideDetail, 
  voteOnOverride 
} from '../api/admin'

export default function AdminDashboard() {
  const { user, logout } = useAuth()
  const [flags, setFlags] = useState([])
  const [overrides, setOverrides] = useState([])
  const [loading, setLoading] = useState(true)
  
  // Modals
  const [selectedFlag, setSelectedFlag] = useState(null)
  const [selectedOverride, setSelectedOverride] = useState(null)
  
  // Forms
  const [justification, setJustification] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const isDev = user?.sub_role === 'admin_dev'

  async function loadData() {
    try {
      const [flagsData, overridesData] = await Promise.all([
        getFlaggedShipments(),
        getOverrideRequests()
      ])
      setFlags(flagsData)
      setOverrides(overridesData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  async function handleInitiateOverride(e) {
    e.preventDefault()
    if (!justification) return
    setSubmitting(true)
    setError('')
    try {
      await overrideFlag(selectedFlag.shipment_id, justification)
      setSelectedFlag(null)
      setJustification('')
      loadData()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to initiate override')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleVote(voteType) {
    setSubmitting(true)
    setError('')
    try {
      await voteOnOverride(selectedOverride.id, voteType)
      setSelectedOverride(null)
      loadData()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to record vote')
    } finally {
      setSubmitting(false)
    }
  }

  async function openOverrideDetail(req) {
    try {
      const detail = await getOverrideDetail(req.id)
      setSelectedOverride(detail)
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="min-h-screen text-slate-100 p-8" style={{ background: '#090e17' }}>
      <header className="flex justify-between items-center mb-10 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">Admin<span className="text-cyan-400">CommandCenter</span></h1>
          <p className="text-slate-400 text-sm mt-1">
            Logged in as <span className="font-semibold text-white">{user?.full_name}</span> ({user?.sub_role})
          </p>
        </div>
        <button onClick={logout} className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-semibold transition-colors">
          Sign Out
        </button>
      </header>

      <div className="max-w-6xl mx-auto space-y-12">
        {/* PENDING OVERRIDES SECTION */}
        <section>
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            Multi-Sig Override Requests
            {overrides.length > 0 && <span className="px-2 py-0.5 text-xs bg-cyan-900 text-cyan-300 rounded-full">{overrides.length}</span>}
          </h2>
          {loading ? (
            <p className="text-slate-500">Loading overrides...</p>
          ) : overrides.length === 0 ? (
            <div className="p-8 text-center border border-slate-800 rounded-2xl bg-slate-900/50">
              <p className="text-slate-400">No pending override requests.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {overrides.map(req => (
                <div key={req.id} className="p-5 border border-slate-800 rounded-xl bg-slate-900 flex flex-col justify-between">
                  <div className="mb-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className={`px-2.5 py-1 text-xs font-bold rounded-md uppercase tracking-wider ${
                        req.status === 'executed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {req.status}
                      </span>
                      <span className="text-xs text-slate-400">{req.current_approvals} / {req.required_approvals} Approvals</span>
                    </div>
                    <p className="text-sm text-slate-300 line-clamp-2">{req.justification}</p>
                  </div>
                  <button 
                    onClick={() => openOverrideDetail(req)}
                    className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-sm rounded-lg transition-colors"
                  >
                    View Details & Vote
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* AI FLAGS SECTION */}
        <section>
          <h2 className="text-xl font-bold mb-4">Pending AI Flags</h2>
          {loading ? (
            <p className="text-slate-500">Loading flags...</p>
          ) : flags.length === 0 ? (
            <div className="p-12 text-center border border-slate-800 rounded-2xl bg-slate-900/50">
              <p className="text-slate-400">No active AI flags to review.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {flags.map(f => (
                <div key={f.shipment_id} className="p-5 border border-slate-800 rounded-xl bg-slate-900 flex justify-between items-center">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="px-2.5 py-1 text-xs font-bold bg-red-500/20 text-red-400 rounded-md">
                        RISK {f.risk_score}
                      </span>
                      <h3 className="font-semibold">{f.shipment_code} ({f.medicine_name})</h3>
                      {f.active_override_request_id && (
                        <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">Override Pending</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400 max-w-2xl line-clamp-1">{f.explanation}</p>
                  </div>
                  <button 
                    onClick={() => setSelectedFlag(f)}
                    className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-sm rounded-lg transition-colors"
                  >
                    Review
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Flag Review Modal */}
      {selectedFlag && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl p-8 rounded-2xl border border-slate-800" style={{ background: '#111827' }}>
            <h3 className="text-2xl font-bold mb-4">Review AI Flag</h3>
            
            <div className="p-4 rounded-xl bg-red-950/30 border border-red-900 mb-6">
              <p className="text-sm text-red-200 mb-2 font-mono uppercase tracking-widest text-xs">AI Analysis</p>
              <p className="text-slate-200 leading-relaxed">{selectedFlag.explanation}</p>
            </div>

            {selectedFlag.active_override_request_id ? (
              <div className="p-4 rounded-xl bg-amber-900/20 border border-amber-900 mb-6">
                <p className="text-amber-200 font-semibold mb-1">Override Already Requested</p>
                <p className="text-sm text-amber-300/70">An override request is currently pending for this shipment. Please review it in the requests section to cast your vote.</p>
              </div>
            ) : isDev ? (
              <div className="p-4 rounded-xl bg-amber-900/20 border border-amber-900 mb-6">
                <p className="text-amber-200 font-semibold mb-1">Override Locked</p>
                <p className="text-sm text-amber-300/70">Your role ({user.sub_role}) does not have permission to initiate overrides. You may only view raw data for debugging purposes.</p>
              </div>
            ) : (
              <form onSubmit={handleInitiateOverride}>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 block">Compliance Justification</label>
                    <textarea 
                      required
                      className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm min-h-[100px] focus:border-cyan-500 outline-none transition-colors text-white"
                      placeholder="Explain why this shipment should be overridden. This will be voted on by other admins."
                      value={justification}
                      onChange={e => setJustification(e.target.value)}
                    />
                  </div>
                  {error && <p className="text-red-400 text-xs">{error}</p>}
                  <div className="flex gap-3 mt-6">
                    <button type="button" onClick={() => setSelectedFlag(null)} className="flex-1 py-2.5 rounded-xl font-semibold text-sm border border-slate-700 hover:bg-slate-800 transition-colors">Cancel</button>
                    <button type="submit" disabled={submitting} className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 transition-colors">
                      {submitting ? 'Initiating...' : 'Initiate Override Request'}
                    </button>
                  </div>
                </div>
              </form>
            )}
            
            {(isDev || selectedFlag.active_override_request_id) && (
              <button onClick={() => setSelectedFlag(null)} className="mt-4 w-full px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 font-semibold text-sm transition-colors">Close</button>
            )}
          </div>
        </div>
      )}

      {/* Override Detail Modal */}
      {selectedOverride && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto py-10">
          <div className="w-full max-w-2xl p-8 rounded-2xl border border-slate-800 bg-[#111827] my-auto">
            <h3 className="text-2xl font-bold mb-4">Override Request Details</h3>
            
            <div className="space-y-6">
              <div className="p-4 bg-slate-900 rounded-xl border border-slate-800">
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Status</p>
                <div className="flex items-center justify-between">
                  <span className={`px-2.5 py-1 text-sm font-bold rounded-md uppercase tracking-wider ${
                    selectedOverride.status === 'executed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                  }`}>
                    {selectedOverride.status}
                  </span>
                  <span className="text-sm font-semibold text-slate-300">
                    {selectedOverride.current_approvals} of {selectedOverride.required_approvals} Required Approvals
                  </span>
                </div>
              </div>

              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Justification</p>
                <p className="text-slate-200 text-sm leading-relaxed p-4 bg-slate-900 rounded-xl border border-slate-800">
                  {selectedOverride.justification}
                </p>
              </div>

              {selectedOverride.ai_cross_check && (
                <div>
                  <p className="text-xs text-cyan-400 uppercase tracking-wider mb-2">AI Cross-Check Result</p>
                  <p className="text-cyan-100 text-sm leading-relaxed p-4 bg-cyan-950/30 rounded-xl border border-cyan-900">
                    {selectedOverride.ai_cross_check}
                  </p>
                </div>
              )}

              {selectedOverride.override_blockchain_hash && (
                <div>
                  <p className="text-xs text-emerald-400 uppercase tracking-wider mb-2">Blockchain TX Hash</p>
                  <p className="text-emerald-100 text-xs font-mono p-3 bg-emerald-950/30 rounded-xl border border-emerald-900 break-all">
                    {selectedOverride.override_blockchain_hash}
                  </p>
                </div>
              )}

              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Votes Cast</p>
                {selectedOverride.votes?.length > 0 ? (
                  <div className="space-y-2">
                    {selectedOverride.votes.map(v => (
                      <div key={v.id} className="flex justify-between items-center p-3 bg-slate-900 rounded-xl border border-slate-800 text-sm">
                        <span><span className="font-semibold">{v.admin_name}</span> ({v.admin_sub_role})</span>
                        <span className={`font-bold uppercase ${v.vote === 'approve' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {v.vote}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 italic">No votes cast yet.</p>
                )}
              </div>

              {/* Voting Actions */}
              {selectedOverride.status === 'pending' && !isDev && !selectedOverride.votes?.find(v => v.admin_id === user.id) && (
                <div className="pt-4 border-t border-slate-800">
                  <p className="text-sm text-slate-300 mb-4 text-center">Cast your vote on this override request:</p>
                  {error && <p className="text-red-400 text-xs text-center mb-4">{error}</p>}
                  <div className="flex gap-4">
                    <button 
                      onClick={() => handleVote('reject')}
                      disabled={submitting}
                      className="flex-1 py-3 rounded-xl font-bold text-sm text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 transition-colors"
                    >
                      Reject
                    </button>
                    <button 
                      onClick={() => handleVote('approve')}
                      disabled={submitting}
                      className="flex-1 py-3 rounded-xl font-bold text-sm text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                    >
                      Approve Override
                    </button>
                  </div>
                </div>
              )}
              
              <div className="pt-4 mt-6">
                <button onClick={() => setSelectedOverride(null)} className="w-full px-4 py-3 rounded-xl border border-slate-700 hover:bg-slate-800 font-semibold text-sm transition-colors">
                  Close Details
                </button>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  )
}

