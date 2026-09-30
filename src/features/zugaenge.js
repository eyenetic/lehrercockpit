/**
 * LehrerZugaenge — quick links on Today (one compact row of icon chips).
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
    'Schulkalender',
    'Stunden- und Pausenzeiten',
    'Kontakt Lehrkraefte',
    'Schulwebseite',
  ];

  function init(dashboardData) {
    _dashboardData = dashboardData || {};
  }

  // Compact row of quick links on "Heute" (icon + name, opens in a new tab):
  // school links plus the teacher's own links. Nextcloud favourites live in „Links“.
  function render(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    var links = _buildLinks();
    // Own links and links for the whole staff (Verbindungen → Links)
    var own = window.LehrerLinks ? window.LehrerLinks.getLinks() : { school: [], personal: [] };
    var extra = (own.school || []).concat(own.personal || []);
    if (!links.length && !extra.length) {
      container.innerHTML = '';
      container.hidden = true;
      return;
    }
    container.hidden = false;
    container.innerHTML = links.map(function(link) {
      return _chip(link.url, link.label, link.note || link.label, link.icon, '');
    }).join('') + extra.map(function(link) {
      return _chip(link.url, link.title, link.title, _svg(ICONS.link), ' quicklink--own');
    }).join('');
  }

  function _chip(url, label, title, icon, extraClass) {
    return '<a href="' + _escHtml(url) + '" target="_blank" rel="noopener noreferrer" class="quicklink' + extraClass + '" title="' + _escHtml(title) + '">' +
      '<span class="quicklink-icon" aria-hidden="true">' + icon + '</span>' +
      '<span class="quicklink-label">' + _escHtml(label) + '</span></a>';
  }

  function _svg(paths) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + paths + '</svg>';
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

  var ICONS = {
    calendar: '<path d="M8 2v4M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/>',
    book: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8"/>',
    cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
    school: '<path d="m4 6 8-4 8 4M18 10v10M6 10v10M2 22h20M10 22v-6h4v6"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 0 20M12 2a15.3 15.3 0 0 0 0 20"/>',
    folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    star: '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  };

  function _iconFor(title, kind) {
    var name = 'link';
    if (title === 'WebUntis') name = 'calendar';
    else if (title === 'itslearning') name = 'book';
    else if (title === 'Dienstmail') name = 'mail';
    else if (title === 'Orgaplan') name = 'file';
    else if (title === 'Nextcloud' || kind === 'Nextcloud') name = 'cloud';
    else if (title === 'Berliner Schulportal' || title === 'Schulportal') name = 'school';
    else if (title === 'Schulwebseite') name = 'globe';
    else if (title === 'Teamordner') name = 'folder';
    else if (title === 'Schulkalender') name = 'calendar';
    else if (title === 'Stunden- und Pausenzeiten') name = 'clock';
    else if (title === 'Kontakt Lehrkraefte') name = 'users';
    return _svg(ICONS[name]);
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
