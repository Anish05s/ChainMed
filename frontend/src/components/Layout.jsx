import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import EmergencyNotificationBar from './EmergencyNotificationBar'
import NotificationBell from './NotificationBell'

const ROLE_NAV = {
  manufacturer: [
    { to: '/manufacturer', label: 'Dashboard', icon: '⚡' },
    { to: '/manufacturer/batch/create', label: 'Create Batch', icon: '＋' },
    { to: '/manufacturer/dispatch', label: 'Dispatch', icon: '🚚' },
  ],
  supplier: [
    { to: '/supplier', label: 'Dashboard', icon: '⚡' },
  ],
  consumer: [
    { to: '/hospital', label: 'Dashboard', icon: '⚡' },
  ],
}

const ROLE_GRADIENT = {
  manufacturer: 'linear-gradient(135deg,#0891b2,#3b82f6)',
  supplier:     'linear-gradient(135deg,#7c3aed,#6d28d9)',
  consumer:     'linear-gradient(135deg,#059669,#047857)',
}

function ProfileDropdown({ handleLogout }) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        type="button" 
        onClick={() => setOpen(!open)}
        className="w-10 h-10 rounded-full flex items-center justify-center transition-colors"
        style={{ background: '#ffffff', border: '1px solid var(--border)' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
        onMouseLeave={e => e.currentTarget.style.background = '#ffffff'}
      >
        <svg className="w-5 h-5" style={{ color: 'var(--text-light)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg py-2 z-50 animate-slide-up" style={{ border: '1px solid var(--border)' }}>
          <button 
            type="button"
            className="w-full text-left px-4 py-2 text-sm font-semibold transition-colors"
            style={{ color: 'var(--text-base)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-base)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            My Profile
          </button>
          
          <div className="px-2 mt-1 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
            <button 
              type="button"
              onClick={handleLogout}
              className="w-full text-left px-3 py-2 text-sm font-bold rounded-lg transition-all duration-300"
              style={{ color: '#ef4444', background: 'transparent', border: '1px solid transparent' }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.06)'
                e.currentTarget.style.border = '1px solid rgba(239,68,68,0.3)'
                e.currentTarget.style.boxShadow = '0 0 12px rgba(239,68,68,0.15)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.border = '1px solid transparent'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function AppFooter() {
  return (
    <footer className="bg-[#0b132b] text-slate-300 py-12 px-8 sm:px-12 mt-auto text-sm">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-5 gap-8">
        <div className="md:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <img src="/logo.png" alt="ChainMed" className="w-10 h-10 object-contain" />
            <span className="text-xl font-bold text-white">ChainMed</span>
          </div>
          <p className="text-slate-400 max-w-sm mb-6 leading-relaxed">
            AI + Blockchain pharmaceutical supply chain integrity for the other 6 billion.
          </p>
          <div className="flex items-center gap-4 text-slate-400">
            <svg className="w-5 h-5 hover:text-white cursor-pointer transition-colors" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
            <svg className="w-5 h-5 hover:text-white cursor-pointer transition-colors" fill="currentColor" viewBox="0 0 24 24"><path d="M22.675 0H1.325C.593 0 0 .593 0 1.326v21.348C0 23.407.593 24 1.325 24H12.82v-9.294H9.692v-3.622h3.128V8.413c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.313h3.587l-.467 3.622h-3.12V24h6.116c.73 0 1.323-.593 1.323-1.326V1.326C24 .593 23.407 0 22.675 0z" /></svg>
            <svg className="w-5 h-5 hover:text-white cursor-pointer transition-colors" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" /></svg>
          </div>
        </div>
        
        <div>
          <h3 className="text-white font-bold mb-4">Company</h3>
          <ul className="space-y-3">
            <li><a href="#" className="hover:text-white transition-colors">About ChainMed</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Events</a></li>
          </ul>
        </div>
        
        <div>
          <h3 className="text-white font-bold mb-4">Products</h3>
          <ul className="space-y-3">
            <li><a href="#" className="hover:text-white transition-colors">AI Agent</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Supply Chain</a></li>
          </ul>
        </div>
        
        <div>
          <h3 className="text-white font-bold mb-4">Resources</h3>
          <ul className="space-y-3">
            <li><a href="#" className="hover:text-white transition-colors">Whitepaper</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Roadmaps</a></li>
          </ul>
        </div>
        
        <div>
          <h3 className="text-white font-bold mb-4">Support</h3>
          <ul className="space-y-3">
            <li><a href="#" className="hover:text-white transition-colors">Customer Support</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Contact Us</a></li>
          </ul>
        </div>
      </div>
      
      <div className="max-w-7xl mx-auto mt-12 pt-6 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center text-slate-500">
        <p>© 2026 ChainMed. All rights reserved.</p>
        <div className="flex gap-6 mt-4 md:mt-0">
          <a href="#" className="hover:text-slate-300 transition-colors">Data Security</a>
          <a href="#" className="hover:text-slate-300 transition-colors">Privacy Statement</a>
        </div>
      </div>
    </footer>
  )
}

export default function Layout({ title, children, actions }) {
  const { user, logout } = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()

  function handleLogout() { logout(); navigate('/login') }

  const links    = ROLE_NAV[user?.role] || []
  const gradient = ROLE_GRADIENT[user?.role] || ROLE_GRADIENT.manufacturer
  const initial  = (user?.full_name || user?.email || 'U')[0].toUpperCase()

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-base)', color: 'var(--text-base)' }}>
      {/* ─── Sidebar ─────────────────────────────────────────── */}
      <aside
        className="w-64 flex-shrink-0 flex flex-col"
        style={{ background: '#ffffff', borderRight: '1px solid var(--border)' }}
      >
        {/* Logo */}
        <div className="p-6 pb-4">
          <Link to="/" className="flex items-center gap-3 group">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-lg group-hover:scale-105 transition-transform"
              style={{ background: gradient }}
            >P</div>
            <div>
              <p className="font-bold text-lg leading-none" style={{ color: 'var(--text-base)' }}>ChainMed</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-light)' }}>AI Supply Chain</p>
            </div>
          </Link>
        </div>

        {/* User card */}
        <div className="mx-4 mb-6 p-3 rounded-xl" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm mb-2 shadow"
            style={{ background: gradient }}
          >{initial}</div>
          <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-base)' }}>{user?.full_name || user?.email}</p>
          {user?.org_name && <p className="text-xs mt-0.5 truncate font-semibold" style={{ color: 'var(--text-base)' }}>{user.org_name}</p>}
          <p className="text-xs mt-0.5 capitalize" style={{ color: 'var(--text-light)' }}>{user?.sub_role?.replace(/_/g, ' ')}</p>
          {user?.entity_id && <p className="text-[10px] mt-2 truncate uppercase font-semibold" style={{ color: 'var(--text-muted)' }}>ID: {user.entity_id}</p>}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 space-y-1">
          {links.map(({ to, label, icon }) => {
            const active = location.pathname === to
            return (
              <Link
                key={to}
                to={to}
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200"
                style={active
                  ? { background: 'rgba(8,145,178,0.08)', color: 'var(--cyan)', border: '1px solid rgba(8,145,178,0.18)' }
                  : { color: 'var(--text-muted)' }}
                onMouseEnter={e => {
                  if (!active) {
                    e.currentTarget.style.background = 'var(--bg-base)';
                    e.currentTarget.style.color = 'var(--text-base)';
                  }
                }}
                onMouseLeave={e => {
                  if (!active) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = 'var(--text-muted)';
                  }
                }}
              >
                <span>{icon}</span>
                {label}
                {active && <span className="ml-auto w-1.5 h-1.5 rounded-full" style={{ background: 'var(--cyan)' }} />}
              </Link>
            )
          })}

          <div className="pt-3 mt-3" style={{ borderTop: '1px solid var(--border)' }}>
            {[
              { to: '/approval-log', icon: '📋', label: 'Audit Log' },
              { to: '/crisis',       icon: '🌍', label: 'Crisis Map' },
            ].map(({ to, icon, label }) => {
              const active = location.pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 mt-1"
                  style={active
                    ? { background: 'rgba(8,145,178,0.08)', color: 'var(--cyan)', border: '1px solid rgba(8,145,178,0.18)' }
                    : { color: 'var(--text-muted)' }}
                  onMouseEnter={e => {
                    if (!active) {
                      e.currentTarget.style.background = 'var(--bg-base)';
                      e.currentTarget.style.color = 'var(--text-base)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!active) {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.color = 'var(--text-muted)';
                    }
                  }}
                >
                  <span>{icon}</span>{label}
                </Link>
              )
            })}
          </div>
        </nav>

        {/* Bottom */}
      </aside>

      {/* ─── Main ────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header
          className="flex items-center justify-between px-8 py-4"
          style={{ borderBottom: '1px solid var(--border)', background: '#ffffff' }}
        >
          <h1 className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>{title}</h1>
          <div className="flex items-center gap-4">
            {actions}
            {actions && <div className="h-6 w-px bg-slate-200"></div>}
            <NotificationBell />
            <ProfileDropdown handleLogout={handleLogout} />
          </div>
        </header>

        <EmergencyNotificationBar />

        <main className="flex-1 overflow-auto flex flex-col bg-slate-50/50">
          <div className="flex-1 p-8">
            <div className="animate-slide-up">{children}</div>
          </div>
          <AppFooter />
        </main>
      </div>
    </div>
  )
}
