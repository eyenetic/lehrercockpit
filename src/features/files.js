/**
 * LehrerFiles — Anhänge (Foto oder PDF) an eigenen Terminen und Aufgaben.
 *
 * Jede Datei wird im Browser mit einem eigenen, zufälligen AES-GCM-Schlüssel
 * verschlüsselt und erst dann hochgeladen. Der Schlüssel steht nur im Eintrag
 * (lehrerCockpit.ownEntries) – und der reist selbst verschlüsselt im Tresor.
 * Der Server sieht also nur unlesbare Bytes, keinen Namen und keinen Dateityp.
 * Ändert sich der Zugangscode, bleiben die Anhänge lesbar (ihr Schlüssel liegt im Eintrag).
 *
 * Fotos werden vor dem Hochladen verkleinert (längste Seite 2000 px, JPEG).
 *
 *   LehrerFiles.add(file)       → Promise<{id, name, type, size, key, iv}>
 *   LehrerFiles.open(meta)      → Foto groß anzeigen, PDF in neuem Tab
 *   LehrerFiles.remove(ids)     → auf dem Server löschen
 *   LehrerFiles.usage()         → Promise<{used, quota}>
 */
(function () {
  'use strict';

  var MAX_BYTES = 10 * 1024 * 1024;
  var MAX_SIDE = 2000;
  var TYPES = /^(image\/(jpeg|png|webp|heic|heif|gif)|application\/pdf)$/;

  function api() { return window.BACKEND_API_URL || ''; }

  function toB64(bytes) {
    var bin = '';
    var arr = new Uint8Array(bytes);
    for (var i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
    return btoa(bin);
  }
  function fromB64(text) {
    var bin = atob(text);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function readBytes(blob) {
    if (blob.arrayBuffer) return blob.arrayBuffer();
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = reject;
      reader.readAsArrayBuffer(blob);
    });
  }

  /** Photos: smaller JPEG (also turns iPhone HEIC into JPEG when the browser can read it). */
  function shrink(file) {
    if (!/^image\//.test(file.type) || file.type === 'image/gif') return Promise.resolve(file);
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
        if (scale === 1 && file.size < 1500000 && file.type === 'image/jpeg') { resolve(file); return; }
        var canvas = document.createElement('canvas');
        canvas.width = Math.round(img.naturalWidth * scale);
        canvas.height = Math.round(img.naturalHeight * scale);
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          if (!blob) { resolve(file); return; }
          var name = String(file.name || 'Foto').replace(/\.(heic|heif|png|webp|jpe?g)$/i, '') + '.jpg';
          try { resolve(new File([blob], name, { type: 'image/jpeg' })); } catch (e) { blob.name = name; resolve(blob); }
        }, 'image/jpeg', 0.85);
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function add(file) {
    if (!window.crypto || !crypto.subtle) return Promise.reject(new Error('Dieser Browser kann keine Anhänge verschlüsseln.'));
    if (!file || !(TYPES.test(file.type) || /\.pdf$/i.test(file.name || ''))) {
      return Promise.reject(new Error('Nur Fotos oder PDF-Dateien.'));
    }
    var meta = null;
    var key = null;
    return shrink(file).then(function (small) {
      if (small.size > MAX_BYTES) throw new Error('„' + (file.name || 'Datei') + '“ ist zu groß (höchstens 10 MB).');
      meta = { name: String(small.name || file.name || 'Anhang').slice(0, 120), type: small.type || 'application/pdf', size: small.size };
      return Promise.all([readBytes(small), crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt'])]);
    }).then(function (res) {
      key = res[1];
      var iv = crypto.getRandomValues(new Uint8Array(12));
      meta.iv = toB64(iv);
      return Promise.all([crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, res[0]), crypto.subtle.exportKey('raw', key)]);
    }).then(function (res) {
      meta.key = toB64(res[1]);
      return fetch(api() + '/api/v2/files', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/octet-stream' }, body: res[0],
      });
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok) throw new Error(data.error || (resp.status === 413 ? 'Die Datei ist zu groß.' : 'Hochladen hat nicht geklappt.'));
        meta.id = data.id;
        return meta;
      });
    }, function (err) {
      throw err && err.message && err.message !== 'Failed to fetch' ? err : new Error('Keine Verbindung zum Server.');
    });
  }

  var _cache = {};   // id → object URL (decrypted, only in this tab)

  function blobUrl(meta) {
    if (_cache[meta.id]) return Promise.resolve(_cache[meta.id]);
    return fetch(api() + '/api/v2/files/' + encodeURIComponent(meta.id), { credentials: 'include' }).then(function (resp) {
      if (!resp.ok) throw new Error(resp.status === 404 ? 'Der Anhang ist nicht mehr da.' : 'Der Anhang konnte nicht geladen werden.');
      return resp.arrayBuffer();
    }).then(function (cipher) {
      return crypto.subtle.importKey('raw', fromB64(meta.key), 'AES-GCM', false, ['decrypt']).then(function (key) {
        return crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromB64(meta.iv) }, key, cipher);
      });
    }).then(function (plain) {
      var url = URL.createObjectURL(new Blob([plain], { type: meta.type }));
      _cache[meta.id] = url;
      return url;
    });
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  /** Photo: large on the page. PDF: new tab (opened right away, so no popup blocker), with a download fallback. */
  function open(meta) {
    var isImage = /^image\//.test(meta.type);
    var win = !isImage ? window.open('', '_blank') : null;
    if (win) { try { win.document.title = meta.name; win.document.body.textContent = 'Anhang wird entschlüsselt …'; } catch (e) { /* ignore */ } }
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay file-viewer';
    overlay.innerHTML = '<div class="file-viewer-box" role="dialog" aria-modal="true" aria-label="' + esc(meta.name) + '">'
      + '<div class="file-viewer-bar"><span class="file-viewer-name">' + esc(meta.name) + '</span>'
      + '<a class="btn btn-secondary btn-sm" data-file-download hidden>Herunterladen</a>'
      + '<button class="modal-close" type="button" data-file-close aria-label="Schließen">✕</button></div>'
      + '<div class="file-viewer-body"><p class="file-viewer-msg">Wird entschlüsselt …</p></div></div>';
    if (isImage || !win) document.body.appendChild(overlay);
    var close = function () { overlay.remove(); document.removeEventListener('keydown', onKey, true); };
    var onKey = function (ev) { if (ev.key === 'Escape') { ev.stopImmediatePropagation(); close(); } };
    overlay.addEventListener('click', function (ev) { if (ev.target === overlay || ev.target.closest('[data-file-close]')) close(); });
    document.addEventListener('keydown', onKey, true);
    return blobUrl(meta).then(function (url) {
      if (win) { win.location.href = url; close(); return; }
      var body = overlay.querySelector('.file-viewer-body');
      var link = overlay.querySelector('[data-file-download]');
      link.href = url;
      link.download = meta.name;
      link.hidden = false;
      body.innerHTML = isImage ? '<img src="' + url + '" alt="' + esc(meta.name) + '" />'
        : '<p class="file-viewer-msg">Der Browser hat kein neues Fenster erlaubt – über „Herunterladen“ öffnest du das PDF.</p>';
    }).catch(function (err) {
      if (win) win.close();
      if (!overlay.isConnected) document.body.appendChild(overlay);
      overlay.querySelector('.file-viewer-body').innerHTML = '<p class="file-viewer-msg is-error">' + esc(err.message || 'Der Anhang konnte nicht geöffnet werden.') + '</p>';
    });
  }

  function remove(ids) {
    (ids || []).forEach(function (id) {
      if (_cache[id]) { URL.revokeObjectURL(_cache[id]); delete _cache[id]; }
      fetch(api() + '/api/v2/files/' + encodeURIComponent(id), { method: 'DELETE', credentials: 'include', keepalive: true }).catch(function () {});
    });
  }

  function usage() {
    return fetch(api() + '/api/v2/files/usage', { credentials: 'include' }).then(function (resp) { return resp.ok ? resp.json() : null; });
  }

  /** Clean stored metadata (from localStorage / vault). */
  function clean(list) {
    return (Array.isArray(list) ? list : []).filter(function (f) {
      return f && /^[A-Za-z0-9_-]{10,40}$/.test(String(f.id || '')) && f.key && f.iv;
    }).slice(0, 10).map(function (f) {
      return { id: String(f.id), name: String(f.name || 'Anhang').slice(0, 120), type: String(f.type || '').slice(0, 60),
               size: +f.size || 0, key: String(f.key), iv: String(f.iv) };
    });
  }

  function sizeText(bytes) {
    return bytes >= 1024 * 1024 ? (bytes / 1024 / 1024).toFixed(1).replace('.', ',') + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB';
  }

  window.LehrerFiles = { add: add, open: open, remove: remove, usage: usage, clean: clean, sizeText: sizeText };
})();
