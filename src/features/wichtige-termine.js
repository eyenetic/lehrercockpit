/**
 * LehrerWichtigeTermine — Wichtige Termine module card for Today (Slice 2)
 *
 * Renders school calendar events fetched from iCal feed (server-side) into a
 * compact module card. Handles loading, error, and empty states.
 *
 * PUBLIC API:
 *   window.LehrerWichtigeTermine.render(containerId, moduleData)
 *     — containerId: ID of the DOM container to render into
 *     — moduleData:  the module result dict from state.data (v2 response),
 *                    or null for loading state
 */
window.LehrerWichtigeTermine = (function() {
  'use strict';

  function _formatDateLabel(isoDate) {
    if (!isoDate) return '';
    try {
      var d = new Date(isoDate + 'T00:00:00');
      return d.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' });
    } catch (_e) { return isoDate; }
  }

  function render(containerId, moduleData) {
    var container = document.getElementById(containerId);
    if (!container) return;

    if (!moduleData) {
      container.innerHTML = _renderShell('Wichtige Termine', _renderLoading());
      return;
    }

    var data = moduleData.data || moduleData;
    var mode = data.mode || '';
    var today_events = Array.isArray(data.today_events) ? data.today_events : [];
    var upcoming_events = Array.isArray(data.upcoming_events) ? data.upcoming_events : [];
    var error = data.error || null;

    if (!moduleData.ok || mode === 'error') {
      container.innerHTML = _renderShell('Wichtige Termine', _renderError(error));
      return;
    }

    var bodyHtml = '';

    if (today_events.length === 0 && upcoming_events.length === 0) {
      bodyHtml = _renderEmpty();
    } else {
      if (today_events.length > 0) {
        bodyHtml += '<div class="wt-section-label">Heute</div>';
        for (var i = 0; i < today_events.length; i++) {
          bodyHtml += _renderEvent(today_events[i]);
        }
      }
      if (upcoming_events.length > 0) {
        bodyHtml += '<div class="wt-section-label">Demnächst</div>';
        var shown = upcoming_events.slice(0, 5);
        for (var j = 0; j < shown.length; j++) {
          bodyHtml += _renderEvent(shown[j]);
        }
      }
    }

    container.innerHTML = _renderShell('Wichtige Termine', bodyHtml);
  }

  function _renderShell(title, bodyContent) {
    return '<div class="module-card wt-card">' +
      '<div class="module-card__header">' +
        '<span class="module-card__title">' + _escHtml(title) + '</span>' +
      '</div>' +
      '<div class="module-card__body">' + bodyContent + '</div>' +
      '</div>';
  }

  function _renderLoading() {
    return '<div class="module-empty-state">Lade Termine\u2026</div>';
  }

  function _renderEmpty() {
    return '<div class="module-empty-state">Keine Termine heute oder in den nächsten 14 Tagen.</div>';
  }

  function _renderError(msg) {
    return '<div class="module-error-state">Termine konnten nicht geladen werden.</div>';
  }

  function _renderEvent(ev) {
    var badge = ev.all_day
      ? '<span class="wt-badge wt-badge--allday">Ganztag</span>'
      : '<span class="wt-badge wt-badge--timed">' + _escHtml(ev.time_label || '') + '</span>';
    var date = ev.start ? '<span class="wt-event__date">' + _escHtml(_formatDateLabel(ev.start)) + '</span>' : '';
    var location = ev.location ? '<span class="wt-event__location">📍 ' + _escHtml(ev.location) + '</span>' : '';
    return '<div class="wt-event">' +
      '<div class="wt-event__meta">' + date + badge + '</div>' +
      '<div class="wt-event__title">' + _escHtml(ev.title || '(Ohne Titel)') + '</div>' +
      location +
      '</div>';
  }

  function _escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { render: render };
})();
