import { apiRequest } from './api.js';

export async function register(email, password) {
  await apiRequest('/register', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });

  return login(email, password);
}

export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const res = await fetch('/login', {
    method: 'POST',
    body: formData
  });

  if (!res.ok) throw new Error('Login failed');

  const data = await res.json();
  localStorage.setItem('shortener_token', data.access_token);
}

export function logout() {
  localStorage.removeItem('shortener_token');
}