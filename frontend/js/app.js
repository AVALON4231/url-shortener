import { login, register, logout } from './auth.js';
import { apiRequest } from './api.js';
import { show, setError, renderHistory, showConfirm, initModal } from './ui.js';

async function init() {
  // Инициализируем модалку один раз при старте страницы
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

// Вешаем обработчики на кнопки удаления после каждого рендера истории.
// Используем data-атрибуты вместо onclick в HTML — это чище.
function attachDeleteHandlers() {
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', () => {
      deleteLink(btn.dataset.code, btn.dataset.url);
    });
  });
}

// ДОБАВЛЕНО: удаление ссылки с кастомной модалкой подтверждения.
// Ждём ответа пользователя через await showConfirm(),
// затем DELETE-запрос, затем убираем карточку из DOM.
async function deleteLink(shortCode, shortUrl) {
  const confirmed = await showConfirm(shortUrl);
  if (!confirmed) return;

  try {
    await apiRequest(`/my-links/${shortCode}`, { method: 'DELETE' });

    const el = document.getElementById(`item-${shortCode}`);
    if (el) el.remove();

    // Если список опустел — показываем заглушку
    const list = document.getElementById('history-list');
    if (!list.querySelector('.history-item')) {
      list.innerHTML = '<p class="text-muted">Пока нет сокращённых ссылок</p>';
    }
  } catch (e) {
    console.error('Ошибка удаления:', e.message);
  }
}

// --- Глобальные обработчики для кнопок в HTML ---

window.login = async () => {
  setError('login', '');
  try {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (!email || !password) { setError('login', 'Заполните все поля'); return; }
    await login(email, password);
    await loadApp();
  } catch (e) {
    setError('login', e.message);
  }
};

window.register = async () => {
  setError('register', '');
  try {
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    if (!email || !password) { setError('register', 'Заполните все поля'); return; }
    await register(email, password);
    await loadApp();
  } catch (e) {
    setError('register', e.message);
  }
};

window.shorten = async () => {
  setError('shorten', '');
  document.getElementById('result').innerHTML = '';

  try {
    const url = document.getElementById('long-url').value.trim();
    if (!url) { setError('shorten', 'Введите URL'); return; }

    const data = await apiRequest('/shorten', {
      method: 'POST',
      body: JSON.stringify({ url })
    });

    // ИСПРАВЛЕНО: clipboard.writeText требует HTTPS и разрешения — оборачиваем в try/catch.
    // Если clipboard недоступен — просто показываем ссылку без копирования.
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
  }
};

window.logout = () => {
  logout();
  document.getElementById('result').innerHTML = '';
  show('step-login');
};

window.showLogin = () => show('step-login');
window.showRegister = () => show('step-register');

// api.js бросает это событие при получении 401
window.addEventListener('unauthorized', () => {
  show('step-login');
  setError('login', 'Сессия истекла, войдите заново');
});

init();
