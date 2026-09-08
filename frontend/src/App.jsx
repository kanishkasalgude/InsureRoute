import React from 'react';
import { Routes, Route } from 'react-router-dom';
import ShipmentSetup from './screens/ShipmentSetup';
import InsureRouteDashboard from './screens/InsureRouteDashboard';

function App() {
  return (
    <Routes>
      {/* Original home page — New Shipment form */}
      <Route
        path="/"
        element={
          <div className="min-h-screen bg-bgPrimary text-textPrimary">
            <header className="bg-bgCard border-b border-border p-4 shadow-sm">
              <div className="max-w-7xl mx-auto flex items-center justify-between">
                <img src="/logo-full.jpeg" alt="InsureRoute" className="h-8" />
                <span className="text-sm text-textSecondary font-mono hidden">Operations Command Center</span>
              </div>
            </header>
            <main className="p-4 md:p-6 max-w-7xl mx-auto">
              <ShipmentSetup />
            </main>
          </div>
        }
      />

      {/* Enhanced multi-modal dashboard (standalone, full-viewport) */}
      <Route path="/dashboard" element={<InsureRouteDashboard />} />
    </Routes>
  );
}

export default App;