/**
 * LehrerVault — Daten bleiben im Browser und reisen verschlüsselt mit.
 *
 * Klassenlisten, Einsammlungen, eigene Links und ein paar Einstellungen liegen
 * im localStorage dieses Geräts. Damit sie auf einem neuen Gerät (oder nach dem
 * Abmelden) wieder da sind, legt der Browser eine Kopie auf dem Server ab –
 * verschlüsselt mit AES-GCM. Der Schlüssel entsteht nur im Browser aus dem
 * Zugangscode (PBKDF2-SHA-256); der Server sieht nur unlesbare Daten.
 *
 *   Anmelden         → Schlüssel aus dem eingegebenen Code ableiten (rememberKey)
 *   Code ändern      → neu verschlüsseln (rekey)
 *   Code vergessen   → der alte Tresor lässt sich nicht mehr öffnen; was auf dem
 *                      Gerät liegt, wird mit dem neuen Code neu gesichert
 *
 * Backend: GET/PUT /api/v2/vault, POST /api/v2/auth/me/verify-code.
 * Exposes window.LehrerVault = { init, rememberKey, unlock, rekey, status, onChange, syncNow }.
 */
(function () {
  'use strict';

  var KEY_STORE = 'lc.vaultKey';
  var USER_STORE = 'lc.vaultUser';
  var VERSION_STORE = 'lc.vaultVersion';
  var DIRTY_STORE = 'lc.vaultDirty';
  var ITERATIONS = 310000;
  var SYNCED_KEYS = [
    'lehrerCockpit.classLists',
    'lehrerCockpit.collections',
    'lehrerCockpit.links',
    'lehrerCockpit.classwork.selectedClasses',
    'lehrerCockpit.todayLayout.local',
    'lc.scheduleView',
    'lc.orgaplanLevel',
    'lc.gradesSettings',
  ];

  var _userId = null;
  var _status = 'off';        // off | syncing | synced | locked | error
  var _applying = false;
  var _timer = null;
  var _busy = null;
  var _listeners = [];

  // ── Helpers ────────────────────────────────────────────────────────────────

  function get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } }
  function del(key) { try { localStorage.removeItem(key); } catch (e) { /* ignore */ } }

  function toB64(bytes) {
    var binary = '';
    var view = new Uint8Array(bytes);
    for (var i = 0; i < view.length; i += 0x8000) binary += String.fromCharCode.apply(null, view.subarray(i, i + 0x8000));
    return btoa(binary);
  }

  function fromB64(text) {
    var binary = atob(text);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch((window.BACKEND_API_URL || '') + path, {
      method: opts.method || 'GET',
      credentials: 'include',
      headers: opts.body ? { 'Content-Type': 'application/json' } : {},
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        return { ok: resp.ok && data.ok !== false, status: resp.status, data: data };
      });
    });
  }

  function setStatus(status) {
    _status = status;
    _listeners.forEach(function (fn) { try { fn(status); } catch (e) { /* ignore */ } });
  }

  function supported() {
    return !!(window.crypto && window.crypto.subtle && window.TextEncoder);
  }

  // ── Schlüssel ──────────────────────────────────────────────────────────────

  function deriveRawKey(code, userId) {
    var enc = new TextEncoder();
    return crypto.subtle.importKey('raw', enc.encode(String(code)), 'PBKDF2', false, ['deriveBits'])
      .then(function (material) {
        return crypto.subtle.deriveBits({
          name: 'PBKDF2', hash: 'SHA-256', iterations: ITERATIONS,
          salt: enc.encode('lehrercockpit-vault-v1:' + userId),
        }, material, 256);
      });
  }

  /** After login: derive the key from the code the teacher just typed. */
  /**
   * Removes everything this app keeps in the browser (except the colour theme).
   * Logout must do this itself: the server's Clear-Site-Data header only reaches
   * the API's origin, not the app's.
   */
  function wipeLocal() {
    try {
      var theme = localStorage.getItem('lehrerCockpit.theme');
      localStorage.clear();
      if (theme) localStorage.setItem('lehrerCockpit.theme', theme);
    } catch (e) { /* ignore */ }
  }

  function rememberKey(code, userId) {
    if (!supported() || !code || userId == null) return Promise.resolve(false);
    // Another account used this browser before: its class lists etc. must
    // neither show up nor be merged into this account's vault.
    if (get(USER_STORE) && get(USER_STORE) !== String(userId)) wipeLocal();
    return deriveRawKey(code, userId).then(function (raw) {
      set(KEY_STORE, toB64(raw));
      set(USER_STORE, String(userId));
      return true;
    }).catch(function () { return false; });
  }

  function cryptoKey() {
    var raw = get(KEY_STORE);
    if (!raw || get(USER_STORE) !== String(_userId)) return Promise.resolve(null);
    return crypto.subtle.importKey('raw', fromB64(raw), 'AES-GCM', false, ['encrypt', 'decrypt']);
  }

  // ── Inhalt ─────────────────────────────────────────────────────────────────

  function snapshot() {
    var data = {};
    SYNCED_KEYS.forEach(function (key) {
      var value = get(key);
      if (value !== null) data[key] = value;
    });
    return data;
  }

  function hasLocalData() {
    return ['lehrerCockpit.classLists', 'lehrerCockpit.collections', 'lehrerCockpit.links'].some(function (key) {
      var value = get(key);
      return value && value !== '{}' && value !== '[]';
    });
  }

  function dirtyKeys() {
    try { return JSON.parse(get(DIRTY_STORE) || '[]'); } catch (e) { return []; }
  }

  function encrypt(key, data) {
    var iv = crypto.getRandomValues(new Uint8Array(12));
    var plain = new TextEncoder().encode(JSON.stringify({ v: 1, data: data }));
    return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, plain).then(function (cipher) {
      return { iv: toB64(iv), ciphertext: toB64(cipher) };
    });
  }

  function decrypt(key, vault) {
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromB64(vault.iv) }, key, fromB64(vault.ciphertext))
      .then(function (plain) { return JSON.parse(new TextDecoder().decode(plain)).data || {}; });
  }

  // Class lists / collections: one entry per class or collection – keep both
  // sides (this device wins for the same entry). Links: union by address.
  function mergeFirstSync(serverData) {
    var merged = Object.assign({}, serverData);
    var changed = false;
    ['lehrerCockpit.classLists', 'lehrerCockpit.collections'].forEach(function (key) {
      var local = get(key);
      if (!local) return;
      try {
        var mine = JSON.parse(local) || {};
        var theirs = serverData[key] ? JSON.parse(serverData[key]) : {};
        var result = Object.assign({}, theirs, mine);
        merged[key] = JSON.stringify(result);
        if (Object.keys(mine).some(function (id) { return !(id in theirs); })) changed = true;
      } catch (e) { /* keep server value */ }
    });
    var localLinks = get('lehrerCockpit.links');
    if (localLinks) {
      try {
        var mineLinks = JSON.parse(localLinks) || [];
        var theirLinks = serverData['lehrerCockpit.links'] ? JSON.parse(serverData['lehrerCockpit.links']) : [];
        var urls = theirLinks.map(function (l) { return l.url; });
        var extra = mineLinks.filter(function (l) { return urls.indexOf(l.url) === -1; });
        merged['lehrerCockpit.links'] = JSON.stringify(theirLinks.concat(extra));
        if (extra.length) changed = true;
      } catch (e) { /* keep server value */ }
    }
    merged.__changed = changed;
    return merged;
  }

  function apply(data, keep) {
    _applying = true;
    try {
      SYNCED_KEYS.forEach(function (key) {
        if (keep.indexOf(key) !== -1) return; // changed here and not yet saved: local wins
        if (Object.prototype.hasOwnProperty.call(data, key)) set(key, data[key]);
        else del(key);
      });
    } finally {
      _applying = false;
    }
    window.dispatchEvent(new CustomEvent('lehrer:vault-updated'));
  }

  // ── Abgleich ───────────────────────────────────────────────────────────────

  function push(key, baseVersion) {
    return encrypt(key, snapshot()).then(function (payload) {
      return api('/api/v2/vault', { method: 'PUT', body: { iv: payload.iv, ciphertext: payload.ciphertext, base_version: baseVersion } });
    }).then(function (result) {
      if (result.ok) {
        set(VERSION_STORE, String(result.data.version));
        del(DIRTY_STORE);
        return 'synced';
      }
      if (result.status === 409) return 'conflict';
      throw new Error(result.data.error || 'Speichern fehlgeschlagen');
    });
  }

  function sync(force) {
    if (_busy) return _busy;
    _busy = cryptoKey().then(function (key) {
      if (!key) { setStatus('off'); return; }
      setStatus('syncing');
      return api('/api/v2/vault').then(function (result) {
        if (!result.ok) throw new Error('Tresor nicht erreichbar');
        var vault = result.data.vault;
        var localVersion = Number(get(VERSION_STORE) || 0);
        var dirty = dirtyKeys();
        if (!vault) return hasLocalData() || dirty.length ? push(key, 0) : 'synced';
        var serverNewer = vault.version !== localVersion;
        if (!serverNewer) return dirty.length || force ? push(key, vault.version) : 'synced';
        return decrypt(key, vault).then(function (data) {
          if (!localVersion) {
            // First sync of this device: merge instead of replacing what it already had.
            data = mergeFirstSync(data);
            var mergedChanges = data.__changed;
            delete data.__changed;
            apply(data, []);
            set(VERSION_STORE, String(vault.version));
            return mergedChanges ? push(key, vault.version) : 'synced';
          }
          apply(data, dirty);
          set(VERSION_STORE, String(vault.version));
          return dirty.length ? push(key, vault.version) : 'synced';
        }, function () {
          // Encrypted with another code (code reset): keep what is on this device.
          if (hasLocalData()) return push(key, vault.version);
          return 'locked';
        });
      });
    }).then(function (state) {
      if (state === 'conflict') { _busy = null; return sync(false); }
      setStatus(state || _status);
    }).catch(function () {
      setStatus('error');
    }).then(function () { _busy = null; });
    return _busy;
  }

  function schedule() {
    clearTimeout(_timer);
    _timer = setTimeout(function () { sync(false); }, 1500);
  }

  function markDirty(key) {
    var dirty = dirtyKeys();
    if (dirty.indexOf(key) === -1) {
      dirty.push(key);
      set(DIRTY_STORE, JSON.stringify(dirty));
    }
    schedule();
  }

  // Every write to a synced key (by any module) is saved to the vault.
  function watchStorage() {
    if (!window.Storage || Storage.prototype.__lcVaultWatched) return;
    Storage.prototype.__lcVaultWatched = true;
    var originalSet = Storage.prototype.setItem;
    var originalRemove = Storage.prototype.removeItem;
    Storage.prototype.setItem = function (key, value) {
      var result = originalSet.apply(this, arguments);
      if (!_applying && this === window.localStorage && SYNCED_KEYS.indexOf(key) !== -1 && _userId != null) markDirty(key);
      return result;
    };
    Storage.prototype.removeItem = function (key) {
      var result = originalRemove.apply(this, arguments);
      if (!_applying && this === window.localStorage && SYNCED_KEYS.indexOf(key) !== -1 && _userId != null) markDirty(key);
      return result;
    };
  }

  // ── Öffentliche Funktionen ────────────────────────────────────────────────

  function init(userId) {
    if (!supported() || userId == null) return;
    _userId = userId;
    if (get(USER_STORE) && get(USER_STORE) !== String(userId)) {
      // another account used this browser before: none of its data applies
      wipeLocal();
    }
    watchStorage();
    sync(false);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') sync(false);
    });
  }

  /** Existing session without a key: confirm the code once. */
  function unlock(code) {
    return api('/api/v2/auth/me/verify-code', { method: 'POST', body: { code: code } }).then(function (result) {
      if (!result.ok) throw new Error(result.data.error || 'Der Code stimmt nicht.');
      return rememberKey(code, _userId);
    }).then(function () { return sync(true); });
  }

  /** After changing the code: encrypt again with the new code. */
  function rekey(newCode) {
    return rememberKey(newCode, _userId).then(function () { return sync(true); });
  }

  window.LehrerVault = {
    init: init,
    rememberKey: rememberKey,
    unlock: unlock,
    rekey: rekey,
    syncNow: function () { return sync(true); },
    status: function () { return _status; },
    hasLocalData: hasLocalData,
    wipeLocal: wipeLocal,
    onChange: function (fn) { _listeners.push(fn); },
  };
})();
