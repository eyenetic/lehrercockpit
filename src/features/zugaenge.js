/**
 * LehrerZugaenge — grouped access launcher for Today.
 *
 * Uses dashboard quickLinks as primary source so Today shows the same complete
 * access set as the backend provides. Falls back to a few well-known base URLs.
 */
window.LehrerZugaenge = (function() {
  'use strict';

  var _dashboardData = {};

  var LINK_ORDER = [
    'Berliner Schulportal',
    'Schulportal',
    'Dienstmail',
    'WebUntis',
    'itslearning',
    'Orgaplan',
    'Nextcloud',
    'Teamordner',
    'Fehlzeiten Q1/Q2',
    'Fehlzeiten Q3/Q4',
    'Schulkalender',
    'Stunden- und Pausenzeiten',
    'Kontakt Lehrkraefte',
  ];

  var TITLE_GROUPS = {
    'Berliner Schulportal': 'Verwaltung',
    'Schulportal': 'Verwaltung',
    'Orgaplan': 'Verwaltung',
    'Schulkalender': 'Verwaltung',
    'Stunden- und Pausenzeiten': 'Verwaltung',
    'WebUntis': 'Unterricht',
    'itslearning': 'Unterricht',
    'Dienstmail': 'Kommunikation',
    'Kontakt Lehrkraefte': 'Kommunikation',
    'Nextcloud': 'Dateien',
    'Teamordner': 'Dateien',
    'Fehlzeiten Q1/Q2': 'Dateien',
    'Fehlzeiten Q3/Q4': 'Dateien',
  };

  var GROUP_ORDER = ['Unterricht', 'Kommunikation', 'Verwaltung', 'Dateien'];

  function init(dashboardData) {
    _dashboardData = dashboardData || {};
  }

  function render(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    var links = _buildLinks();
    if (!links.length) {
      container.innerHTML = '<div class="empty-state">Noch keine Zugänge konfiguriert.</div>';
      return;
    }

    var groups = {};
    links.forEach(function(link) {
      if (!groups[link.group]) groups[link.group] = [];
      groups[link.group].push(link);
    });

    var html = '<div class="zugaenge-card">';
    GROUP_ORDER.filter(function(groupName) { return Array.isArray(groups[groupName]) && groups[groupName].length; }).forEach(function(groupName) {
      html += '<section class="zugaenge-group zugaenge-group--' + _slug(groupName) + '">';
      html += '<div class="zugaenge-group__label">' + _escHtml(groupName) + '</div>';
      html += '<div class="zugaenge-group__links">';
      groups[groupName].forEach(function(link) {
        html += '<a href="' + _escHtml(link.url) + '" target="_blank" rel="noopener noreferrer" class="zugaenge-link" title="' + _escHtml(link.note || link.label) + '">';
        html += '<span class="zugaenge-link__icon" aria-hidden="true">' + _escHtml(link.icon) + '</span>';
        html += '<span class="zugaenge-link__label">' + _escHtml(link.label) + '</span>';
        html += '</a>';
      });
      html += '</div></section>';
    });
    html += '</div>';
    container.innerHTML = html;
  }

  function _buildLinks() {
    var quickLinks = Array.isArray(_dashboardData.quickLinks) ? _dashboardData.quickLinks.slice() : [];
    var base = _dashboardData.base || {};
    var fallbacks = [
      { title: 'Berliner Schulportal', url: base.schoolportal_url, kind: 'Portal', note: 'Zentraler Einstieg in Berliner Schuldienste' },
      { title: 'WebUntis', url: base.webuntis_url, kind: 'Planung', note: 'Stundenplan und Vertretungen' },
      { title: 'itslearning', url: base.itslearning_base_url, kind: 'Lernen', note: 'Kurse und Updates' },
      { title: 'Orgaplan', url: base.orgaplan_pdf_url || base.orgaplan_url, kind: 'PDF', note: 'Aktueller Orgaplan' },
      { title: 'Nextcloud', url: base.nextcloud_workspace_url || base.nextcloud_base_url, kind: 'Dateien', note: 'Dateien und Teamordner' },
      { title: 'Fehlzeiten Q1/Q2', url: base.fehlzeiten_11_url, kind: 'Dateien', note: 'Fehlzeiten 11. Klasse' },
      { title: 'Fehlzeiten Q3/Q4', url: base.fehlzeiten_12_url, kind: 'Dateien', note: 'Fehlzeiten 12. Klasse' },
    ];

    fallbacks.forEach(function(link) {
      if (!link.url) return;
      if (quickLinks.some(function(existing) { return existing.title === link.title; })) return;
      quickLinks.push({
        id: _slug(link.title),
        title: link.title,
        url: link.url,
        kind: link.kind,
        note: link.note,
      });
    });

    return quickLinks
      .filter(function(link) { return link && link.url && link.title; })
      .sort(_compareLinks)
      .map(function(link) {
        return {
          label: link.title,
          url: link.url,
          note: link.note || '',
          icon: _iconFor(link.title, link.kind),
          group: _groupFor(link.title, link.kind),
        };
      });
  }

  function _compareLinks(left, right) {
    var leftIndex = LINK_ORDER.indexOf(left.title);
    var rightIndex = LINK_ORDER.indexOf(right.title);
    if (leftIndex !== -1 || rightIndex !== -1) {
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    }
    return String(left.title || '').localeCompare(String(right.title || ''), 'de');
  }

  function _groupFor(title, kind) {
    if (TITLE_GROUPS[title]) return TITLE_GROUPS[title];
    if (kind === 'Nextcloud' || kind === 'Dateien') return 'Dateien';
    if (kind === 'Mail') return 'Kommunikation';
    if (kind === 'Lernen' || kind === 'Planung') return 'Unterricht';
    return 'Verwaltung';
  }

  function _iconFor(title, kind) {
    if (title === 'WebUntis') return '📅';
    if (title === 'itslearning') return '📚';
    if (title === 'Dienstmail') return '✉️';
    if (title === 'Orgaplan') return '📋';
    if (title === 'Nextcloud' || kind === 'Nextcloud') return '☁️';
    if (title.indexOf('Fehlzeiten') === 0) return '📊';
    if (title === 'Berliner Schulportal' || title === 'Schulportal') return '🏫';
    if (title === 'Teamordner') return '🗂️';
    if (title === 'Schulkalender') return '🗓️';
    if (title === 'Stunden- und Pausenzeiten') return '⏱️';
    if (title === 'Kontakt Lehrkraefte') return '👥';
    return '↗';
  }

  function _slug(value) {
    return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  }

  function _escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { init: init, render: render };
})();
