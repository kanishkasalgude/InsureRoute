import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icons in React Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const MapBounds = ({ markers, routes }) => {
  const map = useMap();

  useEffect(() => {
    let bounds = [];
    if (markers && markers.length > 0) {
      markers.forEach(m => bounds.push([m.lat, m.lon]));
    }
    if (routes && routes.length > 0) {
      routes.forEach(r => {
        if (r.positions) {
          r.positions.forEach(p => {
             if (p) bounds.push(p);
          });
        }
      });
    }
    
    if (bounds.length > 0) {
      try {
        const latLngBounds = L.latLngBounds(bounds);
        map.fitBounds(latLngBounds, { padding: [50, 50], maxZoom: 11 });
      } catch (e) {
        console.error("Error setting map bounds", e);
      }
    }
  }, [map, markers, routes]);

  return null;
};

const Map = ({ center = [18.79, 73.4], zoom = 9, markers = [], routes = [], checkpoints = [], selectedRouteId = null }) => {
  // Sort routes to ensure selected is drawn on top
  const sortedRoutes = [...routes].sort((a, b) => {
    const aSelected = selectedRouteId === a.id || (!selectedRouteId && a.isBest);
    const bSelected = selectedRouteId === b.id || (!selectedRouteId && b.isBest);
    return aSelected ? 1 : bSelected ? -1 : 0;
  });

  return (
    <div className="h-full w-full rounded-lg overflow-hidden border border-border relative z-0">
      <MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }}>
        <MapBounds markers={markers} routes={routes} />
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        {sortedRoutes.map((route) => {
          const isSelected = selectedRouteId === route.id || (!selectedRouteId && route.isBest);
          return (
            <Polyline
              key={route.id}
              positions={route.positions}
              color={isSelected ? '#2563EB' : route.baseColor || '#94A3B8'}
              weight={isSelected ? 6 : 4}
              opacity={isSelected ? 1 : 0.7}
              dashArray={route.isMultimodal ? '8, 8' : null}
            />
          );
        })}
        {checkpoints?.map((cp, idx) => (
          <CircleMarker 
            key={`cp-${idx}`} 
            center={[cp.lat, cp.lon]} 
            radius={cp.isDisrupted ? 7 : 4}
            fillColor={cp.isDisrupted ? '#FEF2F2' : '#FFFFFF'}
            color={cp.isDisrupted ? '#EF4444' : '#94A3B8'}
            weight={cp.isDisrupted ? 3 : 2}
            fillOpacity={1}
          >
            <Popup>
              <strong>{cp.label}</strong>
              {cp.isDisrupted && <div className="text-red-500 text-xs mt-1 font-bold">Disruption Detected!</div>}
            </Popup>
          </CircleMarker>
        ))}
        {markers.map((marker, idx) => (
          <Marker key={idx} position={[marker.lat, marker.lon]}>
            <Popup>{marker.label}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};

export default Map;