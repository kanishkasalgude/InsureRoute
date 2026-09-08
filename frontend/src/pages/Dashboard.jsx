import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Navbar        from '../components/Navbar'
import KPICards      from '../components/KPICards'
import GraphView     from '../components/GraphView'
import InsurancePanel from '../components/InsurancePanel'
import LogsPanel     from '../components/LogsPanel'
import { fetchData, injectDisruption, MOCK_NODES, MOCK_EDGES } from '../services/api'
import { AreaChart, Area, Tooltip, ResponsiveContainer, XAxis, YAxis } from 'recharts'

// ── Log helpers ──────────────────────────────────────────────────────────────
let logId = 0
function makeLog(type, message, value) {
  return {
    id: ++logId,
    type,
    message,
    value,
    time: new Date().toLocaleTimeString(),
  }
}

const INITIAL_LOGS = [
  makeLog('info',   'InsureRoute system initialised', null),
  makeLog('model',  'Isolation Forest loaded (n=200, contamination=0.08)', null),
  makeLog('info',   'Graph engine ready — 50 nodes, Dijkstra active', null),
  makeLog('info',   'Streaming live data from simulation pipeline', null),
]

// ── Risk trend history ───────────────────────────────────────────────────────
const MAX_TREND = 30

// ── Dashboard ───────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [isMock,    setIsMock]    = useState(false)
  const [logs,      setLogs]      = useState(INITIAL_LOGS)
  const [trend,     setTrend]     = useState([])
  const [disrupted, setDisrupted] = useState(false)

  const [params, setParams] = useState({
    origin:      'Pune_Hub',
    destination: 'Mumbai_Hub',
    cargoValue:  70000,
    monsoon:     true,
    weatherType: 'Monsoon Status',
    perishable:  true,
    cargoType:   'Perishable Goods',
    threshold:   -0.15,
    weatherMult: 1.4,
    perishMult:  1.6,
  })

  const addLog = useCallback((type, msg, val) => {
    setLogs(prev => [...prev.slice(-49), makeLog(type, msg, val)])
  }, [])

  // ── Fetch tick ─────────────────────────────────────────────────────────────
  const fetchTick = useCallback(async (forceInject = false) => {
    setLoading(true)
    try {
      const { data: d, mock } = forceInject
        ? await injectDisruption(params)
        : await fetchData(params)

      setData(d)
      setIsMock(mock)

      const isDisrupted = d.route?.disruption_detected ?? false
      setDisrupted(isDisrupted)

      // Trend
      setTrend(prev => [
        ...prev.slice(-(MAX_TREND - 1)),
        { t: new Date().toLocaleTimeString(), risk: Math.round((d.kpis?.risk ?? 0) * 10) / 10 },
      ])

      // Logs
      if (forceInject) {
        addLog('disruption', `Disruption injected at ${params.origin.replace('_', ' ')}`, `Score: ${d.anomaly_score?.toFixed(3)}`)
        addLog('reroute',    `Alternate route via ${(d.route?.path ?? [])[1]?.replace('_', ' ') ?? 'hub'}`, null)
        addLog('savings',    'Hedge cost recalculated after reroute', `₹${(d.insurance?.savings ?? 0).toLocaleString('en-IN')} saved`)
      } else if (isDisrupted) {
        addLog('disruption', 'Anomaly detected in transit data', `P=${(d.insurance?.disruption_probability * 100).toFixed(1)}%`)
      } else {
        const tips = [
          `Shipment ${params.origin.replace('_', ' ')} → ${params.destination.replace('_', ' ')} on track`,
          `Delay ratio: ${d.raw?.delay_ratio?.toFixed(2) ?? '—'}`,
          `Weather severity: ${((d.raw?.weather_severity ?? 0) * 100).toFixed(0)}%`,
          `Pricing engine updated — hedge ₹${(d.insurance?.before_cost ?? 0).toLocaleString('en-IN')}`,
        ]
        addLog('info', tips[logId % tips.length], null)
      }
    } catch (e) {
      addLog('info', 'Pipeline tick error — retrying', null)
    } finally {
      setLoading(false)
    }
  }, [params, addLog])

  // ── Initial fetch + 3s auto-refresh ───────────────────────────────────────
  useEffect(() => { fetchTick() }, [])
  useEffect(() => { fetchTick() }, [params.origin, params.destination])
  useEffect(() => {
    const t = setInterval(() => fetchTick(), 3000)
    return () => clearInterval(t)
  }, [fetchTick])

  const ins = data?.insurance
  const kpis = {
    weather: (data?.raw?.weather_severity ?? 0) * 100,
    traffic: data?.raw?.delay_ratio ?? 1,
    distance: data?.route?.total_distance_km ?? 0,
    risk: data?.kpis?.risk ?? 0
  }
  const route = data?.route
  const nodes = data?.nodes ?? MOCK_NODES
  const edges = data?.edges ?? MOCK_EDGES

  return (
    <div className="min-h-screen bg-bg flex flex-col relative z-10 text-text font-sans">
      <Navbar 
        isLive={true} 
        disrupted={disrupted} 
        isMock={isMock}
        params={params}
        onParamsChange={setParams}
        onInject={() => fetchTick(true)}
        onRefresh={() => fetchTick(false)}
        loading={loading}
      />

      <main className="flex-1 px-4 md:px-6 py-3 space-y-3 max-w-[1600px] mx-auto w-full">

        {/* ── Disruption alert ── */}
        <AnimatePresence>
          {disrupted && (
            <motion.div
              initial={{ opacity: 0, y: -10, height: 0 }}
              animate={{ opacity: 1, y: 0, height: 'auto' }}
              exit={{ opacity: 0, y: -10, height: 0 }}
              className="border-pulse-red border bg-red-50 rounded-xl
                         px-5 py-3 flex items-center gap-3 shadow-sm"
            >
              <div className="w-2 h-2 rounded-full bg-danger animate-ping flex-shrink-0" />
              <div>
                <span className="text-danger font-bold text-sm">DISRUPTION DETECTED</span>
                <span className="text-danger/80 text-sm ml-2 font-medium">
                  {params.origin.replace(/_/g,' ')} → {params.destination.replace(/_/g,' ')} ·
                  Risk {((ins?.disruption_probability ?? 0) * 100).toFixed(1)}% ·
                  Hedge ₹{(ins?.before_cost ?? 0).toLocaleString('en-IN')} → ₹{(ins?.after_cost ?? 0).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="ml-auto text-xs font-semibold text-danger/70 bg-red-100 px-2 py-1 rounded">Reroute applied</div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── KPI row ── */}
        <KPICards kpis={kpis} />

        {/* ── Main grid: Graph + Insurance ── */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5 items-stretch h-[480px] max-h-[480px] overflow-hidden">
          <div className="flex flex-col rounded-xl overflow-hidden h-full min-h-0">
            <GraphView nodes={nodes} edges={edges} route={route} params={params} setParams={setParams} />
          </div>
          <div className="flex flex-col h-full min-h-0">
            <InsurancePanel route={route} disrupted={disrupted} />
          </div>
        </div>

        {/* ── Bottom row: Trend + Logs ── */}
        <div className="flex flex-col gap-5">
          {/* Trend Chart */}
          <div className="glass px-5 py-4 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-text">Risk Trend (Last {MAX_TREND} Ticks)</span>
              <span className={`text-sm font-bold ${(trend.at(-1)?.risk ?? 0) > 60 ? 'text-danger' : 'text-success'}`}>
                {trend.at(-1)?.risk ?? 0}% Current
              </span>
            </div>
            {trend.length > 2 ? (
              <div className="w-full h-[180px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ top: 5, right: 0, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor={disrupted ? '#dc2626' : '#2563eb'} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={disrupted ? '#dc2626' : '#2563eb'} stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="t" hide />
                    <YAxis hide domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 12, boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}
                      labelStyle={{ color: '#64748b' }}
                      formatter={v => [`${v}%`, 'Risk']}
                    />
                    <Area
                      type="monotone" dataKey="risk"
                      stroke={disrupted ? '#dc2626' : '#2563eb'}
                      strokeWidth={2}
                      fill="url(#riskGrad)"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-sm text-muted">Awaiting data...</div>
            )}
          </div>

          <LogsPanel logs={logs} />
        </div>

        {/* ── Footer ── */}
        <div className="text-center text-[11px] text-muted py-2 border-t border-border">
          InsureRoute SaaS Dashboard · Smart Supply Chain Disruption Detection
          {isMock && <span className="ml-2 text-warning font-semibold">· Mock Mode Active</span>}
        </div>
      </main>
    </div>
  )
}
