import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { QRCode } from 'react-qr-code'
import StatusBadge from '../components/StatusBadge'
import { getPublicShipment } from '../api/shared'

function fmt(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const STAGE_META = {
  manufacturer_dispatch: { label: 'Manufacturer Dispatch', icon: '🏭', color: '#0891b2' },
  supplier_receipt:      { label: 'Supplier Receipt',      icon: '🚚', color: '#7c3aed' },
  hospital_receipt:      { label: 'Hospital Delivery',     icon: '🏥', color: '#059669' },
}

export default function PublicShipmentPage() {
  const { id: shipmentId } = useParams()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    getPublicShipment(shipmentId)
      .then(setData)
      .catch(err => setError(err.response?.data?.detail || 'Shipment not found'))
      .finally(() => setLoading(false))
  }, [shipmentId])

  const verifyUrl = `${window.location.origin}/shared/shipment/${shipmentId}`
  const isMock = data?.blockchain_hash?.startsWith('mock:')
  const isReal = data?.blockchain_hash && !isMock

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)', color: 'var(--text-base)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-20 px-6 py-4 flex items-center justify-between"
        style={{ background: '#ffffff', borderBottom: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
      >
        <Link to="/" className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-sm"
            style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)' }}
          >P</div>
          <span className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>ChainMed</span>
        </Link>
        <span
          className="text-xs font-bold px-3 py-1 rounded-full"
          style={{ background: 'rgba(8,145,178,0.08)', color: 'var(--cyan)', border: '1px solid rgba(8,145,178,0.18)' }}
        >
          🔍 Public Verification
        </span>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-10">
        {loading && (
          <div className="flex items-center justify-center py-24 gap-3 text-slate-500">
            <svg className="animate-spin h-6 w-6" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Verifying shipment…
          </div>
        )}

        {error && (
          <div className="px-5 py-4 rounded-2xl text-sm" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', color: '#dc2626' }}>
            ⚠️ {error}
          </div>
        )}

        {data && (
          <div className="space-y-5 animate-slide-up">
            {/* ── Main card ─────────────────────────────── */}
            <div className="p-6 rounded-2xl" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)' }}>
              <div className="flex items-start justify-between gap-3 mb-5">
                <div>
                  <p className="text-xs uppercase tracking-wider font-bold mb-1" style={{ color: 'var(--text-light)' }}>Shipment Code</p>
                  <h1 className="text-2xl font-black font-mono tracking-tight" style={{ color: 'var(--cyan)' }}>{data.shipment_code}</h1>
                  <p className="font-bold text-lg mt-1" style={{ color: 'var(--text-base)' }}>{data.batch_name}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>Batch #{data.batch_number}</p>
                </div>
                <StatusBadge status={data.status} />
              </div>

              <dl className="grid grid-cols-2 gap-4 mb-6">
                {[
                  { label: 'From', value: data.from_entity_name },
                  { label: 'To',   value: data.to_entity_name },
                  { label: 'Quantity', value: data.medicine_quantity ? `${data.medicine_quantity.toLocaleString()} units` : null },
                  { label: 'Expiry',   value: fmt(data.expiry_date) },
                  { label: 'Created',  value: fmt(data.created_at) },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <dt className="text-xs font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-light)' }}>{label}</dt>
                    <dd className="font-semibold text-sm" style={{ color: 'var(--text-base)' }}>{value || '—'}</dd>
                  </div>
                ))}
              </dl>

              {/* QR + blockchain proof */}
              <div className="pt-5 flex flex-col sm:flex-row items-center gap-6" style={{ borderTop: '1px solid var(--border)' }}>
                <div className="flex-shrink-0 flex flex-col items-center gap-2">
                  <div className="p-3 bg-white rounded-xl shadow-lg border" style={{ borderColor: 'var(--border)' }}>
                    <QRCode value={verifyUrl} size={120} viewBox="0 0 256 256" />
                  </div>
                  <p className="text-xs text-center max-w-28 font-semibold" style={{ color: 'var(--text-light)' }}>Scan to verify</p>
                </div>

                <div className="flex-1 space-y-3 w-full">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-light)' }}>Verification URL</p>
                    <code className="block px-3 py-2 rounded-xl text-xs break-all"
                      style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                      {verifyUrl}
                    </code>
                  </div>

                  {data.blockchain_hash ? (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-light)' }}>⛓ Blockchain Record</p>
                      <code className="block px-3 py-2 rounded-xl text-xs break-all"
                        style={isReal
                          ? { background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.2)', color: '#059669' }
                          : { background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.2)', color: '#7c3aed' }
                        }>{data.blockchain_hash}</code>
                      <p className="text-xs mt-1 font-semibold" style={{ color: isReal ? '#059669' : '#7c3aed' }}>
                        {isReal ? '✓ Verified on Ethereum Sepolia testnet' : '🔵 Demo mode — real tx hash after contract deployment'}
                      </p>
                      {isReal && (
                        <a href={`https://sepolia.etherscan.io/tx/${data.blockchain_hash}`} target="_blank" rel="noopener noreferrer"
                          className="text-xs font-bold mt-1 inline-block transition-opacity hover:opacity-70" style={{ color: 'var(--cyan)' }}>
                          View on Etherscan →
                        </a>
                      )}
                    </div>
                  ) : (
                    <div className="px-3 py-2 rounded-xl text-xs font-semibold" style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.15)', color: 'var(--amber)' }}>
                      ⏳ Awaiting on-chain record (blockchain tx pending)
                    </div>
                  {data.override_details && (
                    <div className="mt-4 p-4 rounded-xl border" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)' }}>
                      <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#d97706' }}>⚠️ Multi-Sig Admin Override</p>
                      <p className="text-sm font-semibold mb-1" style={{ color: 'var(--text-base)' }}>Justification: {data.override_details.justification}</p>
                      {data.override_details.ai_cross_check && (
                        <p className="text-xs italic mb-2" style={{ color: 'var(--text-muted)' }}>AI Check: {data.override_details.ai_cross_check}</p>
                      )}
                      <p className="text-xs" style={{ color: 'var(--text-light)' }}>Approved by: {data.override_details.approvers.join(', ')}</p>
                      
                      {data.override_blockchain_hash && (
                        <div className="mt-2">
                          <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-light)' }}>⛓ Override TX Hash</p>
                          <code className="block px-3 py-2 rounded-xl text-xs break-all"
                            style={isReal
                              ? { background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.2)', color: '#059669' }
                              : { background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.2)', color: '#7c3aed' }
                            }>{data.override_blockchain_hash}</code>
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            </div>

            {/* ── Chain of custody timeline ──────────────── */}
            {data.handoffs?.length > 0 && (
              <div className="p-6 rounded-2xl" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <h2 className="font-bold text-lg mb-5" style={{ color: 'var(--text-base)' }}>Chain of Custody</h2>
                <div className="relative">
                  {/* Timeline line */}
                  <div className="absolute left-4 top-0 bottom-0 w-px" style={{ background: 'var(--border)' }} />
                  <div className="space-y-5">
                    {data.handoffs.map((h, i) => {
                      const meta = STAGE_META[h.stage] || { label: h.stage, icon: '📋', color: '#64748b' }
                      return (
                        <div key={i} className="flex items-start gap-4 pl-2">
                          <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0 relative z-10 text-white"
                            style={{ background: meta.color }}>
                            {meta.icon}
                          </div>
                          <div className="flex-1 pb-1">
                            <p className="font-bold text-sm" style={{ color: 'var(--text-base)' }}>{meta.label}</p>
                            <div className="flex flex-wrap gap-3 mt-1">
                              {h.quantity_reported != null && (
                                <span className="text-xs font-semibold animate-none" style={{ color: 'var(--text-muted)' }}>{h.quantity_reported.toLocaleString()} units</span>
                              )}
                              {h.temp_reported != null && (
                                <span className="text-xs font-semibold animate-none" style={{ color: 'var(--text-muted)' }}>{h.temp_reported}°C storage</span>
                              )}
                            </div>
                            <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>{fmt(h.submitted_at)}</p>
                          </div>
                          {i === data.handoffs.length - 1 && (
                            <span className="text-xs px-2 py-0.5 rounded-full flex-shrink-0 font-bold"
                              style={{ background: 'rgba(5,150,105,0.1)', color: '#059669', border: '1px solid rgba(5,150,105,0.2)' }}>
                              Latest
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ── Approval trail ─────────────────────────── */}
            {data.approval_logs?.length > 0 && (
              <div className="p-6 rounded-2xl" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <h2 className="font-bold text-lg mb-4" style={{ color: 'var(--text-base)' }}>Approval Trail</h2>
                <ul className="space-y-3">
                  {data.approval_logs.map(log => (
                    <li key={log.id} className="pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
                      <p className="text-sm font-bold capitalize" style={{ color: 'var(--text-base)' }}>{log.action_type?.replace(/_/g, ' ')}</p>
                      {log.notes && <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-muted)' }}>{log.notes}</p>}
                      <p className="text-xs mt-1" style={{ color: 'var(--text-light)' }}>{log.actor_name} · {fmt(log.created_at)}</p>
                      {log.blockchain_hash && (
                        <code className="block mt-1 text-xs font-mono truncate" style={{ color: '#7c3aed' }}>{log.blockchain_hash}</code>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="text-center py-8 text-xs" style={{ color: 'var(--text-light)' }}>
        Powered by ChainMed · AI + Blockchain pharmaceutical supply chain integrity
      </footer>
    </div>
  )
}
