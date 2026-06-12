import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import PasswordInput from '../components/PasswordInput'

const ROLE_OPTIONS = [
  {
    value: 'manufacturer',
    label: 'Manufacturer',
    hint: 'Creates medicine batches and dispatches to suppliers',
    icon: '🏭',
    gradient: 'linear-gradient(135deg,#0891b2,#3b82f6)',
    glow: 'rgba(8,145,178,0.15)',
  },
  {
    value: 'supplier',
    label: 'Supplier / Distributor',
    hint: 'Receives shipments, verifies handoffs, ships to hospitals',
    icon: '🚚',
    gradient: 'linear-gradient(135deg,#7c3aed,#6d28d9)',
    glow: 'rgba(124,58,237,0.15)',
  },
  {
    value: 'consumer',
    label: 'Hospital / NGO',
    hint: 'Receives pharmaceutical deliveries and confirms receipt',
    icon: '🏥',
    gradient: 'linear-gradient(135deg,#059669,#047857)',
    glow: 'rgba(5,150,105,0.15)',
  },
]

export default function Signup() {
  const navigate = useNavigate()
  const { saveSession } = useAuth()
  const [step, setStep] = useState(1) // 1=pick role, 2=fill form
  const [role, setRole] = useState('manufacturer')
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    organization_name: '',
    country: 'India',
    license_number: '',
    warehouse_location: '',
    location: '',
  })
  const [error,      setError]      = useState('')
  const [submitting, setSubmitting] = useState(false)

  function update(field, value) { setForm((p) => ({ ...p, [field]: value })) }

  const selected = ROLE_OPTIONS.find((r) => r.value === role)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const payload = {
        email:             form.email.trim(),
        password:          form.password,
        full_name:         form.full_name.trim(),
        role,
        organization_name: form.organization_name.trim(),
        country:           form.country.trim() || 'India',
      }
      if (role === 'manufacturer' && form.license_number.trim())
        payload.license_number = form.license_number.trim()
      if (role === 'supplier' && form.warehouse_location.trim())
        payload.warehouse_location = form.warehouse_location.trim()
      if (role === 'consumer' && form.location.trim()) {
        payload.location = form.location.trim()
        payload.consumer_type = 'hospital'
      }

      const data = await register(payload)
      saveSession(data)
      if (data.role === 'manufacturer') navigate('/manufacturer')
      else if (data.role === 'supplier') navigate('/supplier')
      else navigate('/hospital')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Registration failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--bg-base)', color: 'var(--text-base)' }}>
      <div className="w-full max-w-lg animate-slide-up">
        {/* Header */}
        <div className="text-center mb-8">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-2xl shadow-lg mx-auto mb-4"
            style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)' }}
          >P</div>
          <h1 className="text-3xl font-bold">Join ChainMed</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-light)' }}>Create your verified supply chain account</p>
        </div>

        {/* Step 1 — Role selector */}
        {step === 1 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-center mb-5" style={{ color: 'var(--text-light)' }}>Select your role to get started</p>
            <div className="space-y-3">
              {ROLE_OPTIONS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => { setRole(r.value); setStep(2) }}
                  className="w-full p-5 rounded-2xl text-left transition-all duration-200 hover:scale-[1.02] flex items-center gap-4 group"
                  style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
                  onMouseEnter={e => { e.currentTarget.style.boxShadow = `0 0 24px ${r.glow}`; e.currentTarget.style.borderColor = 'var(--cyan)' }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = 'var(--border)' }}
                >
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shadow-lg flex-shrink-0"
                    style={{ background: r.gradient }}
                  >{r.icon}</div>
                  <div className="flex-1">
                    <p className="font-bold" style={{ color: 'var(--text-base)' }}>{r.label}</p>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>{r.hint}</p>
                  </div>
                  <span className="text-slate-400 group-hover:text-slate-700 transition-colors">→</span>
                </button>
              ))}
            </div>
            <p className="text-center text-sm mt-6" style={{ color: 'var(--text-muted)' }}>
              Already registered?{' '}
              <Link to="/login" className="font-semibold transition-opacity hover:opacity-80" style={{ color: 'var(--cyan)' }}>Sign in</Link>
            </p>
          </div>
        )}

        {/* Step 2 — Details form */}
        {step === 2 && (
          <div
            className="p-8 rounded-2xl"
            style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
          >
            <button
              type="button"
              onClick={() => { setStep(1); setError('') }}
              className="text-sm transition-colors flex items-center gap-1.5 mb-5 font-semibold"
              style={{ color: 'var(--text-light)' }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--text-base)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text-light)'}
            >← Back</button>

            {/* Role badge */}
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0" style={{ background: selected?.gradient }}>{selected?.icon}</div>
              <div>
                <p className="font-bold" style={{ color: 'var(--text-base)' }}>{selected?.label}</p>
                <p className="text-xs" style={{ color: 'var(--text-light)' }}>{selected?.hint}</p>
              </div>
            </div>

            {error && (
              <div className="mb-5 px-4 py-3 rounded-xl text-sm flex items-center gap-2"
                style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444' }}>
                <span>⚠️</span>{error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Common fields */}
              {[
                { k: 'full_name', label: 'Your Full Name', placeholder: 'Dr. Ananya Sharma', type: 'text' },
                { k: 'organization_name', label: `${selected?.label} Name`, placeholder: 'e.g. Sun Pharma Ltd.', type: 'text' },
                { k: 'country', label: 'Country', placeholder: 'India', type: 'text' },
                { k: 'email', label: 'Work Email', placeholder: 'you@organization.com', type: 'email' },
              ].map(({ k, label, placeholder, type }) => (
                <div key={k}>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">{label}</label>
                  <input
                    type={type}
                    className="w-full px-4 py-3 text-sm"
                    placeholder={placeholder}
                    value={form[k]}
                    onChange={(e) => update(k, e.target.value)}
                    required={k !== 'country'}
                  />
                </div>
              ))}

              {/* Role-specific */}
              {role === 'manufacturer' && (
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Drug License # (optional)</label>
                  <input className="w-full px-4 py-3 text-sm" placeholder="MH-MUM-123456" value={form.license_number} onChange={(e) => update('license_number', e.target.value)} />
                </div>
              )}
              {role === 'supplier' && (
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Warehouse Location (optional)</label>
                  <input className="w-full px-4 py-3 text-sm" placeholder="Mumbai Warehouse, Maharashtra" value={form.warehouse_location} onChange={(e) => update('warehouse_location', e.target.value)} />
                </div>
              )}
              {role === 'consumer' && (
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Facility Location (optional)</label>
                  <input className="w-full px-4 py-3 text-sm" placeholder="AIIMS, New Delhi" value={form.location} onChange={(e) => update('location', e.target.value)} />
                </div>
              )}

              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Password</label>
                <PasswordInput
                  required
                  minLength={8}
                  className="w-full px-4 py-3 text-sm"
                  placeholder="Min. 8 characters"
                  value={form.password}
                  onChange={(e) => update('password', e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3 rounded-xl font-semibold text-sm text-white transition-all duration-200 hover:scale-[1.02] disabled:opacity-50 mt-1"
                style={{ background: selected?.gradient, boxShadow: `0 4px 16px ${selected?.glow}` }}
              >
                {submitting ? 'Creating account…' : 'Create Account →'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
