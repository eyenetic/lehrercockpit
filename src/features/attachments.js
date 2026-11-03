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

  // Formatted descriptions (tables, lists, bold …) from the source – only plain formatting
  // survives: no scripts, styles, images or event handlers; links only to http(s).
  var ALLOWED = { TABLE: 1, THEAD: 1, TBODY: 1, TR: 1, TD: 1, TH: 1, P: 1, BR: 1, B: 1, STRONG: 1, I: 1, EM: 1, U: 1,
                  UL: 1, OL: 1, LI: 1, A: 1, SPAN: 1, DIV: 1, H1: 1, H2: 1, H3: 1, H4: 1 };
  function richHtml(html) {
    if (typeof DOMParser === 'undefined') return '';
    var doc = new DOMParser().parseFromString('<div>' + String(html || '') + '</div>', 'text/html');
    function clean(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) return;                       // text
        if (child.nodeType !== 1 || !ALLOWED[child.tagName]) {  // anything else: keep only its text
          if (child.nodeType === 1 && !/^(SCRIPT|STYLE|TITLE|HEAD|META|LINK|IFRAME|OBJECT|IMG|SVG)$/.test(child.tagName)) {
            clean(child);
            while (child.firstChild) node.insertBefore(child.firstChild, child);
          }
          node.removeChild(child);
          return;
        }
        Array.prototype.slice.call(child.attributes).forEach(function (attr) {
          var keep = (child.tagName === 'A' && attr.name === 'href' && /^https?:\/\//i.test(attr.value))
            || ((child.tagName === 'TD' || child.tagName === 'TH') && (attr.name === 'colspan' || attr.name === 'rowspan'));
          if (!keep) child.removeAttribute(attr.name);
        });
        if (child.tagName === 'A') { child.setAttribute('target', '_blank'); child.setAttribute('rel', 'noopener noreferrer'); }
        clean(child);
      });
    }
    var root = doc.body.firstChild;
    clean(root);
    return root.textContent.trim() ? '<div class="rich-detail">' + root.innerHTML + '</div>' : '';
  }

  // itslearning's feed flattens tables and lists into one line ("Klasse Fach Kollege 7a … 7b …",
  // "… geplant: 10a: … 10b: …"). Where class names (7a, 10b) mark the rows, rebuild them.
  var CLASS_RE = /(^|\s)(\d{1,2}[a-z])(?=:|\s)/g;
  function structuredHtml(text) {
    if (/\n/.test(text)) return '';
    var starts = [];
    var m;
    CLASS_RE.lastIndex = 0;
    while ((m = CLASS_RE.exec(text))) starts.push(m.index + m[1].length);
    if (starts.length < 3) return '';
    var head = text.slice(0, starts[0]).trim();
    var rows = starts.map(function (start, i) { return text.slice(start, starts[i + 1]).trim(); });
    var headWords = head.split(/\s+/);

    // table: a short header of column names, then one row per class
    if (head && headWords.length >= 2 && headWords.length <= 5 && !/[.:,!?]/.test(head)
        && rows.every(function (r) { return r.length <= 40; })) {
      var tail = headWords.length - 2; // single-word columns at the end (e.g. Kollege)
      return '<table><thead><tr>' + headWords.map(function (w) { return '<th>' + esc(w) + '</th>'; }).join('') + '</tr></thead><tbody>'
        + rows.map(function (r) {
          var words = r.split(/\s+/);
          var cells = [words[0]];
          var end = words.slice(1);
          var last = tail > 0 && end.length > tail ? end.splice(end.length - tail, tail) : [];
          cells.push(end.join(' '));
          cells = cells.concat(last);
          while (cells.length < headWords.length) cells.push('');
          return '<tr>' + cells.map(function (c) { return '<td>' + esc(c) + '</td>'; }).join('') + '</tr>';
        }).join('') + '</tbody></table>';
    }

    // list: "10a: … 10b: …" inside a text; what follows the last item becomes its own paragraph
    if (!rows.every(function (r) { return /^\d{1,2}[a-z]:/.test(r); })) return '';
    var outro = '';
    var lastRow = rows[rows.length - 1];
    var cut = lastRow.search(/\)\s+(?=[A-ZÄÖÜ])/);
    if (cut > 0) { outro = lastRow.slice(cut + 1).trim(); rows[rows.length - 1] = lastRow.slice(0, cut + 1); }
    function para(t) {
      return t ? '<p>' + esc(t)
        .replace(/^(Liebe[^,]{0,40},)\s*/, '$1<br>')
        .replace(/\s+((?:VG|LG|Viele Grüße|Liebe Grüße|Beste Grüße)\b)/, '<br>$1') + '</p>' : '';
    }
    return para(head)
      + '<ul>' + rows.map(function (r) {
        var i = r.indexOf(':');
        return '<li><strong>' + esc(r.slice(0, i)) + '</strong> ' + esc(r.slice(i + 1).trim()) + '</li>';
      }).join('') + '</ul>'
      + para(outro);
  }

  /** Plain description, or the formatted one when the source sends it (htmlDetail). */
  function detailHtml(detail, htmlDetail) {
    var rich = htmlDetail ? richHtml(htmlDetail) : '';
    if (rich) return '<details class="calendar-item-detail" open><summary>Beschreibung</summary>' + rich + '</details>';
    var text = String(detail || '').trim();
    var structured = structuredHtml(text);
    if (structured) return '<details class="calendar-item-detail" open><summary>Beschreibung</summary><div class="rich-detail">' + structured + '</div></details>';
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
