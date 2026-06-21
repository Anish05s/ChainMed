import { useCallback, useEffect, useState } from 'react'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import HandoffForm from '../components/HandoffForm'
import ChainVerificationPanel from '../components/ChainVerificationPanel'
import {
  getIncomingShipments,
  confirmReceipt,
  getInventory,
  updateInventory,
  createStockRequest,
  clearStock,
  getStockClearances,
  getMyRestockRequests,
  resolveRestockRequest,
} from '../api/hospital'
import { getHospitalChain } from '../api/verification'
import { DEFAULT_ENTITY_ID } from '../utils/entityIds'

const SUPPLIER_ID = DEFAULT_ENTITY_ID.supplier

const CLEARANCE_REASONS = [
  { value: 'patient_dispensed', label: 'Patient dispensed / clinical use' },
  { value: 'expired',           label: 'Expired stock' },
  { value: 'damaged',           label: 'Damaged or contaminated' },
  { value: 'recalled',          label: 'Manufacturer recall' },
  { value: 'transfer',          label: 'Transfer to another facility' },
  { value: 'other',             label: 'Other (document in notes)' },
]

const TABS = [
  { id: 'shipments', label: 'Deliveries',        icon: '📥' },
  { id: 'inventory', label: 'Stock',             icon: '💊' },
  { id: 'clearance', label: 'Stock Clearance',   icon: '📤' },
  { id: 'request',   label: 'Emergency Request', icon: '🆘' },
]

/* ── Shared light card components ──────────────────────────────── */
function Card({ children }) {
  return (
    <div className="rounded-2xl overflow-hidden"
      style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
      {children}
    </div>
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
function DInput(props) {
  return <input className="w-full px-4 py-3 text-sm" {...props} />
}
function DSelect({ children, ...props }) {
  return (
    <select className="w-full px-4 py-3 text-sm"
      style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
      {...props}>{children}</select>
  )
}
function PrimaryBtn({ children, disabled, onClick, type = 'submit', danger, warning }) {
  const grad = danger
    ? 'linear-gradient(135deg,#ef4444,#dc2626)'
    : warning
      ? 'linear-gradient(135deg,#f59e0b,#d97706)'
      : 'linear-gradient(135deg,#059669,#047857)'
  const shadow = danger
    ? '0 4px 12px rgba(220,38,38,0.2)'
    : warning
      ? '0 4px 12px rgba(217,119,6,0.2)'
      : '0 4px 12px rgba(5,150,105,0.2)'
  return (
    <button type={type} disabled={disabled} onClick={onClick}
      className="px-5 py-2.5 rounded-xl font-bold text-sm text-white transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
      style={{ background: grad, boxShadow: shadow }}>
      {children}
    </button>
  )
}
function SecondaryBtn({ children, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className="px-5 py-2.5 rounded-xl font-bold text-sm transition-all duration-200"
      style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', background: '#ffffff' }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
      onMouseLeave={e => e.currentTarget.style.background = '#ffffff'}>
      {children}
    </button>
  )
}
/* ─────────────────────────────────────────────────────────────── */

export default function HospitalDashboard() {
  const [tab,        setTab]        = useState('shipments')
  const [shipments,  setShipments]  = useState([])
  const [inventory,  setInventory]  = useState([])
  const [loading,    setLoading]    = useState(true)
  const [message,    setMessage]    = useState({ type: '', text: '' })
  const [confirmId,  setConfirmId]  = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [chainReport,  setChainReport]  = useState(null)
  const [chainLoading, setChainLoading] = useState(false)
  const [chainShipId,  setChainShipId]  = useState(null)
  const [clearances, setClearances] = useState([])
  const [myRequests, setMyRequests] = useState([])

  const [invForm, setInvForm] = useState({ medicine_name: '', quantity: 0, reorder_threshold: 500 })
  const [clearanceForm, setClearanceForm] = useState({ medicine_name: '', quantity_cleared: '', reason: 'patient_dispensed', notes: '' })
  const [clearanceStep, setClearanceStep] = useState('form')
  const [stockForm, setStockForm] = useState({ target_entity_id: SUPPLIER_ID, medicine_name: '', quantity_requested: 500, reason: '', urgency: 'high' })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, i, c, r] = await Promise.all([getIncomingShipments(), getInventory(), getStockClearances(), getMyRestockRequests()])
      setShipments(s); setInventory(i); setClearances(c); setMyRequests(r)
    } catch {
      flash('error', 'Unable to connect to the server. Please refresh the page or try again later.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function flash(type, text) {
    setMessage({ type, text })
    setTimeout(() => setMessage({ type: '', text: '' }), 6000)
  }

  async function handleConfirm(shipmentId, payload) {
    if (typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(30)
    setSubmitting(true)
    try {
      const res = await confirmReceipt(shipmentId, payload)
      const aiMsg = res.ai_status ? ` · AI: ${res.ai_status} (risk ${res.ai_risk_score?.toFixed(0)}/100)` : ''
      flash('success', `Receipt confirmed ✓ — Approval: ${res.approval_log_id.slice(0, 8)}…${aiMsg}`)
      if (typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate([100, 50, 100])
      setConfirmId(null); load()
    } catch (err) {
      if (typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate([300])
      flash('error', err.response?.data?.detail || 'Confirmation failed')
    } finally { setSubmitting(false) }
  }

  async function runChainVerify(shipmentId) {
    if (chainShipId === shipmentId) { setChainReport(null); setChainShipId(null); return }
    setChainLoading(true); setChainReport(null); setChainShipId(shipmentId)
    try { setChainReport(await getHospitalChain(shipmentId)) }
    catch (err) { flash('error', err.response?.data?.detail || 'Chain verify failed'); setChainShipId(null) }
    finally { setChainLoading(false) }
  }

  async function handleInventory(e) {
    e.preventDefault(); setSubmitting(true)
    try {
      await updateInventory({ ...invForm, quantity: Number(invForm.quantity), reorder_threshold: Number(invForm.reorder_threshold) })
      flash('success', 'Stock levels updated'); load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Update failed')
    } finally { setSubmitting(false) }
  }

  const selectedStock = inventory.find(i => i.medicine_name === clearanceForm.medicine_name)
  const maxClearable  = selectedStock?.quantity ?? 0

  function selectMedicineForClearance(name) {
    const item = inventory.find(i => i.medicine_name === name)
    setClearanceForm(f => ({ ...f, medicine_name: name, quantity_cleared: item ? String(item.quantity) : '' }))
    setClearanceStep('form')
  }

  async function handleClearanceReview(e) {
    e.preventDefault()
    const qty = Number(clearanceForm.quantity_cleared)
    if (!clearanceForm.medicine_name) { flash('error', 'Select a medicine'); return }
    if (!qty || qty < 1) { flash('error', 'Enter a valid quantity to clear'); return }
    if (qty > maxClearable) { flash('error', `Only ${maxClearable.toLocaleString()} units in stock`); return }
    setClearanceStep('confirm')
  }

  async function handleClearanceConfirm() {
    setSubmitting(true)
    try {
      const res = await clearStock({
        medicine_name:   clearanceForm.medicine_name.trim(),
        quantity_cleared: Number(clearanceForm.quantity_cleared),
        reason:          clearanceForm.reason,
        notes:           clearanceForm.notes.trim() || undefined,
      })
      const alert = res.low_stock_alert ? ` · ⚠️ Low stock alert!` : ''
      flash('success', `Cleared ${res.quantity_cleared.toLocaleString()} units · ${res.quantity_remaining.toLocaleString()} remaining${alert}`)
      setClearanceForm({ medicine_name: '', quantity_cleared: '', reason: 'patient_dispensed', notes: '' })
      setClearanceStep('form'); load()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Clearance failed')
      setClearanceStep('form')
    } finally { setSubmitting(false) }
  }

  async function handleStockRequest(e) {
    e.preventDefault(); setSubmitting(true)
    try {
      const res = await createStockRequest({ ...stockForm, quantity_requested: Number(stockForm.quantity_requested) })
      flash('success', `Request sent ✓ — Approval: ${res.approval_log_id.slice(0, 8)}…`)
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

  // Derived stats
  const pending    = shipments.filter(s => s.status !== 'delivered').length
  const delivered  = shipments.filter(s => s.status === 'delivered').length
  const lowStock   = inventory.filter(i => i.quantity <= i.reorder_threshold).length

  return (
    <Layout title="Hospital Dashboard">
      {/* Toast */}
      {message.text && (
        <div className="mb-6 px-4 py-3 rounded-xl text-sm flex items-center gap-2 animate-slide-up"
          style={message.type === 'error'
            ? { background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.2)', color: '#dc2626' }
            : { background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.2)', color: '#059669' }
          }>
          <span>{message.type === 'error' ? '⚠️' : '✓'}</span>{message.text}
        </div>
      )}

      {/* Stat strip */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Deliveries', value: shipments.length, icon: '📥', from: '#0891b2', to: '#3b82f6' },
          { label: 'Pending Confirm', value: pending, icon: '⏳', from: '#d97706', to: '#b45309' },
          { label: 'Confirmed', value: delivered, icon: '✓', from: '#059669', to: '#047857' },
          { label: 'Low Stock Alerts', value: lowStock, icon: '⚠️', from: lowStock > 0 ? '#ef4444' : '#059669', to: lowStock > 0 ? '#dc2626' : '#047857' },
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
          <button key={t.id} type="button" onClick={() => setTab(t.id)}
            className="px-4 py-2 rounded-xl text-sm font-bold transition-all duration-200"
            style={tab === t.id
              ? { background: 'linear-gradient(135deg,#059669,#047857)', color: 'white', boxShadow: '0 4px 12px rgba(5,150,105,0.2)' }
              : { background: '#ffffff', color: 'var(--text-muted)', border: '1px solid var(--border)' }
            }>
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

      {/* ── Deliveries tab ───────────────────────────────────── */}
      {!loading && tab === 'shipments' && (
        <Card>
          <CardHeader title="Incoming Deliveries" sub="Confirm receipt to complete 3-party AI verification + blockchain record" />
          {shipments.length === 0 ? (
            <div className="p-12 text-center">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-light)' }}>No deliveries yet. Supplier must dispatch first.</p>
            </div>
          ) : (
            <ul>
              {shipments.map(s => (
                <li key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <div className="px-6 py-4">
                    <div className="flex flex-col sm:flex-row items-start justify-between gap-3 mb-2">
                      <div className="w-full">
                        <div className="flex items-center justify-between sm:justify-start gap-3 w-full">
                          <p className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>{s.medicine_name}</p>
                          <div className="sm:hidden"><StatusBadge status={s.status} /></div>
                        </div>
                        <p className="text-sm font-mono font-bold mt-1" style={{ color: 'var(--emerald)' }}>{s.shipment_code}</p>
                        <p className="text-sm mt-0.5 font-semibold" style={{ color: 'var(--text-light)' }}>Batch {s.batch_number}</p>
                        {s.quantity_dispatched != null && (
                          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                            <span className="font-bold text-slate-800">{s.quantity_dispatched.toLocaleString()}</span> units
                          </p>
                        )}
                      </div>
                      <div className="hidden sm:flex items-center gap-2 flex-shrink-0">
                        <StatusBadge status={s.status} />
                        {s.status === 'delivered' && (
                          <button type="button" onClick={() => { if(typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(20); runChainVerify(s.id); }} disabled={chainLoading}
                            className="text-sm font-bold px-4 py-2 rounded-xl transition-all hover:scale-105 disabled:opacity-50"
                            style={chainShipId === s.id
                              ? { background: 'linear-gradient(135deg,#059669,#047857)', color: 'white' }
                              : { background: 'rgba(5,150,105,0.08)', color: 'var(--emerald)', border: '1px solid rgba(5,150,105,0.18)' }
                            }>
                            {chainShipId === s.id ? '▲ Hide' : '🔍 Verify Authenticity'}
                          </button>
                        )}
                      </div>
                    </div>
                    {/* Mobile-only action row for verified shipments */}
                    {s.status === 'delivered' && (
                      <div className="sm:hidden mt-4">
                        <button type="button" onClick={() => { if(typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(20); runChainVerify(s.id); }} disabled={chainLoading}
                          className="w-full text-sm font-bold px-4 py-3 rounded-xl transition-all hover:scale-105 disabled:opacity-50 flex items-center justify-center gap-2"
                          style={chainShipId === s.id
                            ? { background: 'linear-gradient(135deg,#059669,#047857)', color: 'white' }
                            : { background: 'rgba(5,150,105,0.08)', color: 'var(--emerald)', border: '1px solid rgba(5,150,105,0.18)' }
                          }>
                          {chainShipId === s.id ? '▲ Hide' : '🔍 Verify Authenticity'}
                        </button>
                      </div>
                    )}

                    {s.status !== 'delivered' && (
                      confirmId === s.id ? (
                        <div className="mt-3">
                          <HandoffForm
                            submitLabel="Confirm Receipt"
                            submitting={submitting}
                            defaultQuantity={s.quantity_dispatched || 1000}
                            onCancel={() => setConfirmId(null)}
                            onSubmit={(payload) => handleConfirm(s.id, payload)}
                          />
                        </div>
                      ) : (
                        <button type="button" onClick={() => { if(typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(20); setConfirmId(s.id); }}
                          className="mt-4 w-full sm:w-auto text-sm font-bold px-5 py-3 rounded-xl transition-all hover:scale-105 flex items-center justify-center gap-2"
                          style={{ background: 'linear-gradient(135deg,#059669,#047857)', color: 'white', boxShadow: '0 4px 12px rgba(5,150,105,0.2)' }}>
                          <span>📱</span> Scan & Confirm Delivery
                        </button>
                      )
                    )}

                    {chainShipId === s.id && (
                      <div className="mt-4">
                        <ChainVerificationPanel
                          report={chainReport} loading={chainLoading} error={null}
                          onClose={() => { setChainReport(null); setChainShipId(null) }} />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {/* ── Stock / Inventory tab ────────────────────────────── */}
      {!loading && tab === 'inventory' && (
        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader title="Hospital Stock Levels" sub="Auto-updated on each confirmed delivery" />
            {inventory.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-light)' }}>No stock yet. Confirm a delivery first.</div>
            ) : (
              <ul>
                {inventory.map(item => {
                  const low = item.quantity <= item.reorder_threshold
                  const pct = Math.min(100, Math.round((item.quantity / (item.reorder_threshold * 3)) * 100))
                  return (
                    <li key={item.id} className="px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>{item.medicine_name}</span>
                          {low && (
                            <span className="text-xs px-1.5 py-0.5 rounded font-bold"
                              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>Low</span>
                          )}
                        </div>
                        <span className={`text-sm font-bold ${low ? 'text-red-500' : 'text-slate-800'}`}>
                          {item.pieces_per_pack > 1 ? (
                            <>
                              {Math.floor(item.quantity / item.pieces_per_pack).toLocaleString()} packs
                              {item.quantity % item.pieces_per_pack > 0 && `, ${item.quantity % item.pieces_per_pack} units`}
                            </>
                          ) : (
                            `${item.quantity?.toLocaleString()} units`
                          )}
                        </span>
                      </div>
                      {/* Stock bar */}
                      <div className="h-1.5 rounded-full" style={{ background: 'rgba(0,0,0,0.06)' }}>
                        <div className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, background: low ? '#ef4444' : 'var(--emerald)' }} />
                      </div>
                      <p className="text-xs mt-1" style={{ color: 'var(--text-light)' }}>Reorder at {item.reorder_threshold?.toLocaleString()}</p>
                    </li>
                  )
                })}
              </ul>
            )}
            {inventory.length > 0 && (
              <div className="px-6 py-4" style={{ borderTop: '1px solid var(--border)' }}>
                <button type="button" onClick={() => { setTab('clearance'); selectMedicineForClearance(inventory[0].medicine_name) }}
                  className="text-xs font-semibold transition-opacity hover:opacity-70" style={{ color: 'var(--emerald)' }}>
                  Record stock clearance →
                </button>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader title="Update Stock Manually" />
            <div className="p-6">
              <form onSubmit={handleInventory} className="space-y-4">
                <Field label="Medicine Name">
                  <DInput required placeholder="e.g. Paracetamol 500mg" value={invForm.medicine_name}
                    onChange={e => setInvForm(f => ({ ...f, medicine_name: e.target.value }))} />
                </Field>
                <Field label="Quantity">
                  <DInput type="number" required value={invForm.quantity}
                    onChange={e => setInvForm(f => ({ ...f, quantity: e.target.value }))} />
                </Field>
                <Field label="Reorder Threshold">
                  <DInput type="number" value={invForm.reorder_threshold}
                    onChange={e => setInvForm(f => ({ ...f, reorder_threshold: e.target.value }))} />
                </Field>
                <PrimaryBtn disabled={submitting}>{submitting ? 'Saving…' : 'Save Stock'}</PrimaryBtn>
              </form>
            </div>
          </Card>
        </div>
      )}

      {/* ── Stock Clearance tab ──────────────────────────────── */}
      {!loading && tab === 'clearance' && (
        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader title="Record Stock Clearance"
              sub="Log dispensed, expired or damaged units. Creates stock_clearance audit entry." />
            <div className="p-6">
              {inventory.length === 0 ? (
                <p className="text-slate-500 text-sm">No stock to clear. Confirm a delivery first.</p>
              ) : clearanceStep === 'form' ? (
                <form onSubmit={handleClearanceReview} className="space-y-4">
                  <Field label="Medicine">
                    <DSelect required value={clearanceForm.medicine_name}
                      onChange={e => selectMedicineForClearance(e.target.value)}>
                      <option value="">Select from stock…</option>
                      {inventory.map(item => (
                        <option key={item.id} value={item.medicine_name}>
                          {item.medicine_name} ({item.quantity?.toLocaleString()} in stock)
                        </option>
                      ))}
                    </DSelect>
                  </Field>

                  {selectedStock && (
                    <div className="p-3 rounded-xl text-xs flex justify-between"
                      style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
                      <span style={{ color: 'var(--text-light)' }}>Available</span>
                      <span className="font-bold text-slate-800">{maxClearable.toLocaleString()} units</span>
                    </div>
                  )}

                  <Field label="Quantity to Clear">
                    <DInput required type="number" min={1} max={maxClearable || undefined}
                      disabled={!selectedStock} value={clearanceForm.quantity_cleared}
                      onChange={e => setClearanceForm(f => ({ ...f, quantity_cleared: e.target.value }))} />
                    {selectedStock && maxClearable > 0 && (
                      <button type="button"
                        className="mt-1 text-xs font-semibold transition-opacity hover:opacity-70" style={{ color: 'var(--emerald)' }}
                        onClick={() => setClearanceForm(f => ({ ...f, quantity_cleared: String(maxClearable) }))}>
                        Clear all ({maxClearable.toLocaleString()})
                      </button>
                    )}
                  </Field>

                  <Field label="Reason">
                    <DSelect required value={clearanceForm.reason}
                      onChange={e => setClearanceForm(f => ({ ...f, reason: e.target.value }))}>
                      {CLEARANCE_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                    </DSelect>
                  </Field>

                  <Field label="Notes (optional)">
                    <textarea rows={2} className="w-full px-4 py-3 text-sm resize-none"
                      style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
                      placeholder="Ward, batch ref, incident ID…"
                      value={clearanceForm.notes}
                      onChange={e => setClearanceForm(f => ({ ...f, notes: e.target.value }))} />
                  </Field>

                  <PrimaryBtn disabled={!selectedStock || maxClearable === 0}>
                    Review clearance →
                  </PrimaryBtn>
                </form>
              ) : (
                /* Confirm step */
                <div className="space-y-4">
                  <h3 className="font-bold text-base" style={{ color: 'var(--text-base)' }}>Confirm Clearance</h3>
                  <div className="p-4 rounded-xl space-y-2"
                    style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
                    {[
                      ['Medicine',   clearanceForm.medicine_name],
                      ['Quantity',   `${Number(clearanceForm.quantity_cleared).toLocaleString()} units`],
                      ['Reason',     CLEARANCE_REASONS.find(r => r.value === clearanceForm.reason)?.label],
                      ['After',      `${(maxClearable - Number(clearanceForm.quantity_cleared)).toLocaleString()} units remaining`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between text-sm">
                        <span style={{ color: 'var(--text-light)' }}>{k}</span>
                        <span className="font-semibold text-slate-800">{v}</span>
                      </div>
                    ))}
                  </div>
                  <div className="px-4 py-3 rounded-xl text-xs font-semibold"
                    style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.15)', color: 'var(--amber)' }}>
                    ⚠️ Logged for compliance — use Emergency Request if you need restocking.
                  </div>
                  <div className="flex gap-3">
                    <SecondaryBtn onClick={() => setClearanceStep('form')}>Edit</SecondaryBtn>
                    <PrimaryBtn disabled={submitting} onClick={handleClearanceConfirm} type="button" danger>
                      {submitting ? 'Processing…' : 'Confirm Clearance'}
                    </PrimaryBtn>
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Clearance History" sub="Append-only compliance log" />
            {clearances.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-light)' }}>No clearances recorded yet.</div>
            ) : (
              <ul className="max-h-96 overflow-y-auto">
                {clearances.map(c => (
                  <li key={c.id} className="px-6 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                    <p className="text-sm font-bold" style={{ color: 'var(--text-base)' }}>{c.medicine_name}</p>
                    <p className="text-xs font-semibold mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      <span className="text-red-500 font-bold">−{c.quantity_cleared?.toLocaleString()}</span>
                      {' · '}{CLEARANCE_REASONS.find(r => r.value === c.reason)?.label || c.reason?.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>
                      {c.quantity_remaining_after?.toLocaleString()} left · {new Date(c.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}

      {/* ── Emergency Request tab ────────────────────────────── */}
      {!loading && tab === 'request' && (
        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader title="Emergency Stock Request → Supplier" sub="Creates emergency_stock_request approval log" />
            <div className="p-6">
              <form onSubmit={handleStockRequest} className="space-y-4">
                <Field label="Medicine Name">
                  <DInput required placeholder="e.g. Oral Rehydration Salts" value={stockForm.medicine_name}
                    onChange={e => setStockForm(f => ({ ...f, medicine_name: e.target.value }))} />
                </Field>
                <Field label="Quantity Requested">
                  <DInput type="number" required value={stockForm.quantity_requested}
                    onChange={e => setStockForm(f => ({ ...f, quantity_requested: e.target.value }))} />
                </Field>
                <Field label="Reason">
                  <textarea required rows={3} className="w-full px-4 py-3 text-sm resize-none"
                    style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
                    placeholder="e.g. Flood has disrupted supply, critical shortage…"
                    value={stockForm.reason}
                    onChange={e => setStockForm(f => ({ ...f, reason: e.target.value }))} />
                </Field>
                <Field label="Urgency">
                  <DSelect value={stockForm.urgency} onChange={e => setStockForm(f => ({ ...f, urgency: e.target.value }))}>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </DSelect>
                </Field>
                <PrimaryBtn disabled={submitting} warning>
                  {submitting ? 'Sending…' : '🆘 Submit Emergency Request'}
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
