/**
 * LehrerZugaenge — Zugänge module card for Today (Slice 2)
 *
 * Renders a compact launchpad of quick-access links grouped by category.
 * URLs are resolved from baseData (system_settings passed via init) and static fallbacks.
 *
 * PUBLIC API:
 *   window.LehrerZugaenge.init(baseData)  — call with state.data.base after data load
 *   window.LehrerZugaenge.render(containerId)  — render into container element
 */
window.LehrerZugaenge = (function() {
  'use strict';

  // Links configuration — some URLs come from dashboard base data (dynamic), others are static
  // Will receive baseData from app.js init call
  var STATIC_LINKS = [
    { id: 'webuntis', label: 'WebUntis', group: 'Unterricht', icon: '📅', url: null, configKey: 'webuntis_url' },
    { id: 'itslearning', label: 'itslearning', group: 'Unterricht', icon: '📚', url: null, configKey: 'itslearning_base_url' },
    { id: 'schulportal', label: 'Schulportal', group: 'Verwaltung', icon: '🏫', url: null, configKey: 'schoolportal_url' },
    { id: 'orgaplan', label: 'Orgaplan', group: 'Verwaltung', icon: '📋', url: null, configKeys: ['orgaplan_pdf_url', 'orgaplan_url'] },
    { id: 'fehlzeiten11', label: 'Fehlzeiten Q1/Q2', group: 'Verwaltung', icon: '📊', url: null, configKey: 'fehlzeiten_11_url' },
    { id: 'fehlzeiten12', label: 'Fehlzeiten Q3/Q4', group: 'Verwaltung', icon: '📊', url: null, configKey: 'fehlzeiten_12_url' },
    { id: 'dienstmail', label: 'Dienstmail', group: 'Kommunikation', icon: '✉️', url: 'https://outlook.office.com', configKey: null },
    { id: 'nextcloud', label: 'Nextcloud', group: 'Dateien', icon: '☁️', url: null, configKeys: ['nextcloud_workspace_url', 'nextcloud_base_url'] },
  ];

  var _baseData = {};

  function init(baseData) {
    _baseData = baseData || {};
  }

  function _resolveUrl(link) {
    if (link.url) return link.url;
    if (Array.isArray(link.configKeys)) {
      for (var i = 0; i < link.configKeys.length; i++) {
        var candidate = link.configKeys[i];
        if (candidate && _baseData[candidate]) return _baseData[candidate];
      }
    }
    if (link.configKey && _baseData[link.configKey]) return _baseData[link.configKey];
    return null;
  }

  function render(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    // Group links
    var groups = {};
    for (var i = 0; i < STATIC_LINKS.length; i++) {
      var link = STATIC_LINKS[i];
      var url = _resolveUrl(link);
      if (!groups[link.group]) groups[link.group] = [];
      groups[link.group].push({ id: link.id, label: link.label, group: link.group, icon: link.icon, resolvedUrl: url });
    }

    var html = '<div class="zugaenge-card">';
    var groupNames = Object.keys(groups);
    for (var g = 0; g < groupNames.length; g++) {
      var groupName = groupNames[g];
      var links = groups[groupName];
      html += '<div class="zugaenge-group">';
      html += '<div class="zugaenge-group__label">' + groupName + '</div>';
      html += '<div class="zugaenge-group__links">';
      for (var l = 0; l < links.length; l++) {
        var lnk = links[l];
        if (lnk.resolvedUrl) {
          html += '<a href="' + _escHtml(lnk.resolvedUrl) + '" target="_blank" rel="noopener noreferrer" class="zugaenge-link" title="' + _escHtml(lnk.label) + '">' +
            '<span class="zugaenge-link__icon">' + lnk.icon + '</span>' +
            '<span class="zugaenge-link__label">' + _escHtml(lnk.label) + '</span>' +
            '</a>';
        } else {
          html += '<span class="zugaenge-link zugaenge-link--unconfigured" title="' + _escHtml(lnk.label) + ' (nicht konfiguriert)">' +
            '<span class="zugaenge-link__icon">' + lnk.icon + '</span>' +
            '<span class="zugaenge-link__label">' + _escHtml(lnk.label) + '</span>' +
            '</span>';
        }
      }
      html += '</div></div>';
    }
    html += '</div>';
    container.innerHTML = html;
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
