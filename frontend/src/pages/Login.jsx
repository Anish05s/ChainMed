import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import PasswordInput from '../components/PasswordInput'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { user, saveSession } = useAuth()
  const navigate = useNavigate()

  // Admin Modal States
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [showOtpModal, setShowOtpModal] = useState(false)
  const [adminEmail, setAdminEmail] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [otp, setOtp] = useState('')

  useEffect(() => {
    if (!user) return
    if (user.role === 'manufacturer') navigate('/manufacturer', { replace: true })
    else if (user.role === 'supplier') navigate('/supplier', { replace: true })
    else if (user.role === 'consumer') navigate('/hospital', { replace: true })
    else if (user.role === 'admin') navigate('/admin', { replace: true })
  }, [user, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(email, password)
      saveSession(data)
      if (data.role === 'manufacturer') navigate('/manufacturer')
      else if (data.role === 'supplier') navigate('/supplier')
      else if (data.role === 'consumer') navigate('/hospital')
      else if (data.role === 'admin') navigate('/admin')
      else navigate('/')
    } catch {
      setError('Invalid email or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleAdminSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // login() needs to accept OTP now. We'll update api/auth.js next.
      const data = await login(adminEmail, adminPassword, otp)
      saveSession(data)
      navigate('/admin')
    } catch (err) {
      setError(err.response?.data?.detail || 'Admin login failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-base)' }}>
      {/* Main split view */}
      <div className="flex-1 flex">
        {/* Left panel — feature list */}
        <div
          className="hidden lg:flex lg:w-1/2 flex-col justify-center px-16 py-12"
          style={{ background: 'linear-gradient(135deg, #e0f2fe 0%, #f0fdf4 100%)', borderRight: '1px solid var(--border)' }}
        >
          <div className="animate-slide-up">
            {/* New Logo style */}
            <div className="flex items-center gap-3 mb-10">
              <img src="/logo.png" alt="ChainMed" className="h-[84px] w-auto object-contain" />
              <h1 className="text-4xl font-black" style={{ color: 'var(--text-base)' }}>
                Pharma<span className="gradient-text">Chain</span>
              </h1>
            </div>

            <div className="space-y-4 max-w-md">
              {[
                { icon: '🔐', t: 'Three-Party Attestation', d: 'Fraud requires simultaneous collusion across all three parties — always on-chain.' },
                { icon: '⛓️', t: 'Immutable Blockchain Records', d: 'Every handoff recorded on Ethereum Sepolia. Tamper-proof audit trail.' },
                { icon: '🤖', t: 'Explainable AI Flags', d: 'Risk score 0–100 with human-readable explanation on every cross-match.' },
                { icon: '🌍', t: 'Crisis-Aware Rerouting', d: 'NewsAPI + NetworkX detects floods & conflicts and reroutes supply chains.' },
              ].map(({ icon, t, d }) => (
                <div
                  key={t}
                  className="flex items-start gap-4 p-5 rounded-xl transition-all duration-300 hover:scale-[1.01]"
                  style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
                >
                  <span className="text-2xl flex-shrink-0">{icon}</span>
                  <div>
                    <p className="font-semibold text-sm" style={{ color: 'var(--text-base)' }}>{t}</p>
                    <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-light)' }}>{d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — login form */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-md">
            {/* Mobile logo */}
            <div className="lg:hidden text-center mb-8 flex flex-col items-center">
              <img src="/logo.png" alt="ChainMed" className="h-[72px] w-auto object-contain mb-3" />
              <h1 className="text-2xl font-bold" style={{ color: 'var(--text-base)' }}>ChainMed</h1>
            </div>

            <div
              className="p-8 rounded-2xl animate-slide-up"
              style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)' }}
            >
              <div className="mb-7">
                <h2 className="text-2xl font-bold" style={{ color: 'var(--text-base)' }}>Welcome back</h2>
                <p className="text-sm mt-1" style={{ color: 'var(--text-light)' }}>Sign in to your portal</p>
              </div>

              {error && (
                <div
                  className="mb-5 px-4 py-3 rounded-xl text-sm flex items-center gap-2"
                  style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444' }}
                >
                  <span>⚠️</span> {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Email</label>
                  <input
                    id="login-email"
                    type="email"
                    className="w-full px-4 py-3 text-sm"
                    placeholder="you@chainmed.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">Password</label>
                  <PasswordInput
                    id="login-password"
                    placeholder="Your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>

                <button
                  id="login-submit"
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-sm text-white transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed mt-2"
                  style={{ background: 'linear-gradient(135deg,#0891b2,#3b82f6)', boxShadow: '0 4px 16px rgba(8,145,178,0.2)' }}
                >
                  {loading
                    ? <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Signing in…
                      </span>
                    : 'Sign in'}
                </button>
              </form>

                <p className="text-center text-sm mt-6" style={{ color: 'var(--text-light)' }}>
                New here?{' '}
                <Link to="/signup" className="font-semibold transition-colors" style={{ color: 'var(--cyan)' }}>
                  Create account
                </Link>
              </p>
            </div>

            {/* Admin Login Box (Separate Box) */}
            <div 
              className="mt-4 p-4 rounded-2xl animate-slide-up flex items-center justify-center text-center cursor-pointer transition-all hover:scale-[1.02]"
              style={{ background: '#ffffff', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
              onClick={() => setShowAdminModal(true)}
            >
              <button 
                type="button"
                className="font-semibold"
                style={{ color: 'var(--text-light)', fontSize: '15px' }}
              >
                Admin Login
              </button>
            </div>
            
          </div>
        </div>
      </div>

      {/* Admin Login Modal */}
      {showAdminModal && !showOtpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-sm p-6 rounded-2xl animate-slide-up" style={{ background: '#ffffff', boxShadow: 'var(--shadow-xl)' }}>
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--text-base)' }}>Admin Access</h3>
            <form onSubmit={(e) => { e.preventDefault(); setShowOtpModal(true); }}>
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Admin Email</label>
                  <input type="email" required className="w-full px-4 py-3 text-sm" value={adminEmail} onChange={e => setAdminEmail(e.target.value)} />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Password</label>
                  <PasswordInput value={adminPassword} onChange={e => setAdminPassword(e.target.value)} />
                </div>
                <div className="flex gap-3 mt-6">
                  <button type="button" onClick={() => setShowAdminModal(false)} className="flex-1 py-2.5 rounded-xl font-semibold text-sm border" style={{ color: 'var(--text-muted)' }}>Cancel</button>
                  <button type="submit" className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white" style={{ background: 'var(--cyan)' }}>Continue</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin OTP Modal */}
      {showOtpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-sm p-6 rounded-2xl animate-slide-up" style={{ background: '#ffffff', boxShadow: 'var(--shadow-xl)' }}>
            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--text-base)' }}>Enter OTP</h3>
            <p className="text-xs text-slate-500 mb-6">A one-time passcode is required for admin access. (Use 123456)</p>
            {error && <p className="text-red-500 text-xs mb-3">{error}</p>}
            <form onSubmit={handleAdminSubmit}>
              <div className="space-y-4">
                <div>
                  <input type="text" required maxLength={6} placeholder="123456" className="w-full px-4 py-3 text-center text-xl tracking-widest font-mono" value={otp} onChange={e => setOtp(e.target.value)} />
                </div>
                <div className="flex gap-3 mt-6">
                  <button type="button" onClick={() => setShowOtpModal(false)} className="flex-1 py-2.5 rounded-xl font-semibold text-sm border" style={{ color: 'var(--text-muted)' }}>Back</button>
                  <button type="submit" disabled={loading} className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white" style={{ background: 'var(--cyan)' }}>
                    {loading ? 'Verifying...' : 'Sign In'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer block matching the Resilinc style */}
      <footer className="text-white py-16 px-8 lg:px-24 w-full" style={{ background: '#0b1d3a' }}>
        <div className="max-w-7xl mx-auto flex flex-col lg:flex-row justify-between gap-12 lg:gap-24">
          
          {/* Left side */}
          <div className="lg:w-1/3 flex flex-col">
            <div className="flex items-center gap-3 mb-6">
              <img src="/logo.png" alt="ChainMed" className="h-[60px] w-auto object-contain" />
              <span className="text-2xl font-bold tracking-tight">ChainMed</span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed mb-8 max-w-sm">
              AI + Blockchain pharmaceutical supply chain integrity for the other 6 billion.
            </p>
            
            {/* Social Icons (using SVGs) */}
            <div className="flex items-center gap-5 mb-10">
              <a href="#" className="text-white hover:text-cyan-400 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              </a>
              <a href="#" className="text-white hover:text-cyan-400 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path fillRule="evenodd" d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z" clipRule="evenodd"/></svg>
              </a>
              <a href="#" className="text-white hover:text-cyan-400 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path fillRule="evenodd" d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" clipRule="evenodd"/></svg>
              </a>
            </div>
          </div>

          {/* Right side columns */}
          <div className="lg:w-2/3 grid grid-cols-2 md:grid-cols-4 gap-8">
            <div>
              <h3 className="font-bold text-white mb-4">Company</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li><a href="#" className="hover:text-white transition-colors">About ChainMed</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Events</a></li>
              </ul>
            </div>
            <div>
              <h3 className="font-bold text-white mb-4">Products</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li><a href="#" className="hover:text-white transition-colors">AI Agent</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Supply Chain</a></li>
              </ul>
            </div>
            <div>
              <h3 className="font-bold text-white mb-4">Resources</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li><a href="#" className="hover:text-white transition-colors">Whitepaper</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Roadmaps</a></li>
              </ul>
            </div>
            <div>
              <h3 className="font-bold text-white mb-4">Support</h3>
              <ul className="space-y-3 text-sm text-slate-300">
                <li><a href="#" className="hover:text-white transition-colors">Customer Support</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact Us</a></li>
              </ul>
            </div>
          </div>
          
        </div>
        
        {/* Copyright */}
        <div className="max-w-7xl mx-auto mt-16 pt-8 border-t border-slate-700/50 flex flex-col md:flex-row justify-between items-center text-xs text-slate-400">
          <p>© 2026 ChainMed. All rights reserved.</p>
          <div className="flex gap-6 mt-4 md:mt-0">
            <a href="#" className="hover:text-white transition-colors">Data Security</a>
            <a href="#" className="hover:text-white transition-colors">Privacy Statement</a>
          </div>
        </div>
      </footer>
    </div>
  )
}