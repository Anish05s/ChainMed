import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { getApprovalLogs } from '../api/approvalLogs'

const FILTERS = ['', 'batch_creation', 'shipment_dispatch', 'incoming_verification', 'receipt_confirmation', 'emergency_restock', 'emergency_stock_request', 'admin_override']

const ACTION_COLORS = {
  batch_creation:          { bg: 'rgba(8,145,178,0.08)',  color: '#0891b2' },
  shipment_dispatch:       { bg: 'rgba(124,58,237,0.08)', color: '#7c3aed' },
  incoming_verification:   { bg: 'rgba(5,150,105,0.08)', color: '#059669' },
  receipt_confirmation:    { bg: 'rgba(5,150,105,0.08)', color: '#059669' },
  emergency_restock:       { bg: 'rgba(217,119,6,0.08)', color: '#d97706' },
  emergency_stock_request: { bg: 'rgba(220,38,38,0.08)',  color: '#dc2626' },
  stock_clearance:         { bg: 'rgba(100,116,139,0.08)', color: '#64748b' },
  admin_override:          { bg: 'rgba(202,138,4,0.08)', color: '#ca8a04' },
}

function formatTime(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function ApprovalLogPage() {
  const [logs,    setLogs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('')

  useEffect(() => {
    setLoading(true)
    const params = filter ? { action_type: filter } : {}
    getApprovalLogs(params)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false))
  }, [filter])

  return (
    <Layout title="Approval Audit Trail">
      {/* Filter pills */}
      <div className="flex flex-wrap gap-2 mb-6">
        {FILTERS.map((f) => {
          const active = filter === f
          return (
            <button
              key={f || 'all'}
              type="button"
              onClick={() => setFilter(f)}
              className="text-xs px-3 py-1.5 rounded-full font-bold transition-all duration-200 hover:scale-105"
              style={active
                ? { background: 'linear-gradient(135deg,#0891b2,#3b82f6)', color: 'white', boxShadow: '0 2px 10px rgba(8,145,178,0.2)' }
                : { background: '#ffffff', color: 'var(--text-muted)', border: '1px solid var(--border)' }
              }
            >
              {f ? f.replace(/_/g, ' ') : 'All actions'}
            </button>
          )
        })}
      </div>

      {/* Log entries */}
      <div className="rounded-2xl overflow-hidden" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
        <div className="px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <h2 className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>Immutable Audit Log</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>Every action is append-only — no edits, no deletions, ever</p>
        </div>

        {loading ? (
          <div className="p-10 flex items-center justify-center gap-3 text-sm font-semibold animate-pulse" style={{ color: 'var(--text-light)' }}>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading audit log…
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-light)' }}>No audit log entries yet.</p>
          </div>
        ) : (
          <ul className="divide-y" style={{ '--tw-divide-opacity': 1, borderColor: 'var(--border)' }}>
            {logs.map((log, i) => {
              const c = ACTION_COLORS[log.action_type] || { bg: 'rgba(100,116,139,0.08)', color: '#64748b' }
              return (
                <li
                  key={log.id}
                  className="px-6 py-4 transition-colors animate-slide-up"
                  style={{ borderBottom: '1px solid var(--border)', animationDelay: `${i * 20}ms` }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <span
                      className="text-xs font-bold px-2.5 py-0.5 rounded-full flex-shrink-0"
                      style={{ background: c.bg, color: c.color }}
                    >
                      {log.action_type?.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-semibold flex-shrink-0" style={{ color: 'var(--text-light)' }}>{formatTime(log.created_at)}</span>
                  </div>

                  <p className="text-sm font-bold" style={{ color: 'var(--text-base)' }}>
                    {log.actor_name}{' '}
                    <span className="font-semibold text-xs" style={{ color: 'var(--text-light)' }}>({log.actor_role?.replace(/_/g, ' ')})</span>
                  </p>

                  {log.notes && (
                    <p className="text-xs mt-1.5 leading-relaxed font-medium" style={{ color: 'var(--text-muted)' }}>{log.notes}</p>
                  )}

                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-light)' }}>
                      {log.entity_type} · {log.entity_id?.slice(0, 12)}…
                    </span>
                    {log.entity_type === 'shipment' && log.entity_id && (
                      <Link
                        to={`/shared/shipment/${log.entity_id}`}
                        className="text-xs font-bold transition-opacity hover:opacity-70"
                        style={{ color: 'var(--cyan)' }}
                      >
                        View shipment →
                      </Link>
                    )}
                    {log.blockchain_hash && (
                      <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-light)' }} title={log.blockchain_hash}>
                        ⛓ {log.blockchain_hash.slice(0, 16)}…
                      </span>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Layout>
  )
}
