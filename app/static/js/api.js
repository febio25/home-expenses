// Thin wrapper around fetch for the JSON API. The frontend talks to the
// backend only through these calls.

const BASE = '/api/v1';
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(status, detail, { network = false } = {}) {
    super(detail);
    this.status = status;
    this.network = network; // true when the request never got an answer
  }
}

async function request(method, path, { json, body, headers = {}, timeout = TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const options = {
    method,
    credentials: 'same-origin',
    signal: controller.signal,
    // Required by the server on every cookie-authenticated write (CSRF guard).
    headers: { 'X-Requested-With': 'spese', ...headers },
  };
  if (json !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(json);
  } else if (body !== undefined) {
    options.body = body;
  }

  let response;
  try {
    response = await fetch(BASE + path, options);
  } catch (error) {
    throw new ApiError(0, 'Connessione assente o server non raggiungibile.', { network: true });
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail = `Errore ${response.status}.`;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') detail = data.detail;
    } catch (ignored) { /* not JSON: keep the generic message */ }
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new CustomEvent('spese:unauthorized'));
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

async function jsonOf(response) {
  return response.status === 204 ? null : response.json();
}

export const api = {
  get: async (path) => jsonOf(await request('GET', path)),
  post: async (path, json) => jsonOf(await request('POST', path, { json })),
  patch: async (path, json) => jsonOf(await request('PATCH', path, { json })),
  put: async (path, json) => jsonOf(await request('PUT', path, { json })),
  del: async (path) => jsonOf(await request('DELETE', path)),

  // Returns the saved expense plus whether it was newly created (201) or
  // was already there from an earlier attempt with the same client_uuid (200).
  async createExpense(json) {
    const response = await request('POST', '/expenses', { json });
    return { expense: await response.json(), created: response.status === 201 };
  },

  // Fetch a file (CSV, backup) and hand it to the browser as a download.
  async download(path, fallbackName) {
    const response = await request('GET', path, { timeout: 60000 });
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = match ? match[1] : fallbackName;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  },

  async restore(file) {
    return jsonOf(await request('POST', '/restore', {
      body: file,
      headers: { 'Content-Type': 'application/octet-stream' },
      timeout: 120000,
    }));
  },
};
