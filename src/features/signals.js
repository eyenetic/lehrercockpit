/**
 * LehrerSignals — "Neu & geändert" inside the Tagesbriefing card.
 *
 * Data: data.signals from GET /api/v2/dashboard/data (backend/signal_store.py):
 *   { items: [...], new_ids: [...], new_count, classes, classes_known }
 * Actions: POST /api/v2/signals/state, POST /api/v2/signals/seen.
 * Classes chosen in "Heute anpassen" are mirrored to PUT /api/v2/signals/preferences.
 *
 * Exposes window.LehrerSignals = { init, render, syncPreferredClasses }.
 */
(function () {
  'use strict';

  var VISIBLE_LIMIT = 6;
  var SYNCED_CLASSES_KEY = 'lc.signals.syncedClasses';
  var KIND_LABELS = {
    entfall: 'Entfall', klassenarbeit: 'Klassenarbeit', termin: 'Termin',
    frist: 'Frist', datei: 'Datei', nachricht: 'Nachricht',
  };

  var _getData = function () { return {}; };
  var _expanded = false;
  var _hidden = {}; // ids acted on in this session (optimistic)

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function _api(path, body, method) {
    return fetch((window.BACKEND_API_URL || '') + path, {
      method: method || 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    });
  }

  function _dayLabel(isoDate) {
    if (!isoDate) return '';
    var day = new Date(isoDate + 'T00:00:00');
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var diff = Math.round((day - today) / 86400000);
    if (diff === 0) return 'heute';
    if (diff === 1) return 'morgen';
    if (diff === -1) return 'gestern';
    if (diff > 1 && diff <= 6) return day.toLocaleDateString('de-DE', { weekday: 'long' });
    return day.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  }

  function _freshItems(signals) {
    var byId = {};
    (signals.items || []).forEach(function (item) { byId[item.id] = item; });
    return (signals.new_ids || [])
      .map(function (id) { return byId[id]; })
      .filter(function (item) { return item && !_hidden[item.id]; });
  }

  function _itemHtml(item) {
    var title = item.url
      ? '<a href="' + esc(item.url) + '" target="_blank" rel="noopener noreferrer">' + esc(item.title) + '</a>'
      : esc(item.title);
    var when = [_dayLabel(item.date), item.time].filter(Boolean).join(', ');
    var meta = [when, item.detail].filter(Boolean).join(' · ');
    return '<article class="signal-item signal-' + esc(item.kind) + '" data-signal-id="' + esc(item.id) + '">' +
      '<div class="signal-main">' +
        '<div class="signal-tags"><span class="signal-kind">' + esc(KIND_LABELS[item.kind] || item.kind) + '</span>' +
        (item.state && item.state.changed ? '<span class="signal-changed">geändert</span>' : '') + '</div>' +
        '<p class="signal-title">' + title + '</p>' +
        (meta ? '<p class="signal-meta">' + esc(meta) + '</p>' : '') +
      '</div>' +
      '<div class="signal-actions">' +
        '<button type="button" data-signal-action="done" aria-label="Erledigt" title="Erledigt">✓</button>' +
        '<button type="button" data-signal-action="snooze" aria-label="Morgen wieder zeigen" title="Morgen wieder zeigen">⏰</button>' +
        '<button type="button" data-signal-action="hide" aria-label="Ausblenden" title="Ausblenden">×</button>' +
      '</div>' +
    '</article>';
  }

  function render() {
    var panel = document.getElementById('signals-panel');
    var list = document.getElementById('signals-list');
    var hint = document.getElementById('signals-hint');
    var markAll = document.getElementById('signals-mark-all');
    if (!panel || !list) return;
    var signals = (_getData() || {}).signals;
    if (!signals) { panel.hidden = true; return; }
    panel.hidden = false;

    var fresh = _freshItems(signals);
    var visible = _expanded ? fresh : fresh.slice(0, VISIBLE_LIMIT);
    if (markAll) markAll.hidden = !fresh.length;
    list.innerHTML = fresh.length
      ? visible.map(_itemHtml).join('') +
        (fresh.length > VISIBLE_LIMIT
          ? '<button type="button" class="signals-more" data-signals-toggle>' +
            (_expanded ? 'Weniger anzeigen' : '+ ' + (fresh.length - VISIBLE_LIMIT) + ' weitere') + '</button>'
          : '')
      : '<p class="signals-empty">Nichts Neues seit deinem letzten Besuch.</p>';

    var classworkLoaded = ((_getData().planDigest || {}).classwork || {}).status === 'ok';
    if (hint) {
      hint.hidden = !(classworkLoaded && !signals.classes_known);
      hint.textContent = 'Tipp: Wähle unter „Heute anpassen“ deine Klassen – dann erscheinen ihre Klassenarbeiten hier.';
    }
  }

  function _act(id, action) {
    _hidden[id] = true;
    render();
    _api('/api/v2/signals/state', { id: id, action: action }).catch(function () {
      delete _hidden[id];
      render();
    });
  }

  function _markAll() {
    var signals = (_getData() || {}).signals;
    if (!signals) return;
    var ids = _freshItems(signals).map(function (item) { return item.id; });
    ids.forEach(function (id) { _hidden[id] = true; });
    render();
    _api('/api/v2/signals/seen', { ids: ids }).catch(function () {
      ids.forEach(function (id) { delete _hidden[id]; });
      render();
    });
  }

  /** Mirror the classes chosen in "Heute anpassen" to the server (for signals and push). */
  function syncPreferredClasses(classes) {
    if (!window.MULTIUSER_ENABLED) return;
    var cleaned = (classes || []).filter(Boolean).map(String).sort();
    var key = JSON.stringify(cleaned);
    var synced = null;
    try { synced = localStorage.getItem(SYNCED_CLASSES_KEY); } catch (e) { /* ignore */ }
    if (synced === key) return;
    _api('/api/v2/signals/preferences', { classes: cleaned }, 'PUT')
      .then(function () { try { localStorage.setItem(SYNCED_CLASSES_KEY, key); } catch (e) { /* ignore */ } })
      .catch(function () { /* retried on the next load */ });
  }

  function init(options) {
    options = options || {};
    if (typeof options.getData === 'function') _getData = options.getData;
    var panel = document.getElementById('signals-panel');
    if (!panel || panel.dataset.bound) return;
    panel.dataset.bound = '1';
    panel.addEventListener('click', function (event) {
      var toggle = event.target.closest('[data-signals-toggle]');
      if (toggle) { _expanded = !_expanded; render(); return; }
      if (event.target.closest('#signals-mark-all')) { _markAll(); return; }
      var button = event.target.closest('[data-signal-action]');
      if (!button) return;
      var item = button.closest('[data-signal-id]');
      if (item) _act(item.getAttribute('data-signal-id'), button.getAttribute('data-signal-action'));
    });
  }

  window.LehrerSignals = { init: init, render: render, syncPreferredClasses: syncPreferredClasses };
})();
