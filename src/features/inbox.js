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
  var _tabsInitialized = false;

  var INBOX_TAB_STORAGE_KEY = 'lehrerCockpit.inbox.activeTab';

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

  function compareMessages(left, right) {
    var leftKey = left && left.sortKey ? String(left.sortKey) : '';
    var rightKey = right && right.sortKey ? String(right.sortKey) : '';
    if (leftKey && rightKey && leftKey !== rightKey) {
      return rightKey.localeCompare(leftKey);
    }
    return compareMessageTime(right && right.timestamp, left && left.timestamp);
  }

  function statusLabel(status) {
    return ({ ok: 'bereit', warning: 'vorbereitet', error: 'blockiert' }[status] || status);
  }

  function monitorStatusLabel(status) {
    return ({ tracked: 'beobachtet', changed: 'geändert', warning: 'blockiert', error: 'offline' }[status] || status);
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
      : '<div class="empty-state">Noch keine priorisierten Hinweise verfügbar.</div>';
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
            + '<p class="source-detail"><strong>Nächster Schritt:</strong> ' + source.nextStep + '</p>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Noch keine Quellen eingerichtet.</div>';
  }

  function renderMessages() {
    // Dienstmail-Tab entfernt — delegiert an renderItslearningTab für Live-Updates
    renderItslearningTab();
    renderItslearningCalendar();
    renderNextcloudFeed();
  }

  function _relativeTime(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return '';
    var minutes = Math.round((Date.now() - date.getTime()) / 60000);
    if (minutes < 1) return 'gerade eben';
    if (minutes < 60) return 'vor ' + minutes + ' Min.';
    var hours = Math.round(minutes / 60);
    if (hours < 24) return 'vor ' + hours + ' Std.';
    var days = Math.round(hours / 24);
    if (days === 1) return 'gestern';
    if (days < 7) return 'vor ' + days + ' Tagen';
    return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  }

  /**
   * "Neu in Nextcloud": notifications plus recent activity of other people
   * (changed and shared files, comments). Hidden when Nextcloud is not connected.
   */
  function renderNextcloudFeed() {
    var block = document.getElementById('nextcloud-feed-block');
    var list = document.getElementById('nextcloud-feed-list');
    if (!block || !list || !_getData) return;
    var feed = _getData().nextcloudFeed;
    if (!feed) { block.hidden = true; return; }
    block.hidden = false;
    if (feed.error) {
      list.innerHTML = '<div class="empty-state">' + esc(feed.error) + '</div>';
      return;
    }
    var items = (feed.notifications || []).map(function (n) {
      return { time: n.time, title: n.subject, detail: n.message, link: n.link, tag: 'Hinweis' };
    }).concat((feed.activity || []).map(function (a) {
      return { time: a.time, title: a.subject, detail: '', link: a.link, tag: a.label || 'Datei' };
    }));
    items.sort(function (left, right) { return String(right.time).localeCompare(String(left.time)); });
    items = items.slice(0, 8);
    if (!items.length) {
      list.innerHTML = '<div class="empty-state">Nichts Neues in euren geteilten Ordnern.</div>';
      return;
    }
    list.innerHTML = items.map(function (item) {
      var title = item.link
        ? '<a href="' + esc(item.link) + '" target="_blank" rel="noopener noreferrer">' + esc(item.title) + '</a>'
        : esc(item.title);
      return '<article class="feed-item">'
        + '<div class="feed-item-main"><p class="calendar-item-title">' + title + '</p>'
        + (item.detail ? '<p class="message-snippet">' + esc(item.detail) + '</p>' : '')
        + '</div>'
        + '<div class="feed-item-meta"><span class="meta-tag">' + esc(item.tag) + '</span>'
        + '<span>' + esc(_relativeTime(item.time)) + '</span></div>'
        + '</article>';
    }).join('');
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function _dayLabel(date, today) {
    var dayMs = 86400000;
    var startOf = function (d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); };
    var diff = Math.round((startOf(date) - startOf(today)) / dayMs);
    if (diff === 0) return 'Heute';
    if (diff === 1) return 'Morgen';
    return date.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
  }

  function _timeLabel(event, start) {
    var time = start.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    if (event.kind === 'todo') return 'Abgabe bis ' + time;
    if (event.allDay) return 'ganztägig';
    return time;
  }

  /**
   * Upcoming dates and deadlines from the itslearning calendar subscription.
   * Hidden when no calendar is connected.
   */
  function renderItslearningCalendar() {
    var block = document.getElementById('itslearning-calendar-block');
    var list = document.getElementById('itslearning-calendar-list');
    if (!block || !list || !_getData) return;
    var calendar = _getData().itslearningCalendar;
    if (!calendar) { block.hidden = true; return; }
    block.hidden = false;
    if (!calendar.ok) {
      list.innerHTML = '<div class="empty-state">' + esc(calendar.error || 'Kalender konnte nicht geladen werden.') + '</div>';
      return;
    }
    var events = (calendar.events || []).slice(0, 12);
    if (!events.length) {
      list.innerHTML = '<div class="empty-state">Keine Termine oder Abgaben in den nächsten drei Wochen.</div>';
      return;
    }
    var today = new Date();
    list.innerHTML = events.map(function (event) {
      var start = new Date(event.start);
      var title = event.url
        ? '<a href="' + esc(event.url) + '" target="_blank" rel="noopener noreferrer">' + esc(event.title) + '</a>'
        : esc(event.title);
      return '<article class="calendar-item' + (event.kind === 'todo' ? ' is-deadline' : '') + '">'
        + '<div class="calendar-item-when"><strong>' + esc(_dayLabel(start, today)) + '</strong>'
        + '<span>' + esc(_timeLabel(event, start)) + '</span></div>'
        + '<div class="calendar-item-body"><p class="calendar-item-title">' + title + '</p>'
        + (event.location ? '<p class="message-snippet">' + esc(event.location) + '</p>' : '')
        + '</div></article>';
    }).join('');
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

  // ── Inbox tabs (Slice 3) ─────────────────────────────────────────────────────

  /**
   * Render itslearning messages into #message-list-itslearning.
   * Called once the itslearning tab is activated.
   */
  function renderItslearningTab() {
    var container = document.getElementById('message-list-itslearning');
    if (!container) return;
    var messages = [];
    if (_getRelevantInboxMessages) {
      messages = _getRelevantInboxMessages()
        .filter(function (msg) { return msg.channel === 'itslearning'; })
        .sort(compareMessages);
    }
    container.classList.remove('is-collapsed');
    container.classList.add('is-expanded');
    container.innerHTML = messages.length
      ? messages.map(function (message) {
          return '<article class="message-item">'
            + '<div class="message-top">'
            + '<div>'
            + '<strong>' + esc(message.title) + '</strong>'
            + '<p class="message-snippet">' + esc(message.sender) + ' - ' + esc(message.timestamp) + '</p>'
            + '</div>'
            + '<span class="meta-tag ' + messagePriorityClass(message.priority) + '">' + (message.unread ? 'neu' : 'gesehen') + '</span>'
            + '</div>'
            + '<p class="message-snippet">' + esc(message.snippet) + '</p>'
            + '<div class="meta-row">'
            + '<span class="meta-tag">itslearning</span>'
            + '<span class="meta-tag">' + priorityLabel(message.priority) + '</span>'
            + '</div>'
            + '</article>';
        }).join('')
      : (_getData && _getData().itslearningMode === 'calendar'
          ? '<p class="empty-state">Nachrichten aus itslearning kannst du optional unter „Verbindungen“ per Login dazuholen.</p>'
          : '<div class="empty-state">Keine neuen Nachrichten in itslearning.</div>');
  }

  /**
   * Update unread count badges on the tab buttons.
   * @param {Array} messages - array of message objects with .channel and .unread fields
   */
  function renderBadges(messages) {
    var allMessages = messages || (_getRelevantInboxMessages ? _getRelevantInboxMessages() : []);
    var mailUnread = allMessages.filter(function (m) { return m.channel === 'mail' && m.unread; }).length;
    var itslUnread = allMessages.filter(function (m) { return m.channel === 'itslearning' && m.unread; }).length;

    var mailBadge = document.getElementById('inbox-badge-mail');
    var itslBadge = document.getElementById('inbox-badge-itslearning');

    if (mailBadge) {
      mailBadge.textContent = mailUnread > 0 ? String(mailUnread) : '';
      mailBadge.hidden = mailUnread === 0;
    }
    if (itslBadge) {
      itslBadge.textContent = itslUnread > 0 ? String(itslUnread) : '';
      itslBadge.hidden = itslUnread === 0;
    }
  }

  /**
   * Activate a named tab ('mail' or 'itslearning'), updating DOM state.
   */
  function _activateTab(tabName) {
    var tabBar = document.querySelector('.inbox-tabs');
    var panels = document.querySelectorAll('.inbox-tab-panel');
    if (!tabBar) return;

    tabBar.querySelectorAll('.inbox-tab').forEach(function (btn) {
      var isActive = btn.dataset.inboxTab === tabName;
      btn.classList.toggle('inbox-tab--active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    panels.forEach(function (panel) {
      var isActive = panel.dataset.inboxPanel === tabName;
      panel.classList.toggle('inbox-tab-panel--active', isActive);
    });

    // Render itslearning content when that tab is activated
    if (tabName === 'itslearning') {
      renderItslearningTab();
    }

    try { localStorage.setItem(INBOX_TAB_STORAGE_KEY, tabName); } catch (_e) {}
  }

  /**
   * Initialize inbox — renders itslearning messages directly (no tabs).
   * Safe to call multiple times — idempotent.
   */
  function initInboxTabs() {
    if (_tabsInitialized) return;
    _tabsInitialized = true;
    renderItslearningTab();
  }

  return {
    init: init,
    renderPriorities: renderPriorities,
    renderSources: renderSources,
    renderMessages: renderMessages,
    renderDocumentMonitor: renderDocumentMonitor,
    pickInboxBriefing: pickInboxBriefing,
    initInboxTabs: initInboxTabs,
    renderBadges: renderBadges,
    renderItslearningTab: renderItslearningTab,
    renderItslearningCalendar: renderItslearningCalendar,
    renderNextcloudFeed: renderNextcloudFeed,
  };
})();

window.LehrerInbox = LehrerInbox;
