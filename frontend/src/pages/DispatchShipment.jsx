import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { getBatches, createShipment } from '../api/manufacturer'
import { DEFAULT_ENTITY_ID } from '../utils/entityIds'

const SUPPLIER_ID = DEFAULT_ENTITY_ID.supplier

export default function DispatchShipment() {
  const [batches, setBatches] = useState([])
  const [form, setForm] = useState({
    batch_id: '',
    to_entity_id: SUPPLIER_ID,
    quantity: '',
  })
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const loadBatches = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getBatches()
      setBatches(data.filter((b) => (b.quantity_remaining ?? b.quantity) > 0))
    } catch {
      setError('Could not load batches')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBatches()
  }, [loadBatches])

  const selectedBatch = batches.find((b) => b.id === form.batch_id)
  const remaining = selectedBatch?.quantity_remaining ?? 0

  useEffect(() => {
    if (!form.batch_id) return
    const batch = batches.find((b) => b.id === form.batch_id)
    if (!batch) return
    setForm((f) => ({
      ...f,
      quantity: String(batch.quantity_remaining ?? 0),
    }))
  }, [form.batch_id, batches])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setResult(null)

    const packs = Number(form.quantity)
    if (!packs || packs < 1) {
      setError('Enter a valid dispatch quantity')
      return
    }
    
    const qty = packs * (selectedBatch?.pieces_per_pack || 1)
    
    if (qty > remaining) {
      setError(`Only ${Math.floor(remaining / (selectedBatch?.pieces_per_pack || 1)).toLocaleString()} packs available for this batch`)
      return
    }

    setSubmitting(true)
    try {
      const data = await createShipment({
        batch_id: form.batch_id,
        to_entity_id: form.to_entity_id,
        quantity: qty,
      })
      setResult(data)
      await loadBatches()
      setForm((f) => ({ ...f, batch_id: '', quantity: '' }))
    } catch (err) {
      setError(err.response?.data?.detail || 'Dispatch failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout title="Dispatch Batch">
      <Link to="/manufacturer" className="text-sm font-bold transition-opacity hover:opacity-85" style={{ color: 'var(--cyan)' }}>
        ← Back to Dashboard
      </Link>

      <div className="mt-6 max-w-lg animate-slide-up">
        <h1 className="text-2xl font-black mb-2" style={{ color: 'var(--text-base)' }}>Ship Batch to Supplier</h1>
        <p className="text-xs font-semibold mb-6" style={{ color: 'var(--text-light)' }}>
          Dispatch part or all of a batch. Remaining units update after each shipment.
        </p>

        {error && (
          <p className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3 font-semibold">
            ⚠️ {error}
          </p>
        )}

        {result && (
          <div className="mb-6 text-sm bg-green-50 border border-green-200 rounded-xl p-5 space-y-2 font-semibold">
            <p className="font-bold text-green-800">
              Dispatched {result.quantity_dispatched?.toLocaleString()} units · {result.shipment_code}
            </p>
            <p className="text-green-700">Approval log: {result.approval_log_id}</p>
            <p className="text-green-700">
              <Link
                to={`/shared/shipment/${result.id}`}
                target="_blank"
                className="underline"
              >
                Open public verification page →
              </Link>
            </p>
            {result.qr_code_url && (
              <div className="pt-2">
                <p className="text-slate-600 mb-2">QR code:</p>
                <img src={result.qr_code_url} alt="Shipment QR" className="w-40 h-40 border rounded-lg" />
              </div>
            )}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="rounded-xl p-6 space-y-4"
          style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)' }}
        >
          <Field label="Batch">
            <select
              required
              disabled={loading}
              className="w-full px-4 py-3 text-sm"
              style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)', borderRadius: '0.75rem' }}
              value={form.batch_id}
              onChange={(e) => setForm((f) => ({ ...f, batch_id: e.target.value }))}
            >
              <option value="">Select batch…</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} — {b.batch_number} ({Math.floor((b.quantity_remaining ?? 0) / b.pieces_per_pack).toLocaleString()} of{' '}
                  {Math.floor((b.quantity ?? 0) / b.pieces_per_pack).toLocaleString()} packs left)
                </option>
              ))}
            </select>
          </Field>

          {selectedBatch && (
            <div className="text-xs rounded-xl px-3 py-2 space-y-1 font-semibold" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
              <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Batch Total</span><span className="font-bold text-slate-800">{Math.floor(selectedBatch.quantity / selectedBatch.pieces_per_pack).toLocaleString()} packs</span></div>
              <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Already Dispatched</span><span className="font-bold text-slate-800">{Math.floor((selectedBatch.quantity_dispatched ?? 0) / selectedBatch.pieces_per_pack).toLocaleString()} packs</span></div>
              <div className="flex justify-between"><span style={{ color: 'var(--text-light)' }}>Available to Ship</span><span className="font-bold text-emerald-600">{Math.floor(remaining / selectedBatch.pieces_per_pack).toLocaleString()} packs</span></div>
            </div>
          )}

          <Field label="Packs to dispatch">
            <input
              required
              type="number"
              min={1}
              max={Math.floor(remaining / selectedBatch?.pieces_per_pack) || undefined}
              disabled={!selectedBatch}
              className="w-full px-4 py-3 text-sm"
              value={form.quantity}
              onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
              placeholder="Number of strips/boxes"
            />
            {selectedBatch && (
              <button
                type="button"
                className="mt-1 text-xs font-bold transition-opacity hover:opacity-85"
                style={{ color: 'var(--cyan)' }}
                onClick={() => setForm((f) => ({ ...f, quantity: String(Math.floor(remaining / selectedBatch.pieces_per_pack)) }))}
              >
                Dispatch all remaining ({Math.floor(remaining / selectedBatch.pieces_per_pack).toLocaleString()} packs)
              </button>
            )}
          </Field>

          <Field label="Supplier ID">
            <input
              required
              className="w-full px-4 py-3 text-sm font-mono"
              value={form.to_entity_id}
              onChange={(e) => setForm((f) => ({ ...f, to_entity_id: e.target.value }))}
            />
          </Field>

          <button
            type="submit"
            disabled={submitting || batches.length === 0 || !selectedBatch}
            className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all duration-200 hover:scale-[1.01] disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 12px rgba(8,145,178,0.2)' }}
          >
            {submitting ? 'Dispatching…' : 'Dispatch & Generate QR'}
          </button>
        </form>
      </div>
    </Layout>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5 block">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}
