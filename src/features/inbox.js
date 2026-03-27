/**
 * src/features/inbox.js — Inbox, priorities, and sources rendering
 *
 * Extracted from src/app.js. Owns:
 *   - renderPriorities()        — priority item list
 *   - renderSources()           — source status cards
 *   - renderChannelFilters()    — mail/itslearning filter buttons
 *   - renderMessages()          — inbox message list
 *   - renderDocumentMonitor()   — document monitor list
 *   - priorityLabel()           — priority → German label
 *   - messagePriorityClass()    — priority → CSS class
 *   - compareMessageTime()      — HH:MM time sort comparator
 *   - statusLabel()             — source status → German label
 *   - monitorStatusLabel()      — monitor status → German label
 *   - monitorStatusClass()      — monitor status → CSS class
 *
 * Initialization:
 *   window.LehrerInbox.init(state, elements, {
 *     getData, getRelevantInboxMessages, getVisiblePanelItems, setExpandableMeta
 *   })
 *
 * Exports (to window.LehrerInbox):
 *   init, renderPriorities, renderSources, renderChannelFilters,
 *   renderMessages, renderDocumentMonitor
 */
var LehrerInbox = (function () {
  'use strict';

  var _state = null;
  var _elements = null;
  var _getData = null;
  var _getRelevantInboxMessages = null;
  var _getVisiblePanelItems = null;
  var _setExpandableMeta = null;

  var channelLabels = {
    mail: 'Dienstmail',
    itslearning: 'itslearning',
  };

  function init(state, elements, callbacks) {
    _state = state;
    _elements = elements;
    _getData = callbacks.getData;
    _getRelevantInboxMessages = callbacks.getRelevantInboxMessages;
    _getVisiblePanelItems = callbacks.getVisiblePanelItems;
    _setExpandableMeta = callbacks.setExpandableMeta;
  }

  // ── Label helpers ────────────────────────────────────────────────────────────

  function priorityLabel(priority) {
    return ({ critical: 'kritisch', high: 'wichtig', medium: 'mittel', low: 'niedrig' }[priority] || priority);
  }

  function messagePriorityClass(priority) {
    return ({ critical: 'critical', high: 'high', medium: '', low: 'low' }[priority] || '');
  }

  function compareMessageTime(left, right) {
    var lParts = String(left || '00:00').split(':').map(function (v) { return Number(v) || 0; });
    var rParts = String(right || '00:00').split(':').map(function (v) { return Number(v) || 0; });
    return (lParts[0] * 60 + (lParts[1] || 0)) - (rParts[0] * 60 + (rParts[1] || 0));
  }

  function statusLabel(status) {
    return ({ ok: 'bereit', warning: 'vorbereitet', error: 'blockiert' }[status] || status);
  }

  function monitorStatusLabel(status) {
    return ({ tracked: 'beobachtet', changed: 'geaendert', warning: 'blockiert', error: 'offline' }[status] || status);
  }

  function monitorStatusClass(status) {
    return ({ tracked: 'low', changed: 'high', warning: 'high', error: 'critical' }[status] || '');
  }

  // ── Render functions ─────────────────────────────────────────────────────────

  function renderPriorities() {
    if (!_elements || !_elements.priorityList) return;
    var data = _getData();
    _elements.priorityList.innerHTML = (data.priorities || []).length
      ? data.priorities.map(function (item) {
          return '<article class="priority-item">'
            + '<div class="priority-top">'
            + '<strong>' + item.title + '</strong>'
            + '<span class="meta-tag ' + item.priority + '">' + priorityLabel(item.priority) + '</span>'
            + '</div>'
            + '<p class="priority-copy">' + item.detail + '</p>'
            + '<div class="meta-row">'
            + '<span class="meta-tag">' + item.source + '</span>'
            + '<span class="meta-tag">' + item.due + '</span>'
            + '</div>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Noch keine priorisierten Hinweise verfuegbar.</div>';
  }

  function renderSources() {
    if (!_elements || !_elements.sourceList) return;
    var data = _getData();
    _elements.sourceList.innerHTML = (data.sources || []).length
      ? data.sources.map(function (source) {
          return '<article class="source-item">'
            + '<div class="source-top">'
            + '<div>'
            + '<strong>' + source.name + '</strong>'
            + '<p class="source-detail">' + source.type + ' - letzter Sync ' + source.lastSync + ' - ' + source.cadence + '</p>'
            + '</div>'
            + '<span class="source-status ' + source.status + '">' + statusLabel(source.status) + '</span>'
            + '</div>'
            + '<p class="source-detail">' + source.detail + '</p>'
            + '<p class="source-detail"><strong>Naechster Schritt:</strong> ' + source.nextStep + '</p>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Noch keine Quellen eingerichtet.</div>';
  }

  function renderChannelFilters() {
    if (!_elements || !_elements.channelFilters) return;
    var availableChannels = _getRelevantInboxMessages()
      .map(function (msg) { return msg.channel; })
      .filter(function (ch, idx, arr) { return ch && arr.indexOf(ch) === idx; });

    if (!availableChannels.length) {
      _elements.channelFilters.hidden = true;
      _elements.channelFilters.innerHTML = '';
      return;
    }

    if (!availableChannels.includes(_state.selectedChannel)) {
      _state.selectedChannel = availableChannels[0];
    }

    _elements.channelFilters.hidden = availableChannels.length <= 1;
    _elements.channelFilters.innerHTML = availableChannels.map(function (id) {
      return '<button class="filter-button ' + (_state.selectedChannel === id ? 'active' : '') + '" type="button" data-channel="' + id + '">'
        + (channelLabels[id] || id)
        + '</button>';
    }).join('');

    _elements.channelFilters.querySelectorAll('[data-channel]').forEach(function (button) {
      button.addEventListener('click', function () {
        _state.selectedChannel = button.dataset.channel;
        renderChannelFilters();
        renderMessages();
      });
    });
  }

  function renderMessages() {
    if (!_elements || !_elements.messageList) return;
    var filteredMessages = _getRelevantInboxMessages()
      .filter(function (msg) { return msg.channel === _state.selectedChannel; })
      .sort(function (left, right) { return compareMessageTime(right.timestamp, left.timestamp); });
    var visibleMessages = _getVisiblePanelItems(filteredMessages, 'inbox');
    _setExpandableMeta(_elements.messageList, filteredMessages.length, visibleMessages.length);

    _elements.messageList.innerHTML = filteredMessages.length
      ? visibleMessages.map(function (message) {
          return '<article class="message-item">'
            + '<div class="message-top">'
            + '<div>'
            + '<strong>' + message.title + '</strong>'
            + '<p class="message-snippet">' + message.sender + ' - ' + message.timestamp + '</p>'
            + '</div>'
            + '<span class="meta-tag ' + messagePriorityClass(message.priority) + '">' + (message.unread ? 'neu' : 'gesehen') + '</span>'
            + '</div>'
            + '<p class="message-snippet">' + message.snippet + '</p>'
            + '<div class="meta-row">'
            + '<span class="meta-tag">' + message.channelLabel + '</span>'
            + '<span class="meta-tag">' + priorityLabel(message.priority) + '</span>'
            + '</div>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Fuer diesen Kanal liegen gerade keine Hinweise vor.</div>';
  }

  function renderDocumentMonitor() {
    if (!_elements || !_elements.monitorList) return;
    var data = _getData();
    _elements.monitorList.innerHTML = (data.documentMonitor || []).length
      ? data.documentMonitor.map(function (item) {
          return '<article class="priority-item">'
            + '<div class="priority-top">'
            + '<strong>' + item.title + '</strong>'
            + '<span class="meta-tag ' + monitorStatusClass(item.status) + '">' + monitorStatusLabel(item.status) + '</span>'
            + '</div>'
            + '<p class="priority-copy">' + item.detail + '</p>'
            + '<div class="meta-row">'
            + '<span class="meta-tag">' + item.type + '</span>'
            + '<span class="meta-tag">' + item.checkedAt + '</span>'
            + '</div>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Noch keine beobachteten Dokumente konfiguriert.</div>';
  }

  // ── Briefing helper ──────────────────────────────────────────────────────────

  /**
   * Pick a short inbox briefing string from dashboard data.
   * Used by renderBriefing() in app.js to build the overview card.
   * @param {object} data - dashboard data
   * @returns {string} briefing text, or "" if no unread messages
   */
  function pickInboxBriefing(data) {
    var unread = (data.messages || []).filter(function (message) { return message.unread; });
    if (!unread.length) return '';
    var mailMessages = unread.filter(function (message) { return message.channel === 'mail'; });
    if (mailMessages.length) {
      return mailMessages.length + ' neue Mail' + (mailMessages.length === 1 ? '' : 's') +
        ', zuerst: ' + mailMessages[0].title + '.';
    }
    return unread.length + ' neue Hinweise, zuerst: ' + unread[0].title + '.';
  }

  return {
    init: init,
    renderPriorities: renderPriorities,
    renderSources: renderSources,
    renderChannelFilters: renderChannelFilters,
    renderMessages: renderMessages,
    renderDocumentMonitor: renderDocumentMonitor,
    pickInboxBriefing: pickInboxBriefing,
  };
})();

window.LehrerInbox = LehrerInbox;
