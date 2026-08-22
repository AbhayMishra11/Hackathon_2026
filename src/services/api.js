const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  health: () => requestFromOrigin("/health"),
  summary: () => request("/dashboard/summary"),
  zones: () => request("/zones"),
  liveZone: (zoneId) => request(`/dashboard/zones/${zoneId}/live`),
  zoneHistory: (zoneId) =>
    request(
      `/dashboard/zones/${zoneId}/history?sensor_type=TEMPERATURE&hours=24`,
    ),
  activeAlerts: () => request("/alerts/active"),
};

async function requestFromOrigin(path, options = {}) {
  const response = await fetch(`${API_ORIGIN}${path}`, options);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}
