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

  function attachmentsHtml(list) {
    if (!list || !list.length) return '';
    var images = '';
    var files = '';
    list.forEach(function (a) {
      if (!/^https?:\/\//i.test(a.url || '')) return;
      var image = /^image\//i.test(a.type || '') || /\.(png|jpe?g|gif|webp)$/i.test(a.name || '');
      if (image) {
        images += '<a class="attach-image" href="' + esc(a.url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(a.name || 'Bild') + ' – groß ansehen">'
          + '<img class="attach-img" src="' + esc(a.url) + '" alt="' + esc(a.name || 'Bild') + '" loading="lazy" referrerpolicy="no-referrer" />'
          + '<span class="attach-fallback">' + chip(a, true).replace(/^<a /, '<span ').replace(/<\/a>$/, '</span>') + '</span></a>';
      } else {
        files += chip(a, false);
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
