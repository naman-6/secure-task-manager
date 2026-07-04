/**
 * api.js
 * Thin fetch wrapper for the Secure Task & Asset Manager backend.
 *
 * IMPORTANT: We intentionally call a RELATIVE path ("/api/v1/...") rather
 * than a hard-coded backend hostname/port. The Nginx container serving this
 * frontend (see nginx.conf) reverse-proxies "/api/" to the backend Service.
 * This keeps the frontend image environment-agnostic: the exact same image
 * built once on the mothership works in docker-compose AND in Kubernetes,
 * because only Nginx's upstream target changes between environments.
 */

const BASE_URL = '/api/v1';

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    const detail = body && body.detail ? body.detail : response.statusText;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      : detail;
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return body;
}

export const TaskAPI = {
  list: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString();
    return request(`/tasks${query ? `?${query}` : ''}`);
  },
  get: (id) => request(`/tasks/${id}`),
  create: (payload) =>
    request('/tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (id, payload) =>
    request(`/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  remove: (id) =>
    request(`/tasks/${id}`, {
      method: 'DELETE',
    }),
};
