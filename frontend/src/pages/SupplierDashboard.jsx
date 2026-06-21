import { useCallback, useEffect, useState } from 'react'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import HandoffForm from '../components/HandoffForm'
import ChainVerificationPanel from '../components/ChainVerificationPanel'
import {
  getIncomingShipments,
  getDispatchableBatches,
  verifyShipment,
  dispatchOutbound,
  getInventory,
  updateInventory,
  createRestockRequest,
  getMyRestockRequests,
  resolveRestockRequest,
} from '../api/supplier'
import { submitShipmentDispute } from '../api/shared'
import { getSupplierChain } from '../api/verification'
import { DEFAULT_ENTITY_ID } from '../utils/entityIds'

const HOSPITAL_ID    = DEFAULT_ENTITY_ID.consumer
const MANUFACTURER_ID = DEFAULT_ENTITY_ID.manufacturer

const TABS = [
  { id: 'shipments', label: 'Incoming', icon: '📥' },
  { id: 'dispatch',  label: 'Dispatch', icon: '🚚' },
  { id: 'inventory', label: 'Inventory', icon: '📦' },
  { id: 'restock',   label: 'Restock',   icon: '🆘' },
]

/* ─── Reusable light card wrapper ─────────────────────────────── */
function Card({ children, className = '' }) {
  return (
    <div
      className={`rounded-2xl overflow-hidden ${className}`}
      style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
    >{children}</div>
  )
}

function CardHeader({ title, sub }) {
  return (
    <div className="px-6 py-5" style={{ borderBottom: '1px solid var(--border)' }}>
      <h2 className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>{title}</h2>
      {sub && <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>{sub}</p>}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">{label}</label>
      {children}
    </div>
  )
}

function Input({ className = '', ...props }) {
  return (
    <input 
      className={`w-full px-4 py-3 text-sm ${className}`} 
      style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
      {...props} 
    />
  )
}

function Select({ children, ...props }) {
  return (
    <select
      className="w-full px-4 py-3 text-sm"
      style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
      {...props}
    >
      {children}
    </select>
  )
}

function PrimaryBtn({ children, disabled, onClick, type = 'submit', style }) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="px-5 py-2.5 rounded-xl font-bold text-sm text-white transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
      style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 12px rgba(8,145,178,0.2)', ...style }}
    >{children}</button>
  )
}

/* ─────────────────────────────────────────────────────────────── */

export default function SupplierDashboard() {
  const [tab,      setTab]      = useState('shipments')
  const [shipments, setShipments] = useState([])
  const [inventory, setInventory] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [message,   setMessage]   = useState({ type: '', text: '' })
  const [verifyId,  setVerifyId]  = useState(null)
  const [disputeId, setDisputeId] = useState(null)
  const [disputeText, setDisputeText] = useState('')
  const [submitting,setSubmitting]= useState(false)
  const [chainReport,  setChainReport]  = useState(null)
  const [chainLoading, setChainLoading] = useState(false)
  const [chainShipId,  setChainShipId]  = useState(null)
  const [dispatchableBatches, setDispatchableBatches] = useState([])
  const [dispatchForm, setDispatchForm] = useState({ batch_id: '', to_entity_id: HOSPITAL_ID, quantity: '' })
  const [restockForm,  setRestockForm]  = useState({ target_entity_id: MANUFACTURER_ID, medicine_name: '', quantity_requested: 1000, reason: '', urgency: 'normal' })
  const [invForm, setInvForm] = useState({ medicine_name: '', quantity: 0, reorder_threshold: 1000 })
  const [myRequests, setMyRequests] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, i, d, r] = await Promise.all([getIncomingShipments(), getInventory(), getDispatchableBatches(), getMyRestockRequests()])
      setShipments(s); setInventory(i); setDispatchableBatches(d); setMyRequests(r)
    } catch {
      flash('error', 'Unable to connect to the server. Please refresh the page or try again later.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function flash(type, text) {
    setMessage({ type, text })
    setTimeout(() => setMessage({ type: '', text: '' }), 5000)
  }

  async function handleVerify(shipmentId, payload) {
    setSubmitting(true)
    try {
      const res = await verifyShipment(shipmentId, payload)
      const aiMsg = res.ai_status ? ` · AI: ${res.ai_status} (risk ${res.ai_risk_score?.toFixed(0)})` : ''
      flash('success', `Verified ✓ — Approval: ${res.approval_log_id.slice(0,8)}…${aiMsg}`)
      setVerifyId(null); load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Verification failed')
    } finally { setSubmitting(false) }
  }

  async function handleDispute(shipmentId) {
    if (!disputeText.trim()) { flash('error', 'Please provide a justification'); return }
    setSubmitting(true)
    try {
      await submitShipmentDispute(shipmentId, disputeText)
      flash('success', 'Dispute submitted. Awaiting multi-sig admin approval.')
      setDisputeId(null)
      setDisputeText('')
      load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Failed to submit dispute')
    } finally { setSubmitting(false) }
  }

  async function runChainVerify(shipmentId) {
    if (chainShipId === shipmentId) { setChainReport(null); setChainShipId(null); return }
    setChainLoading(true); setChainReport(null); setChainShipId(shipmentId)
    try { setChainReport(await getSupplierChain(shipmentId)) }
    catch (err) { flash('error', err.response?.data?.detail || 'Chain verify failed'); setChainShipId(null) }
    finally { setChainLoading(false) }
  }

  async function handleDispatch(e) {
    e.preventDefault()
    const packs = Number(dispatchForm.quantity)
    const selected = dispatchableBatches.find(b => b.batch_id === dispatchForm.batch_id)
    if (!packs || packs < 1) { flash('error', 'Enter a valid dispatch quantity'); return }
    const qty = packs * (selected?.pieces_per_pack || 1)
    if (selected && qty > selected.quantity_remaining) { flash('error', `Only ${Math.floor(selected.quantity_remaining / (selected?.pieces_per_pack || 1)).toLocaleString()} packs available`); return }
    setSubmitting(true)
    try {
      const res = await dispatchOutbound({ batch_id: dispatchForm.batch_id, to_entity_id: dispatchForm.to_entity_id, quantity: qty })
      flash('success', `Dispatched ${Math.floor((res.quantity_dispatched || qty) / (selected?.pieces_per_pack || 1)).toLocaleString()} packs — ${res.shipment_code}`)
      setDispatchForm({ batch_id: '', to_entity_id: HOSPITAL_ID, quantity: '' }); load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Dispatch failed')
    } finally { setSubmitting(false) }
  }

  async function handleRestock(e) {
    e.preventDefault(); setSubmitting(true)
    try {
      const res = await createRestockRequest({ ...restockForm, quantity_requested: Number(restockForm.quantity_requested) })
      flash('success', `Restock request sent — Approval: ${res.approval_log_id.slice(0,8)}…`)
      load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Request failed')
    } finally { setSubmitting(false) }
  }

  async function handleResolveRequest(id) {
    setSubmitting(true)
    try {
      await resolveRestockRequest(id)
      flash('success', 'Emergency request marked as resolved ✓')
      load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Failed to resolve request')
    } finally { setSubmitting(false) }
  }

  async function handleInventory(e) {
    e.preventDefault(); setSubmitting(true)
    try {
      await updateInventory({ ...invForm, quantity: Number(invForm.quantity), reorder_threshold: Number(invForm.reorder_threshold) })
      flash('success', 'Inventory updated'); load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Update failed')
    } finally { setSubmitting(false) }
  }

  const selectedBatch   = dispatchableBatches.find(b => b.batch_id === dispatchForm.batch_id)
  const dispatchRem     = selectedBatch?.quantity_remaining ?? 0

  useEffect(() => {
    if (!dispatchForm.batch_id) return
    const b = dispatchableBatches.find(b => b.batch_id === dispatchForm.batch_id)
    if (b) setDispatchForm(f => ({ ...f, quantity: String(b.quantity_remaining) }))
  }, [dispatchForm.batch_id, dispatchableBatches])

  const pending  = shipments.filter(s => s.status !== 'delivered').length
  const verified = shipments.filter(s => s.status === 'delivered').length

  return (
    <Layout title="Supplier Dashboard">
      {/* Toast */}
      {message.text && (
        <div
          className="mb-6 px-4 py-3 rounded-xl text-sm flex items-center gap-2 animate-slide-up"
          style={message.type === 'error'
            ? { background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.2)', color: '#dc2626' }
            : { background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.2)', color: '#059669' }
          }
        >
          <span>{message.type === 'error' ? '⚠️' : '✓'}</span>
          {message.text}
        </div>
      )}

      {/* Stat strip */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Incoming', value: shipments.length, icon: '📥', from: '#0891b2', to: '#3b82f6' },
          { label: 'Pending Verify', value: pending, icon: '⏳', from: '#d97706', to: '#b45309' },
          { label: 'Verified', value: verified, icon: '✓', from: '#059669', to: '#047857' },
        ].map(({ label, value, icon, from, to }) => (
          <div key={label} className="p-4 rounded-2xl transition-all hover:scale-[1.02]"
            style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3 text-white"
              style={{ background: `linear-gradient(135deg,${from},${to})` }}>{icon}</div>
            <p className="text-2xl font-black" style={{ color: 'var(--text-base)' }}>{loading ? '…' : value}</p>
            <p className="text-xs font-bold uppercase tracking-wider mt-0.5" style={{ color: 'var(--text-light)' }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className="px-4 py-2 rounded-xl text-sm font-bold transition-all duration-200"
            style={tab === t.id
              ? { background: 'linear-gradient(135deg,#0891b2,#3b82f6)', color: 'white', boxShadow: '0 4px 12px rgba(8,145,178,0.2)' }
              : { background: '#ffffff', color: 'var(--text-muted)', border: '1px solid var(--border)' }
            }
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16 gap-3 text-slate-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Loading…
        </div>
      )}

      {/* ── Incoming shipments tab ─────────────────────────── */}
      {!loading && tab === 'shipments' && (
        <Card>
          <CardHeader title="Incoming from Manufacturers" sub="Verify each handoff — triggers AI cross-match automatically" />
          {shipments.length === 0 ? (
            <div className="p-12 text-center">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-light)' }}>No incoming shipments yet.</p>
            </div>
          ) : (
            <ul>
              {shipments.map((s, i) => (
                <li key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <div className="px-6 py-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div>
                        <p className="font-bold text-base" style={{ color: 'var(--text-base)' }}>{s.medicine_name}</p>
                        <p className="text-xs font-mono font-bold mt-0.5" style={{ color: 'var(--cyan)' }}>{s.shipment_code}</p>
                        <p className="text-xs mt-0.5 font-semibold" style={{ color: 'var(--text-light)' }}>Batch {s.batch_number}</p>
                        {s.quantity_dispatched != null && (
                          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                            <span className="font-bold text-slate-800">{Math.floor(s.quantity_dispatched / (s.pieces_per_pack || 1)).toLocaleString()}</span> packs dispatched
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <StatusBadge status={s.status} />
                        {s.status === 'delivered' && (
                          <button
                            type="button"
                            onClick={() => runChainVerify(s.id)}
                            disabled={chainLoading}
                            className="text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:scale-105 disabled:opacity-50"
                            style={chainShipId === s.id
                              ? { background: 'linear-gradient(135deg,#0891b2,#3b82f6)', color: 'white' }
                              : { background: 'rgba(8,145,178,0.08)', color: 'var(--cyan)', border: '1px solid rgba(8,145,178,0.18)' }
                            }
                          >
                            {chainShipId === s.id ? '▲ Hide' : '🔍 Chain Verify'}
                          </button>
                        )}
                      </div>
                    </div>

                    {s.status === 'FLAGGED' && (
                      disputeId === s.id ? (
                        <div className="mt-3 bg-red-500/10 p-4 rounded-xl border border-red-500/20">
                          <p className="text-sm font-semibold text-red-400 mb-2">Dispute AI Flag</p>
                          <textarea
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-white mb-3"
                            rows="3"
                            placeholder="Provide justification or reference to manual sensor logs..."
                            value={disputeText}
                            onChange={(e) => setDisputeText(e.target.value)}
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleDispute(s.id)}
                              disabled={submitting}
                              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg transition-colors text-sm"
                            >
                              {submitting ? 'Submitting...' : 'Submit Dispute'}
                            </button>
                            <button
                              onClick={() => setDisputeId(null)}
                              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-lg transition-colors text-sm"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDisputeId(s.id)}
                          className="mt-2 text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:scale-105"
                          style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--red)', border: '1px solid rgba(239,68,68,0.2)' }}
                        >
                          ⚠️ Dispute Flag
                        </button>
                      )
                    )}

                    {s.status !== 'delivered' && s.status !== 'FLAGGED' && (
                      verifyId === s.id ? (
                        <div className="mt-3">
                          <HandoffForm
                            submitLabel="Verify Receipt"
                            submitting={submitting}
                            defaultQuantity={Math.floor((s.quantity_dispatched || 0) / (s.pieces_per_pack || 1)) || 1000}
                            onCancel={() => setVerifyId(null)}
                            onSubmit={(payload) => handleVerify(s.id, {
                              ...payload,
                              quantity_reported: payload.quantity_reported * (s.pieces_per_pack || 1)
                            })}
                          />
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setVerifyId(s.id)}
                          className="mt-2 text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:scale-105"
                          style={{ background: 'rgba(5,150,105,0.08)', color: 'var(--emerald)', border: '1px solid rgba(5,150,105,0.18)' }}
                        >
                          ✓ Verify incoming shipment
                        </button>
                      )
                    )}

                    {chainShipId === s.id && (
                      <div className="mt-4">
                        <ChainVerificationPanel
                          report={chainReport}
                          loading={chainLoading}
                          error={null}
                          onClose={() => { setChainReport(null); setChainShipId(null) }}
                        />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {/* ── Dispatch tab ────────────────────────────────────── */}
      {!loading && tab === 'dispatch' && (
        <div className="max-w-lg">
          <Card>
            <CardHeader title="Dispatch to Hospital" sub="Ship verified batch units forward. QR code + approval log generated automatically." />
            <div className="p-6">
              <form onSubmit={handleDispatch} className="space-y-4">
                <Field label="Batch (verified)">
                  <Select required value={dispatchForm.batch_id} onChange={e => setDispatchForm(f => ({ ...f, batch_id: e.target.value }))}>
                    <option value="">Select batch…</option>
                    {dispatchableBatches.map(b => (
                      <option key={b.batch_id} value={b.batch_id}>
                        {b.medicine_name} — {b.batch_number} ({Math.floor((b.quantity_remaining ?? 0) / (b.pieces_per_pack || 1)).toLocaleString()} packs left)
                      </option>
                    ))}
                  </Select>
                </Field>

                {selectedBatch && (
                  <div className="p-3 rounded-xl text-xs space-y-1" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
                    <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Received</span><span className="font-bold text-slate-800">{Math.floor((selectedBatch.quantity_received ?? 0) / (selectedBatch.pieces_per_pack || 1)).toLocaleString()} packs</span></div>
                    <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Already sent</span><span className="font-bold text-slate-800">{Math.floor((selectedBatch.quantity_dispatched ?? 0) / (selectedBatch.pieces_per_pack || 1)).toLocaleString()} packs</span></div>
                    <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Available</span><span className="font-bold" style={{ color: 'var(--emerald)' }}>{Math.floor(dispatchRem / (selectedBatch.pieces_per_pack || 1)).toLocaleString()} packs</span></div>
                  </div>
                )}

                <Field label="Packs to dispatch">
                  <Input type="number" required min={1} max={Math.floor(dispatchRem / (selectedBatch?.pieces_per_pack || 1)) || undefined} disabled={!selectedBatch}
                    value={dispatchForm.quantity} onChange={e => setDispatchForm(f => ({ ...f, quantity: e.target.value }))} placeholder="Number of strips/boxes" />
                  {selectedBatch && (
                    <button type="button" className="mt-1 text-xs font-semibold transition-opacity hover:opacity-70" style={{ color: 'var(--cyan)' }}
                      onClick={() => setDispatchForm(f => ({ ...f, quantity: String(Math.floor(dispatchRem / selectedBatch.pieces_per_pack)) }))}>
                      Dispatch all ({Math.floor(dispatchRem / selectedBatch.pieces_per_pack).toLocaleString()} packs)
                    </button>
                  )}
                </Field>

                <Field label="Hospital Entity ID">
                  <Input className="font-mono text-xs" value={dispatchForm.to_entity_id}
                    onChange={e => setDispatchForm(f => ({ ...f, to_entity_id: e.target.value }))} />
                </Field>

                <PrimaryBtn disabled={submitting || !selectedBatch}>
                  {submitting ? 'Dispatching…' : 'Dispatch + QR + Approval Log →'}
                </PrimaryBtn>
              </form>
            </div>
          </Card>
        </div>
      )}

      {/* ── Inventory tab ────────────────────────────────────── */}
      {!loading && tab === 'inventory' && (
        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader title="Warehouse Stock" sub="Auto-updated when you verify incoming shipments" />
            {inventory.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-light)' }}>No stock records. Verify a shipment first.</div>
            ) : (
              <ul className="divide-y" style={{ '--tw-divide-opacity': 1 }}>
                {inventory.map(item => (
                  <li key={item.id} className="px-6 py-3 flex items-center justify-between text-sm"
                    style={{ borderBottom: '1px solid var(--border)' }}>
                    <span className="font-semibold" style={{ color: 'var(--text-muted)' }}>{item.medicine_name}</span>
                    <div className="text-right">
                      <span className="font-bold text-slate-800">{Math.floor(item.quantity / (item.pieces_per_pack || 1)).toLocaleString()} packs</span>
                      {item.quantity < item.reorder_threshold && (
                        <span className="ml-2 text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: 'rgba(217,119,6,0.1)', color: 'var(--amber)' }}>Low</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Update Stock" />
            <div className="p-6">
              <form onSubmit={handleInventory} className="space-y-4">
                <Field label="Medicine Name">
                  <Input required placeholder="e.g. Paracetamol 500mg" value={invForm.medicine_name}
                    onChange={e => setInvForm(f => ({ ...f, medicine_name: e.target.value }))} />
                </Field>
                <Field label="Quantity">
                  <Input type="number" required value={invForm.quantity}
                    onChange={e => setInvForm(f => ({ ...f, quantity: e.target.value }))} />
                </Field>
                <Field label="Reorder Threshold">
                  <Input type="number" value={invForm.reorder_threshold}
                    onChange={e => setInvForm(f => ({ ...f, reorder_threshold: e.target.value }))} />
                </Field>
                <PrimaryBtn disabled={submitting}>{submitting ? 'Saving…' : 'Save Stock'}</PrimaryBtn>
              </form>
            </div>
          </Card>
        </div>
      )}

      {/* ── Restock tab ─────────────────────────────────────── */}
      {!loading && tab === 'restock' && (
        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader title="Emergency Restock → Manufacturer" sub="Creates emergency_restock approval log entry" />
            <div className="p-6">
              <form onSubmit={handleRestock} className="space-y-4">
                <Field label="Medicine Name">
                  <Input required placeholder="e.g. Amoxicillin 250mg" value={restockForm.medicine_name}
                    onChange={e => setRestockForm(f => ({ ...f, medicine_name: e.target.value }))} />
                </Field>
                <Field label="Quantity Requested">
                  <Input type="number" required value={restockForm.quantity_requested}
                    onChange={e => setRestockForm(f => ({ ...f, quantity_requested: e.target.value }))} />
                </Field>
                <Field label="Reason">
                  <textarea
                    required
                    rows={3}
                    className="w-full px-4 py-3 text-sm resize-none"
                    style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
                    placeholder="Flood disrupted supply chain…"
                    value={restockForm.reason}
                    onChange={e => setRestockForm(f => ({ ...f, reason: e.target.value }))}
                  />
                </Field>
                <Field label="Urgency">
                  <Select value={restockForm.urgency} onChange={e => setRestockForm(f => ({ ...f, urgency: e.target.value }))}>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </Select>
                </Field>
                <PrimaryBtn disabled={submitting} style={{ background: 'linear-gradient(135deg,#f59e0b,#d97706)', boxShadow: '0 4px 12px rgba(217,119,6,0.2)' }}>
                  {submitting ? 'Sending…' : '🆘 Submit Restock Request'}
                </PrimaryBtn>
              </form>
            </div>
          </Card>

          <Card>
            <CardHeader title="My Emergency Requests" sub="Manage requests you have submitted" />
            {myRequests.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-light)' }}>No active or past emergency requests.</div>
            ) : (
              <ul className="max-h-[600px] overflow-y-auto">
                {myRequests.map(r => (
                  <li key={r.id} className="px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <p className="text-sm font-bold" style={{ color: 'var(--text-base)' }}>{r.medicine_name}</p>
                        <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>{r.quantity_requested.toLocaleString()} units requested</p>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        r.status === 'resolved' ? 'bg-emerald-100 text-emerald-700' : 
                        r.urgency === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {r.status === 'resolved' ? 'Resolved' : 'Pending'}
                      </span>
                    </div>
                    <p className="text-xs italic mb-3" style={{ color: 'var(--text-light)' }}>"{r.reason}"</p>
                    {r.status !== 'resolved' && (
                      <button 
                        onClick={() => handleResolveRequest(r.id)}
                        disabled={submitting}
                        className="text-xs px-3 py-1.5 rounded-lg font-bold transition-all hover:scale-105"
                        style={{ background: 'rgba(5,150,105,0.08)', color: 'var(--emerald)', border: '1px solid rgba(5,150,105,0.18)' }}
                      >
                        ✓ Mark as Resolved
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </Layout>
  )
}
