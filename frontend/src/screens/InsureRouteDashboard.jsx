import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { getLiveDisruptions, getWeatherStatus, getRouteNews, getNodes, chatWithAgent } from '../api';
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Marker,
  Popup,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Truck,
  Train,
  Plane,
  Send,
  Bot,
  CheckCircle,
  Zap,
  Clock,
  IndianRupee,
  MapPin,
  Navigation,
  Shield,
  X,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Download,
  CloudLightning, Activity, Briefcase, FileText, CloudRain, Cloud, Newspaper
} from 'lucide-react';
import KPICards from '../components/KPICards';
import RouteIntelDrawer from '../components/RouteIntelDrawer';

const BASE_ROUTES = [
  {
    id: 1,
    mode: 'road',
    label: 'Road only',
    subLabel: 'via NH48',
    eta: '2h 31m',
    baseCost: 3360,
    best: true,
    waypoints: [
      [18.9388, 72.8354],
      [18.7837, 73.1277],
      [18.754, 73.4062],
      [18.7333, 73.678],
      [18.5204, 73.8567],
    ],
    stops: ['Mumbai', 'Khopoli', 'Lonavla', 'Talegaon', 'Pune'],
    color: '#2563eb',
    dashArray: null,
  },
  {
    id: 2,
    mode: 'rail',
    label: 'Rail + Road',
    subLabel: 'via CST → Pune Stn',
    eta: '6h 7m',
    baseCost: 6951,
    best: false,
    waypoints: [
      [18.9398, 72.8354],
      [19.0183, 72.8478],
      [18.9108, 73.3211],
      [18.5285, 73.8741],
      [18.5204, 73.8567],
    ],
    stops: ['Mumbai CST', 'Dadar', 'Karjat', 'Pune Station', 'Pune'],
    color: '#f97316',
    dashArray: '8 4',
  },
  {
    id: 3,
    mode: 'air',
    label: 'Air + Road',
    subLabel: 'via CSIA → PNQ',
    eta: '5h 45m',
    baseCost: 42800,
    best: false,
    waypoints: [
      [19.0549, 72.8323],
      [19.0896, 72.8656],
      [18.5822, 73.9197],
      [18.5204, 73.8567],
    ],
    stops: ['Mumbai Pickup', 'CSIA Airport', 'Pune Airport', 'Pune'],
    color: '#16a34a',
    dashArray: '4 4',
  },
];

const MUMBAI = [18.9388, 72.8354];
const PUNE = [18.5204, 73.8567];

//  Leaflet Icon Fix 
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

//  Custom Pin Icons 
const makePin = (color, label) =>
  L.divIcon({
    className: '',
    iconAnchor: [16, 40],
    popupAnchor: [0, -40],
    html: `
      <div style="display:flex;flex-direction:column;align-items:center;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.35))">
        <div style="background:${color};color:#fff;font-size:11px;font-weight:700;
          padding:4px 8px;border-radius:6px;white-space:nowrap;font-family:system-ui">
          ${label}
        </div>
        <div style="width:0;height:0;border-left:8px solid transparent;
          border-right:8px solid transparent;border-top:10px solid ${color};margin-top:-1px"></div>
      </div>`,
  });

// Dynamic icons will be created in MapLayer to support dynamic naming

//  Gemini API Call 
async function callGeminiViaBackend(message, shipmentId) {
  const payload = await chatWithAgent({
    shipment_id: shipmentId,
    message,
  });
  return payload?.response || 'Unable to reach InsureRoute AI. Please try again.';
}

const INIT_PROMPT =
  'The user is shipping cargo from Mumbai to Pune. We have 3 route options: (1) Road only via NH48: ETA 2h 31m, Cost ₹3,360, low traffic delay risk; (2) Rail + Road: ETA 6h 7m, Cost ₹6,951, rail schedule dependency risk; (3) Air + Road: ETA 5h 45m, Cost ₹42,800, weather-dependent risk. Greet the user as InsureRoute AI, recommend the best route with a brief reason, and ask if they have any constraints such as cargo type, budget, or urgency.';

//  Mode Icon 
function ModeIcon({ mode, size = 16, className = '' }) {
  const cls = `${className}`;
  if (mode === 'road')
    return <Truck size={size} className={`text-blue-600 ${cls}`} />;
  if (mode === 'rail')
    return (
      <span className={`inline-flex items-center gap-1 ${cls}`}>
        <Train size={size} className="text-orange-500" />
        <Truck size={size} className="text-orange-500" />
      </span>
    );
  return (
    <span className={`inline-flex items-center gap-1 ${cls}`}>
      <Truck size={size} className="text-green-600" />
      <Plane size={size} className="text-green-600" />
    </span>
  );
}

//  Typing Indicator 
function TypingDots() {
  return (
    <div className="flex items-end gap-1 px-4 py-3 bg-white rounded-2xl rounded-tl-sm shadow-sm w-fit">
      {[0, 0.15, 0.3].map((d, i) => (
        <span
          key={i}
          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: `${d}s` }}
        />
      ))}
    </div>
  );
}

//  Markdown Renderer 
/**
 * Lightweight parser: handles **bold**, `code`, # headers, * / - / 1. lists,
 * blank-line paragraphs, and horizontal rules. No external deps.
 */
function renderMarkdown(text, isUser) {
  const textColor = isUser ? 'text-blue-50' : 'text-slate-800';
  const boldColor  = isUser ? 'text-white'   : 'text-slate-900';
  const mutedColor = isUser ? 'text-blue-200' : 'text-slate-500';
  const codeBase   = isUser
    ? 'bg-blue-800/60 text-blue-100'
    : 'bg-slate-100 text-slate-700';
  const bulletDot  = isUser ? 'bg-blue-300' : 'bg-blue-500';

  //  inline: **bold** and `code` 
  const renderInline = (str) => {
    const parts = [];
    const re = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
    let last = 0, m;
    while ((m = re.exec(str)) !== null) {
      if (m.index > last) parts.push(str.slice(last, m.index));
      if (m[2] !== undefined)
        parts.push(<strong key={m.index} className={`font-bold ${boldColor}`}>{m[2]}</strong>);
      else
        parts.push(<code key={m.index} className={`text-xs font-mono rounded px-1 py-0.5 ${codeBase}`}>{m[3]}</code>);
      last = re.lastIndex;
    }
    if (last < str.length) parts.push(str.slice(last));
    return parts;
  };

  //  split into logical blocks 
  const lines = text.split('\n');
  const blocks = [];
  let listBuffer = [];   // { ordered, items }
  let listType   = null; // 'ul' | 'ol'

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push({ type: listType, items: [...listBuffer] });
    listBuffer = [];
    listType   = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    // Blank line
    if (!line.trim()) { flushList(); blocks.push({ type: 'br' }); continue; }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
      flushList();
      blocks.push({ type: 'hr' });
      continue;
    }

    // Heading  # / ## / ###
    const hMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (hMatch) {
      flushList();
      blocks.push({ type: 'h', level: hMatch[1].length, content: hMatch[2] });
      continue;
    }

    // Unordered bullet  * / - / •
    const ulMatch = line.match(/^[\*\-•]\s+(.*)/);
    if (ulMatch) {
      if (listType === 'ol') flushList();
      listType = 'ul';
      listBuffer.push(ulMatch[1]);
      continue;
    }

    // Ordered list  1. / 2. …
    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (listType === 'ul') flushList();
      listType = 'ol';
      listBuffer.push(olMatch[1]);
      continue;
    }

    // Plain paragraph
    flushList();
    blocks.push({ type: 'p', content: line });
  }
  flushList();

  //  render blocks 
  const rendered = [];
  let prevBr = false;

  blocks.forEach((b, i) => {
    if (b.type === 'br') { prevBr = true; return; }

    const gap = prevBr ? 'mt-2.5' : i > 0 ? 'mt-1' : '';
    prevBr = false;

    if (b.type === 'hr') {
      rendered.push(
        <hr key={i} className={`border-t ${isUser ? 'border-blue-400/40' : 'border-slate-200'} ${gap}`} />
      );
    } else if (b.type === 'h') {
      const sizes = { 1: 'text-sm font-bold', 2: 'text-sm font-bold', 3: 'text-xs font-bold uppercase tracking-wide' };
      rendered.push(
        <p key={i} className={`${sizes[b.level]} ${boldColor} ${gap}`}>
          {renderInline(b.content)}
        </p>
      );
    } else if (b.type === 'ul') {
      rendered.push(
        <ul key={i} className={`space-y-1.5 ${gap}`}>
          {b.items.map((item, j) => (
            <li key={j} className={`flex items-start gap-2 text-xs leading-relaxed ${textColor}`}>
              <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${bulletDot}`} />
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      );
    } else if (b.type === 'ol') {
      rendered.push(
        <ol key={i} className={`space-y-1.5 ${gap}`}>
          {b.items.map((item, j) => (
            <li key={j} className={`flex items-start gap-2 text-xs leading-relaxed ${textColor}`}>
              <span className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                isUser ? 'bg-blue-400/50 text-white' : 'bg-blue-100 text-blue-700'
              }`}>{j + 1}</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      );
    } else {
      // paragraph — skip if it's purely whitespace
      if (!b.content.trim()) return;
      rendered.push(
        <p key={i} className={`text-xs leading-relaxed ${textColor} ${gap}`}>
          {renderInline(b.content)}
        </p>
      );
    }
  });

  return rendered;
}

//  Chat Bubble 
function ChatBubble({ role, text }) {
  const isUser = role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[88%] px-4 py-3 rounded-2xl shadow-sm ${
          isUser
            ? 'bg-blue-600 rounded-tr-sm'
            : 'bg-white rounded-tl-sm border border-slate-100'
        }`}
      >
        {renderMarkdown(text, isUser)}
      </div>
    </div>
  );
}


//  Route Card 
function RouteCard({ route, selected, onSelect, onKnowMore }) {
  const modeColor = {
    road: 'border-blue-500',
    rail: 'border-orange-400',
    air: 'border-green-500',
  }[route.mode];

  const modeBg = {
    road: 'bg-blue-50',
    rail: 'bg-orange-50',
    air: 'bg-green-50',
  }[route.mode];

  const dotColor = {
    road: 'bg-blue-500',
    rail: 'bg-orange-400',
    air: 'bg-green-500',
  }[route.mode];

  return (
    <div
      onClick={() => onSelect(route)}
      className={`relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-200 hover:shadow-md ${
        selected
          ? `${modeColor} ${modeBg} shadow-md`
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${dotColor} flex-shrink-0`}
            style={
              route.dashArray
                ? { outline: `2px dashed ${route.color}`, outlineOffset: '2px', background: 'transparent' }
                : {}
            }
          />
          <div>
            <div className="font-bold text-slate-900 text-sm">{route.label}</div>
            <div className="text-xs text-slate-500">{route.subLabel}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {route.best && (
            <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 text-xs font-bold px-2 py-0.5 rounded-full">
              <CheckCircle size={10} /> Best
            </span>
          )}
          {selected && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded-full">
              Selected
            </span>
          )}
        </div>
      </div>

      {/* Icon row */}
      <div className="flex justify-center mb-3">
        <ModeIcon mode={route.mode} size={22} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div>
          <div className="text-xs text-slate-500 flex items-center gap-1">
            <Clock size={10} /> ETA
          </div>
          <div className="font-bold text-slate-900 text-base">{route.eta}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500 flex items-center gap-1">
            <IndianRupee size={10} /> Cost
          </div>
          <div className="font-bold text-slate-900 text-base">{route.cost}</div>
        </div>
      </div>

      {/* Market Trend Badge */}
      {route.market_trend && (
        <div className={`mb-3 p-2 rounded-lg border flex items-center justify-between ${
          route.market_trend.delta_pct > 0 
            ? 'bg-red-50 border-red-100 text-red-700' 
            : 'bg-emerald-50 border-emerald-100 text-emerald-700'
        }`}>
          <div className="flex items-center gap-2">
            {route.market_trend.delta_pct > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase leading-none">{route.market_trend.label}</span>
              <span className="text-[9px] opacity-70 leading-tight">{route.market_trend.driver}</span>
            </div>
          </div>
          <span className="font-mono font-bold text-xs">
            {route.market_trend.delta_pct > 0 ? '+' : ''}{route.market_trend.delta_pct}%
          </span>
        </div>
      )}

      {/* Select button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSelect(route);
        }}
        className={`w-full py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
          selected
            ? 'bg-blue-600 text-white shadow-sm'
            : 'bg-slate-100 text-slate-700 hover:bg-blue-50 hover:text-blue-700'
        }`}
      >
        {selected ? ' Route Selected' : 'Select Route'}
      </button>

      {/* Know More → Insurance */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onKnowMore(route);
        }}
        className="w-full py-2 mt-2 rounded-lg text-sm font-medium border border-blue-500 text-blue-600 hover:bg-blue-50 transition-all duration-200 flex items-center justify-center gap-1.5"
      >
        <Shield size={13} /> Know More
      </button>
    </div>
  );
}

//  Weather Icon Helper 
function getWeatherIcon(id) {
  if (id >= 200 && id < 300) return <CloudLightning size={14} className="text-amber-500" />;
  if (id >= 300 && id < 600) return <CloudRain size={14} className="text-blue-500" />;
  if (id >= 600 && id < 700) return <Activity size={14} className="text-slate-300" />; // Snow placeholder
  if (id === 800) return <Zap size={14} className="text-amber-400" />; // Clear
  return <Cloud size={14} className="text-slate-400" />;
}

//  Map Route Layer 
function MapLayer({ selectedRouteId, weatherData, routes, originNode, destinationNode }) {
  const originIcon = makePin('#1e40af', originNode?.name || 'Origin');
  const destIcon = makePin('#b91c1c', destinationNode?.name || 'Destination');
  
  return (
    <>
      {routes.map((route) => {
        const isSelected = route.id === selectedRouteId;
        return (
          <React.Fragment key={route.id}>
            <Polyline
              positions={route.waypoints}
              pathOptions={{
                color: route.color,
                weight: isSelected ? 5 : 2.5,
                opacity: isSelected ? 1 : 0.3,
                dashArray: route.dashArray,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Intermediate stops */}
            {route.waypoints.slice(1, -1).map((pos, i) => (
              <CircleMarker
                key={i}
                center={pos}
                radius={isSelected ? 5 : 3}
                pathOptions={{
                  color: route.color,
                  fillColor: '#ffffff',
                  fillOpacity: isSelected ? 1 : 0.4,
                  weight: isSelected ? 2 : 1,
                  opacity: isSelected ? 1 : 0.3,
                }}
              >
                <Popup>
                  <span className="text-xs font-medium">{route.stops[i + 1]}</span>
                </Popup>
              </CircleMarker>
            ))}
          </React.Fragment>
        );
      })}

      {/* Live Weather Checkpoints mapped to selected route */}
      {routes.find(r => r.id === selectedRouteId)?.waypoints.slice(1, -1).map((pos, idx) => {
        const cp = weatherData?.checkpoints?.[idx % (weatherData?.checkpoints?.length || 1)] || {
          is_dangerous: false, temperature: 25, humidity: 50, rain_1h: 0, description: 'Clear sky'
        };
        const stopName = routes.find(r => r.id === selectedRouteId)?.stops[idx + 1] || 'Checkpoint';
        
        return (
        <Marker 
          key={`weather-${idx}`} 
          position={pos} 
          icon={L.divIcon({
            className: 'custom-div-icon',
            html: `<div class="p-1 bg-white rounded-full shadow-md border border-slate-200 flex items-center justify-center ${cp.is_dangerous ? 'animate-pulse border-red-400' : ''}">
              <div class="w-6 h-6 flex items-center justify-center text-sm">
                ${cp.is_dangerous ? '⚠️' : '🌤️'}
              </div>
            </div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          })}
        >
          <Popup>
            <div className="text-xs p-1">
              <div className="font-bold border-b pb-1 mb-1">{stopName}</div>
              <div className="flex flex-col gap-0.5 text-[10px] text-slate-600">
                <div className="flex justify-between"><span>Temp</span><b>{cp.temperature}°C</b></div>
                <div className="flex justify-between"><span>Humid</span><b>{cp.humidity}%</b></div>
                {cp.rain_1h > 0 && <div className="flex justify-between text-blue-600"><span>Rain</span><b>{cp.rain_1h}mm/h</b></div>}
                <div className="mt-1 pt-1 border-t italic">{cp.description}</div>
              </div>
            </div>
          </Popup>
        </Marker>
      )})}

      {/* Origin & destination pins */}
      {originNode && (
        <Marker position={[originNode.lat, originNode.lon]} icon={originIcon}>
          <Popup>
            <div className="text-sm font-bold text-blue-800">{originNode.name}</div>
            <div className="text-xs text-slate-500">Origin</div>
          </Popup>
        </Marker>
      )}
      {destinationNode && (
        <Marker position={[destinationNode.lat, destinationNode.lon]} icon={destIcon}>
          <Popup>
            <div className="text-sm font-bold text-red-800">{destinationNode.name}</div>
            <div className="text-xs text-slate-500">Destination</div>
          </Popup>
        </Marker>
      )}
    </>
  );
}

//  Main Dashboard 
export default function InsureRouteDashboard() {
  const [selectedRouteId, setSelectedRouteId] = useState(1);
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const chatEndRef = useRef(null);

  //  Insurance drawer state 
  const [insuranceRoute, setInsuranceRoute] = useState(null);
  const [coverageTier, setCoverageTier] = useState('comprehensive');
  const [insights, setInsights] = useState(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [routes, setRoutes] = useState([]);

  //  Hackathon Demo State 
  const [scenarioActive, setScenarioActive] = useState(false);
  const [isRouteIntelOpen, setIsRouteIntelOpen] = useState(false);
  const [isHollywoodDelay, setIsHollywoodDelay] = useState(false);
  const [delayText, setDelayText] = useState('');
  const [mitigationModal, setMitigationModal] = useState(null);
  const [mitigationComplete, setMitigationComplete] = useState(false);

  // Baseline global metrics so the dashboard looks alive before the demo
  // These will now dynamically increment based on the actual cargo values
  const [globalBaseline, setGlobalBaseline] = useState({
    co2: 12450,
    savings: 310500,
    shocks: 12
  });

  const location = useLocation();
  const setupData = location.state; // contains { options: [...] }

  useEffect(() => {
    // Generate dynamic baseline metrics based on the current cargo value
    if (setupData?.cargo_value_inr) {
      const cargo = setupData.cargo_value_inr;
      setGlobalBaseline({
        co2: Math.round(cargo * 0.00012), 
        savings: Math.round(cargo * 0.0035), 
        shocks: Math.floor(Math.random() * 5) + 8 
      });
    }
  }, [setupData]);

  const triggerHollywoodDelay = () => {
    setScenarioActive(true);
    setIsHollywoodDelay(true);
    setDelayText('️ ISOLATION FOREST ANOMALY DETECTED: SEVERITY 0.89');
    
    // Dynamic Actuarial Calculation based on actual cargo value
    const cargoValue = setupData?.cargo_value_inr || 500000;
    const basePrem = Math.round(cargoValue * 0.003); // 0.3% standard rate
    
    const surgeRisk = 0.89; // 89% risk on compromised route
    const surgeMultiplier = 1 + (surgeRisk * 1.2); 
    const surgePremium = Math.round(basePrem * surgeMultiplier);
    
    const optimizedRisk = 0.05; // 5% risk on safe route
    const optimizedMultiplier = 1 + (optimizedRisk * 1.2);
    const optimizedPremium = Math.round(basePrem * optimizedMultiplier);
    
    const actualSavings = surgePremium - optimizedPremium;
    
    setTimeout(() => setDelayText(' RECALCULATING GRAPH TOPOLOGY (DIJKSTRA BYPASS)...'), 400);
    setTimeout(() => setDelayText(' RE-PRICING ACTUARIAL HEDGE BASED ON NEW RISK VECTOR...'), 900);
    setTimeout(() => setDelayText(' SECURING CARGO. APPLYING PREMIUM DISCOUNT.'), 1400);
    
    setTimeout(() => {
      setIsHollywoodDelay(false);
      setMitigationComplete(true);
      setMitigationModal({
        oldRisk: `${Math.round(surgeRisk * 100)}%`, oldDelay: '14 hrs', oldPremium: `₹${surgePremium.toLocaleString('en-IN')} (Surge Pricing)`,
        newRisk: `${Math.round(optimizedRisk * 100)}%`, newDelay: '45 mins', newPremium: `₹${optimizedPremium.toLocaleString('en-IN')} (Optimized Base Rate)`,
        actualSavings: actualSavings,
        cargoValueStr: `₹${(cargoValue / 10000000).toFixed(2)} Crores`
      });
      if (routes.length > 1) {
        setSelectedRouteId(routes.find(r => r.mode === 'road' && !r.best)?.id || routes[0].id);
      }
    }, 1800);
  };

  const demoKpis = {
    cargo_value: setupData?.cargo_value_inr || 500000, 
    co2: mitigationComplete ? globalBaseline.co2 + Math.round((setupData?.cargo_value_inr || 500000) * 0.00002) : globalBaseline.co2,
    premium_savings: mitigationComplete ? globalBaseline.savings + (mitigationModal?.actualSavings || 0) : globalBaseline.savings,
    shocks_averted: mitigationComplete ? globalBaseline.shocks + 1 : globalBaseline.shocks
  };
  
  const { data: nodes } = useQuery({ queryKey: ['nodes'], queryFn: getNodes });

  const originId = setupData?.options?.[0]?.path?.[0] || 'PUNE_DEPOT';
  const destinationId = setupData?.options?.[0]?.path?.slice(-1)[0] || 'MUMBAI_DEST';
  
  const originNode = nodes?.find(n => n.id === originId);
  const destinationNode = nodes?.find(n => n.id === destinationId);

  useEffect(() => {
    if (setupData?.options && nodes) {
      // Map dynamic routes from setup state
      const dynamicRoutes = setupData.options.map((opt, idx) => {
        const waypoints = opt.path.map(nodeId => {
          const n = nodes.find(x => x.id === nodeId);
          return n ? [n.lat, n.lon] : [0, 0];
        });
        const stops = opt.path.map(nodeId => nodes.find(x => x.id === nodeId)?.name || nodeId);
        const mode = opt.modes[0] || 'road';
        const labelMap = { road: 'Road only', rail: 'Rail + Road', air: 'Air + Road' };
        
        return {
          id: idx + 1,
          mode: mode,
          label: labelMap[mode] || mode,
          subLabel: `via ${stops[1] || 'Main Corridor'}`,
          eta: `${Math.floor(opt.total_time_min / 60)}h ${Math.round(opt.total_time_min % 60)}m`,
          cost: `₹${Math.round(opt.total_cost_inr).toLocaleString('en-IN')}`,
          rawCost: opt.total_cost_inr,
          best: idx === 0,
          waypoints: waypoints,
          stops: stops,
          color: mode === 'road' ? '#2563eb' : mode === 'rail' ? '#f97316' : '#16a34a',
          dashArray: mode === 'rail' ? '8 4' : mode === 'air' ? '4 4' : null,
          market_trend: opt.market_trend
        };
      });
      setRoutes(dynamicRoutes);
    } else {
      // Fallback to BASE_ROUTES with dynamic surge
      const dynamicRoutes = BASE_ROUTES.map(route => {
        const volatility = route.mode === 'road' ? 0.3 : route.mode === 'rail' ? 0.15 : 0.05;
        const surge = 1 + (Math.random() * volatility - (volatility / 2));
        const newCost = Math.round(route.baseCost * surge);
        return {
          ...route,
          cost: `₹${newCost.toLocaleString('en-IN')}`,
          rawCost: newCost
        };
      });
      setRoutes(dynamicRoutes);
    }
  }, [setupData, nodes]);

  const { data: disruptions } = useQuery({ queryKey: ['disruptions'], queryFn: getLiveDisruptions, refetchInterval: 10000 });
  const { data: weatherData } = useQuery({ queryKey: ['weatherStatus'], queryFn: getWeatherStatus, refetchInterval: 30000 });
  const { data: newsData } = useQuery({ 
    queryKey: ['newsData', originId, destinationId], 
    queryFn: () => getRouteNews(originId, destinationId), 
    refetchInterval: 60000,
    enabled: !!originId && !!destinationId
  });

  //  Gemini AI Insights logic 
  useEffect(() => {
    if (!insuranceRoute) return;
    setInsights(null);
    setLoadingInsights(true);

    const prompt = `You are InsureRoute Intelligence — a senior AI advisor inside a real-time logistics command centre serving the ${originNode?.name || 'Mumbai'}–${destinationNode?.name || 'Pune'} corridor.

You have received LIVE sensor data from OpenWeatherMap across all route checkpoints, live news from NewsData API, and actuarial insurance data. Use ONLY the numbers below. Never invent data.

 ROUTE 
Route ID        : ${insuranceRoute.id}
Modes           : ${insuranceRoute.mode}
Path            : ${insuranceRoute.stops?.join(' → ') || 'N/A'}
ETA             : ${insuranceRoute.eta}
Total Cost      : ${insuranceRoute.cost}
Multimodal      : ${insuranceRoute.mode !== 'road' ? 'Yes' : 'No'}
System Pick     : ${insuranceRoute.best ? 'Yes — Recommended' : 'No'}
Active Alerts   : ${disruptions?.map(d => d.checkpoint_id).join(', ') || 'None'}

 LIVE WEATHER (OpenWeatherMap) 
Overall Status  : ${weatherData?.is_dangerous ? ' DANGEROUS' : '🟢 CLEAR'}
Last Polled     : ${weatherData?.last_checked || 'Unknown'}
Auto-Reroute Via: ${weatherData?.alternate_route_via || 'N/A'}

${(weatherData?.checkpoints || []).map(cp => `
Checkpoint : ${cp.name} (${cp.role?.replace(/_/g, ' ')})
Condition  : ${cp.description}
Temp       : ${cp.temperature}°C | Humidity: ${cp.humidity}%
Rain       : ${cp.rain_1h ?? 0} mm/hr | Wind: ${cp.wind_speed ?? 0} m/s
Severity   : ${Math.round((cp.severity ?? 0) * 100)}% | Dangerous: ${cp.is_dangerous ? 'YES ️' : 'No'}
`).join('---') || 'No live checkpoint data available.'}

 LIVE NEWS (NewsData API) 
${(newsData?.news || []).filter(n => (n.relevance_score || 0) >= 0.4).slice(0, 4).map(n =>
  `- "${n.title}" | Source: ${n.source} | Relevance: ${(n.relevance_score || 0).toFixed(2)} | Location: ${n.location_tag || 'Route Corridor'} | Published: ${n.published_at || 'Recent'}`
).join('\n') || 'No high-relevance news for this corridor right now.'}

 YOUR TASK 
Return ONLY a raw JSON object. No markdown. No backticks. No text outside the JSON.

{
  "summary": "2-3 sentences covering route status, live weather posture, and overall risk — use actual checkpoint names and data",
  "weather_headline": "One sentence naming the single most dangerous weather condition right now with the checkpoint name and its exact rain/wind reading",
  "most_dangerous_checkpoint": "Checkpoint name with highest severity, or 'All Clear'",
  "checkpoint_advisory": "2 sentences for the driver and dispatcher about the worst checkpoint — reference its role (mountain pass, expressway entry, etc.) and tell them exactly what to do",
  "pros": ["pro grounded in live data 1", "pro grounded in live data 2", "pro grounded in live data 3"],
  "cons": ["con grounded in live data 1", "con grounded in live data 2"],
  "risk_level": "LOW or MEDIUM or HIGH",
  "risk_reason": "One sentence citing the actual anomaly score, weather severity %, or active disruption that drives this rating",
  "insurance_tip": "One actionable tip — tell the underwriter what to watch or adjust",
  "routing_verdict": "One decisive sentence — take this route or switch, and exactly why based on the data",
  "news_highlight": "One sentence on the most operationally relevant news item, or 'No significant alerts for this corridor.'",
  "operations_action": "Specific action for the operations manager right now — name the checkpoint, cost, or ETA impact",
  "underwriter_action": "Specific action for the underwriter — what coverage adjustment to make",
  "analyst_action": "Specific monitoring recommendation — which checkpoint metric to watch and at what threshold to escalate",
  "best_for": "The cargo type or shipment scenario this route is optimally suited for given current conditions",
  "one_line_verdict": "One bold decisive sentence — the complete situation and recommended posture in plain English"
}`;

    chatWithAgent({
      shipment_id: setupData?.shipment_id,
      message: prompt,
    })
      .then((data) => {
        const raw = data?.response ?? '{}';
        const clean = raw.replace(/```json|```/g, '').trim();
        try {
          setInsights(JSON.parse(clean));
        } catch (e) {
          console.error("Failed to parse Gemini response", e, raw);
          setInsights({ 
            one_line_verdict: "Error: AI response parsing failed",
            summary: raw,
            risk_level: "MEDIUM",
            risk_reason: "AI unavailable",
            routing_verdict: "System fallback required"
          });
        }
      })
      .catch(() => setInsights({
        one_line_verdict: "Error: AI unavailable",
        summary: "Failed to reach InsureRoute AI.",
        risk_level: "MEDIUM",
        risk_reason: "AI unavailable",
        routing_verdict: "System fallback required"
      }))
      .finally(() => setLoadingInsights(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insuranceRoute, setupData?.shipment_id]);


  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  // Initial Gemini greeting on mount
  useEffect(() => {
    if (!originNode || !destinationNode || routes.length === 0) return;

    (async () => {
      setTyping(true);
      try {
        const INIT_PROMPT = `The user is shipping cargo from ${originNode.name} to ${destinationNode.name}. We have ${routes.length} route options. Briefly introduce yourself as InsureRoute AI and provide a one-sentence high-level summary of the best route choice based on current data. Keep it professional.`;
        const initHistory = [{ role: 'user', parts: [{ text: INIT_PROMPT }] }];
        const reply = await callGeminiViaBackend(INIT_PROMPT, setupData?.shipment_id);
        const newHistory = [
          ...initHistory,
          { role: 'model', parts: [{ text: reply }] },
        ];
        setHistory(newHistory);
        setMessages([{ role: 'model', text: reply }]);
      } catch {
        setMessages([
          {
            role: 'model',
            text: 'Unable to reach InsureRoute AI. Please try again.',
          },
        ]);
      } finally {
        setTyping(false);
      }
    })();
  }, [originNode, destinationNode, routes.length]);

  // Send user message
  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim()) return;
      const userText = text.trim();
      setInput('');
      setMessages((prev) => [...prev, { role: 'user', text: userText }]);

      const newHistory = [
        ...history,
        { role: 'user', parts: [{ text: userText }] },
      ];
      setTyping(true);
      try {
        const reply = await callGeminiViaBackend(userText, setupData?.shipment_id);
        const updatedHistory = [
          ...newHistory,
          { role: 'model', parts: [{ text: reply }] },
        ];
        setHistory(updatedHistory);
        setMessages((prev) => [...prev, { role: 'model', text: reply }]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            role: 'model',
            text: 'Unable to reach InsureRoute AI. Please try again.',
          },
        ]);
      } finally {
        setTyping(false);
      }
    },
    [history, setupData?.shipment_id]
  );

  // Select route + notify Gemini
  const handleRouteSelect = useCallback(
    (route) => {
      setSelectedRouteId(route.id);
      const autoMsg = `User selected ${route.label} (${route.mode}, ${route.cost}, ${route.eta}). Briefly tell the user what to expect with this choice and any tips to ensure smooth delivery.`;
      sendMessage(autoMsg);
    },
    [sendMessage]
  );
  
  const handleDownloadPDF = (insuranceRoute, insights, totalPrem, coverageTier) => {
    const printWindow = window.open('', '_blank');
    const date = new Date().toLocaleDateString();
    const policyId = `IR-${Math.random().toString(36).substr(2, 9).toUpperCase()}`;

    const content = `
      <html>
        <head>
          <title>InsureRoute Policy Quote - ${policyId}</title>
          <style>
            body { font-family: 'Inter', system-ui, sans-serif; color: #1e293b; line-height: 1.5; padding: 40px; }
            .header { display: flex; justify-between; align-items: center; border-bottom: 2px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }
            .logo { font-size: 24px; font-bold; color: #2563eb; }
            .meta { text-align: right; font-size: 14px; color: #64748b; }
            .title { font-size: 28px; font-bold; margin-bottom: 10px; }
            .section { margin-bottom: 30px; }
            .section-title { font-size: 16px; font-bold; text-transform: uppercase; color: #3b82f6; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; margin-bottom: 15px; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .label { font-size: 12px; color: #64748b; text-transform: uppercase; }
            .value { font-size: 16px; font-bold; }
            .premium-box { background: #eff6ff; border: 1px solid #bfdbfe; padding: 20px; border-radius: 12px; text-align: center; margin: 30px 0; }
            .premium-value { font-size: 40px; font-bold; color: #1e3a8a; }
            .risk-badge { display: inline-block; padding: 4px 12px; border-radius: 99px; font-size: 12px; font-bold; margin-top: 10px; }
            .risk-low { background: #ecfdf5; color: #059669; }
            .risk-medium { background: #fffbeb; color: #d97706; }
            .risk-high { background: #fef2f2; color: #dc2626; }
            .list { margin: 0; padding-left: 20px; }
            .footer { margin-top: 50px; font-size: 12px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; pt-20; }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="logo">InsureRoute Intelligence</div>
            <div class="meta">
              <div>Quote ID: ${policyId}</div>
              <div>Date: ${date}</div>
            </div>
          </div>

          <div class="title">Logistics Insurance Policy Quote</div>
          <p>Official risk assessment and premium quotation for shipment corridor transit.</p>

          <div class="section">
            <div class="section-title">Shipment Details</div>
            <div class="grid">
              <div>
                <div class="label">Route</div>
                <div class="value">${insuranceRoute.stops[0]} → ${insuranceRoute.stops.slice(-1)}</div>
              </div>
              <div>
                <div class="label">Mode of Transport</div>
                <div class="value" style="text-transform: capitalize">${insuranceRoute.mode}</div>
              </div>
              <div>
                <div class="label">Estimated Transit Time</div>
                <div class="value">${insuranceRoute.eta}</div>
              </div>
              <div>
                <div class="label">Coverage Tier</div>
                <div class="value" style="text-transform: capitalize">${coverageTier}</div>
              </div>
            </div>
          </div>

          <div class="premium-box">
            <div class="label">Total Calculated Premium</div>
            <div class="premium-value">₹${totalPrem.toLocaleString()}</div>
            <div class="risk-badge risk-${insights?.risk_level?.toLowerCase() || 'medium'}">
              ${insights?.risk_level || 'STANDARD'} RISK LEVEL
            </div>
          </div>

          <div class="section">
            <div class="section-title">AI Risk Intelligence Summary</div>
            <p style="font-size: 14px;">${insights?.summary || 'No detailed summary available.'}</p>
          </div>

          <div class="grid">
            <div class="section">
              <div class="section-title">Safety Pros</div>
              <ul class="list">
                ${(Array.isArray(insights?.pros) ? insights.pros : []).map(p => `<li style="font-size: 13px; margin-bottom: 5px;">${p}</li>`).join('')}
              </ul>
            </div>
            <div class="section">
              <div class="section-title">Risk Factors</div>
              <ul class="list">
                ${(Array.isArray(insights?.cons) ? insights.cons : []).map(c => `<li style="font-size: 13px; margin-bottom: 5px;">${c}</li>`).join('')}
              </ul>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Route Advisory</div>
            <p style="font-size: 13px; font-style: italic; color: #475569;">
              ${insights?.one_line_verdict || 'Proceed with standard operational procedures.'}
            </p>
          </div>

          <div class="footer">
            Generated by InsureRoute AI Intelligence Platform. This is a digital quotation valid for 24 hours.
          </div>

          <script>
            window.onload = () => {
              window.print();
              // window.close(); 
            }
          </script>
        </body>
      </html>
    `;

    printWindow.document.write(content);
    printWindow.document.close();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <>
    <div className="flex flex-col overflow-hidden bg-slate-50" style={{ height: '100dvh' }}>
      {/*  Header  */}
      <header className="flex-shrink-0 bg-white border-b border-slate-200 shadow-sm z-10">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center">
            <div className="h-8 flex items-center justify-center">
              <img src="/logo-full.jpeg" alt="InsureRoute Logo" className="h-full w-auto object-contain" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setIsRouteIntelOpen(true)}
              className="bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
            >
              <Newspaper size={14} /> Live Route News
            </button>
            <button 
              onClick={triggerHollywoodDelay}
              className="bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
            >
              <AlertCircle size={14} /> Inject Crisis
            </button>
            <div className="flex items-center gap-2 border-l border-slate-200 pl-4 hidden">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-sm text-slate-500 font-medium">Operations Command Center</span>
            </div>
          </div>
        </div>
      </header>

      {/*  Three-panel body  */}
      <div className="flex flex-1 overflow-hidden">
        {/*  LEFT: Route Options  */}
        <aside className="w-72 flex-shrink-0 flex flex-col bg-slate-50 border-r border-slate-200 overflow-hidden">
          <div className="px-4 pt-4 pb-3 border-b border-slate-200 bg-white">
            <div className="flex items-center gap-2">
              <MapPin size={14} className="text-blue-600" />
              <div>
                <div className="font-bold text-slate-900 text-sm">Route Options</div>
                <div className="text-xs text-slate-500">{originNode?.name || 'Mumbai'} → {destinationNode?.name || 'Pune'}</div>
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="px-4 py-2 border-b border-slate-200 bg-white">
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <span className="inline-block w-6 h-0.5 bg-blue-600 rounded" /> Road
              </span>
              <span className="flex items-center gap-1">
                <svg width="24" height="3" className="inline-block">
                  <line x1="0" y1="1.5" x2="24" y2="1.5" stroke="#f97316" strokeWidth="2" strokeDasharray="5 3" />
                </svg>
                Rail
              </span>
              <span className="flex items-center gap-1">
                <svg width="24" height="3" className="inline-block">
                  <line x1="0" y1="1.5" x2="24" y2="1.5" stroke="#16a34a" strokeWidth="2" strokeDasharray="3 3" />
                </svg>
                Air
              </span>
            </div>
          </div>

          {/* Cards */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
            {routes.map((route) => (
              <RouteCard
                key={route.id}
                route={route}
                selected={selectedRouteId === route.id}
                onSelect={handleRouteSelect}
                onKnowMore={setInsuranceRoute}
              />
            ))}

            {/* Route summary footnote */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 mt-2">
              <div className="flex items-start gap-2">
                <Zap size={13} className="text-blue-500 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-blue-700 leading-relaxed">
                  Click a route card to highlight it on the map. Ask the AI chatbot for personalized recommendations.
                </p>
              </div>
            </div>
          </div>
        </aside>

        {/*  CENTER: Map  */}
        <div className="flex-1 relative flex flex-col overflow-hidden bg-slate-50">
          <div className="p-4 z-[400] shadow-sm border-b border-slate-200 bg-white relative shrink-0">
             <KPICards kpis={demoKpis} />
          </div>
          <div className="flex-1 relative z-0">
            <MapContainer
            center={[18.7, 73.2]}
            zoom={9}
            style={{ width: '100%', height: '100%' }}
            zoomControl={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            />
            <MapLayer 
              selectedRouteId={selectedRouteId} 
              weatherData={weatherData} 
              routes={routes} 
              originNode={originNode}
              destinationNode={destinationNode}
            />
          </MapContainer>

          {/* Floating route info overlay */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[500] pointer-events-none">
            {(() => {
              const r = routes.find((x) => x.id === selectedRouteId);
              if (!r) return null;
              return (
                <div
                  className="flex items-center gap-3 px-4 py-2 rounded-full shadow-lg text-sm font-medium text-white"
                  style={{ background: r.color }}
                >
                  <ModeIcon mode={r.mode} size={14} className="" />
                  <span>{r.label}</span>
                  <span className="opacity-80">·</span>
                  <span>{r.eta}</span>
                  <span className="opacity-80">·</span>
                  <span>{r.cost}</span>
                </div>
              );
            })()}
          </div>
        </div>
        </div>

        {/*  RIGHT: Gemini Chat  */}
        <aside className="w-80 flex-shrink-0 flex flex-col bg-white border-l border-slate-200">
          {/* Chat header */}
          <div className="flex-shrink-0 px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-blue-600 to-blue-700">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                <Bot size={18} className="text-white" />
              </div>
              <div>
                <div className="font-bold text-white text-sm">InsureRoute AI</div>
                <div className="text-blue-200 text-xs">Powered by Gemini 2.5 Flash</div>
              </div>
              <div className="ml-auto flex items-center gap-1.5">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-blue-200 text-xs">Live</span>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-3 bg-slate-50">
            {messages.length === 0 && !typing && (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-3">
                  <Bot size={24} className="text-blue-600" />
                </div>
                <p className="text-sm text-slate-500">Connecting to InsureRoute AI...</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <ChatBubble key={i} role={msg.role} text={msg.text} />
            ))}
            {typing && <TypingDots />}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="flex-shrink-0 border-t border-slate-200 p-3 bg-white">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Gemini to optimize..."
                rows={1}
                disabled={typing}
                className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50 bg-slate-50"
                style={{ maxHeight: '100px', overflowY: 'auto' }}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={typing || !input.trim()}
                className="flex-shrink-0 w-10 h-10 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl flex items-center justify-center transition-colors shadow-sm"
              >
                <Send size={16} />
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-1.5 text-center">
              Press Enter to send · Shift+Enter for newline
            </p>
          </div>
        </aside>
      </div>

      {/* Mobile notice */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-900/90 text-white text-xs text-center py-2 px-4 z-50">
        Rotate device or use desktop for best experience
      </div>
    </div>

    {insuranceRoute && (() => {
      //  Real Actuarial Logic using Cargo Value (NOT transport cost) 
      // cargo_value_inr comes from the shipment setup form via location.state
      const cargoValue = setupData?.cargo_value_inr || 500000;
      const cargoTypeId = setupData?.cargo_type || 'fmcg';

      // Base rate: 0.3% of cargo value (standard freight insurance rate)
      const BASE_RATE = 0.003;

      // Cargo type risk multipliers (matches backend insurance_engine.py)
      const CARGO_RISK_MULT = {
        electronics: 1.4, pharmaceuticals: 1.6, automotive: 1.0,
        fmcg: 1.1, chemicals: 1.5, textiles: 0.9, perishables: 1.8,
        'industrial_chemicals': 1.5,
      };
      const cargoRiskMult = CARGO_RISK_MULT[cargoTypeId] || 1.0;

      // Weather Risk Factor (0.0 to 1.0)
      const weatherRisk = weatherData?.is_dangerous ? (weatherData?.severity || 0.4) : 0.05;
      const weatherMultiplier = 1 + (weatherRisk * 1.2); // Up to 2.2x multiplier for extreme weather

      let modeMult = 1.0;
      if (insuranceRoute.mode === 'rail') modeMult = 0.85; // Rail is safer
      else if (insuranceRoute.mode === 'air') modeMult = 1.2; // Air has higher liability

      let tierMult = 1.0;
      if (coverageTier === 'basic') tierMult = 0.65;
      else if (coverageTier === 'comprehensive') tierMult = 1.0;
      else if (coverageTier === 'all_risk') tierMult = 1.4;

      const etaStr = insuranceRoute?.eta || '0h 0m';
      const etaHours = parseInt(etaStr.split('h')[0] || 0) + (parseInt(etaStr.split('m')[0].split(' ').pop() || 0) / 60);

      //  Calculate premium components from CARGO VALUE 
      // Incorporate trip duration into base rate modifier (longer trips = higher exposure)
      const durationMult = 1 + (etaHours * 0.02); // 2% increase per hour of travel
      
      const basePrem   = Math.round(cargoValue * BASE_RATE * modeMult * durationMult);
      const weatherAdj = Math.round(basePrem * (weatherMultiplier - 1));
      const cargoAdj   = Math.round(basePrem * (cargoRiskMult - 1));
      const covAdj     = Math.round(basePrem * (tierMult - 1));

      const totalPrem = Math.round((basePrem + weatherAdj + cargoAdj + covAdj) * tierMult);
      
      // Dynamic Risk Score (0-100)
      const baseRiskScore = { road: 15, rail: 10, air: 25 }[insuranceRoute.mode] || 15;
      const weatherScore  = Math.round(weatherRisk * 50);
      
      // Add distance/duration factor to make it dynamic per route
      const durationRisk = Math.min(Math.round((etaHours || 0) * 1.5), 25);
      
      const rawScore = (baseRiskScore + weatherScore + durationRisk) * cargoRiskMult;
      const riskScore = Math.min(Math.round(rawScore || 0), 100);
      
      const riskClass = riskScore < 30 ? 'LOW' : riskScore < 60 ? 'MEDIUM' : 'HIGH';
      const riskClr   = { 
        LOW: 'text-emerald-600 bg-emerald-50 border-emerald-200', 
        MEDIUM: 'text-amber-600 bg-amber-50 border-amber-200', 
        HIGH: 'text-red-600 bg-red-50 border-red-200' 
      }[riskClass];
      
      const breakdown = [
        { label: 'Base Premium',    amount: basePrem,   color: 'bg-slate-400' },
        { label: 'Weather Adjustment', amount: weatherAdj, color: 'bg-amber-400' },
        { label: 'Cargo Risk',      amount: cargoAdj,   color: 'bg-blue-400'  },
        { label: 'Coverage Tier',   amount: covAdj,     color: 'bg-indigo-400'},
      ];
      const maxAmt = Math.max(...breakdown.map(b => b.amount));

      const tiers = [
        { id: 'basic',          label: 'Basic',         desc: 'Named perils only · lowest cost' },
        { id: 'comprehensive',  label: 'Comprehensive', desc: 'All perils except war/nuclear' },
        { id: 'all_risk',       label: 'All-Risk',      desc: 'Maximum protection · recommended' },
      ];

      return (
        <div className="fixed inset-0 z-[9999] flex justify-end">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setInsuranceRoute(null)} />

          {/* Panel */}
          <div
            className="relative w-full max-w-md bg-white shadow-2xl flex flex-col overflow-hidden"
            style={{ animation: 'slideIn 0.25s ease-out' }}
          >
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-4 bg-gradient-to-r from-blue-700 to-indigo-700 text-white">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Shield size={16} className="opacity-80" />
                    <span className="font-bold text-base">Insurance Quote</span>
                  </div>
                  <p className="text-blue-200 text-xs">
                    {insuranceRoute.label} · {insuranceRoute.eta} · {insuranceRoute.cost}
                  </p>
                </div>
                <button onClick={() => setInsuranceRoute(null)} className="text-blue-200 hover:text-white">
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">

              {/* Premium hero */}
              <div className="text-center py-4 border-b border-slate-100">
                <div className="text-xs text-slate-500 mb-1 uppercase tracking-wide">Estimated Premium</div>
                <div className="text-5xl font-mono font-bold text-slate-900">₹{totalPrem.toLocaleString()}</div>
                <span className={`inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full text-xs font-bold border ${riskClr}`}>
                  <AlertCircle size={11} /> {riskClass} RISK · Score {riskScore}/100
                </span>
                <div className="mt-2 text-xs text-slate-400">
                  Cargo Insured: <span className="font-semibold text-slate-600">₹{cargoValue.toLocaleString('en-IN')}</span>
                  {' · '}
                  <span className="capitalize">{cargoTypeId.replace(/_/g, ' ')}</span>
                </div>
              </div>

              {/* Coverage tier selector */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Coverage Level</div>
                <div className="space-y-2">
                  {tiers.map(t => (
                    <button
                      key={t.id}
                      onClick={() => setCoverageTier(t.id)}
                      className={`w-full text-left p-3 rounded-xl border-2 transition-all ${
                        coverageTier === t.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-slate-800">{t.label}</span>
                        {coverageTier === t.id && <CheckCircle size={14} className="text-blue-600" />}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">{t.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Premium breakdown bars */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Premium Breakdown</div>
                <div className="space-y-3">
                  {breakdown.map(b => (
                    <div key={b.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-600">{b.label}</span>
                        <span className="font-mono font-medium">₹{b.amount.toLocaleString()}</span>
                      </div>
                      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${b.color} transition-all duration-700`}
                          style={{ width: `${Math.round((b.amount / maxAmt) * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Live Telemetry Feed */}
              {weatherData?.checkpoints?.length > 0 && (
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3 flex items-center justify-between">
                    <span>Route Telemetry (Live)</span>
                    <span className="text-[10px] text-emerald-500 flex items-center gap-1 animate-pulse">
                      <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full" /> Live sensor feed
                    </span>
                  </div>
                  <div className="space-y-2">
                    {insuranceRoute.stops.slice(0, 5).map((stopName, idx) => {
                      const cp = weatherData?.checkpoints?.[idx % (weatherData?.checkpoints?.length || 1)] || {
                        weather_id: 800, temperature: 25, humidity: 50, rain_1h: 0, description: 'Clear sky', wind_speed: 3.5
                      };
                      return (
                      <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 bg-white rounded-md shadow-sm border border-slate-100">
                            {getWeatherIcon(cp.weather_id)}
                          </div>
                          <div>
                            <div className="text-[11px] font-bold text-slate-700">{stopName}</div>
                            <div className="text-[10px] text-slate-400 capitalize">{cp.description}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-[11px] font-mono font-bold text-slate-700">{cp.temperature}°C</div>
                          <div className="text-[9px] text-slate-400">Wind: {cp.wind_speed}m/s</div>
                        </div>
                      </div>
                    )})}
                  </div>
                </div>
              )}

              {/* Risk trajectory */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <TrendingUp size={12} /> Risk Trajectory (last 1h)
                </div>
                <div className="flex items-end gap-1 h-16">
                  {[20, 23, 27, 25, 30, 28, riskScore].map((v, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-1">
                      <div
                        className={`w-full rounded-sm ${
                          i === 6 ? (riskScore < 35 ? 'bg-emerald-500' : riskScore < 50 ? 'bg-amber-500' : 'bg-red-500') : 'bg-slate-200'
                        }`}
                        style={{ height: `${(v / 100) * 64}px` }}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                  <span>10:00</span><span>Now</span>
                </div>
              </div>

              {/* AI Insights integration */}
              {loadingInsights ? (
                <div className="flex flex-col items-center justify-center py-8 gap-4 border-t border-slate-100">
                  <div className="flex gap-2">
                    {[0, 0.15, 0.3].map((d, i) => (
                      <div key={i} className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: `${d}s` }} />
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 font-medium">InsureRoute AI is analyzing live telemetry...</p>
                </div>
              ) : insights ? (
                <div className="space-y-6 pt-4 border-t border-slate-100">
                  {/* Verdict Header */}
                  <div className="bg-gradient-to-br from-slate-900 to-slate-800 p-4 rounded-xl text-white shadow-md">
                    <div className="text-[10px] text-slate-400 font-bold tracking-widest uppercase mb-1">Command Verdict</div>
                    <div className="text-sm font-semibold leading-relaxed">
                      {insights.one_line_verdict}
                    </div>
                  </div>

                  {/* Summary */}
                  <div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-2">Situation Summary</div>
                    <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">{insights.summary}</p>
                  </div>

                  {/* Routing Decision */}
                  <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Navigation className="w-4 h-4 text-blue-600" />
                      <div className="text-[10px] font-bold text-blue-800 uppercase tracking-wide">Routing Decision</div>
                    </div>
                    <p className="text-xs text-blue-900 leading-relaxed font-medium mb-3">{insights.routing_verdict}</p>
                    <div className="pt-3 border-t border-blue-200/50">
                      <div className="text-[10px] text-blue-600 font-bold uppercase mb-1">Optimized For</div>
                      <div className="text-xs text-blue-900">{insights.best_for}</div>
                    </div>
                  </div>

                  {/* Weather Intelligence */}
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <CloudLightning className="w-4 h-4 text-amber-500" />
                      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Weather Intelligence</div>
                    </div>
                    <div className="space-y-2">
                      <div className="bg-white border-l-4 border-amber-500 shadow-sm p-3 rounded-r-lg">
                        <div className="text-[10px] text-amber-600 font-bold uppercase mb-1">{insights.most_dangerous_checkpoint}</div>
                        <div className="text-xs font-medium text-slate-800">{insights.weather_headline}</div>
                      </div>
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                        <div className="text-[10px] text-slate-500 font-bold uppercase mb-1">Advisory</div>
                        <div className="text-xs text-slate-700">{insights.checkpoint_advisory}</div>
                      </div>
                    </div>
                  </div>

                  {/* Actions Matrix */}
                  <div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-3">Required Actions</div>
                    <div className="space-y-2">
                      <div className="flex gap-3 bg-red-50 border border-red-100 p-3 rounded-lg">
                        <Activity className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] text-red-600 font-bold uppercase mb-0.5">Operations</div>
                          <div className="text-xs text-red-900 leading-relaxed">{insights.operations_action}</div>
                        </div>
                      </div>
                      <div className="flex gap-3 bg-emerald-50 border border-emerald-100 p-3 rounded-lg">
                        <Briefcase className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] text-emerald-600 font-bold uppercase mb-0.5">Underwriting</div>
                          <div className="text-xs text-emerald-900 leading-relaxed">{insights.underwriter_action}</div>
                          <div className="mt-1.5 text-[10px] bg-emerald-200/50 text-emerald-800 px-2 py-1 rounded inline-block font-medium">Tip: {insights.insurance_tip}</div>
                        </div>
                      </div>
                      <div className="flex gap-3 bg-indigo-50 border border-indigo-100 p-3 rounded-lg">
                        <FileText className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] text-indigo-600 font-bold uppercase mb-0.5">Analytics</div>
                          <div className="text-xs text-indigo-900 leading-relaxed">{insights.analyst_action}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* News Highlight */}
                  {insights.news_highlight && insights.news_highlight !== 'No significant alerts for this corridor.' && (
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 flex gap-2 items-start">
                      <AlertCircle className="w-4 h-4 text-orange-600 shrink-0" />
                      <div>
                        <div className="text-[10px] text-orange-600 font-bold uppercase mb-0.5">Live News</div>
                        <div className="text-xs text-orange-900 leading-relaxed">{insights.news_highlight}</div>
                      </div>
                    </div>
                  )}

                  {/* Pros & Cons */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-emerald-50/50 border border-emerald-100 p-3 rounded-lg">
                      <div className="text-[10px] font-bold text-emerald-700 mb-2 uppercase tracking-wide flex items-center gap-1"><CheckCircle className="w-3 h-3"/> Strengths</div>
                      <ul className="space-y-1.5">
                        {(Array.isArray(insights?.pros) ? insights.pros : []).map((p, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-xs text-slate-700">
                            <span className="text-emerald-500 mt-0.5 shrink-0">•</span>
                            <span className="leading-tight">{p}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-red-50/50 border border-red-100 p-3 rounded-lg">
                      <div className="text-[10px] font-bold text-red-600 mb-2 uppercase tracking-wide flex items-center gap-1"><X className="w-3 h-3"/> Weaknesses</div>
                      <ul className="space-y-1.5">
                        {(Array.isArray(insights?.cons) ? insights.cons : []).map((c, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-xs text-slate-700">
                            <span className="text-red-500 mt-0.5 shrink-0">•</span>
                            <span className="leading-tight">{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* CTA */}
              <button 
                onClick={() => handleDownloadPDF(insuranceRoute, insights, totalPrem, coverageTier)}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-colors shadow-sm flex items-center justify-center gap-2"
              >
                <Download size={14} /> Download Policy Quote PDF
              </button>
            </div>
          </div>
        </div>
      );
    })()}

      {/*  Hollywood Delay Overlay  */}
      {isHollywoodDelay && (
        <div className="fixed inset-0 z-[9999] bg-slate-900/85 backdrop-blur-sm flex items-center justify-center">
          <div className="font-mono text-emerald-400 text-xl font-bold tracking-wider animate-pulse flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            {delayText}
          </div>
        </div>
      )}

      {/*  Before/After Mitigation Modal  */}
      {mitigationModal && (
        <div className="fixed inset-0 z-[9998] bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4" onClick={() => setMitigationModal(null)}>
          <div className="bg-white rounded-2xl shadow-2xl overflow-hidden max-w-4xl w-full" style={{ animation: 'slideIn 0.3s ease-out' }} onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <div className="font-bold text-slate-800 flex items-center gap-2">
                <Shield className="text-blue-600" size={18} /> InsureRoute Automated Mitigation Report
              </div>
              <button onClick={() => setMitigationModal(null)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>
            
            <div className="grid grid-cols-2 divide-x divide-slate-100">
              {/* Left Side (Disaster) */}
              <div className="p-8 bg-red-50/30">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-bold mb-6 animate-pulse">
                  <AlertCircle size={14} /> CRITICAL VULNERABILITY DETECTED
                </div>
                <div className="space-y-6">
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Projected Outcome</div>
                    <div className="text-xl font-bold text-slate-900">{mitigationModal.oldDelay} Gridlock (Cargo Spoilage)</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Financial Exposure</div>
                    <div className="text-xl font-bold text-slate-900">{mitigationModal.cargoValueStr} at risk</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Insurance Liability</div>
                    <div className="text-xl font-bold text-red-600">{mitigationModal.oldPremium}</div>
                  </div>
                </div>
              </div>
              
              {/* Right Side (Mitigation) */}
              <div className="p-8 bg-emerald-50/30 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                  <Shield size={120} />
                </div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold mb-6">
                  <CheckCircle size={14} /> AI MITIGATION ENGAGED
                </div>
                <div className="space-y-6 relative z-10">
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Projected Outcome</div>
                    <div className="text-xl font-bold text-slate-900">+{mitigationModal.newDelay} Detour (Cargo Preserved)</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Financial Exposure</div>
                    <div className="text-xl font-bold text-emerald-600">₹0 (Safe Zone)</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Insurance Liability</div>
                    <div className="text-xl font-bold text-emerald-600">{mitigationModal.newPremium}</div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="bg-slate-50 p-4 border-t border-slate-100 text-center text-sm text-slate-500">
              System successfully averted total loss. Real-time actuarial arbitrage applied: <span className="font-bold text-emerald-600">₹{mitigationModal.actualSavings?.toLocaleString('en-IN')} Saved</span>.
            </div>
          </div>
        </div>
      )}

      <RouteIntelDrawer isOpen={isRouteIntelOpen} onClose={() => setIsRouteIntelOpen(false)} origin={originId} destination={destinationId} />
    <style>{`
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
    `}</style>
    </>
  );
}
