import axios from 'axios'

const BASE = 'http://localhost:8000'

// ── API client ──────────────────────────────────────────────────────────────
const client = axios.create({ baseURL: BASE, timeout: 5000 })

// ── Mock data factory (used when API is unavailable) ────────────────────────
export function makeMockData(injected = false, params = {}) {
  const risk    = injected ? 72 + Math.random() * 20 : 25 + Math.random() * 40
  const prob    = risk / 100
  const cargo   = 70000
  const before  = Math.round(cargo * prob * 0.08 * (injected ? 1.4 : 1.1) * 1.6)
  const after   = Math.round(before * 0.35)
  const savings = Math.round(before - after)
  const savPct  = Math.round((savings / before) * 100)

  const origin = params.origin || 'Pune_Hub'
  const destination = params.destination || 'Mumbai_Hub'
  
  // BFS to find a valid path
  const adj = {}
  EDGE_PAIRS.forEach(([u, v]) => {
    if (!adj[u]) adj[u] = []
    if (!adj[v]) adj[v] = []
    adj[u].push(v)
    adj[v].push(u)
  })
  
  // Dijkstra's algorithm to find the shortest path based on geographical distance
  function getDistance(u, v) {
    const n1 = MOCK_NODES.find(n => n.id === u)
    const n2 = MOCK_NODES.find(n => n.id === v)
    if (!n1 || !n2) return 1
    return Math.hypot(n1.lon - n2.lon, n1.lat - n2.lat)
  }

  function findPath(start, end) {
    const dist = {}
    const prev = {}
    const unvisited = new Set(Object.keys(adj))
    
    // Ensure start and end are in the set
    unvisited.add(start)
    unvisited.add(end)

    for (const node of unvisited) {
      dist[node] = Infinity
      prev[node] = null
    }
    dist[start] = 0

    while (unvisited.size > 0) {
      let u = null
      let minDist = Infinity
      for (const node of unvisited) {
        if (dist[node] < minDist) {
          minDist = dist[node]
          u = node
        }
      }
      
      if (u === null || u === end) break
      unvisited.delete(u)

      for (const v of (adj[u] || [])) {
        if (!unvisited.has(v)) continue
        const alt = dist[u] + getDistance(u, v)
        if (alt < dist[v]) {
          dist[v] = alt
          prev[v] = u
        }
      }
    }

    const path = []
    let curr = end
    while (curr) {
      path.unshift(curr)
      curr = prev[curr]
    }
    if (path[0] === start) return path
    return [start, end]
  }

  const PATH_NORMAL = findPath(origin, destination)
  // Just make rerouted path somewhat different by inserting a random hub if possible
  const PATH_REROUTED = PATH_NORMAL.length >= 2 
    ? [PATH_NORMAL[0], 'Navi_Mumbai_DC', ...PATH_NORMAL.slice(1)] 
    : PATH_NORMAL

  const path = injected ? PATH_REROUTED : PATH_NORMAL

  return {
    kpis: {
      sla:                +(8 + Math.random() * 5).toFixed(1),
      delay:              +(7 + Math.random() * 6).toFixed(1),
      risk:               +risk.toFixed(1),
      savings:            savPct,
      total_disruptions:  2342,
      total_shipments:    30000,
    },
    insurance: {
      cargo_value:            cargo,
      disruption_probability: +prob.toFixed(4),
      base_premium:           Math.round(cargo * prob * 0.08),
      before_cost:            before,
      after_cost:             after,
      savings:                savings,
      savings_pct:            savPct,
      weather_multiplier:     1.4,
      perishable_multiplier:  1.6,
    },
    route: {
      path,
      disruption_detected: injected,
      origin:      origin,
      destination: destination,
      total_time_hrs:   injected ? 9.2 : 4.1,
      total_distance_km: injected ? 487 : 149,
      total_cost_inr:    injected ? 12400 : 5800,
      hops:              path.length - 1,
      rerouted:          injected,
    },
    anomaly_score: injected ? -(0.2 + Math.random() * 0.3) : -(0.05 + Math.random() * 0.1),
    flags:  { monsoon: true, perishable: true, injected },
    raw:    { delay_ratio: injected ? 2.8 + Math.random() : 1.05 + Math.random() * 0.1,
              weather_severity: injected ? 0.8 : 0.2 },
    nodes: MOCK_NODES,
    edges: MOCK_EDGES,
  }
}

const EDGE_PAIRS = [
  ['Pune_Hub','Mumbai_Hub'],['Pune_Hub','Nashik_Hub'],['Nashik_Hub','Mumbai_Hub'],
  ['Nashik_Hub','Surat_Hub'],['Surat_Hub','Navi_Mumbai_DC'],['Navi_Mumbai_DC','Mumbai_Hub'],
  ['Mumbai_Hub','Ahmedabad_Hub'],['Delhi_Hub','Jaipur_Hub'],['Jaipur_Hub','Ahmedabad_Hub'],
  ['Delhi_Hub','Lucknow_Hub'],['Lucknow_Hub','Patna_Hub'],['Kolkata_Hub','Patna_Hub'],
  ['Chennai_Hub','Bangalore_Hub'],['Bangalore_Hub','Hyderabad_Hub'],
  ['Hyderabad_Hub','Visakhapatnam_Hub'],['Coimbatore_Hub','Chennai_Hub'],
  ['Kochi_Hub','Coimbatore_Hub'],['Nagpur_Hub','Hyderabad_Hub'],
  ['Nagpur_Hub','Bhopal_Hub'],['Bhopal_Hub','Indore_Hub'],
  ['Indore_Hub','Ahmedabad_Hub'],['Mumbai_Hub','Pune_Hub'],
]

// ── Network nodes (Indian supply chain hubs, lon/lat) ─────────────────────
export const MOCK_NODES = [
  { id: 'Delhi_Hub',          label: 'Delhi Hub',         lon: 77.1, lat: 28.7 },
  { id: 'Mumbai_Hub',         label: 'Mumbai Hub',        lon: 72.8, lat: 19.1 },
  { id: 'Bangalore_Hub',      label: 'Bangalore Hub',     lon: 77.6, lat: 12.9 },
  { id: 'Chennai_Hub',        label: 'Chennai Hub',       lon: 80.3, lat: 13.1 },
  { id: 'Kolkata_Hub',        label: 'Kolkata Hub',       lon: 88.4, lat: 22.6 },
  { id: 'Hyderabad_Hub',      label: 'Hyderabad Hub',     lon: 78.5, lat: 17.4 },
  { id: 'Pune_Hub',           label: 'Pune Hub',          lon: 73.9, lat: 18.5 },
  { id: 'Ahmedabad_Hub',      label: 'Ahmedabad Hub',     lon: 72.6, lat: 23.0 },
  { id: 'Jaipur_Hub',         label: 'Jaipur Hub',        lon: 75.8, lat: 26.9 },
  { id: 'Lucknow_Hub',        label: 'Lucknow Hub',       lon: 80.9, lat: 26.8 },
  { id: 'Surat_Hub',          label: 'Surat Hub',         lon: 72.8, lat: 21.2 },
  { id: 'Nashik_Hub',         label: 'Nashik Hub',        lon: 73.8, lat: 20.0 },
  { id: 'Nagpur_Hub',         label: 'Nagpur Hub',        lon: 79.1, lat: 21.1 },
  { id: 'Navi_Mumbai_DC',     label: 'Navi Mumbai',       lon: 73.0, lat: 19.0 },
  { id: 'Indore_Hub',         label: 'Indore Hub',        lon: 75.9, lat: 22.7 },
  { id: 'Bhopal_Hub',         label: 'Bhopal Hub',        lon: 77.4, lat: 23.3 },
  { id: 'Coimbatore_Hub',     label: 'Coimbatore Hub',    lon: 77.0, lat: 11.0 },
  { id: 'Visakhapatnam_Hub',  label: 'Vizag Hub',         lon: 83.3, lat: 17.7 },
  { id: 'Patna_Hub',          label: 'Patna Hub',         lon: 85.1, lat: 25.6 },
  { id: 'Kochi_Hub',          label: 'Kochi Hub',         lon: 76.3, lat: 10.0 },
]

export const MOCK_EDGES = EDGE_PAIRS.map(([s, t]) => ({ source: s, target: t }))

// ── API calls ────────────────────────────────────────────────────────────────
export async function fetchData(params = {}) {
  try {
    const res = await client.get('/data', { params })
    return { data: res.data, mock: false }
  } catch {
    return { data: makeMockData(false, params), mock: true }
  }
}

export async function injectDisruption(params = {}) {
  try {
    const res = await client.post('/inject-disruption', {
      origin:      params.origin      || 'Pune_Hub',
      destination: params.destination || 'Mumbai_Hub',
      cargo_value: params.cargoValue  || 70000,
      monsoon:     params.monsoon     ?? true,
      perishable:  params.perishable  ?? true,
      anomaly_threshold: params.threshold ?? -0.15,
    })
    return { data: res.data, mock: false }
  } catch {
    return { data: makeMockData(true, params), mock: true }
  }
}
