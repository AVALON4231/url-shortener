const BASE_URL = '';

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('shortener_token');

  const res = await fetch(BASE_URL + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(options.headers || {})
    }
  });

  if (res.status === 401) {
    localStorage.removeItem('shortener_token');
    window.dispatchEvent(new Event('unauthorized'));
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'API error');
  }

  return res.json();
}