/**
 * LehrerAPI — Unified API client for Lehrercockpit
 *
 * Provides a single entry point for all API calls.
 * All requests use credentials: 'include' for session cookie forwarding.
 *
 * v1 endpoints are marked as LEGACY — they will be migrated to v2 over time.
 * v2 endpoints are the canonical SaaS API.
 */
(function() {
  'use strict';

  const BASE = window.BACKEND_API_URL || 'https://api.lehrercockpit.com';

  async function apiFetch(path, opts) {
    opts = opts || {};
    var defaults = { credentials: 'include', headers: {} };
    var merged = Object.assign({}, defaults, opts);
    if (opts.headers) merged.headers = Object.assign({}, defaults.headers, opts.headers);
    var url = path.startsWith('http') ? path : BASE + path;
    return fetch(url, merged);
  }

  window.LehrerAPI = {
    // ---- Auth (v2) ----
    me: function() { return apiFetch('/api/v2/auth/me'); },
    login: function(code) {
      return apiFetch('/api/v2/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_code: code })
      });
    },
    logout: function() { return apiFetch('/api/v2/auth/logout', { method: 'POST' }); },

    // ---- Dashboard v2 ----
    getDashboardV2: function() { return apiFetch('/api/v2/dashboard'); },
    getDashboardLayout: function() { return apiFetch('/api/v2/dashboard/layout'); },
    saveDashboardLayout: function(modules) {
      return apiFetch('/api/v2/dashboard/layout', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modules: modules })
      });
    },
    getModuleConfig: function(moduleId) { return apiFetch('/api/v2/modules/' + moduleId + '/config'); },
    saveModuleConfig: function(moduleId, config) {
      return apiFetch('/api/v2/modules/' + moduleId + '/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
    },
    completeOnboarding: function() {
      return apiFetch('/api/v2/dashboard/onboarding/complete', { method: 'POST' });
    },
    getOnboardingStatus: function() { return apiFetch('/api/v2/dashboard/onboarding-status'); },

    // ---- Modules v2 ----
    getModules: function() { return apiFetch('/api/v2/modules'); },

    // ---- Admin v2 ----
    admin: {
      getUsers: function() { return apiFetch('/api/v2/admin/users'); },
      createUser: function(data) {
        return apiFetch('/api/v2/admin/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      updateUser: function(id, data) {
        return apiFetch('/api/v2/admin/users/' + id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      deactivateUser: function(id) {
        return apiFetch('/api/v2/admin/users/' + id + '/deactivate', { method: 'POST' });
      },
      rotateCode: function(id) {
        return apiFetch('/api/v2/admin/users/' + id + '/rotate-code', { method: 'POST' });
      },
      getModuleDefaults: function() { return apiFetch('/api/v2/admin/modules/defaults'); },
      saveModuleDefaults: function(data) {
        return apiFetch('/api/v2/admin/modules/defaults', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      getSettings: function() { return apiFetch('/api/v2/admin/settings'); },
      saveSetting: function(key, value) {
        return apiFetch('/api/v2/admin/settings/' + key, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: value })
        });
      },
      getAuditLog: function(limit, offset, eventType) {
        limit = limit || 50;
        offset = offset || 0;
        var url = '/api/v2/admin/audit-log?limit=' + limit + '&offset=' + offset;
        if (eventType) url += '&event_type=' + encodeURIComponent(eventType);
        return apiFetch(url);
      },
    },

    // ---- Grades & Notes v2 (Phase 9b) ----
    getNotesData: function() { return apiFetch('/api/v2/modules/noten/data'); },
    saveGrade: function(data) {
      return apiFetch('/api/v2/modules/noten/grades', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
    },
    deleteGrade: function(id) {
      return apiFetch('/api/v2/modules/noten/grades/' + id, { method: 'DELETE' });
    },
    saveNote: function(data) {
      return apiFetch('/api/v2/modules/noten/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
    },
    deleteNote: function(className) {
      return apiFetch('/api/v2/modules/noten/notes/' + encodeURIComponent(className), { method: 'DELETE' });
    },

    // ---- LEGACY v1 endpoints (retained for backward compat, no v2 equivalent yet) ----
    legacy: {
      getDashboard: function() { return apiFetch('/api/dashboard', { cache: 'no-store' }); },
      getGrades: function() { return apiFetch('/api/grades'); },
      getNotes: function() { return apiFetch('/api/notes'); },
      getClasswork: function() { return apiFetch('/api/classwork'); },
      saveItslearning: function(data) {
        return apiFetch('/api/local-settings/itslearning', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      saveNextcloud: function(data) {
        return apiFetch('/api/local-settings/nextcloud', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      saveGrade: function(data) {
        return apiFetch('/api/local-settings/grades', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
      saveNote: function(data) {
        return apiFetch('/api/local-settings/notes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      },
    }
  };
})();
