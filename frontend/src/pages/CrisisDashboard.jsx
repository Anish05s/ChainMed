import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import Layout from '../components/Layout'
import api from '../api/client'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

const SEVERITY_COLOR = {
  low: '#10b981',
  medium: '#f59e0b',
  high: '#ef4444',
  critical: '#7c3aed',
}

const SEVERITY_LABEL = {
  low: '🟢 Low',
  medium: '🟡 Medium',
  high: '🔴 High',
  critical: '🟣 Critical',
}

const EVENT_ICONS = {
  flood: '🌊',
  earthquake: '⚡',
  disease_outbreak: '🦠',
  conflict: '⚔️',
  cyclone: '🌀',
  port_closure: '⚓',
  heatwave: '🔥',
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

export default function CrisisDashboard() {
  const navigate = useNavigate()
  const mapRef = useRef(null)
  const mapInstance = useRef(null)

  const [events, setEvents] = useState([])
  const [eventTypes, setEventTypes] = useState([])
  const [selected, setSelected] = useState(null)
  const [recommendations, setRecommendations] = useState(null)
  const [recLoading, setRecLoading] = useState(false)

  // Form state
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    event_type: 'flood',
    region: '',
    severity: 'medium',
    source: 'manual',
    affected_routes: '',
  })
  const [formLoading, setFormLoading] = useState(false)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    fetchEvents()
    fetchEventTypes()
  }, [])

  async function fetchEvents() {
    try {
      const { data } = await api.get('/crisis/events?active_only=true')
      setEvents(data)
    } catch (err) {
      console.error('Failed to load crisis events', err)
    }
  }

  async function fetchEventTypes() {
    try {
      const { data } = await api.get('/crisis/event-types')
      setEventTypes(data.event_types || [])
    } catch {
      setEventTypes(['flood', 'earthquake', 'disease_outbreak', 'conflict', 'cyclone', 'port_closure', 'heatwave'])
    }
  }

  // Initialise Mapbox
  useEffect(() => {
    if (!mapRef.current) return
    if (!MAPBOX_TOKEN) return  // skip if no token — show fallback

    mapboxgl.accessToken = MAPBOX_TOKEN

    const map = new mapboxgl.Map({
      container: mapRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [78.9629, 20.5937],  // India — typical target region
      zoom: 3,
    })

    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    mapInstance.current = map

    return () => map.remove()
  }, [])

  // Add markers when events change
  useEffect(() => {
    const map = mapInstance.current
    if (!map || !MAPBOX_TOKEN) return

    // Remove existing markers (simple approach for MVP)
    document.querySelectorAll('.crisis-marker').forEach((el) => el.remove())

    events.forEach((event) => {
      // Approximate coordinates per region name (MVP — Phase 3 uses geocoding API)
      const coords = guessCoords(event.region)
      if (!coords) return

      const el = document.createElement('div')
      el.className = 'crisis-marker'
      el.style.cssText = `
        width: 32px; height: 32px; border-radius: 50%;
        background: ${SEVERITY_COLOR[event.severity] || '#gray'};
        border: 3px solid white;
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; cursor: pointer;
        box-shadow: 0 0 12px ${SEVERITY_COLOR[event.severity]}88;
        animation: pulse 2s infinite;
      `
      el.innerHTML = EVENT_ICONS[event.event_type] || '⚠️'
      el.title = `${event.region} — ${event.severity.toUpperCase()}`

      el.addEventListener('click', () => handleSelectEvent(event))

      new mapboxgl.Marker(el)
        .setLngLat(coords)
        .setPopup(
          new mapboxgl.Popup({ offset: 20 }).setHTML(
            `<div style="font-size:13px; color:#1e293b; font-family: sans-serif;">
              <b>${event.region}</b><br/>
              ${EVENT_ICONS[event.event_type] || ''} ${event.event_type.replace(/_/g, ' ')}<br/>
              Severity: <b>${event.severity}</b><br/>
              ${event.affected_routes ? `Routes: ${event.affected_routes}` : ''}
            </div>`
          )
        )
        .addTo(map)
    })
  }, [events])

  async function handleSelectEvent(event) {
    setSelected(event)
    setRecommendations(null)
    setRecLoading(true)
    try {
      const { data } = await api.get(`/crisis/recommendations/${event.id}`)
      setRecommendations(data)
    } catch {
      setRecommendations(null)
    } finally {
      setRecLoading(false)
    }
  }

  async function handleResolve(eventId) {
    try {
      await api.patch(`/crisis/events/${eventId}/resolve`)
      setEvents((prev) => prev.filter((e) => e.id !== eventId))
      if (selected?.id === eventId) {
        setSelected(null)
        setRecommendations(null)
      }
    } catch (err) {
      alert('Failed to resolve event')
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault()
    setFormLoading(true)
    setFormError('')
    try {
      const { data } = await api.post('/crisis/events', formData)
      setEvents((prev) => [data, ...prev])
      setShowForm(false)
      setFormData({ event_type: 'flood', region: '', severity: 'medium', source: 'manual', affected_routes: '' })
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create event')
    } finally {
      setFormLoading(false)
    }
  }

  return (
    <Layout title="Crisis Intelligence">
      <div className="space-y-6">
        {/* Header row */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-black" style={{ color: 'var(--text-base)' }}>Crisis Disruption Center</h1>
            <p className="text-xs font-semibold mt-1" style={{ color: 'var(--text-light)' }}>
              Real-time disruption tracking · Medicine pre-positioning recommendations
            </p>
          </div>
          <button
            id="report-crisis-btn"
            onClick={() => setShowForm((v) => !v)}
            className="px-4 py-2 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 transition-all text-sm flex items-center gap-2 shadow-md hover:scale-[1.01]"
          >
            {showForm ? '✕ Cancel' : '+ Report Event'}
          </button>
        </div>

        {/* Report form */}
        {showForm && (
          <div className="bg-white border rounded-2xl p-6 shadow-md animate-slide-up" style={{ borderColor: 'var(--border)' }}>
            <h2 className="font-bold text-lg mb-4" style={{ color: 'var(--text-base)' }}>Report Disruption Event</h2>
            <form onSubmit={handleFormSubmit} className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Event Type</label>
                <select
                  id="crisis-event-type"
                  value={formData.event_type}
                  onChange={(e) => setFormData((d) => ({ ...d, event_type: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)' }}
                  required
                >
                  {eventTypes.map((t) => (
                    <option key={t} value={t}>{EVENT_ICONS[t] || ''} {t.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Region / Location</label>
                <input
                  id="crisis-region"
                  type="text"
                  value={formData.region}
                  onChange={(e) => setFormData((d) => ({ ...d, region: e.target.value }))}
                  placeholder="e.g. Assam, India"
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)' }}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Severity</label>
                <select
                  id="crisis-severity"
                  value={formData.severity}
                  onChange={(e) => setFormData((d) => ({ ...d, severity: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)' }}
                >
                  <option value="low">🟢 Low</option>
                  <option value="medium">🟡 Medium</option>
                  <option value="high">🔴 High</option>
                  <option value="critical">🟣 Critical</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Source</label>
                <input
                  type="text"
                  value={formData.source}
                  onChange={(e) => setFormData((d) => ({ ...d, source: e.target.value }))}
                  placeholder="manual / gdelt / openweather / WHO"
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)' }}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Affected Routes (optional)</label>
                <input
                  type="text"
                  value={formData.affected_routes}
                  onChange={(e) => setFormData((d) => ({ ...d, affected_routes: e.target.value }))}
                  placeholder="e.g. NH37, Brahmaputra ferry route"
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  style={{ background: '#ffffff', border: '1px solid var(--border-strong)', color: 'var(--text-base)' }}
                />
              </div>
              {formError && (
                <p className="sm:col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2 font-semibold">
                  ⚠️ {formError}
                </p>
              )}
              <div className="sm:col-span-2 flex justify-end">
                <button
                  id="submit-crisis-event-btn"
                  type="submit"
                  disabled={formLoading}
                  className="px-6 py-2.5 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 disabled:opacity-50 transition text-sm shadow-md"
                >
                  {formLoading ? 'Submitting…' : 'Report Event'}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Map */}
          <div className="lg:col-span-2">
            {MAPBOX_TOKEN ? (
              <div className="bg-white rounded-2xl overflow-hidden shadow-sm border" style={{ height: 420, borderColor: 'var(--border)' }}>
                <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
              </div>
            ) : (
              <div className="bg-white rounded-2xl flex flex-col items-center justify-center text-center p-10 shadow-sm border" style={{ height: 420, borderColor: 'var(--border)' }}>
                <span className="text-4xl mb-3">🗺️</span>
                <p className="font-bold text-lg" style={{ color: 'var(--text-base)' }}>Mapbox map not configured</p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-light)' }}>
                  Set <code className="bg-slate-100 border px-1.5 py-0.5 rounded font-mono font-bold text-slate-800">VITE_MAPBOX_TOKEN</code> in{' '}
                  <code className="bg-slate-100 border px-1.5 py-0.5 rounded font-mono font-bold text-slate-800">frontend/.env</code> to enable the live crisis map.
                </p>
                <p className="text-xs mt-3 font-semibold text-slate-400">Events are still tracked and listed in the panel →</p>
              </div>
            )}
          </div>

          {/* Events list */}
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            <h2 className="font-bold text-slate-500 text-xs uppercase tracking-wide">
              Active Events ({events.length})
            </h2>
            {events.length === 0 && (
              <p className="text-sm py-4 text-center font-semibold" style={{ color: 'var(--text-light)' }}>No active disruption events</p>
            )}
            {events.map((event) => (
              <div
                key={event.id}
                onClick={() => handleSelectEvent(event)}
                className={`bg-white border rounded-xl p-4 cursor-pointer transition shadow-sm hover:scale-[1.01] ${
                  selected?.id === event.id ? 'border-red-500 ring-1 ring-red-200' : 'border-slate-200'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-lg">{EVENT_ICONS[event.event_type] || '⚠️'}</span>
                  <span
                    className="text-xs font-bold px-2 py-0.5 rounded-full"
                    style={{
                      background: SEVERITY_COLOR[event.severity] + '15',
                      color: SEVERITY_COLOR[event.severity],
                    }}
                  >
                    {event.severity.toUpperCase()}
                  </span>
                </div>
                <p className="font-bold text-slate-800 text-sm mt-1 capitalize">
                  {event.event_type.replace(/_/g, ' ')}
                </p>
                <p className="text-xs font-semibold text-slate-500 mt-0.5">📍 {event.region}</p>
                <p className="text-xs text-slate-400 mt-1 font-semibold">{formatDate(event.detected_at)}</p>
                <button
                  onClick={(e) => { e.stopPropagation(); handleResolve(event.id) }}
                  className="mt-2 text-xs font-bold text-green-600 hover:underline"
                >
                  Mark resolved
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Recommendations panel */}
        {selected && (
          <div className="bg-white border border-amber-200 rounded-2xl p-6 shadow-md animate-slide-up">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
              <div>
                <h2 className="text-lg font-black text-slate-800 flex items-center gap-2">
                  <span>{EVENT_ICONS[selected.event_type] || '⚠️'}</span>
                  {selected.event_type.replace(/_/g, ' ')} — {selected.region}
                </h2>
                <p className="text-xs font-semibold text-slate-500 mt-1">
                  Severity: <span style={{ color: SEVERITY_COLOR[selected.severity] }} className="font-bold">{selected.severity.toUpperCase()}</span>
                  {selected.affected_routes && ` · Affected routes: ${selected.affected_routes}`}
                </p>
              </div>
              <span className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-3 py-1 rounded-full font-bold">
                AI Medicine Recommendations
              </span>
            </div>

            {recLoading ? (
              <div className="flex items-center gap-2 text-slate-500 text-sm font-semibold">
                <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                Generating recommendations…
              </div>
            ) : recommendations ? (
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {recommendations.recommendations.map((rec, i) => (
                  <div key={i} className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                    <p className="font-bold text-slate-800 text-sm">{rec.medicine}</p>
                    <p className="text-xs text-slate-600 mt-1 font-medium leading-relaxed">{rec.rationale}</p>
                    <div className="mt-2 flex items-center gap-1">
                      <span className="text-xs font-black text-amber-700">
                        ×{rec.quantity_multiplier}
                      </span>
                      <span className="text-xs font-semibold text-slate-400">normal stock</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-400 text-sm font-semibold">Click an event to see medicine recommendations.</p>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

/** Rough coordinate lookup by region name keyword — Phase 3: replace with geocoding API */
function guessCoords(region) {
  const r = region.toLowerCase()
  if (r.includes('assam') || r.includes('guwahati')) return [91.7362, 26.1445]
  if (r.includes('mumbai') || r.includes('maharashtra')) return [72.8777, 19.0760]
  if (r.includes('delhi')) return [77.2090, 28.6139]
  if (r.includes('kerala')) return [76.2711, 10.8505]
  if (r.includes('karnataka') || r.includes('bangalore')) return [77.5946, 12.9716]
  if (r.includes('pakistan')) return [69.3451, 30.3753]
  if (r.includes('bangladesh')) return [90.3563, 23.6850]
  if (r.includes('myanmar')) return [95.9560, 16.8661]
  if (r.includes('nigeria')) return [8.6753, 9.0820]
  if (r.includes('ethiopia')) return [40.4897, 9.1450]
  if (r.includes('ukraine')) return [31.1656, 48.3794]
  if (r.includes('haiti')) return [-72.3388, 18.9712]
  if (r.includes('syria')) return [38.9968, 34.8021]
  if (r.includes('sudan')) return [30.2176, 12.8628]
  if (r.includes('indonesia')) return [113.9213, -0.7893]
  // Default: world center offset
  return [Math.random() * 60 - 30, Math.random() * 30 - 10]
}
