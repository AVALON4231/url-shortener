import { login, register, logout } from './auth.js';
import { apiRequest } from './api.js';
import { show, setError, renderHistory, showConfirm, initModal } from './ui.js';

// Индикатор загрузки
function loading(show) {
  document.getElementById('loading-overlay').classList.toggle('hidden', !show);
}

async function init() {
  initModal();

  const token = localStorage.getItem('shortener_token');
  if (token) {
    await loadApp();
  } else {
    show('step-login');
  }
}

async function loadApp() {
  show('step-shorten');
  try {
    const links = await apiRequest('/my-links');
    renderHistory(links);
    attachDeleteHandlers();
  } catch (e) {
    // 401 обрабатывается в api.js через событие 'unauthorized'
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
    loading(true);                          // индикатор при удалении
    await apiRequest(`/my-links/${shortCode}`, { method: 'DELETE' });

    const el = document.getElementById(`item-${shortCode}`);
    if (el) el.remove();

    const list = document.getElementById('history-list');
    if (!list.querySelector('.history-item')) {
      list.innerHTML = '<p class="text-muted">Пока нет сокращённых ссылок</p>';
    }
  } catch (e) {
    console.error('Ошибка удаления:', e.message);
  } finally {
    loading(false);
  }
}

// --- Глобальные обработчики ---

window.login = async () => {
  setError('login', '');
  try {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (!email || !password) { setError('login', 'Заполните все поля'); return; }
    loading(true);
    await login(email, password);
    await loadApp();
  } catch (e) {
    setError('login', e.message);
  } finally {
    loading(false);
  }
};

window.register = async () => {
  setError('register', '');
  try {
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    if (!email || !password) { setError('register', 'Заполните все поля'); return; }
    loading(true);
    await register(email, password);
    await loadApp();
  } catch (e) {
    setError('register', e.message);
  } finally {
    loading(false);
  }
};

window.shorten = async () => {
  setError('shorten', '');
  document.getElementById('result').innerHTML = '';

  try {
    const url = document.getElementById('long-url').value.trim();
    if (!url) { setError('shorten', 'Введите URL'); return; }

    loading(true);
    const data = await apiRequest('/shorten', {
      method: 'POST',
      body: JSON.stringify({ url })
    });

    let message = '';
    try {
      await navigator.clipboard.writeText(data.short_url);
      message = '✅ Скопировано в буфер обмена';
    } catch {
      message = '✅ Ссылка создана';
    }

    document.getElementById('result').innerHTML = `
      <div class="alert alert-success">
        ${message}:<br>
        <a href="${data.short_url}" target="_blank" class="short-link">${data.short_url}</a>
      </div>`;

    document.getElementById('long-url').value = '';
    await loadApp();
  } catch (e) {
    setError('shorten', e.message);
  } finally {
    loading(false);
  }
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