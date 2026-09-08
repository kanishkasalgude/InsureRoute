import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getCargoTypes, createShipment, getNodes } from '../api';
import Map from '../components/Map';
import { Package, MapPin, Navigation, Clock, Truck, Train, Plane, Anchor, Monitor, Pill, Wrench, FlaskConical, Shirt, Leaf } from 'lucide-react';

export default function ShipmentSetup() {
  const navigate = useNavigate();
  
  const iconMap = {
    'electronics': <Monitor className="w-6 h-6 text-indigo-500" />,
    'pharmaceuticals': <Pill className="w-6 h-6 text-rose-500" />,
    'automotive': <Wrench className="w-6 h-6 text-slate-500" />,
    'fmcg': <Package className="w-6 h-6 text-amber-600" />,
    'chemicals': <FlaskConical className="w-6 h-6 text-emerald-500" />,
    'textiles': <Shirt className="w-6 h-6 text-sky-500" />,
    'perishables': <Leaf className="w-6 h-6 text-green-600" />
  };

  const [formData, setFormData] = useState({
    origin: 'PUNE_DEPOT',
    destination: 'MUMBAI_DEST',
    cargo_type: 'fmcg',
    cargo_value_inr: 500000,
    cargo_weight_tons: 2,
    priority: 'safety',
    transport_preference: 'any'
  });

  const { data: cargoTypes, isLoading: loadingCargo } = useQuery({
    queryKey: ['cargoTypes'],
    queryFn: getCargoTypes
  });

  const { data: nodes, isLoading: loadingNodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: getNodes
  });

  const createMutation = useMutation({
    mutationFn: createShipment,
    onSuccess: (data) => {
      // Navigate to the enhanced dashboard with the analysis result
      navigate('/dashboard', { state: data });
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const markers = nodes?.filter(n => n.id === formData.origin || n.id === formData.destination).map(n => ({
    lat: n.lat, lon: n.lon, label: n.name
  })) || [];

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-100px)]">
      {/* Left Panel - Form */}
      <div className="w-full lg:w-[40%] bg-bgCard p-6 rounded-xl shadow-card overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
          <Package className="text-accentPrimary" />
          New Shipment
        </h2>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-textSecondary mb-1">Origin</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-3 w-4 h-4 text-textMuted" />
                <select 
                  value={formData.origin}
                  onChange={(e) => setFormData({...formData, origin: e.target.value})}
                  className="w-full bg-bgPrimary border border-border rounded-lg py-2 pl-9 pr-3 text-sm appearance-none"
                  disabled={loadingNodes}
                >
                  {nodes?.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-textSecondary mb-1">Destination</label>
              <div className="relative">
                <Navigation className="absolute left-3 top-3 w-4 h-4 text-textMuted" />
                <select 
                  value={formData.destination}
                  onChange={(e) => setFormData({...formData, destination: e.target.value})}
                  className="w-full bg-bgPrimary border border-border rounded-lg py-2 pl-9 pr-3 text-sm appearance-none"
                  disabled={loadingNodes}
                >
                  {nodes?.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-textSecondary mb-3">Cargo Type</label>
            {loadingCargo ? (
              <div className="text-sm text-textSecondary">Loading cargo types...</div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {cargoTypes?.types?.map((ct) => (
                  <button
                    key={ct.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, cargo_type: ct.id })}
                    className={`p-3 rounded-lg border text-sm flex flex-col items-center gap-2 transition-all
                      ${formData.cargo_type === ct.id 
                        ? 'border-accentPrimary bg-bgCardAlt text-accentPrimary shadow-sm' 
                        : 'border-border hover:bg-bgPrimary text-textSecondary'}`}
                  >
                    <div className="flex items-center justify-center h-8">
                      {iconMap[ct.id] || <Package className="w-6 h-6" />}
                    </div>
                    <span className="text-xs text-center truncate w-full">{ct.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-textSecondary mb-1">Value (₹)</label>
              <input 
                type="number" 
                value={formData.cargo_value_inr}
                onChange={(e) => setFormData({...formData, cargo_value_inr: Number(e.target.value)})}
                className="w-full border border-border rounded-lg p-2 text-sm font-mono" 
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-textSecondary mb-1">Weight (Tons)</label>
              <input 
                type="number" 
                value={formData.cargo_weight_tons}
                onChange={(e) => setFormData({...formData, cargo_weight_tons: Number(e.target.value)})}
                className="w-full border border-border rounded-lg p-2 text-sm font-mono" 
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-textSecondary mb-2">Optimization Priority</label>
            <div className="flex bg-bgPrimary p-1 rounded-lg border border-border">
              {['speed', 'cost', 'safety'].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setFormData({ ...formData, priority: p })}
                  className={`flex-1 py-2 text-sm rounded-md capitalize transition-colors
                    ${formData.priority === p 
                      ? 'bg-bgCard shadow-sm text-textPrimary font-medium' 
                      : 'text-textSecondary hover:text-textPrimary'}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={createMutation.isPending || loadingCargo || loadingNodes}
            className="w-full bg-accentPrimary hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Analyzing...' : 'Analyse Route'}
          </button>
        </form>
      </div>

      {/* Right Panel - Map */}
      <div className="w-full lg:w-[60%] bg-bgCard p-2 rounded-xl shadow-card h-[400px] lg:h-full relative">
        <Map markers={markers} />
        <div className="absolute top-6 right-6 bg-white p-3 rounded-lg shadow-md z-[400] border border-border">
          <h4 className="text-xs font-bold text-textSecondary mb-2 uppercase">Corridor Context</h4>
          <div className="flex items-center gap-2 text-sm mb-1">
            <span className="w-2 h-2 rounded-full bg-accentSuccess"></span> Safe
          </div>
          <div className="flex items-center gap-2 text-sm mb-1">
            <span className="w-2 h-2 rounded-full bg-accentWarning"></span> Medium Risk
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-accentDanger"></span> High Risk
          </div>
        </div>
      </div>
    </div>
  );
}