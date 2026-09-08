import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, Info, Newspaper, ChevronRight } from 'lucide-react';
import { api } from '../api/index';

export default function RouteIntelDrawer({ isOpen, onClose, origin, destination }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && origin && destination) {
      setLoading(true);
      // Fetching from the existing Python backend route
      api.get(`/api/v1/route-intelligence?origin=${origin}&destination=${destination}`)
        .then(res => setData(res.data))
        .catch(err => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [isOpen, origin, destination]);

  if (!isOpen) return null;

  const riskLevel = data?.risk_score >= 60 ? 'HIGH' : data?.risk_score >= 30 ? 'MEDIUM' : 'LOW';
  const riskColor = riskLevel === 'HIGH' ? 'text-red-600 bg-red-50 border-red-200' : 
                    riskLevel === 'MEDIUM' ? 'text-amber-600 bg-amber-50 border-amber-200' : 
                    'text-emerald-600 bg-emerald-50 border-emerald-200';

  const riskDot = riskLevel === 'HIGH' ? '' : riskLevel === 'MEDIUM' ? '🟡' : '🟢';

  return (
    <div className="fixed inset-0 z-[9999] flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity" onClick={onClose} />

      {/* Sliding Panel */}
      <div 
        className="relative w-full max-w-md bg-slate-50 shadow-2xl flex flex-col overflow-hidden h-full"
        style={{ animation: 'slideIn 0.3s ease-out' }}
      >
        {/* Header */}
        <div className="flex-shrink-0 px-6 py-4 bg-white border-b border-slate-200 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Newspaper size={18} className="text-blue-600" />
            <h2 className="font-bold text-slate-800 text-lg">Live Route News</h2>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-40 gap-3">
              <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-500 font-medium">Analyzing live route data...</p>
            </div>
          ) : data ? (
            <>
              {/* AI Summary Section */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                    <Info size={14} /> AI Summary
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${riskColor}`}>
                    {riskLevel} RISK
                  </span>
                </div>
                <div className="p-4 space-y-4">
                  {/* Reasons */}
                  <ul className="space-y-2">
                    {data.risks?.slice(0, 3).map((risk, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                        <span className="text-slate-400 mt-1">•</span>
                        <span>{risk.reason}</span>
                      </li>
                    ))}
                    {(!data.risks || data.risks.length === 0) && (
                      <li className="text-sm text-slate-500 italic">No significant risks detected.</li>
                    )}
                  </ul>
                  
                  {/* Recommendation */}
                  <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-800 font-medium flex items-start gap-2">
                    <AlertTriangle size={16} className="text-blue-600 shrink-0 mt-0.5" />
                    <span>{data.intelligence_highlight}</span>
                  </div>
                </div>
              </div>

              {/* Alerts Feed Section */}
              <div>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 px-1">Alerts Feed</h3>
                <div className="space-y-3">
                  {data.news?.length > 0 ? data.news.map((item, i) => {
                    const impactLvl = item.impact?.toUpperCase() || 'LOW';
                    const icon = impactLvl === 'HIGH' ? '' : impactLvl === 'MEDIUM' ? '🟡' : '🟢';
                    
                    return (
                      <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-slate-300 transition-colors group">
                        <div className="flex gap-2 items-start mb-2">
                          <span className="text-xs shrink-0 mt-0.5">{icon}</span>
                          <h4 className="text-sm font-semibold text-slate-800 leading-tight group-hover:text-blue-600 transition-colors">
                            {item.title}
                          </h4>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-slate-500 mb-2 pl-6">
                          <span className="font-medium bg-slate-100 px-1.5 py-0.5 rounded">{item.source}</span>
                          <span>•</span>
                          <span>{item.location_tag}</span>
                        </div>
                        <div className="pl-6 flex items-center gap-1.5 text-xs">
                          <span className="text-slate-400">→</span>
                          <span className="font-medium text-slate-700">
                            Impact: {impactLvl === 'HIGH' ? 'Possible severe disruption' : impactLvl === 'MEDIUM' ? 'Minor delays expected' : 'Normal operations'}
                          </span>
                        </div>
                      </div>
                    )
                  }) : (
                    <div className="text-center p-6 bg-white rounded-xl border border-dashed border-slate-200">
                      <p className="text-sm text-slate-500">No recent alerts for this route.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="text-center text-sm text-slate-500 py-10">Failed to load route intelligence.</div>
          )}
        </div>
      </div>
    </div>
  );
}