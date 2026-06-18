import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { createBatch, searchCatalog } from '../api/manufacturer'

const initialForm = {
  name: '',
  batch_number: '',
  medicine_type: 'tablets',
  pack_size: '',
  number_of_packs: '',
  manufacturing_date: '',
  expiry_date: '',
  storage_temp_declared: 25,
}

export default function CreateBatch() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [step, setStep] = useState('form') // form | confirm
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  
  // Autocomplete state
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [searchTimeout, setSearchTimeout] = useState(null)
  const wrapperRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [wrapperRef])

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function generateBatchNumber(medicineName) {
    const prefix = medicineName.substring(0, 3).toUpperCase()
    const match = medicineName.match(/\d+/)
    const dose = match ? match[0] : '00'
    const suffix = Math.random().toString(36).substring(2, 6).toUpperCase()
    return `${prefix}${dose}${suffix}`
  }

  function handleNameChange(e) {
    const value = e.target.value
    update('name', value)
    
    if (searchTimeout) clearTimeout(searchTimeout)
    if (value.trim().length > 2) {
      setSearchTimeout(setTimeout(async () => {
        try {
          const results = await searchCatalog(value)
          setSuggestions(results || [])
          setShowSuggestions(true)
        } catch (err) {
          console.error("Failed to fetch catalog", err)
        }
      }, 300))
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  function handleSelectMedicine(med) {
    const newBatchNum = generateBatchNumber(med.medicine_name)
    setForm(prev => ({
      ...prev,
      name: med.medicine_name,
      batch_number: newBatchNum,
      pack_size: med.pack_size_label || '',
      medicine_type: med.pack_size_label.toLowerCase().includes('syrup') ? 'syrup' : 
                     med.pack_size_label.toLowerCase().includes('capsule') ? 'capsules' : 'tablets'
    }))
    setShowSuggestions(false)
  }

  function handleReview(e) {
    e.preventDefault()
    setError('')
    if (!form.name.trim() || !form.batch_number.trim() || !form.number_of_packs) {
      setError('Fill in medicine name, batch number, and number of units.')
      return
    }
    if (!form.manufacturing_date || !form.expiry_date) {
      setError('Manufacturing and expiry dates are required.')
      return
    }
    if (form.expiry_date <= form.manufacturing_date) {
      setError('Expiry date must be after manufacturing date.')
      return
    }
    setStep('confirm')
  }

  async function handleConfirm() {
    setError('')
    setSubmitting(true)
    
    // Auto-calculate total quantity based on pack size
    const match = form.pack_size.match(/\d+/)
    const sizeMultiplier = match ? parseInt(match[0], 10) : 1
    const totalQuantity = Number(form.number_of_packs) * sizeMultiplier

    try {
      const payload = {
        name: form.name.trim(),
        batch_number: form.batch_number.trim(),
        medicine_type: form.medicine_type,
        pack_size: form.pack_size.trim(),
        number_of_packs: Number(form.number_of_packs),
        quantity: totalQuantity,
        storage_temp_declared: Number(form.storage_temp_declared),
        manufacturing_date: `${form.manufacturing_date}T00:00:00`,
        expiry_date: `${form.expiry_date}T00:00:00`,
      }
      const data = await createBatch(payload)
      setSuccess(data)
      setTimeout(() => navigate('/manufacturer'), 2000)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to create batch')
      setStep('form')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout title="Create Batch">
      <Link to="/manufacturer" className="text-sm font-bold transition-opacity hover:opacity-85" style={{ color: 'var(--cyan)' }}>
        ← Back to Dashboard
      </Link>

      <div className="mt-6 max-w-xl animate-slide-up">
        <h1 className="text-2xl font-black mb-2" style={{ color: 'var(--text-base)' }}>New Batch</h1>
        <p className="text-xs font-semibold mb-6" style={{ color: 'var(--text-light)' }}>
          Search for a medicine from the catalog. Batch numbers will auto-generate.
        </p>

        {error && (
          <p className="mb-4 text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm font-semibold">
            ⚠️ {error}
          </p>
        )}

        {success && (
          <div className="mb-4 text-green-700 bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm font-semibold">
            <p className="font-bold">Batch created successfully.</p>
            <p className="mt-1">Approval log ID: {success.approval_log_id}</p>
            <p className="mt-1">Redirecting to dashboard…</p>
          </div>
        )}

        {step === 'form' && (
          <form
            onSubmit={handleReview}
            className="rounded-xl p-6 space-y-4"
            style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)' }}
          >
            <div className="relative" ref={wrapperRef}>
              <Field label="Medicine name">
                <input
                  required
                  className="w-full px-4 py-3 text-sm"
                  value={form.name}
                  onChange={handleNameChange}
                  onFocus={() => { if(suggestions.length > 0) setShowSuggestions(true) }}
                  placeholder="Start typing medicine name..."
                  autoComplete="off"
                />
              </Field>
              {showSuggestions && suggestions.length > 0 && (
                <ul className="absolute z-10 w-full mt-1 bg-white border rounded-xl shadow-lg max-h-60 overflow-auto" style={{ borderColor: 'var(--border)' }}>
                  {suggestions.map((med) => (
                    <li 
                      key={med.id} 
                      className="px-4 py-3 hover:bg-slate-50 cursor-pointer border-b last:border-0"
                      onClick={() => handleSelectMedicine(med)}
                    >
                      <div className="font-bold text-sm" style={{ color: 'var(--text-base)' }}>{med.medicine_name}</div>
                      <div className="text-xs text-slate-500 mt-1">{med.pack_size_label}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <Field label="Batch number">
              <input
                required
                className="w-full px-4 py-3 text-sm bg-slate-50"
                value={form.batch_number}
                onChange={(e) => update('batch_number', e.target.value)}
                placeholder="Auto-generated or type manually"
              />
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Field label="Medicine Type">
                <select
                  className="w-full px-4 py-3 text-sm"
                  value={form.medicine_type}
                  onChange={(e) => update('medicine_type', e.target.value)}
                >
                  <option value="tablets">Tablets</option>
                  <option value="capsules">Capsules</option>
                  <option value="syrup">Syrup</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              
              <Field label="Size">
                <input
                  required
                  className="w-full px-4 py-3 text-sm"
                  value={form.pack_size}
                  onChange={(e) => update('pack_size', e.target.value)}
                  placeholder="e.g. 10 per strip"
                />
              </Field>

              <Field label="No. of units">
                <input
                  required
                  type="number"
                  min={1}
                  className="w-full px-4 py-3 text-sm"
                  value={form.number_of_packs}
                  onChange={(e) => update('number_of_packs', e.target.value)}
                  placeholder="e.g. 10000"
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Manufacturing date">
                <input
                  required
                  type="date"
                  className="w-full px-4 py-3 text-sm"
                  value={form.manufacturing_date}
                  onChange={(e) => update('manufacturing_date', e.target.value)}
                />
              </Field>
              <Field label="Expiry date">
                <input
                  required
                  type="date"
                  className="w-full px-4 py-3 text-sm"
                  value={form.expiry_date}
                  onChange={(e) => update('expiry_date', e.target.value)}
                />
              </Field>
            </div>

            <Field label="Storage temp declared (°C)">
              <input
                type="number"
                step="0.1"
                className="w-full px-4 py-3 text-sm"
                value={form.storage_temp_declared}
                onChange={(e) => update('storage_temp_declared', e.target.value)}
              />
            </Field>

            <button
              type="submit"
              className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all duration-200 hover:scale-[1.01]"
              style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 12px rgba(8,145,178,0.2)' }}
            >
              Review details →
            </button>
          </form>
        )}

        {step === 'confirm' && (
          <div className="rounded-xl p-6 space-y-4" style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)' }}>
            <h2 className="font-bold text-base" style={{ color: 'var(--text-base)' }}>Confirm before creating</h2>
            <dl className="text-sm space-y-2">
              <Row label="Medicine" value={form.name} />
              <Row label="Batch number" value={form.batch_number} />
              <Row label="Type & Size" value={`${form.medicine_type} | ${form.pack_size}`} />
              <Row label="Number of packs" value={form.number_of_packs} />
              <Row label="Manufactured" value={form.manufacturing_date} />
              <Row label="Expires" value={form.expiry_date} />
              <Row label="Storage temp" value={`${form.storage_temp_declared} °C`} />
            </dl>
            <p className="text-xs font-semibold bg-amber-50 border border-amber-200 rounded-xl px-3 py-2" style={{ color: 'var(--amber)' }}>
              Check every field. This is logged as a compliance approval (batch_creation).
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep('form')}
                className="flex-1 py-2.5 rounded-xl font-bold text-sm transition-all border"
                style={{ color: 'var(--text-muted)', borderColor: 'var(--border)', background: '#ffffff' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
                onMouseLeave={e => e.currentTarget.style.background = '#ffffff'}
              >
                Edit
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleConfirm}
                className="flex-1 py-2.5 rounded-xl font-bold text-sm text-white transition-all hover:scale-[1.01] disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 12px rgba(8,145,178,0.2)' }}
              >
                {submitting ? 'Creating…' : 'Confirm & create batch'}
              </button>
            </div>
          </div>
        )}
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

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4 border-b pb-2" style={{ borderColor: 'var(--border)' }}>
      <dt style={{ color: 'var(--text-light)' }} className="font-semibold">{label}</dt>
      <dd className="font-bold text-right" style={{ color: 'var(--text-base)' }}>{value}</dd>
    </div>
  )
}
