/**
 * LehrerOneDriveSync — keeps the Klassenarbeitsplan fresh from its OneDrive link.
 *
 * The plan stays on OneDrive. The server tries to fetch it first; Microsoft may
 * refuse datacenter IPs. Then the backend reports sync.needs_browser and this
 * module fetches the file in the teacher's browser (a normal home/school IP)
 * and posts it to the API. One browser is enough – everyone gets the update.
 *
 * Same anonymous "badger" flow as backend/onedrive_share.py:
 *   token → share metadata (eTag, @content.downloadUrl) → download → POST.
 * Not a documented Microsoft API: failures are reported, the manual upload stays.
 *
 * Exposes window.LehrerOneDriveSync = { maybeSync, syncNow, getStatus }.
 */
(function () {
  'use strict';

  var TOKEN_URL = 'https://api-badgerp.svc.ms/v1.0/token';
  var APP_ID = '5cbed6ac-a083-4e14-b191-b4ba07653de2';
  var API_BASE = 'https://my.microsoftpersonalcontent.com/_api/v2.0';
  var TOKEN_KEY = 'lc.onedrive.token';
  var ATTEMPT_KEY = 'lc.onedrive.lastAttempt';
  var STATUS_KEY = 'lc.onedrive.status';
  var MIN_INTERVAL_MS = 30 * 60 * 1000;
  var TOKEN_TTL_MS = 24 * 60 * 60 * 1000; // tokens last ~7 days; refresh daily
  var MAX_BYTES = 15 * 1024 * 1024;

  var _running = null;

  function _storageGet(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; }
  }

  function _storageSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  function shareId(url) {
    // u! + base64url of the UTF-8 sharing URL, without padding
    var utf8 = unescape(encodeURIComponent(url.trim()));
    return 'u!' + btoa(utf8).replace(/=+$/, '').replace(/\//g, '_').replace(/\+/g, '-');
  }

  function _fail(message, cause) {
    var err = new Error(message);
    err.cause = cause;
    return err;
  }

  function getToken() {
    var cached = _storageGet(TOKEN_KEY);
    if (cached && cached.token && cached.expires > Date.now()) return Promise.resolve(cached.token);
    return fetch(TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ appId: APP_ID }),
    }).then(function (resp) {
      if (!resp.ok) throw _fail('OneDrive-Zugriffstoken nicht erhalten (HTTP ' + resp.status + ').');
      return resp.json();
    }).then(function (data) {
      if (!data.token) throw _fail('OneDrive hat kein Zugriffstoken geliefert.');
      _storageSet(TOKEN_KEY, { token: data.token, expires: Date.now() + TOKEN_TTL_MS });
      return data.token;
    });
  }

  function resolveShare(url, token) {
    var endpoint = API_BASE + '/shares/' + shareId(url) +
      '/driveitem?$select=name,size,eTag,lastModifiedDateTime,@content.downloadUrl';
    return fetch(endpoint, {
      headers: { Authorization: 'Badger ' + token, Prefer: 'autoredeem', Accept: 'application/json' },
    }).then(function (resp) {
      if (resp.status === 404) throw _fail('Der OneDrive-Link wurde nicht gefunden oder ist nicht mehr freigegeben.');
      if (resp.status === 401) {
        try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ }
      }
      if (!resp.ok) throw _fail('OneDrive antwortet mit HTTP ' + resp.status + '.');
      return resp.json();
    });
  }

  function _api(path, init) {
    init = init || {};
    init.credentials = 'include';
    return fetch((window.BACKEND_API_URL || '') + path, init).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok || data.ok === false) throw _fail(data.error || ('Cockpit-API: HTTP ' + resp.status));
        return data;
      });
    });
  }

  /**
   * Fetch the plan now. knownEtag = the backend's current OneDrive eTag; when it
   * still matches, only a confirmation is sent instead of the whole file.
   * Resolves to { state: 'ok' | 'unchanged', name }.
   */
  function syncNow(url, knownEtag) {
    var meta = null;
    return getToken()
      .then(function (token) { return resolveShare(url, token); })
      .then(function (item) {
        meta = item;
        if (knownEtag && item.eTag && item.eTag === knownEtag) {
          return _api('/api/v2/modules/klassenarbeitsplan/sync-confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ etag: item.eTag }),
          }).then(function () { return { state: 'unchanged', name: item.name }; });
        }
        if ((item.size || 0) > MAX_BYTES) throw _fail('Die Datei ist zu groß (max. 15 MB).');
        var downloadUrl = item['@content.downloadUrl'];
        if (!downloadUrl) throw _fail('OneDrive liefert keine Download-Adresse (ist es ein Ordner-Link?).');
        return fetch(downloadUrl)
          .then(function (resp) {
            if (!resp.ok) throw _fail('Download von OneDrive fehlgeschlagen (HTTP ' + resp.status + ').');
            return resp.arrayBuffer();
          }, function (cause) {
            throw _fail('Der Browser darf die Datei nicht direkt von OneDrive laden.', cause);
          })
          .then(function (buffer) {
            return _api('/api/v2/modules/klassenarbeitsplan/browser-sync', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/octet-stream',
                'X-Source-ETag': meta.eTag || '',
                'X-Source-Modified': meta.lastModifiedDateTime || '',
                'X-Source-Name': encodeURIComponent(meta.name || ''),
              },
              body: buffer,
            });
          })
          .then(function () { return { state: 'ok', name: meta.name }; });
      });
  }

  function _remember(status) {
    status.at = new Date().toISOString();
    _storageSet(STATUS_KEY, status);
    return status;
  }

  /**
   * Called after each dashboard load. Fetches only when the backend asks for a
   * browser fetch (server blocked) and at most every 30 minutes per browser.
   * onUpdated() runs after a new plan was stored.
   */
  function maybeSync(data, onUpdated) {
    if (!window.MULTIUSER_ENABLED || !data) return null;
    var sync = data.classworkSync;
    var url = data.base && data.base.klassenarbeitsplan_url;
    if (!sync || !sync.onedrive || !sync.needs_browser || !url) return null;
    var last = _storageGet(ATTEMPT_KEY);
    if (last && Date.now() - last < MIN_INTERVAL_MS) return null;
    return run(url, sync.etag, onUpdated);
  }

  function run(url, etag, onUpdated) {
    if (_running) return _running;
    _storageSet(ATTEMPT_KEY, Date.now());
    _running = syncNow(url, etag)
      .then(function (result) {
        _remember({ state: result.state, message: '' });
        if (result.state === 'ok' && typeof onUpdated === 'function') onUpdated();
        return result;
      })
      .catch(function (err) {
        _remember({ state: 'error', message: err.message });
        throw err;
      })
      .finally(function () { _running = null; });
    return _running;
  }

  window.LehrerOneDriveSync = {
    maybeSync: maybeSync,
    syncNow: run,
    getStatus: function () { return _storageGet(STATUS_KEY); },
    shareId: shareId,
  };
})();
