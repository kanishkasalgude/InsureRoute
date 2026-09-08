import { motion, animate } from 'framer-motion'
import { useEffect, useRef } from 'react'
import { AlertTriangle, Map, Navigation, Cloud } from 'lucide-react'

function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 1, className = '' }) {
  const ref = useRef(null)
  const prev = useRef(0)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    const from = prev.current
    prev.current = value
    const ctrl = animate(from, value, {
      duration: 0.9,
      ease: [0.4, 0, 0.2, 1],
      onUpdate(v) {
        node.textContent = prefix + v.toFixed(decimals) + suffix
      },
    })
    return () => ctrl.stop()
  }, [value, prefix, suffix, decimals])

  return <span ref={ref} className={className}>{prefix}{value.toFixed(decimals)}{suffix}</span>
}

const CARDS = [
  {
    key: 'weather',
    label: 'Weather',
    suffix: '%',
    icon: Cloud,
    accent: 'border-t-blue-500',
    iconColor: 'text-blue-500',
    desc: 'severity',
    threshold: (v) => v > 50 ? 'danger' : v > 20 ? 'warning' : 'success',
  },
  {
    key: 'traffic',
    label: 'Traffic Delay',
    suffix: 'x',
    prefix: '',
    icon: Navigation,
    accent: 'border-t-warning',
    iconColor: 'text-warning',
    desc: 'ratio',
    threshold: (v) => v > 2 ? 'danger' : v > 1.2 ? 'warning' : 'success',
  },
  {
    key: 'distance',
    label: 'Distance',
    suffix: ' km',
    icon: Map,
    accent: 'border-t-success',
    iconColor: 'text-success',
    desc: 'total route length',
    threshold: () => 'success',
  },
  {
    key: 'risk',
    label: 'Current Risk',
    suffix: '%',
    icon: AlertTriangle,
    accent: 'border-t-danger',
    iconColor: 'text-danger',
    desc: 'disruption probability',
    threshold: (v) => v > 60 ? 'danger' : v > 30 ? 'warning' : 'success',
  },
]

const LEVEL_STYLES = {
  danger:  'text-danger',
  warning: 'text-warning',
  success: 'text-text', // Keep normal text for success looking metrics instead of neon green
}

export default function KPICards({ kpis }) {
  if (!kpis) return null

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map((card, i) => {
        const value = kpis[card.key] ?? 0
        const level = card.threshold(value)
        const Icon  = card.icon
        
        return (
          <motion.div
            key={card.key}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.4 }}
            className={`glass p-5 flex flex-col gap-2 rounded-xl border-t-2 ${card.accent}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Icon size={16} className={card.iconColor} />
              <span className="text-sm font-semibold text-slate-600">
                {card.label}
              </span>
            </div>
            
            <div className={`text-4xl font-black tracking-tight ${LEVEL_STYLES[level]}`}>
              <AnimatedNumber
                value={value}
                prefix={card.prefix || ''}
                suffix={card.suffix}
                decimals={1}
              />
            </div>
            
            <span className="text-xs font-medium text-muted mt-1">{card.desc}</span>
          </motion.div>
        )
      })}
    </div>
  )
}
