import { useEffect, useState } from 'react'

export default function HandoffForm({
  onSubmit,
  onCancel,
  submitting,
  submitLabel,
  defaultQuantity = 1000,
}) {
  const [form, setForm] = useState({
    quantity_reported: defaultQuantity,
    expiry_reported:   '2028-01-01',
    temp_reported:     24,
    notes:             '',
  })

  useEffect(() => {
    setForm((f) => ({ ...f, quantity_reported: defaultQuantity }))
  }, [defaultQuantity])

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function handleVibrate(pattern) {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(pattern)
    }
  }

  function adjustQuantity(amount) {
    handleVibrate(30)
    setForm(f => ({ ...f, quantity_reported: Math.max(1, Number(f.quantity_reported) + amount) }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    handleVibrate(50)
    onSubmit({
      quantity_reported: Number(form.quantity_reported),
      expiry_reported:   ${form.expiry_reported}T00:00:00,
      temp_reported:     Number(form.temp_reported),
      notes:             form.notes || undefined,
    })
  }

  const inputStyle = {
    background:   '#ffffff',
    border:       '1px solid var(--border-strong)',
    color:        'var(--text-base)',
    borderRadius: '0.75rem',
    padding:      '0.75rem 1rem',
    fontSize:     '1rem',
    width:        '100%',
    outline:      'none',
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 mt-3 p-4 sm:p-5 rounded-2xl"
      style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}
    >
      <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Handoff Attestation</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Quantity Stepper */}
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5 block">
            Qty Reported (Packs)
          </label>
          <div className="flex items-center" style={inputStyle}>
            <button 
              type="button" 
              onClick={() => adjustQuantity(-100)}
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold transition-colors active:bg-slate-300"
            >
              -
            </button>
            <input
              type="number" min={1} required 
              className="flex-1 text-center font-bold text-lg outline-none bg-transparent"
              value={form.quantity_reported}
              onChange={(e) => update('quantity_reported', e.target.value)}
            />
            <button 
              type="button" 
              onClick={() => adjustQuantity(100)}
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold transition-colors active:bg-slate-300"
            >
              +
            </button>
          </div>
        </div>

        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5 block">
            Expiry date
          </label>
          <input
            type="date" required style={inputStyle}
            value={form.expiry_reported}
            onChange={(e) => update('expiry_reported', e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5 block">
          Storage temp (°C)
        </label>
        <input
          type="number" step="0.1" style={inputStyle}
          value={form.temp_reported}
          onChange={(e) => update('temp_reported', e.target.value)}
        />
      </div>

      <div>
        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5 block">
          Notes
        </label>
        <textarea
          rows={3} style={{ ...inputStyle, resize: 'none' }}
          placeholder="Cold chain maintained, packaging intact…"
          value={form.notes}
          onChange={(e) => update('notes', e.target.value)}
        />
      </div>

      <div className="flex flex-col sm:flex-row gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="w-full sm:w-auto px-6 py-3.5 rounded-xl text-sm font-bold text-white transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
          style={{ background: 'linear-gradient(135deg,#059669,#047857)', boxShadow: '0 4px 12px rgba(5,150,105,0.2)' }}
        >
          {submitting ? 'Submitting…' : <><span>?</span> {submitLabel}</>}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={() => { handleVibrate(20); onCancel(); }}
            className="w-full sm:w-auto text-sm font-bold px-6 py-3.5 rounded-xl transition-colors"
            style={{ color: 'var(--text-light)', border: '1px solid var(--border)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--border)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
