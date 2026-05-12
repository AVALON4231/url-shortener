import { escapeHtml } from './utils.js';

export function show(id) {
  document.querySelectorAll('.card').forEach(c => c.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

export function setError(step, message) {
  const el = document.getElementById(step + '-error');
  if (!message) return el.classList.add('hidden');
  el.textContent = message;
  el.classList.remove('hidden');
}

// ВОССТАНОВЛЕНО: полный рендер истории с кликами, датой и кнопкой удаления.
// В упрощённой версии были только заголовок и ссылка.
export function renderHistory(links) {
  const list = document.getElementById('history-list');

  if (!links || !links.length) {
    list.innerHTML = '<p class="text-muted">Пока нет сокращённых ссылок</p>';
    return;
  }

  list.innerHTML = links.map(item => {
    // Форматируем дату
    let dateStr = '';
    if (item.created_at) {
      const d = new Date(item.created_at);
      if (!isNaN(d)) {
        dateStr = d.toLocaleDateString('ru-RU', {
          day: '2-digit', month: '2-digit', year: 'numeric'
        });
      }
    }

    // Форматируем клики
    const clicksStr = item.clicks === 1 ? '1 переход' : `${item.clicks} переходов`;

    // data-атрибуты вместо onclick — app.js вешает обработчики через addEventListener
    return `
      <div class="history-item" id="item-${escapeHtml(item.short_code)}">
        <div class="history-item-body">
          <div class="history-title">${escapeHtml(item.title)}</div>
          <div class="history-short">
            <a href="${item.short_url}" target="_blank">${escapeHtml(item.short_url)}</a>
          </div>
          <div class="history-meta">${clicksStr}${dateStr ? ' · ' + dateStr : ''}</div>
        </div>
        <button
          class="btn-delete"
          data-code="${escapeHtml(item.short_code)}"
          data-url="${escapeHtml(item.short_url)}"
          title="Удалить"
        >✕</button>
      </div>
    `;
  }).join('');
}

// ── Модалка подтверждения удаления ───────────────────────────────
// Работает как Promise: showConfirm() возвращает промис,
// который резолвится в true/false когда пользователь нажимает кнопку.
// Вызывающий код просто делает: const ok = await showConfirm('...')
let _resolve = null;

export function showConfirm(subtitle) {
  document.getElementById('confirm-subtitle').textContent = subtitle;
  document.getElementById('confirm-overlay').classList.add('visible');
  return new Promise(resolve => { _resolve = resolve; });
}

export function confirmResolve(result) {
  document.getElementById('confirm-overlay').classList.remove('visible');
  if (_resolve) { _resolve(result); _resolve = null; }
}

// Инициализация: вешаем обработчики модалки один раз при старте
export function initModal() {
  const overlay = document.getElementById('confirm-overlay');
  // Клик по тёмному фону = отмена
  overlay.addEventListener('click', e => {
    if (e.target === overlay) confirmResolve(false);
  });
  document.getElementById('confirm-cancel').addEventListener('click', () => confirmResolve(false));
  document.getElementById('confirm-ok').addEventListener('click', () => confirmResolve(true));
}
