/**
 * LehrerNews — „Neu im Cockpit“.
 *
 * Erscheint jeder Lehrkraft einmal (gemerkt im Konto, also auf allen Geräten)
 * und lässt sich über das Nutzermenü wieder öffnen. Für eine neue Neuigkeit
 * ID und ITEMS hier sowie NEWS_ID in backend/news.py ändern.
 */
(function () {
  'use strict';

  var ID = '2026-11-videos';

  var ITEMS = [
    ['Zwei kurze Videos', 'Was das Cockpit alles kann – und wie man es in wenigen Minuten einrichtet. Das erste siehst du gleich hier oben; gut auch zum Weiterzeigen im Kollegium.'],
    ['Einfacher einrichten', 'Zuerst nur den Stundenplan verbinden, alles andere später. Für itslearning, Dienstmail und das iPhone gibt es jetzt Anleitungen mit Bildern.'],
    ['Eigene Termine und Aufgaben', 'Trag eigene Termine und Aufgaben ein. Was ansteht, zeigt die Kachel „Zu erledigen“ auf Heute.'],
    ['Alle Termine in einem Kalender', 'Unter Termine → „Alle“ siehst du Orgaplan, Klassenarbeiten, itslearning und deinen Stundenplan zusammen – auf Wunsch auch als Abo in deinem eigenen Kalender.'],
    ['Suche über alles', 'Mit der Lupe oben (am Mac ⌘K) findest du Termine, Nachrichten und Ferien sofort.'],
  ];

  var overlay = null;

  function api() { return window.BACKEND_API_URL || ''; }

  function esc(value) {
    return String(value).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  function markSeen() {
    if (!window.MULTIUSER_ENABLED) return;
    fetch(api() + '/api/v2/auth/me/news', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: ID }),
    }).catch(function () { /* beim nächsten Öffnen noch einmal */ });
  }

  function onKey(event) {
    if (event.key === 'Escape' && overlay) close();
  }

  function close() {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    document.removeEventListener('keydown', onKey);
  }

  function open(options) {
    if (overlay) return;
    var first = !!(options && options.first);
    var video = window.LehrerVideo ? window.LehrerVideo.teaser('lehrercockpit', 'Video ansehen') : '';
    overlay = document.createElement('div');
    overlay.className = 'modal-overlay news-overlay';
    overlay.innerHTML = ''
      + '<div class="modal news-modal" role="dialog" aria-modal="true" aria-labelledby="news-title">'
      +   '<div class="modal-header">'
      +     '<h2 class="modal-title" id="news-title">Neu im Cockpit</h2>'
      +     '<button class="modal-close" type="button" data-news-close aria-label="Schließen">✕</button>'
      +   '</div>'
      +   (first ? '<p class="news-lead">Seit deinem letzten Besuch ist einiges dazugekommen:</p>' : '')
      +   video
      +   '<ul class="news-list">' + ITEMS.map(function (item) {
            return '<li><strong>' + esc(item[0]) + '</strong><span>' + esc(item[1]) + '</span></li>';
          }).join('') + '</ul>'
      +   '<p class="news-hint">Du kannst das jederzeit wieder öffnen: Menü → „Neu im Cockpit“.</p>'
      +   '<div class="modal-actions"><button class="btn btn-primary" type="button" data-news-close>Verstanden</button></div>'
      + '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay || event.target.closest('[data-news-close]')) close();
    });
    document.addEventListener('keydown', onKey);
    if (first) markSeen();
    var button = overlay.querySelector('.modal-actions .btn');
    if (button) setTimeout(function () { button.focus({ preventScroll: true }); }, 40);
  }

  /** Called after login: shows the news once if this account has not seen them. */
  function maybeShow(user) {
    var news = user && user.news;
    if (!news || news.seen || news.id !== ID) return;
    setTimeout(function () { open({ first: true }); }, 900);
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-open-news]');
    if (!trigger) return;
    event.preventDefault();
    var sheet = document.getElementById('mobile-more-sheet');
    if (sheet) sheet.hidden = true;
    var popover = document.getElementById('user-menu-popover');
    if (popover) popover.hidden = true;
    open();
  });

  window.LehrerNews = { ID: ID, ITEMS: ITEMS, open: open, close: close, maybeShow: maybeShow };
})();
