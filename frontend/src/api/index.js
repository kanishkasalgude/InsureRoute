import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'https://insureroute-backend-758641920121.us-central1.run.app';

export const api = axios.create({
  baseURL: API_BASE,
});

export const createShipment = async (data) => {
  const res = await api.post('/api/v1/shipments/create', data);
  return res.data;
};

export const getRouteOptions = async (shipmentId) => {
  const res = await api.get(`/api/v1/routes/${shipmentId}/options`);
  return res.data;
};

export const getQuote = async (data) => {
  const res = await api.post('/api/v1/insurance/quote', data);
  return res.data;
};

export const chatWithAgent = async (data) => {
  const res = await api.post('/api/v1/gemini/chat', data);
  return res.data;
};

export const getLiveDisruptions = async () => {
  const res = await api.get('/api/v1/disruptions/live');
  return res.data;
};

export const getNodes = async () => {
  const res = await api.get('/api/v1/nodes');
  return res.data;
};

export const getCargoTypes = async () => {
  const res = await api.get('/api/v1/cargo-types');
  return res.data;
};

export const getWeatherStatus = async () => {
  const res = await api.get('/api/v1/weather-status');
  return res.data;
};

export const getRouteNews = async (origin, destination) => {
  const res = await api.get('/api/v1/route-news', {
    params: { origin, destination }
  });
  return res.data;
};