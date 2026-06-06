const BASE_URL = '/api'

async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

function post(url, data) {
  return request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export const sourcesApi = {
  getAll: () => request(`${BASE_URL}/sources`),
  getById: (id) => request(`${BASE_URL}/sources/${id}`),
  create: (data) => post(`${BASE_URL}/sources`, data),
  delete: (id) => request(`${BASE_URL}/sources/${id}`, { method: 'DELETE' }),
};

export const assetsApi = {
  getAll: () => request(`${BASE_URL}/assets`),
  getById: (id) => request(`${BASE_URL}/assets/${id}`),
  getAsOf: (id, timestamp) => request(`${BASE_URL}/assets/${id}?as_of=${encodeURIComponent(timestamp)}`),
  create: (data) => post(`${BASE_URL}/assets`, data),
  delete: (id) => request(`${BASE_URL}/assets/${id}`, { method: 'DELETE' }),
};

export const assetsByClassApi = {
  getAll: () => request(`${BASE_URL}/assets-by-class`),
  create: (data) => post(`${BASE_URL}/assets-by-class`, data),
};

export const timeSeriesApi = {
  getAll: () => request(`${BASE_URL}/time-series`),
  getFiltered: (assetId, sourceId) => {
    const params = new URLSearchParams();
    if (assetId) params.set('asset_id', assetId);
    if (sourceId) params.set('source_id', sourceId);
    return request(`${BASE_URL}/time-series?${params}`);
  },
  create: (data) => post(`${BASE_URL}/time-series`, data),
};

export const ingestApi = {
  run: (data) => post(`${BASE_URL}/ingest`, data),
};

export const assistantApi = {
  chat: (message, history = []) =>
    post(`${BASE_URL}/assistant/chat`, { message, history }),
};

export const analyticsApi = {
  aggregate: (data) => post(`${BASE_URL}/analytics/aggregate`, data),
  trend:     (data) => post(`${BASE_URL}/analytics/trend`, data),
  forecast:  (data) => post(`${BASE_URL}/analytics/forecast`, data),
  risk:      (data) => post(`${BASE_URL}/analytics/risk`, data),
  compare:   (data) => post(`${BASE_URL}/analytics/compare`, data),
};

export const exportApi = {
  download: async (data) => {
    const res = await fetch(`${BASE_URL}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new Error(text || `Export failed: ${res.status}`);
    }
    return res;
  },
};
