/**
 * LehrerAttachments — Beschreibung und Anhänge von Kalendereinträgen
 * (itslearning, Schultermine), überall gleich dargestellt.
 *
 * - Bilder werden direkt gezeigt. Lädt ein Bild nicht (z. B. weil itslearning
 *   es nur angemeldeten Personen gibt), erscheint stattdessen ein Knopf, der
 *   den Anhang in der Quelle öffnet.
 * - Andere Anhänge (PDF, Word …) sind Knöpfe.
 * - Beschreibungen: Text mit klickbaren Links, lange Texte aufklappbar.
 *
 * Exports (window.LehrerAttachments): detailHtml, attachmentsHtml
 */
var LehrerAttachments = (function () {
  'use strict';

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function detailHtml(detail) {
    var text = String(detail || '').trim();
    if (!text) return '';
    var html = esc(text).replace(/https?:\/\/[^\s<]+/g, function (url) {
      return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + (url.length > 48 ? url.slice(0, 45) + '…' : url) + '</a>';
    }).replace(/\n/g, '<br>');
    return text.length > 160 || text.split('\n').length > 3
      ? '<details class="calendar-item-detail"><summary>Beschreibung</summary><p>' + html + '</p></details>'
      : '<p class="calendar-item-note">' + html + '</p>';
  }

  var ICON_IMAGE = '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>';
  var ICON_FILE = '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>';

  function chip(a, image) {
    return '<a class="attach-chip" href="' + esc(a.url) + '" target="_blank" rel="noopener noreferrer" title="Öffnet den Anhang in der Quelle">'
      + '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
      + (image ? ICON_IMAGE : ICON_FILE) + '</svg>' + esc(a.name || 'Anhang') + '</a>';
  }

  /** options.viaServer: fetch through the cockpit server with the teacher's itslearning login. */
  function attachmentsHtml(list, options) {
    if (!list || !list.length) return '';
    var viaServer = options && options.viaServer;
    function src(url) {
      return viaServer ? (window.BACKEND_API_URL || '') + '/api/v2/itslearning/attachment?url=' + encodeURIComponent(url) : url;
    }
    var images = '';
    var files = '';
    list.forEach(function (a) {
      if (!/^https?:\/\//i.test(a.url || '')) return;
      var original = a;
      var served = { url: src(a.url), name: a.name, type: a.type };
      var image = /^image\//i.test(a.type || '') || /\.(png|jpe?g|gif|webp)$/i.test(a.name || '');
      if (image) {
        // the picture itself; if it does not load, the button opens the original in the source
        images += '<span class="attach-image">'
          + '<a class="attach-image-link" href="' + esc(served.url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(a.name || 'Bild') + ' – groß ansehen">'
          + '<img class="attach-img" src="' + esc(served.url) + '" alt="' + esc(a.name || 'Bild') + '" loading="lazy"' + (viaServer ? '' : ' referrerpolicy="no-referrer"') + ' /></a>'
          + '<span class="attach-fallback">' + chip(original, true) + '</span></span>';
      } else {
        files += chip(served, false);
      }
    });
    return (images ? '<div class="calendar-images">' + images + '</div>' : '')
      + (files ? '<div class="calendar-attachments">' + files + '</div>' : '');
  }

  // A picture that does not load (sign-in needed, removed …) turns into its button.
  if (typeof document !== 'undefined') {
    document.addEventListener('error', function (event) {
      var img = event.target;
      if (img && img.classList && img.classList.contains('attach-img')) {
        var box = img.closest('.attach-image');
        if (box) box.classList.add('is-broken');
      }
    }, true);
  }

  return { detailHtml: detailHtml, attachmentsHtml: attachmentsHtml };
})();

if (typeof window !== 'undefined') window.LehrerAttachments = LehrerAttachments;
