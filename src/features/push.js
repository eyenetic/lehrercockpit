/**
 * LehrerPush — Web-Push on this device: morning overview (school days) and
 * week preview (Sunday evening). Sending happens on the server (backend/push_service.py).
 *
 * iPhone/iPad: Web-Push only works when the cockpit is installed on the home
 * screen (Teilen → „Zum Home-Bildschirm“), iOS 16.4 or newer.
 *
 * Exposes window.LehrerPush = { status, enable, disable, updatePrefs, test }.
 */
(function () {
  'use strict';

  var PREFS_KEY = 'lc.push.prefs';

  function _api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', credentials: 'include', headers: {} };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    return fetch((window.BACKEND_API_URL || '') + path, init).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok || data.ok === false) throw new Error(data.error || ('HTTP ' + resp.status));
        return data;
      });
    });
  }

  function supported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  function isIos() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function isStandalone() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
      window.navigator.standalone === true;
  }

  function _keyBytes(base64url) {
    var padded = (base64url + '===='.slice((base64url.length + 3) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(padded);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  function getPrefs() {
    try {
      var stored = JSON.parse(localStorage.getItem(PREFS_KEY) || 'null');
      if (stored && typeof stored === 'object') return { morning: stored.morning !== false, weekly: stored.weekly !== false };
    } catch (e) { /* ignore */ }
    return { morning: true, weekly: true };
  }

  function _storePrefs(prefs) {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
  }

  function _subscription() {
    if (!supported()) return Promise.resolve(null);
    return navigator.serviceWorker.getRegistration('./').then(function (reg) {
      return reg ? reg.pushManager.getSubscription() : null;
    });
  }

  /** { supported, serverEnabled, iosNeedsInstall, permission, subscribed, prefs } */
  function status() {
    var base = {
      supported: supported(),
      iosNeedsInstall: isIos() && !isStandalone(),
      permission: 'Notification' in window ? Notification.permission : 'unsupported',
      prefs: getPrefs(),
    };
    return Promise.all([
      _api('/api/v2/push/config').catch(function () { return { enabled: false }; }),
      _subscription().catch(function () { return null; }),
    ]).then(function (results) {
      base.serverEnabled = !!results[0].enabled;
      base.publicKey = results[0].public_key || '';
      base.subscribed = !!results[1];
      return base;
    });
  }

  function _register(sub, prefs) {
    return _api('/api/v2/push/subscribe', { method: 'POST', body: { subscription: sub.toJSON(), prefs: prefs } });
  }

  function enable(prefs) {
    prefs = prefs || getPrefs();
    if (!supported()) return Promise.reject(new Error('Dieser Browser unterstützt keine Push-Nachrichten.'));
    return _api('/api/v2/push/config').then(function (config) {
      if (!config.enabled) throw new Error('Push-Nachrichten sind auf dem Server noch nicht eingerichtet.');
      return Notification.requestPermission().then(function (permission) {
        if (permission !== 'granted') throw new Error('Benachrichtigungen wurden in diesem Browser nicht erlaubt.');
        return navigator.serviceWorker.register('./sw.js', { scope: './' });
      }).then(function () {
        return navigator.serviceWorker.ready;
      }).then(function (reg) {
        return reg.pushManager.getSubscription().then(function (existing) {
          return existing || reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: _keyBytes(config.public_key),
          });
        });
      }).then(function (sub) {
        _storePrefs(prefs);
        return _register(sub, prefs);
      });
    });
  }

  function updatePrefs(prefs) {
    _storePrefs(prefs);
    return _subscription().then(function (sub) {
      if (sub) return _register(sub, prefs);
      return null;
    });
  }

  function disable() {
    return _subscription().then(function (sub) {
      if (!sub) return null;
      return _api('/api/v2/push/subscribe', { method: 'DELETE', body: { endpoint: sub.endpoint } })
        .catch(function () { return null; })
        .then(function () { return sub.unsubscribe(); });
    });
  }

  function test() {
    return _api('/api/v2/push/test', { method: 'POST' });
  }

  window.LehrerPush = {
    status: status,
    enable: enable,
    disable: disable,
    updatePrefs: updatePrefs,
    test: test,
    getPrefs: getPrefs,
  };
})();
