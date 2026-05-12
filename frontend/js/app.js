import { login, register, logout } from './auth.js';
import { apiRequest } from './api.js';
import { show, setError, renderHistory, showConfirm, initModal } from './ui.js';

async function init() {
  initModal();

  const token = localStorage.getItem('shortener_token');
  if (token) {
    show('step-shorten');
    try {
      const links = await apiRequest('/my-links');
      renderHistory(links);
      attachDeleteHandlers();
    } catch (e) {
      console.error('История:', e);
    }
  } else {
    show('step-login');
  }
}

function attachDeleteHandlers() {
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', () => {
      deleteLink(btn.dataset.code, btn.dataset.url);
    });
  });
}

async function deleteLink(shortCode, shortUrl) {
  const confirmed = await showConfirm(shortUrl);
  if (!confirmed) return;
  try {
    await apiRequest(`/my-links/${shortCode}`, { method: 'DELETE' });
    const el = document.getElementById(`item-${shortCode}`);
    if (el) el.remove();
    if (!document.querySelector('.history-item')) {
      document.getElementById('history-list').innerHTML = '<p class="text-muted">Пока нет сокращённых ссылок</p>';
    }
  } catch (e) {
    console.error('Удаление:', e);
  }
}

window.login = async () => {
  setError('login', '');
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  if (!email || !password) { setError('login', 'Заполните все поля'); return; }
  try {
    await login(email, password);
    show('step-shorten');
    const links = await apiRequest('/my-links');
    renderHistory(links);
    attachDeleteHandlers();
  } catch (e) { setError('login', e.message); }
};

window.register = async () => {
  setError('register', '');
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  if (!email || !password) { setError('register', 'Заполните все поля'); return; }
  try {
    await register(email, password);
    show('step-shorten');
    const links = await apiRequest('/my-links');
    renderHistory(links);
    attachDeleteHandlers();
  } catch (e) { setError('register', e.message); }
};

window.shorten = async () => {
  setError('shorten', '');
  document.getElementById('result').innerHTML = '';
  const url = document.getElementById('long-url').value.trim();
  if (!url) { setError('shorten', 'Введите URL'); return; }
  try {
    const data = await apiRequest('/shorten', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
    let msg = '✅ Ссылка создана';
    try {
      await navigator.clipboard.writeText(data.short_url);
      msg = '✅ Скопировано в буфер обмена';
    } catch {}
    document.getElementById('result').innerHTML = `
      <div class="alert alert-success">
        ${msg}:<br>
        <a href="${data.short_url}" target="_blank" class="short-link">${data.short_url}</a>
      </div>`;
    document.getElementById('long-url').value = '';
    const links = await apiRequest('/my-links');
    renderHistory(links);
    attachDeleteHandlers();
  } catch (e) { setError('shorten', e.message); }
};

window.logout = () => {
  logout();
  document.getElementById('result').innerHTML = '';
  show('step-login');
};
window.showLogin = () => show('step-login');
window.showRegister = () => show('step-register');
window.addEventListener('unauthorized', () => {
  show('step-login');
  setError('login', 'Сессия истекла, войдите заново');
});

init();