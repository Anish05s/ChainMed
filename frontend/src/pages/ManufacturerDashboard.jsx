import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import ChainVerificationPanel from '../components/ChainVerificationPanel'
import StatusBadge from '../components/StatusBadge'
import { getBatches, downloadComplianceReport } from '../api/manufacturer'
import { getManufacturerChain } from '../api/verification'

function fmt(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}
function expiringSoon(d) {
  if (!d) return false
  const days = (new Date(d) - Date.now()) / 86400000
  return days < 90 && days > 0
}

function StatCard({ label, value, hint, icon, fromColor, toColor, alert }) {
  return (
    <div
      className="p-5 rounded-2xl transition-all duration-200 hover:scale-[1.02] cursor-default"
      style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
    >
      <div className="flex items-start justify-between mb-4">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shadow-md text-white"
          style={{ background: `linear-gradient(135deg,${fromColor},${toColor})` }}
        >{icon}</div>
        {alert && (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: 'rgba(217,119,6,0.1)', color: 'var(--amber)', border: '1px solid rgba(217,119,6,0.2)' }}>
            Alert
          </span>
        )}
      </div>
      <p className="text-3xl font-black mb-1" style={{ color: 'var(--text-base)' }}>{value}</p>
      <p className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>{label}</p>
      {hint && <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{hint}</p>}
    </div>
  )
}

export default function ManufacturerDashboard() {
  const [batches,      setBatches]      = useState([])
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState('')
  const [chainReport,  setChainReport]  = useState(null)
  const [chainLoading, setChainLoading] = useState(false)
  const [chainError,   setChainError]   = useState('')
  const [activeBatchId,setActiveBatchId]= useState(null)
  const [pdfLoading,   setPdfLoading]   = useState({}) // { [batchId]: true/false }

  useEffect(() => {
    getBatches()
      .then(setBatches)
      .catch(() => setError('Unable to connect to the server. Please refresh the page or try again later.'))
      .finally(() => setLoading(false))
  }, [])

  async function runChainVerify(batchId) {
    if (activeBatchId === batchId) { setChainReport(null); setActiveBatchId(null); return }
    setChainLoading(true); setChainReport(null); setChainError(''); setActiveBatchId(batchId)
    try {
      setChainReport(await getManufacturerChain(batchId))
    } catch (err) {
      setChainError(err.response?.data?.detail || 'Verification failed')
    } finally {
      setChainLoading(false)
    }
  }

  async function handleExportReport(batchId, batchNumber) {
    setPdfLoading(prev => ({ ...prev, [batchId]: true }))
    try {
      await downloadComplianceReport(batchId, batchNumber)
    } catch (err) {
      alert('Failed to generate report: ' + (err.message || 'Unknown error'))
    } finally {
      setPdfLoading(prev => ({ ...prev, [batchId]: false }))
    }
  }

  const totalUnits     = batches.reduce((s, b) => s + (b.quantity || 0), 0)
  const dispatched     = batches.reduce((s, b) => s + (b.quantity_dispatched || 0), 0)
  const soonCount      = batches.filter(b => expiringSoon(b.expiry_date)).length

  return (
    <Layout
      title="Manufacturer Dashboard"
      actions={
        <>
          <Link
            to="/manufacturer/dispatch"
            className="text-sm px-4 py-2 rounded-xl font-semibold transition-all"
            style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', background: '#ffffff' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
            onMouseLeave={e => e.currentTarget.style.background = '#ffffff'}
          >
            Dispatch
          </Link>
          <Link
            to="/manufacturer/batch/create"
            className="text-sm px-5 py-2 rounded-xl font-bold text-white transition-all hover:scale-105"
            style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 12px rgba(8,145,178,0.2)' }}
          >
            + Create Batch
          </Link>
        </>
      }
    >
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard label="Total Batches" value={loading ? '…' : batches.length}
          icon="🧪" fromColor="#0891b2" toColor="#3b82f6" />
        <StatCard label="Total Units" value={loading ? '…' : totalUnits.toLocaleString()}
          hint={`${dispatched.toLocaleString()} dispatched`}
          icon="📦" fromColor="#7c3aed" toColor="#6d28d9" />
        <StatCard label="Expiring Soon" value={loading ? '…' : soonCount}
          hint="Within 90 days" icon="⏳"
          fromColor={soonCount > 0 ? '#d97706' : '#059669'}
          toColor={soonCount > 0 ? '#b45309' : '#047857'}
          alert={soonCount > 0} />
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-xl text-sm flex items-center gap-2" style={{ background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.2)', color: '#dc2626' }}>
          <span>⚠️</span> {error}
        </div>
      )}

      {/* Chain Verification Panel */}
      {(chainLoading || chainReport || chainError) && (
        <div className="mb-6">
          <ChainVerificationPanel
            report={chainReport}
            loading={chainLoading}
            error={chainError}
            onClose={() => { setChainReport(null); setActiveBatchId(null); setChainError('') }}
          />
        </div>
      )}

      {/* Batches table */}
      <div className="rounded-2xl overflow-hidden" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
        <div className="px-6 py-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h2 className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>Medicine Batches</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>Click "Chain Verify" to run 3-party AI cross-match</p>
          </div>
          <Link to="/manufacturer/dispatch" className="text-xs font-semibold transition-colors hover:opacity-80" style={{ color: 'var(--cyan)' }}>
            Dispatch to supplier →
          </Link>
        </div>

        {loading ? (
          <div className="p-10 flex items-center justify-center gap-3 text-sm" style={{ color: 'var(--text-light)' }}>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading batches…
          </div>
        ) : batches.length === 0 ? (
          <div className="p-14 text-center">
            <div className="text-5xl mb-4">🧪</div>
            <p className="text-sm mb-4" style={{ color: 'var(--text-light)' }}>No batches created yet.</p>
            <Link to="/manufacturer/batch/create" className="text-sm font-semibold hover:opacity-80 transition-opacity" style={{ color: 'var(--cyan)' }}>
              Create your first batch →
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
                  {['Batch #', 'Medicine', 'Units (rem / total)', 'Mfg Date', 'Expiry', 'AI Verify', 'Report'].map(h => (
                    <th key={h} className="text-left px-6 py-3 text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => {
                  const soon   = expiringSoon(b.expiry_date)
                  const active = activeBatchId === b.id
                  return (
                    <tr
                      key={b.id}
                      className="transition-colors"
                      style={{ borderBottom: '1px solid var(--border)', background: active ? 'rgba(8,145,178,0.06)' : 'transparent' }}
                      onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--bg-base)' }}
                      onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
                    >
                      <td className="px-6 py-4 font-mono text-xs font-bold" style={{ color: 'var(--cyan)' }}>{b.batch_number}</td>
                      <td className="px-6 py-4 font-semibold" style={{ color: 'var(--text-base)' }}>{b.name}</td>
                      <td className="px-6 py-4" style={{ color: 'var(--text-muted)' }}>
                        <span className="font-bold text-slate-800">{(b.quantity_remaining ?? b.quantity)?.toLocaleString()}</span>
                        <span> / {b.quantity?.toLocaleString()}</span>
                      </td>
                      <td className="px-6 py-4 text-xs" style={{ color: 'var(--text-light)' }}>{fmt(b.manufacturing_date)}</td>
                      <td className="px-6 py-4 text-xs">
                        {soon && <span className="mr-1">⚠️</span>}
                        <span style={{ color: soon ? 'var(--amber)' : 'var(--text-light)' }} className="font-semibold">{fmt(b.expiry_date)}</span>
                      </td>
                      <td className="px-6 py-4">
                        <button
                          id={`mfr-verify-${b.id}`}
                          type="button"
                          disabled={chainLoading}
                          onClick={() => runChainVerify(b.id)}
                          className="text-xs font-bold px-3 py-1.5 rounded-lg transition-all duration-200 hover:scale-105 disabled:opacity-50"
                          style={active
                            ? { background: 'linear-gradient(135deg,#0891b2,#3b82f6)', color: 'white', boxShadow: '0 2px 10px rgba(8,145,178,0.2)' }
                            : { background: 'rgba(8,145,178,0.08)', color: 'var(--cyan)', border: '1px solid rgba(8,145,178,0.18)' }
                          }
                        >
                          {active ? '▲ Hide' : '🔍 Chain Verify'}
                        </button>
                      </td>
                      <td className="px-6 py-4">
                        <button
                          id={`mfr-export-${b.id}`}
                          type="button"
                          disabled={!!pdfLoading[b.id]}
                          onClick={() => handleExportReport(b.id, b.batch_number)}
                          className="text-xs font-bold px-3 py-1.5 rounded-lg transition-all duration-200 hover:scale-105 disabled:opacity-60"
                          style={{ background: 'rgba(124,58,237,0.08)', color: '#7c3aed', border: '1px solid rgba(124,58,237,0.18)' }}
                        >
                          {pdfLoading[b.id] ? '⏳ …' : '📄 Export'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  )
}
