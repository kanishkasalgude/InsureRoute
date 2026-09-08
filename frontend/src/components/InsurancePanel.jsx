import { motion } from 'framer-motion'
import { Map, ArrowRight, Navigation, MapPin } from 'lucide-react'

export default function RoutePanel({ insurance, route, disrupted }) {
  if (!route) return null

  const {
    total_distance_km, total_time_hrs, origin, destination, rerouted, hops
  } = route

  const isHighRisk = disrupted

  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      className="glass p-5 flex flex-col h-full bg-white relative overflow-hidden"
    >
      {/* Top Header Block */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Map size={18} className="text-slate-800" />
          <span className="font-bold text-slate-800 text-lg">Path Optimization</span>
        </div>
        {isHighRisk && (
          <span className="text-[10px] font-bold bg-red-100 text-danger border border-red-200 px-2 py-1 rounded">
            REROUTE ACTIVE
          </span>
        )}
      </div>

      {/* Breakdown List */}
      <div className="space-y-4 mb-6 flex-1">
        <DataRow label="Origin Hub" value={origin?.replace('_', ' ')} strong />
        <DataRow label="Destination Hub" value={destination?.replace('_', ' ')} strong />
        
        <div className="py-2 space-y-2">
          <DataRow label="Total Nodes Traversed" value={`${hops} Hubs`} subtext="Includes origin & destination" />
          <DataRow label="Total Calculated Distance" value={`${total_distance_km} km`} />
          <DataRow label="Estimated Transit Time" value={`${total_time_hrs} hrs`} />
        </div>

        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 space-y-2">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Shortest Path Status</div>
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Navigation size={14} className={rerouted ? 'text-danger' : 'text-success'} />
            <span>{rerouted ? 'Dynamic Avoidance Path' : 'Optimal Standard Path'}</span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {rerouted ? 'A disruption was detected on the standard path. The system has automatically shifted to the shortest available alternative route to minimize delay.' : 'The current active route represents the shortest and most efficient path under normal operating conditions.'}
          </p>
        </div>
      </div>

      {/* Quote Comparison (Before / After Reroute) */}
      <div className="flex items-center justify-between bg-slate-100 p-4 rounded-xl border border-slate-200 mb-4">
        <div className="flex flex-col">
          <span className="text-xs text-slate-500 font-semibold mb-1">Base Distance</span>
          <span className={`text-xl font-black ${rerouted ? 'text-danger line-through opacity-70' : 'text-slate-800'}`}>
            {rerouted ? Math.round(total_distance_km * 0.7) : total_distance_km} km
          </span>
        </div>
        <ArrowRight className="text-slate-400" />
        <div className="flex flex-col text-right">
          <span className="text-xs text-slate-500 font-semibold mb-1">Active Distance</span>
          <span className="text-2xl font-black text-slate-900">
            {total_distance_km} km
          </span>
        </div>
      </div>

    </motion.div>
  )
}

function DataRow({ label, value, strong, subtext, highlight }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex flex-col">
        <span className={`${strong ? 'font-semibold text-slate-800' : 'text-slate-500 font-medium'}`}>
          {label}
        </span>
        {subtext && <span className="text-[10px] text-slate-400 mt-0.5">{subtext}</span>}
      </div>
      <span className={`${strong ? 'font-bold text-lg' : 'font-semibold'} ${highlight ? 'text-warning' : 'text-slate-800'}`}>
        {value}
      </span>
    </div>
  )
}
