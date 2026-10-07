// ─────────────────────────────────────────────────────────────────────────────
// src/app.js — Lehrer-Cockpit frontend dashboard orchestrator
//
// All feature rendering is delegated to extracted modules (loaded before this file):
//   window.LehrerGrades      — src/features/grades.js
//   window.LehrerInbox       — src/features/inbox.js
//   window.LehrerDocuments   — src/features/documents.js
//   window.LehrerClasswork   — src/features/classwork.js
//   window.LehrerWebUntis    — src/features/webuntis.js
//   window.LehrerItslearning — src/features/itslearning.js
//   window.LehrerNextcloud   — src/features/nextcloud.js
//   window.DashboardManager  — src/modules/dashboard-manager.js
//
// This file owns: loadDashboard(), renderAll(), renderToday(),
// renderNavSignals(), isSectionEnabled(), renderSectionFocus(), event wiring,
// normalization helpers, and initialization.
// ─────────────────────────────────────────────────────────────────────────────

(function bootstrapApp() {
  // ── SECTION: State & constants ──────────────────────────────────────────────
  const WEBUNTIS_SHORTCUTS_KEY = "lehrerCockpit.webuntis.shortcuts";
  const WEBUNTIS_FAVORITES_KEY = "lehrerCockpit.webuntis.favorites";
  const ACTIVE_WEBUNTIS_PLAN_KEY = "lehrerCockpit.webuntis.activePlan";
  const THEME_KEY = "lehrerCockpit.theme";
  const CLASSWORK_SELECTED_CLASSES_KEY = "lehrerCockpit.classwork.selectedClasses";
  // NEXTCLOUD_LAST_OPENED_KEY moved to src/features/nextcloud.js (LehrerNextcloud extraction)
  const EXPANDED_PANELS_KEY = "lehrerCockpit.expandedPanels";
  const DASHBOARD_CACHE_KEY = "lc.dashboardCache";
  // Official direct mailbox link (Schulportal SSO); mail clients are not permitted in Berlin.
  const DIENSTMAIL_DEFAULT_URL = "https://lehrkraeftemail.schule.berlin.de/?iam_sso=1";
  const DASHBOARD_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // shown at once, then refreshed
  const AUTO_REFRESH_MS = 180000;
  const PANEL_COLLAPSE_LIMITS = {
    inbox: 10,
    grades: 4,
    notes: 3,
    classwork: 4,
    documents: 4,
    access: 8,
  };
  const IS_LOCAL_RUNTIME =
    window.location.protocol === "file:" ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";
  const PRODUCTION_API_BASES = buildProductionApiBases();

  const state = {
    activeSection: "overview",
    selectedChannel: "mail",
    documentSearch: "",
    webuntisView: (function () { try { return localStorage.getItem("lc.scheduleView") === "day" ? "day" : "week"; } catch (_e) { return "week"; } })(),
    webuntisDayOffset: 0,
    webuntisWeekOffset: 0,
    webuntisPickerOpen: false,
    webuntisPickerCategory: null,
    webuntisPickerSearch: "",
    data: null,
    shortcuts: loadSavedShortcuts(),
    favorites: loadWebUntisFavorites(),
    activeShortcutId: "personal",
    activeFinderEntityId: null,
    classworkUploadFeedback: "",
    classworkUploadFeedbackKind: "",
    classworkSelectedClasses: loadStoredClassworkClasses(),
    classworkClassSearch: "",
    classworkView: "list",
    gradesData: null,
    gradesSelectedClass: "",
    gradesFeedback: "",
    gradesFeedbackKind: "",
    notesData: null,
    notesSelectedClass: "",
    notesFeedback: "",
    notesFeedbackKind: "",
    theme: loadStoredTheme(),
    expandedPanels: loadExpandedPanels(),
  };

  const elements = {
    briefingButton: document.querySelector("#briefing-button"),
    briefingOutput: document.querySelector("#briefing-output"),
    todayInboxPreview: document.querySelector("#today-inbox-preview"),
    todayDocumentsPreview: document.querySelector("#today-documents-preview"),
    heroNote: document.querySelector("#hero-note"),
    runtimeBanner: document.querySelector("#runtime-banner"),
    settingsButton: document.querySelector("#settings-button"),
    themeToggle: document.querySelector("#theme-toggle"),
    navLinks: Array.from(document.querySelectorAll("[data-section-target]")),
    viewSections: Array.from(document.querySelectorAll("[data-view-section]")),
    viewDividers: Array.from(document.querySelectorAll("[data-divider-for]")),
    todayOverviewGrid: document.querySelector("#today-overview-grid"),
    expandToggles: Array.from(document.querySelectorAll("[data-expand-toggle]")),
    workspaceTitle: document.querySelector("#workspace-title"),
    itslearningConnectCard: document.querySelector("#itslearning-connect-card"),
    itslearningConnectStatus: document.querySelector("#itslearning-connect-status"),
    itslearningConnectCopy: document.querySelector("#itslearning-connect-copy"),
    itslearningConnectForm: document.querySelector("#itslearning-connect-form"),
    itslearningUsername: document.querySelector("#itslearning-username"),
    itslearningPassword: document.querySelector("#itslearning-password"),
    itslearningConnectFeedback: document.querySelector("#itslearning-connect-feedback"),
    nextcloudConnectCard: document.querySelector("#nextcloud-connect-card"),
    nextcloudConnectStatus: document.querySelector("#nextcloud-connect-status"),
    nextcloudConnectCopy: document.querySelector("#nextcloud-connect-copy"),
    nextcloudConnectForm: document.querySelector("#nextcloud-connect-form"),
    nextcloudUsername: document.querySelector("#nextcloud-username"),
    nextcloudPassword: document.querySelector("#nextcloud-password"),
    nextcloudConnectFeedback: document.querySelector("#nextcloud-connect-feedback"),
    nextcloudWorkspaceUrl: document.querySelector("#nextcloud-workspace-url"),
    nextcloudOpenRoot: document.querySelector("#nextcloud-open-root"),
    nextcloudOpenQ1Q2: document.querySelector("#nextcloud-open-q1q2"),
    nextcloudOpenQ3Q4: document.querySelector("#nextcloud-open-q3q4"),
    nextcloudQ1Q2UrlInput: document.querySelector("#nextcloud-q1q2-url"),
    nextcloudQ3Q4UrlInput: document.querySelector("#nextcloud-q3q4-url"),
    nextcloudLink1Label: document.querySelector("#nextcloud-link1-label"),
    nextcloudLink1Url: document.querySelector("#nextcloud-link1-url"),
    nextcloudLink2Label: document.querySelector("#nextcloud-link2-label"),
    nextcloudLink2Url: document.querySelector("#nextcloud-link2-url"),
    nextcloudLink3Label: document.querySelector("#nextcloud-link3-label"),
    nextcloudLink3Url: document.querySelector("#nextcloud-link3-url"),
    nextcloudCustomLinks: document.querySelector("#nextcloud-custom-links"),
    nextcloudLastOpened: document.querySelector("#nextcloud-last-opened"),
    priorityList: document.querySelector("#priority-list"),
    sourceList: document.querySelector("#source-list"),
    messageList: document.querySelector("#message-list"),
    dienstmailOpenLink: document.querySelector("#dienstmail-open-link"),
    dienstmailSetupButton: document.querySelector("#dienstmail-setup-button"),
    dienstmailSetupStatus: document.querySelector("#dienstmail-setup-status"),
    itslearningOpenLink: document.querySelector("#itslearning-open-link"),
    scheduleList: document.querySelector("#schedule-list"),
    webuntisViewSwitch: document.querySelector("#webuntis-view-switch"),
    webuntisRefreshButton: document.querySelector("#webuntis-refresh-button"),
    webuntisOpenToday: document.querySelector("#webuntis-open-today"),
    webuntisOpenBase: document.querySelector("#webuntis-open-base"),
    webuntisActivePlan: document.querySelector("#webuntis-active-plan"),
    webuntisDetail: document.querySelector("#webuntis-detail"),
    webuntisRangeLabel: document.querySelector("#webuntis-range-label"),
    webuntisPlanStrip: document.querySelector("#webuntis-plan-strip"),
    webuntisWatchlist: document.querySelector("#webuntis-watchlist"),
    webuntisPickerButton: document.querySelector("#webuntis-picker-button"),
    webuntisPickerOverlay: document.querySelector("#webuntis-picker-overlay"),
    webuntisPickerBackdrop: document.querySelector("#webuntis-picker-backdrop"),
    webuntisPickerClose: document.querySelector("#webuntis-picker-close"),
    webuntisPickerEdit: document.querySelector("#webuntis-picker-edit"),
    webuntisPickerSearch: document.querySelector("#webuntis-picker-search"),
    webuntisPickerHome: document.querySelector("#webuntis-picker-home"),
    webuntisPickerCurrent: document.querySelector("#webuntis-picker-current"),
    webuntisPickerResultsSection: document.querySelector("#webuntis-picker-results-section"),
    webuntisPickerResultsLabel: document.querySelector("#webuntis-picker-results-label"),
    webuntisPickerResults: document.querySelector("#webuntis-picker-results"),
    webuntisPickerFavorites: document.querySelector("#webuntis-picker-favorites"),
    webuntisPickerCategories: document.querySelector("#webuntis-picker-categories"),
    webuntisPickerCategoryView: document.querySelector("#webuntis-picker-category"),
    webuntisPickerBack: document.querySelector("#webuntis-picker-back"),
    webuntisPickerCategoryKicker: document.querySelector("#webuntis-picker-category-kicker"),
    webuntisPickerCategoryTitle: document.querySelector("#webuntis-picker-category-title"),
    webuntisPickerCategoryNote: document.querySelector("#webuntis-picker-category-note"),
    webuntisPickerCategoryResults: document.querySelector("#webuntis-picker-category-results"),
    orgaplanOpenLink: document.querySelector("#orgaplan-open-link"),
    orgaplanDigestCard: document.querySelector('[aria-labelledby="orgaplan-digest-title"]'),
    orgaplanDigestDetail: document.querySelector("#orgaplan-digest-detail"),
    orgaplanTodayList: document.querySelector("#orgaplan-today-list"),
    orgaplanWeekList: document.querySelector("#orgaplan-week-list"),
    orgaplanUpcomingList: document.querySelector("#orgaplan-upcoming-list"),
    classworkOpenLink: document.querySelector("#classwork-open-link"),
    classworkDigestCard: document.querySelector('[aria-labelledby="classwork-digest-title"]'),
    classworkUploadInput: document.querySelector("#classwork-upload-input"),
    classworkUploadStatus: document.querySelector("#classwork-upload-status"),
    classworkDigestDetail: document.querySelector("#classwork-digest-detail"),
    classworkClassSearch: document.querySelector("#classwork-class-search"),
    classworkClassFilter: document.querySelector("#classwork-class-filter"),
    classworkViewSwitch: document.querySelector("#classwork-view-switch"),
    classworkPreviewList: document.querySelector("#classwork-preview-list"),
    classworkUploadButton: document.querySelector("#classwork-upload-button"),
    classworkUploadFeedback: document.querySelector("#classwork-upload-feedback"),
    gradesDetail: document.querySelector("#grades-detail"),
    gradesSummaryCount: document.querySelector("#grades-summary-count"),
    gradesSummaryAverage: document.querySelector("#grades-summary-average"),
    gradesSummaryRisk: document.querySelector("#grades-summary-risk"),
    gradesRows: document.querySelector("#grades-rows"),
    gradesAddRow: document.querySelector("#grades-add-row"),
    gradesReset: document.querySelector("#grades-reset"),
    gradesPresetButtons: document.querySelector("#grades-preset-buttons"),
    gradesFeedback: document.querySelector("#grades-feedback"),
    gradesForm: document.querySelector("#grades-form"),
    gradesList: document.querySelector("#grades-list"),
    documentList: document.querySelector("#document-list"),
    documentsExtraBlock: document.querySelector("#documents-extra-block"),
    documentSearch: document.querySelector("#document-search"),
    documentSearchWrap: document.querySelector("#document-search-wrap"),
  };

  // channelLabels moved to src/features/inbox.js (Phase 16)

  // ── SECTION: DashboardManager (Multi-User) ──────────────────────────────────
  //
  // Activated when window.MULTIUSER_ENABLED === true.
  // Fetches GET /api/v2/dashboard, stores module layout, wires the settings
  // panel (layout management), and injects module-config banners.

  // DashboardManager is extracted to src/modules/dashboard-manager.js (Phase 8d)
  const DashboardManager = window.DashboardManager;

  function isModuleVisible(moduleId) {
    if (!DashboardManager || typeof DashboardManager.isModuleVisible !== "function") {
      return true;
    }
    return DashboardManager.isModuleVisible(moduleId);
  }

  function isAnyModuleVisible(moduleIds) {
    return (moduleIds || []).some((moduleId) => isModuleVisible(moduleId));
  }

  // Returns true only after DashboardManager has loaded the layout from the API at least once.
  // Before that point, _modules is empty and isModuleVisible() defaults to true for all modules,
  // which would cause disabled modules to flash briefly on first render.
  // renderToday() skips module-derived content until this returns true.
  // Non-module content (priorities, documents, workspace) always renders normally.
  function isLayoutReady() {
    if (!DashboardManager || typeof DashboardManager.isLayoutReady !== "function") {
      // DashboardManager not present (non-multiuser mode) → treat as always ready
      return true;
    }
    return DashboardManager.isLayoutReady();
  }

  function hasStandaloneDocumentsContent() {
    const data = getData();
    const extraDocuments = (data.documents || []).filter((entry) => !isPrimaryPlanDocument(entry));
    return extraDocuments.length > 0 || (data.documentMonitor || []).length > 0;
  }

  function isSectionEnabled(sectionId) {
    switch (sectionId) {
      case "overview":
      case "schedule":
      case "inbox":
      case "documents":
        return true;
      case "grades":
        return DashboardManager && typeof DashboardManager.isModuleVisible === 'function'
          ? DashboardManager.isModuleVisible('noten')
          : true;
      case "access":
        return false;
      case "links":
        return Boolean(window.MULTIUSER_ENABLED);
      default:
        return true;
    }
  }

  // ── SECTION: API / data loading ─────────────────────────────────────────────

  function saveDashboardCache(data) {
    try {
      const userId = window.CURRENT_USER ? window.CURRENT_USER.id : null;
      localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify({ data, ts: Date.now(), userId }));
    } catch (_) {}
  }

  function loadDashboardCache(maxAgeMs = DASHBOARD_CACHE_MAX_AGE_MS) {
    try {
      const raw = localStorage.getItem(DASHBOARD_CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.data) return null;
      if (Date.now() - parsed.ts > maxAgeMs) return null;
      // Only ever show a teacher their own last state.
      if (window.MULTIUSER_ENABLED && (!window.CURRENT_USER || parsed.userId !== window.CURRENT_USER.id)) return null;
      return parsed.data;
    } catch (_) { return null; }
  }

  async function loadDashboard(forceRefresh = false) {
    // ── Phase 12: v2 PRIMARY path ──────────────────────────────────────────
    // When running in multi-user SaaS mode, call GET /api/v2/dashboard/data
    // first. The response includes a 'base' section (quickLinks, workspace,
    // berlinFocus) plus all per-module data. normalizeV2Dashboard() maps the
    // v2 response to the same shape all render functions expect.
    // If the v2 call fails for any reason, fall through to the v1 path below.
    if (window.MULTIUSER_ENABLED && window.LehrerAPI) {
      // Multi-user: the v2 API is the only source. Never fall back to the local
      // v1 endpoints or the mock data – that would show another school's plan.
      const resp = await window.LehrerAPI.getDashboardData();
      if (resp.status === 401) {
        window.location.href = './login.html';
        throw new Error("Nicht angemeldet.");
      }
      const v2Json = resp.ok ? await resp.json() : null;
      if (!v2Json || !v2Json.ok) {
        throw new Error("Das Cockpit ist gerade nicht erreichbar.");
      }
      return normalizeV2Dashboard(v2Json);
    }

    // ── Fallback: v1 / local path ──────────────────────────────────────────
    const sources = IS_LOCAL_RUNTIME
      ? [`/api/dashboard${forceRefresh ? "?refresh=1" : ""}`, "./data/mock-dashboard.json"]
      : [...PRODUCTION_API_BASES.map((base) => `${base}/api/dashboard${forceRefresh ? "?refresh=1" : ""}`), "./data/mock-dashboard.json"];

    for (const source of sources) {
      try {
        // credentials: 'include' ensures session cookie forwarded to backend (Phase 8c/8d)
        const response = await fetch(source, { cache: "no-store", credentials: "include" });
        if (!response.ok) {
          continue;
        }

        let data = normalizeDashboard(await response.json());

        // Phase 9e: override grades/notes with v2 per-user data when available.
        // Fails silently — v1 data (or empty arrays) remain usable as fallback.
        try {
          if (window.LehrerGrades && window.MULTIUSER_ENABLED && window.LehrerAPI) {
            const v2Data = await window.LehrerAPI.getNotesData();
            if (v2Data.ok) {
              const json = await v2Data.json();
              if (data.grades !== undefined) data.grades = json.grades || [];
              if (data.notes !== undefined) data.notes = json.notes || [];
            }
          }
        } catch (_e) {
          // Fail silently — v1 data is still usable
        }

        return data;
      } catch (error) {
        continue;
      }
    }

    if (window.LEHRER_COCKPIT_FALLBACK_DATA) {
      return normalizeDashboard(window.LEHRER_COCKPIT_FALLBACK_DATA);
    }

    throw new Error("Dashboard-Daten konnten nicht geladen werden.");
  }

  function normalizeDashboard(payload) {
    const data = JSON.parse(JSON.stringify(payload));
    const now = new Date();

    data.generatedAt = data.generatedAt || now.toISOString();
    data.meta = data.meta || {};
    data.meta.lastUpdatedLabel = data.meta.lastUpdatedLabel || formatTime(now);

    data.webuntisCenter = data.webuntisCenter || {
      status: "warning",
      note: "WebUntis-Bereich ist vorbereitet.",
      detail: "Noch keine WebUntis-Daten vorhanden.",
      activePlan: "Mein WebUntis-Plan",
      todayUrl: "",
      startUrl: "",
      currentDate: now.toISOString().slice(0, 10),
      currentWeekLabel: "KW --",
      events: [],
      planTypes: [
        { id: "teacher", label: "Lehrkraft" },
        { id: "class", label: "Klasse" },
        { id: "room", label: "Raum" },
      ],
      finder: {
        status: "warning",
        note: "Planfinder ist vorbereitet.",
        indexedAt: formatTime(now),
        supportsSessionSearch: false,
        searchPlaceholder: "Lehrkraft, Klasse oder Raum suchen",
        entities: [],
        watchlist: [],
      },
      shortcutHint: "WebUntis-Links können hier als Schnellzugriff gespeichert werden.",
    };

    data.planDigest = data.planDigest || {
      orgaplan: {
        status: "warning",
        title: "Orgaplan",
        detail: "Noch kein Orgaplan-Digest verfügbar.",
        monthLabel: "",
        updatedAt: formatTime(now),
        highlights: [],
        upcoming: [],
        sourceUrl: "",
      },
      classwork: {
        status: "warning",
        title: "Klassenarbeitsplan",
        detail: "Noch kein Klassenarbeitsplan-Digest verfügbar.",
        updatedAt: formatTime(now),
        previewRows: [],
        classes: [],
        entries: [],
        defaultClass: "",
        sourceUrl: "",
      },
    };

    return data;
  }

  async function fetchBackendMailPreview() {
    try {
      const apiBase = getBackendApiBase();
      const url = `${apiBase}/api/mail`;
      const response = await fetch(url, { cache: "no-store", credentials: "include" });
      if (!response.ok) return null;
      return await response.json();
    } catch (_error) {
      return null;
    }
  }

  // ── SECTION: v2 Module Data Overlay (Phase 11d) ─────────────────────────────
  //
  // overlayV2ModuleData() is called after normalizeDashboard() in loadDashboard().
  // It fetches the v2 aggregated dashboard data from GET /api/v2/dashboard/data
  // and overlays per-module fields on top of the v1 base payload.
  // Each module overlay is independent — a single module failure is silent.
  // The v1 data always remains the safety net.

  async function overlayV2ModuleData(data) {
    if (!window.MULTIUSER_ENABLED) return data;
    if (!window.LehrerAPI || typeof window.LehrerAPI.getDashboardData !== 'function') return data;

    // Get active module IDs from DashboardManager (avoids fetching disabled modules)
    var activeModuleIds = null;
    if (window.DashboardManager && typeof window.DashboardManager.getActiveModuleIds === 'function') {
      activeModuleIds = window.DashboardManager.getActiveModuleIds();
    }

    var resp, json;
    try {
      resp = await window.LehrerAPI.getDashboardData();
      if (!resp.ok) return data;
      json = await resp.json();
    } catch (_e) {
      return data;  // network error — v1 data remains
    }

    if (!json || !json.ok || !json.modules) return data;
    var modules = json.modules;

    // Overlay WebUntis events/schedule
    if (modules.webuntis && modules.webuntis.ok === true) {
      if (!activeModuleIds || activeModuleIds.indexOf('webuntis') !== -1) {
        try { _applyWebuntisV2Data(data, modules.webuntis.data || modules.webuntis); } catch (_e) {}
      }
    }

    // Overlay itslearning messages + source
    if (modules.itslearning && modules.itslearning.ok === true) {
      if (!activeModuleIds || activeModuleIds.indexOf('itslearning') !== -1) {
        try { _applyItslearningV2Data(data, modules.itslearning.data || modules.itslearning); } catch (_e) {}
      }
    }

    // Overlay orgaplan digest
    if (modules.orgaplan && modules.orgaplan.ok === true) {
      if (!activeModuleIds || activeModuleIds.indexOf('orgaplan') !== -1) {
        try { _applyOrgaplanV2Data(data, modules.orgaplan.data || modules.orgaplan); } catch (_e) {}
      }
    }

    // Overlay Klassenarbeitsplan classwork
    if (modules.klassenarbeitsplan && modules.klassenarbeitsplan.ok === true) {
      if (!activeModuleIds || activeModuleIds.indexOf('klassenarbeitsplan') !== -1) {
        try { _applyClassworkV2Data(data, modules.klassenarbeitsplan.data || modules.klassenarbeitsplan); } catch (_e) {}
      }
    }

    return data;
  }

  // v2 → v1 field mapping helpers (private, not exported)

  function _applyWebuntisV2Data(data, v2) {
    // v2 = WebUntisSyncResult dict: {source, events[], schedule[], priorities[], mode, note}
    if (!v2) return;
    data.webuntisCenter = Object.assign({}, data.webuntisCenter, {
      status: (v2.source && v2.source.status) || data.webuntisCenter.status,
      note: v2.note || data.webuntisCenter.note,
      detail: (v2.source && v2.source.detail) || data.webuntisCenter.detail,
      events: Array.isArray(v2.events) ? v2.events : data.webuntisCenter.events,
      schedule: Array.isArray(v2.schedule) ? v2.schedule : (data.webuntisCenter.schedule || []),
    });
    if (Array.isArray(v2.priorities) && v2.priorities.length) {
      data.priorities = _mergeV2Priorities(v2.priorities, data.priorities || []);
    }
  }

  function _applyItslearningV2Data(data, v2) {
    // v2 = ItslearningSyncResult dict: {source, messages[], priorities[], mode, note, calendar?}
    if (!v2) return;
    data.itslearningCalendar = v2.calendar || null;
    data.itslearningMode = v2.mode || "";
    if (Array.isArray(v2.messages)) {
      // Replace itslearning-channel messages with fresh v2 data; preserve other channels
      var nonItslearning = (data.messages || []).filter(function(m) { return m.channel !== 'itslearning'; });
      data.messages = v2.messages.concat(nonItslearning);
    }
    if (v2.source) {
      data.sources = _mergeV2Source(data.sources || [], v2.source);
    }
    if (Array.isArray(v2.priorities) && v2.priorities.length) {
      data.priorities = _mergeV2Priorities(v2.priorities, data.priorities || []);
    }
  }

  function _applyOrgaplanV2Data(data, v2) {
    // v2 = backend/orgaplan.py build_digest(): status ok|outdated|pending|error, upcoming,
    // today_entries, week_entries, highlights, sourceUrl, schoolYear, stand, checkedAt …
    if (!v2) return;
    var digest = v2.digest || v2;
    data.planDigest = data.planDigest || {};
    data.planDigest.orgaplan = Object.assign({}, data.planDigest.orgaplan, digest, {
      upcoming: digest.upcoming || [],
      highlights: digest.highlights || [],
      today_entries: digest.today_entries || [],
      week_entries: digest.week_entries || [],
    });
  }

  function _applyClassworkV2Data(data, v2) {
    // v2 = backend/classwork_sync.py plan_view(): entries from today on, planStatus
    if (!v2) return;
    data.planDigest = data.planDigest || {};
    data.planDigest.classwork = Object.assign({}, data.planDigest.classwork, v2, {
      entries: v2.entries || [],
      classes: v2.classes || [],
      previewRows: v2.previewRows || [],
    });
  }

  function _mergeV2Priorities(incoming, existing) {
    // Incoming priorities replace existing entries for same source, others kept
    var incomingSources = {};
    incoming.forEach(function(p) { if (p.source) incomingSources[p.source] = true; });
    var merged = incoming.concat(
      existing.filter(function(p) { return !incomingSources[p.source]; })
    );
    return merged.slice(0, 8);
  }

  function _mergeV2Source(existing, sourceUpdate) {
    // Replace matching source by id, or prepend if new
    if (!sourceUpdate || !sourceUpdate.id) return existing;
    var filtered = existing.filter(function(s) { return s.id !== sourceUpdate.id; });
    return [sourceUpdate].concat(filtered);
  }

  // ── SECTION: normalizeV2Dashboard (Phase 12) ────────────────────────────────
  //
  // Maps a GET /api/v2/dashboard/data response to the same normalized data
  // shape that normalizeDashboard() produces from the v1 payload.
  // All render functions (renderWorkspace, renderToday, etc.)
  // work unchanged because the output shape is identical.

  function normalizeV2Dashboard(v2) {
    // Start with the v1 default shape (provides safe defaults for every field)
    var data = normalizeDashboard({});

    // ── base section → workspace, quickLinks, berlinFocus ──────────────────
    if (v2.base) {
      // Preserve raw base so URL fields (schoolportal_url, fehlzeiten_11_url, etc.)
      // are accessible at state.data.base for the Zugaenge module card (Slice 2)
      data.base = v2.base;
      if (v2.base.workspace && typeof v2.base.workspace === 'object') {
        data.workspace = v2.base.workspace;
      }
      if (Array.isArray(v2.base.quick_links)) {
        data.quickLinks = v2.base.quick_links;
      }
      if (Array.isArray(v2.base.berlin_focus)) {
        data.berlinFocus = v2.base.berlin_focus;
      }
      // documents is deferred in Phase 12 — keep the v1 default (empty array)
    }

    // ── modules section → same overlay logic as overlayV2ModuleData() ──────
    if (v2.modules) {
      var modules = v2.modules;

      // WebUntis
      if (modules.webuntis && modules.webuntis.ok === true) {
        try { _applyWebuntisV2Data(data, modules.webuntis.data || modules.webuntis); } catch (_e) {}
      }

      // itslearning
      if (modules.itslearning && modules.itslearning.ok === true) {
        try { _applyItslearningV2Data(data, modules.itslearning.data || modules.itslearning); } catch (_e) {}
      }

      // orgaplan
      if (modules.orgaplan && modules.orgaplan.ok === true) {
        try { _applyOrgaplanV2Data(data, modules.orgaplan.data || modules.orgaplan); } catch (_e) {}
      }

      // klassenarbeitsplan
      if (modules.klassenarbeitsplan && modules.klassenarbeitsplan.ok === true) {
        try { _applyClassworkV2Data(data, modules.klassenarbeitsplan.data || modules.klassenarbeitsplan); } catch (_e) {}
      }

      // Schultermine (calendar of the school website)
      var calendar = modules['wichtige-termine'];
      data.schoolCalendar = calendar && calendar.data ? calendar.data : null;

      // "Neu & geändert": unified entries with per-teacher state
      data.signals = v2.signals || null;

      // Klassenarbeitsplan OneDrive sync status (browser fetch when the server is blocked)
      data.classworkSync = modules.klassenarbeitsplan && modules.klassenarbeitsplan.sync
        ? modules.klassenarbeitsplan.sync
        : null;

      // Nextcloud activity + notifications (Login Flow v2)
      data.nextcloudFeed = modules.nextcloud && modules.nextcloud.ok === true ? (modules.nextcloud.data || null) : null;

      // grades + notes (noten module)
      if (modules.noten && modules.noten.ok === true && modules.noten.data) {
        try {
          var notenData = modules.noten.data;
          if (Array.isArray(notenData.grades)) data.grades = notenData.grades;
          if (Array.isArray(notenData.notes)) data.notes = notenData.notes;
        } catch (_e) {}
      }
    }

    // ── Store raw modules dict for optional direct access ───────────────────
    if (v2.modules && typeof v2.modules === 'object') {
      data.modules = v2.modules;
    }

    // ── user / meta ─────────────────────────────────────────────────────────
    if (v2.user && v2.user.display_name) {
      data.meta = data.meta || {};
      data.meta.mode = 'live';
      data.meta.note = 'Daten werden direkt aus der v2 API geladen.';
    }
    if (v2.generated_at) {
      data.generatedAt = v2.generated_at;
    }

    return data;
  }

  function getData() {
    return (
      state.data || {
        meta: {
          mode: "empty",
          note: "Noch keine Daten geladen.",
          lastUpdatedLabel: formatTime(new Date()),
        },
        priorities: [],
        messages: [],
        documents: [],
        sources: [],
        quickLinks: [],
        berlinFocus: [],
        documentMonitor: [],
        schedule: [],
        webuntisCenter: {
          status: "warning",
          note: "WebUntis-Bereich ist vorbereitet.",
          detail: "Noch keine WebUntis-Daten vorhanden.",
          activePlan: "Mein WebUntis-Plan",
          todayUrl: "",
          startUrl: "",
          currentDate: new Date().toISOString().slice(0, 10),
          currentWeekLabel: "KW --",
          events: [],
          planTypes: [
            { id: "teacher", label: "Lehrkraft" },
            { id: "class", label: "Klasse" },
            { id: "room", label: "Raum" },
          ],
          finder: {
            status: "warning",
            note: "Planfinder ist vorbereitet.",
            indexedAt: formatTime(new Date()),
            supportsSessionSearch: false,
            searchPlaceholder: "Lehrkraft, Klasse oder Raum suchen",
            entities: [],
            watchlist: [],
          },
          shortcutHint: "WebUntis-Links können hier als Schnellzugriff gespeichert werden.",
        },
        planDigest: {
          orgaplan: {
            status: "warning",
            title: "Orgaplan",
            detail: "Noch kein Orgaplan-Digest verfügbar.",
            monthLabel: "",
            updatedAt: formatTime(new Date()),
            highlights: [],
            upcoming: [],
            sourceUrl: "",
          },
          classwork: {
            status: "warning",
            title: "Klassenarbeitsplan",
            detail: "Noch kein Klassenarbeitsplan-Digest verfügbar.",
            updatedAt: formatTime(new Date()),
            previewRows: [],
            classes: [],
            entries: [],
            defaultClass: "",
            sourceUrl: "",
          },
        },
        workspace: {
          eyebrow: "Lehrer-Cockpit",
          title: "Dein Tagesstart",
          description: "Noch keine Workspace-Daten geladen.",
        },
      }
    );
  }

  // ── SECTION: Core render helpers (workspace, theme, meta, stats, briefing) ──

  function renderWorkspace() {
    const data = getData();
    const titleFromWorkspace = data.workspace?.title || "";
    // Backend sends "Dein Tagesstart für <Schule>" (older payloads: "fuer")
    const schoolFromTitle = titleFromWorkspace.match(/^Dein Tagesstart f(?:ü|ue)r (.+)$/)?.[1] || "";
    const schoolName = data.base?.school_name || data.teacher?.school || schoolFromTitle;
    if (elements.workspaceTitle) {
      elements.workspaceTitle.textContent = schoolName || "";
      elements.workspaceTitle.hidden = !schoolName;
    }
  }

  function applyTheme() {
    document.documentElement.dataset.theme = state.theme;
    const isDark = state.theme === "dark";
    if (elements.themeToggle) {
      elements.themeToggle.setAttribute("aria-pressed", String(isDark));
    }
    // Menu items name the action, not the current state.
    ["theme-label", "more-sheet-theme-label"].forEach((id) => {
      const label = document.getElementById(id);
      if (label) label.textContent = isDark ? "Helles Design" : "Dunkles Design";
    });
  }

  const SECTION_TITLES = {
    schedule: "Stundenplan",
    inbox: "Posteingang",
    documents: "Pläne",
    links: "Links",
    grades: "Notenrechner",
    classlist: "Klassen",
    collections: "Einsammlungen",
  };

  function renderPageHead() {
    const active = state.activeSection || "overview";
    const now = new Date();
    const titleEl = document.getElementById("today-weekday");
    const subtitleEl = document.getElementById("today-date-display");
    if (titleEl) {
      if (active === "overview") {
        const hour = now.getHours();
        const greeting = hour < 11 ? "Guten Morgen" : hour < 18 ? "Guten Tag" : "Guten Abend";
        const firstName = (window.CURRENT_USER && window.CURRENT_USER.first_name) || "";
        titleEl.textContent = firstName ? `${greeting}, ${firstName}` : greeting;
      } else {
        titleEl.textContent = SECTION_TITLES[active] || "Lehrercockpit";
      }
    }
    if (subtitleEl) {
      subtitleEl.textContent = `${now.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })} · KW ${isoWeekNumber(now)}`;
    }
    const topbarTitle = document.getElementById("mobile-topbar-title");
    if (topbarTitle) topbarTitle.textContent = active === "overview" ? "Heute" : (SECTION_TITLES[active] || "Lehrercockpit");
  }

  function renderSectionFocus() {
    let active = state.activeSection || "overview";
    if (active !== "overview" && !isSectionEnabled(active)) {
      active = "overview";
      state.activeSection = active;
    }

    elements.navLinks.forEach((button) => {
      const sectionId = button.dataset.sectionTarget || "";
      const isVisible = isSectionEnabled(sectionId);
      button.hidden = !isVisible;
      button.classList.toggle("active", sectionId === active);
      if (sectionId === active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });

    elements.viewSections.forEach((section) => {
      const sectionId = section.dataset.viewSection;
      const isVisible = isSectionEnabled(sectionId);
      section.hidden = !isVisible || sectionId !== active;
    });

    elements.viewDividers.forEach((divider) => {
      const targetSection = divider.dataset.dividerFor || "";
      divider.hidden = !targetSection || !isSectionEnabled(targetSection);
    });

    if (elements.settingsButton) {
      elements.settingsButton.hidden = active !== "overview";
    }
    renderPageHead();
    // The week grid sizes itself to the visible screen: draw it once it is shown.
    if (active === "schedule" && lastFocusedSection !== "schedule") renderWebUntisSchedule();
    lastFocusedSection = active;
  }

  var lastFocusedSection = "";

  function renderMeta() {
    const data = getData();
    if (elements.heroNote) {
      elements.heroNote.textContent = state.showingCache
        ? "Stand wird aktualisiert …"
        : `Stand ${data.meta.lastUpdatedLabel} Uhr`;
    }
  }

  function renderRuntimeBanner() {
    const data = getData();

    if (state.offlineSince) {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent = state.data
        ? `Keine Verbindung zum Cockpit-Server. Du siehst den letzten Stand (${formatTime(new Date(state.data.generatedAt || Date.now()))} Uhr).`
        : "Keine Verbindung zum Cockpit-Server.";
      return;
    }

    if (window.MULTIUSER_ENABLED) {
      elements.runtimeBanner.hidden = true;
      elements.runtimeBanner.textContent = "";
      return;
    }

    if (window.location.protocol === "file:") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        "Direktdatei geöffnet. Für Live-Daten bitte http://127.0.0.1:4173 nutzen.";
      return;
    }

    if (data.meta.mode === "snapshot") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        `Backend ist gerade nicht erreichbar. Du siehst den zuletzt synchronisierten Stand von ${data.meta.lastUpdatedLabel}.`;
      return;
    }

    if (data.meta.mode !== "live") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent = `${data.meta.note} Letztes Update: ${data.meta.lastUpdatedLabel}.`;
      return;
    }

    elements.runtimeBanner.hidden = true;
    elements.runtimeBanner.textContent = "";
  }

  // ── SECTION: Heute ───────────────────────────────────────────────────────────
  // Each tile answers one question in a few rows; details live in the sections.
  //   schedule   Welche Stunden habe ich heute?      (WebUntis)
  //   school     Was ist heute an der Schule los?    (Orgaplan, Schultermine)
  //   classwork  Welche Arbeiten stehen an?          (Klassenarbeitsplan, meine Klassen)
  //   inbox      Was ist neu für mich?               (itslearning, Nextcloud)
  //   upcoming   Was kommt in den nächsten Tagen?    (Orgaplan, Schultermine)
  // "Neu & geändert" (signals.js) and the KI tile (ai.js) render themselves.

  const TODAY_TILE_MODULES = {
    schedule: ["webuntis"],
    school: ["orgaplan", "wichtige-termine"],
    classwork: ["klassenarbeitsplan"],
    inbox: ["itslearning", "mail"],
    upcoming: ["orgaplan", "wichtige-termine"],
    access: ["zugaenge"],
  };

  function localIso(date) {
    return date.toLocaleDateString("en-CA");
  }

  function addDaysIso(days) {
    const date = startOfDay(new Date());
    date.setDate(date.getDate() + days);
    return localIso(date);
  }

  function dayLabel(iso) {
    const date = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
    const diff = Math.round((date - startOfDay(new Date())) / 86400000);
    if (diff === 0) return "Heute";
    if (diff === 1) return "Morgen";
    return date.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" }).replace(",", "");
  }

  function setTileMeta(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || "";
  }

  function tileEmpty(text, actionHtml) {
    return `<div class="tile-empty"><p>${escapeHtml(text)}</p>${actionHtml || ""}</div>`;
  }

  function tileList(rows, moreCount, moreTarget) {
    return `<ul class="tile-list">${rows.map((row) => `
      <li class="tile-row${row.cls ? ` ${row.cls}` : ""}">
        ${row.when !== undefined ? `<span class="tile-when">${escapeHtml(row.when)}</span>` : ""}
        <span class="tile-main">
          <span class="tile-title">${row.titleHtml || escapeHtml(row.title)}</span>
          ${row.sub ? `<span class="tile-sub">${escapeHtml(row.sub)}</span>` : ""}
        </span>
        ${row.tag ? `<span class="tile-tag${row.tagCls ? ` ${row.tagCls}` : ""}">${escapeHtml(row.tag)}</span>` : ""}
      </li>`).join("")}</ul>`
      + (moreCount > 0 ? `<button class="tile-more" type="button" ${moreTarget}>+ ${moreCount} weitere</button>` : "");
  }

  function orgaplanLevel() {
    try { return localStorage.getItem("lc.orgaplanLevel") || "all"; } catch (_e) { return "all"; }
  }

  // Orgaplan columns of one day as [{tag, text}], respecting the level filter from "Pläne".
  function orgaplanParts(entry) {
    const level = orgaplanLevel();
    const join = (main, notes) => (main && notes ? `${main} (${notes})` : main || notes || "");
    return [
      { tag: "Alle", kind: "general", text: entry.general },
      { tag: "Mittelstufe", kind: "middle", text: join(entry.middle, entry.middleNotes) },
      { tag: "Oberstufe", kind: "upper", text: join(entry.upper, entry.upperNotes) },
    ].filter((part) => part.text)
      .filter((part) => !(level === "middle" && part.kind === "upper") && !(level === "upper" && part.kind === "middle"));
  }

  function renderToday() {
    const data = getData();
    const bodies = ["briefing-output", "today-school-body", "today-classwork-body", "today-inbox-preview", "today-documents-preview"];
    if (!isLayoutReady()) {
      bodies.forEach((id) => {
        const el = document.getElementById(id);
        if (el && !el.innerHTML.trim()) el.innerHTML = '<div class="tile-skeleton" aria-hidden="true"><span></span><span></span><span></span></div>';
      });
      return;
    }
    renderScheduleTile(data);
    renderSchoolTile(data);
    renderClassworkTile(data);
    renderInboxTile(data);
    renderUpcomingTile(data);
  }

  // Problems with personal calendar links (wrong link, needs login, gone …),
  // shown on "Heute", in the sections and under "Verbindungen".
  function personalSourceProblems(data) {
    const problems = {};
    const webuntis = ((data.modules || {}).webuntis || {});
    const source = (webuntis.data || {}).source || {};
    if (webuntis.configured !== false && (source.status === "error" || webuntis.ok === false)) {
      problems.webuntis = source.detail || webuntis.error || "WebUntis konnte nicht geladen werden.";
    }
    const calendar = data.itslearningCalendar;
    if (calendar && calendar.ok === false) problems.itslearning = calendar.error || "Der itslearning-Kalender konnte nicht geladen werden.";
    window.LehrerSourceProblems = problems;
    return problems;
  }

  function renderScheduleTile(data) {
    const body = elements.briefingOutput;
    if (!body) return;
    const problem = personalSourceProblems(data).webuntis;
    if (problem && isWebUntisConnected(data)) {
      setTileMeta("tile-schedule-meta", "");
      body.innerHTML = tileEmpty(problem,
        window.MULTIUSER_ENABLED ? '<button class="btn btn-primary btn-sm" type="button" data-open-connections="webuntis">Link prüfen</button>' : "");
      return;
    }
    if (!isWebUntisConnected(data)) {
      setTileMeta("tile-schedule-meta", "");
      body.innerHTML = tileEmpty(
        "Verbinde WebUntis – dann stehen hier deine Stunden, Vertretungen und Entfälle.",
        window.MULTIUSER_ENABLED ? '<button class="btn btn-primary btn-sm" type="button" data-open-connections="webuntis">WebUntis verbinden</button>' : ""
      );
      return;
    }
    const { events, previewLabel } = todayLessons(data);
    if (!events.length) {
      setTileMeta("tile-schedule-meta", "");
      body.innerHTML = tileEmpty("Heute stehen keine Stunden im Plan.");
      return;
    }
    const duties = events.filter((event) => isSupervision(event)).length;
    const lessons = events.length - duties;
    const cancelled = events.filter((event) => event.cancelled).length;
    setTileMeta("tile-schedule-meta", previewLabel
      ? previewLabel
      : [`${lessons} ${lessons === 1 ? "Stunde" : "Stunden"}`, duties ? `${duties} ${duties === 1 ? "Aufsicht" : "Aufsichten"}` : "", cancelled ? `${cancelled} entfällt` : ""].filter(Boolean).join(" · "));
    body.innerHTML = renderTodayFullSchedule(data, events, previewLabel);
  }

  function renderSchoolTile(data) {
    const body = document.getElementById("today-school-body");
    if (!body) return;
    const items = [];
    if (isModuleVisible("orgaplan")) {
      (data.planDigest?.orgaplan?.today_entries || []).forEach((entry) => {
        orgaplanParts(entry).forEach((part) => items.push({ tag: part.tag, tagCls: `tile-tag-${part.kind}`, title: part.text }));
      });
    }
    (data.schoolCalendar?.today_events || []).forEach((event) => {
      const multiDay = event.end && event.end.slice(0, 10) !== event.start.slice(0, 10);
      items.push({
        tag: "Termin",
        tagCls: "tile-tag-event",
        title: event.title,
        sub: [event.time_label ? `${event.time_label} Uhr` : "", multiDay ? `bis ${dayLabel(event.end)}` : ""].filter(Boolean).join(" · "),
      });
    });
    if (!items.length) {
      const orgaplan = data.planDigest?.orgaplan || {};
      body.innerHTML = tileEmpty(orgaplan.status === "outdated" || orgaplan.status === "error"
        ? "Kein aktueller Orgaplan – siehe Hinweis oben."
        : "Heute keine besonderen Termine.");
      return;
    }
    body.innerHTML = tileList(items.slice(0, 6).map((item) => ({ ...item, title: truncateText(item.title, 160) })),
      items.length - 6, 'data-briefing-target="documents" data-plans-tab="orgaplan"');
  }

  function renderClassworkTile(data) {
    const body = document.getElementById("today-classwork-body");
    if (!body) return;
    const classwork = data.planDigest?.classwork || {};
    const plan = classwork.planStatus || {};
    const allClasses = (classwork.classes || []).filter(Boolean);
    const selected = getSelectedClassworkClasses(allClasses, classwork.defaultClass || "");
    const filtered = selected.length && selected.length < allClasses.length;
    setTileMeta("tile-classwork-meta", filtered ? (selected.length <= 3 ? selected.join(", ") : `${selected.length} Klassen`) : "");

    if (plan.state === "outdated") {
      body.innerHTML = tileEmpty("Der Klassenarbeitsplan ist veraltet.",
        window.MULTIUSER_ENABLED ? '<button class="btn btn-secondary btn-sm" type="button" data-open-connections="klassenarbeitsplan">Ansehen</button>' : "");
      return;
    }
    const todayIso = localIso(new Date());
    const horizon = addDaysIso(14);
    const entries = (classwork.entries || [])
      .filter((entry) => entry.isoDate && entry.isoDate >= todayIso && entry.isoDate <= horizon)
      .filter((entry) => !filtered || selected.includes(entry.classLabel))
      .sort((left, right) => left.isoDate.localeCompare(right.isoDate) || String(left.classLabel).localeCompare(String(right.classLabel)));
    if (!entries.length) {
      body.innerHTML = tileEmpty(plan.state === "ok" || (classwork.entries || []).length
        ? `Keine Arbeiten in den nächsten zwei Wochen${filtered ? " für deine Klassen" : ""}.`
        : "Noch kein Klassenarbeitsplan geladen.");
      return;
    }
    body.innerHTML = tileList(entries.slice(0, 5).map((entry) => ({
      when: dayLabel(entry.isoDate),
      title: `${entry.classLabel} · ${entry.summary || entry.title}`,
      cls: entry.isoDate === todayIso ? "is-today" : "",
    })), entries.length - 5, 'data-briefing-target="documents" data-plans-tab="klassenarbeitsplan"');
  }

  function isConnected(data, moduleId) {
    const module = (data.modules || {})[moduleId];
    return Boolean(module) && module.configured !== false;
  }

  function renderInboxTile(data) {
    const body = elements.todayInboxPreview;
    if (!body) return;
    const itslearning = isConnected(data, "itslearning");
    if (window.MULTIUSER_ENABLED && !itslearning) {
      setTileMeta("tile-inbox-meta", "");
      body.innerHTML = tileEmpty("Verbinde itslearning – dann siehst du hier Termine, Abgaben und Nachrichten deiner Kurse.",
        '<button class="btn btn-secondary btn-sm" type="button" data-open-connections="itslearning">Verbinden</button>');
      return;
    }
    const rows = [];
    const soon = addDaysIso(3);
    ((data.itslearningCalendar || {}).events || [])
      .filter((event) => event.kind === "todo" && String(event.start).slice(0, 10) <= soon)
      .slice(0, 2)
      .forEach((event) => rows.push({ when: dayLabel(event.start), title: event.title, tag: "Abgabe", tagCls: "tile-tag-warn" }));
    const messages = getRelevantInboxMessages(data).filter((message) => message.unread);
    messages.slice(0, 3).forEach((message) => rows.push({ title: message.title, sub: message.sender, tag: "itslearning" }));
    if (rows.length < 4) {
      ((data.itslearningCalendar || {}).events || [])
        .filter((event) => event.kind !== "todo" && String(event.start).slice(0, 10) <= addDaysIso(7))
        .slice(0, 4 - rows.length)
        .forEach((event) => rows.push({ when: dayLabel(event.start), title: event.title, tag: "Termin", tagCls: "tile-tag-event" }));
    }

    setTileMeta("tile-inbox-meta", messages.length ? `${messages.length} neu` : "");
    body.innerHTML = rows.length
      ? tileList(rows.slice(0, 4), 0, "")
      : tileEmpty("Nichts Neues.");
  }

  function renderUpcomingTile(data) {
    const body = elements.todayDocumentsPreview;
    if (!body) return;
    const tomorrow = addDaysIso(1);
    const horizon = addDaysIso(10);
    const rows = [];
    if (isModuleVisible("orgaplan")) {
      (data.planDigest?.orgaplan?.upcoming || [])
        .filter((entry) => entry.isoDate >= tomorrow && entry.isoDate <= horizon)
        .forEach((entry) => {
          const parts = orgaplanParts(entry);
          if (!parts.length) return;
          rows.push({ iso: entry.isoDate, title: parts.map((part) => part.text).join(" · "), tag: parts.length === 1 && parts[0].kind !== "general" ? parts[0].tag : "" });
        });
    }
    (data.schoolCalendar?.events || [])
      .filter((event) => event.start && event.start.slice(0, 10) >= tomorrow && event.start.slice(0, 10) <= horizon)
      .forEach((event) => rows.push({ iso: event.start.slice(0, 10), title: event.title, sub: event.time_label ? `${event.time_label} Uhr` : "", tag: "Termin", tagCls: "tile-tag-event" }));
    rows.sort((left, right) => left.iso.localeCompare(right.iso));
    // Multi-day items (class trips …) appear on every day of the plan: show them once with "bis …".
    const merged = [];
    const byTitle = new Map();
    rows.forEach((row) => {
      const key = `${row.tag}|${row.title}`;
      const first = byTitle.get(key);
      if (first) {
        first.until = row.iso;
        return;
      }
      byTitle.set(key, row);
      merged.push(row);
    });
    if (!merged.length) {
      body.innerHTML = tileEmpty("In den nächsten Tagen steht nichts Besonderes an.");
      return;
    }
    let previous = "";
    body.innerHTML = tileList(merged.slice(0, 6).map((row) => {
      const when = row.iso === previous ? "" : dayLabel(row.iso);
      previous = row.iso;
      const until = row.until ? `bis ${dayLabel(row.until)}` : "";
      return { ...row, when, title: truncateText(row.title, 140), sub: [row.sub, until].filter(Boolean).join(" · ") };
    }), merged.length - 6, 'data-briefing-target="documents" data-plans-tab="orgaplan"');
  }

  // Sources that need someone to act (outdated plan, broken link …): shown on top
  // of "Heute" and as a dot on "Verbindungen".
  function collectSourceAttention(data) {
    const items = [];
    if (!window.MULTIUSER_ENABLED || !data || !data.planDigest) return items;
    const personal = personalSourceProblems(data);
    if (personal.webuntis) items.push({ section: "webuntis", title: "Stundenplan", text: personal.webuntis });
    if (personal.itslearning) items.push({ section: "itslearning", title: "itslearning", text: personal.itslearning });
    const orgaplan = data.planDigest.orgaplan || {};
    if (isModuleVisible("orgaplan") && (orgaplan.status === "outdated" || orgaplan.status === "error")) {
      items.push({ section: "orgaplan", title: "Orgaplan", text: orgaplan.status === "outdated" ? "Kein aktueller Plan gefunden." : (orgaplan.error || "Konnte nicht gelesen werden.") });
    }
    const plan = (data.planDigest.classwork || {}).planStatus || {};
    const sync = data.classworkSync || {};
    if (isModuleVisible("klassenarbeitsplan")) {
      const previousLink = sync.onedrive && !sync.last_success && /^onedrive/.test(plan.source || "");
      if (previousLink && sync.last_error) {
        items.push({ section: "klassenarbeitsplan", title: "Klassenarbeitsplan", text: "Der neue Link lässt sich nicht laden." });
      } else if (previousLink) {
        // a new link is being loaded – nothing to do yet
      } else if (plan.state === "outdated") {
        items.push({ section: "klassenarbeitsplan", title: "Klassenarbeitsplan", text: plan.schoolYear ? `Plan von ${plan.schoolYear} – ein aktueller Link fehlt.` : "Der Plan enthält keine kommenden Termine." });
      } else if (sync.onedrive && sync.needs_browser && sync.last_result === "error") {
        items.push({ section: "klassenarbeitsplan", title: "Klassenarbeitsplan", text: "Abruf von OneDrive gestört." });
      }
    }
    return items;
  }

  function renderSourceAttention() {
    const items = collectSourceAttention(state.data);
    const box = document.getElementById("source-attention");
    const dot = document.getElementById("connections-attention-dot");
    if (dot) dot.hidden = !items.length;
    if (!box) return;
    box.hidden = !items.length;
    box.innerHTML = items.map((item) => `
      <div class="attention-item">
        <span class="attention-dot" aria-hidden="true"></span>
        <p><strong>${escapeHtml(item.title)}</strong> ${escapeHtml(item.text)}</p>
        <button class="btn btn-secondary btn-sm" type="button" data-open-connections="${escapeHtml(item.section)}">Ansehen</button>
      </div>`).join("");
  }

  function findNextLesson(data) {
    const events = (data.webuntisCenter?.events || []).filter((event) => event.startsAt);
    const now = new Date(data.generatedAt || Date.now());

    const upcoming = events
      .filter((event) => new Date(event.startsAt) >= now)
      .sort((left, right) => new Date(left.startsAt) - new Date(right.startsAt));

    if (upcoming.length) {
      return upcoming[0];
    }

    return events
      .filter((event) => isSameDay(new Date(event.startsAt), now))
      .sort((left, right) => new Date(left.startsAt) - new Date(right.startsAt))[0] || null;
  }

  function _nextSchoolDay(fromDate) {
    // Returns start of next Monday (or next day if weekday) after fromDate
    const d = new Date(fromDate);
    d.setDate(d.getDate() + 1);
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    return startOfDay(d);
  }

  // ── Lerngruppen-Erkennung & Klausur-Verknüpfung ─────────────────────────────
  // Leitet aus einer WebUntis-Stunde die Lerngruppe ab und verknüpft sie – aber
  // NUR wo die Datenlage es hergibt – mit dem Klassenarbeitsplan (Sek I) bzw.
  // dem Orgaplan (Oberstufe, nur als Tageskontext, nie an die Einzelstunde).

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function _normClassLabel(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, "");
  }

  // Sek-I-Klasse wie "8a", "10b" → eindeutig mit dem Klassenarbeitsplan koppelbar.
  function _isSekOneClass(label) {
    return /^(?:[5-9]|1[0-3])[a-z]$/i.test(String(label || "").trim());
  }

  // Oberstufe wie "Q1/Q2", "Q3", "S2" → nur Tageskontext, keine Kurszuordnung möglich.
  function _isOberstufeClass(label) {
    return /^(?:q\d|s\d)/i.test(String(label || "").trim());
  }

  // Nächste anstehende Arbeit für eine konkrete Sek-I-Klasse im Zeithorizont.
  function _upcomingClassworkForLabel(data, label, now, horizonDays) {
    const target = _normClassLabel(label);
    if (!target) return null;
    const entries = data.planDigest?.classwork?.entries || [];
    const todayStart = startOfDay(now);
    const horizon = new Date(todayStart);
    horizon.setDate(horizon.getDate() + (horizonDays || 14));
    return entries
      .filter((e) => e.isoDate && _normClassLabel(e.classLabel) === target)
      .map((e) => ({ entry: e, when: new Date(`${e.isoDate}T00:00:00`) }))
      .filter((x) => x.when >= todayStart && x.when <= horizon)
      .sort((a, b) => a.when - b.when)[0] || null;
  }

  // Kompaktes "wann"-Label relativ zu heute: heute / morgen / Wochentag / TT.MM.
  function _relativeDayLabel(when, now) {
    const todayStart = startOfDay(now);
    const diffDays = Math.round((startOfDay(when) - todayStart) / 86400000);
    if (diffDays <= 0) return "heute";
    if (diffDays === 1) return "morgen";
    if (diffDays <= 6) return when.toLocaleDateString("de-DE", { weekday: "short" });
    return when.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  }

  // Baut – wenn zulässig – ein Klausur-Flag für eine einzelne Stunde.
  // Gibt null zurück, wenn keine sichere Verknüpfung möglich ist.
  function _classworkFlagForEvent(data, event, now) {
    const labels = extractClassLabels(event);
    if (!labels.length) return null;
    for (const label of labels) {
      if (!_isSekOneClass(label)) continue; // Oberstufe & Sonstiges: nie an die Stunde
      const hit = _upcomingClassworkForLabel(data, label, now, 14);
      if (!hit) continue;
      const when = _relativeDayLabel(hit.when, now);
      const isToday = when === "heute";
      const kindShort = (hit.entry.kind || "Arbeit").toUpperCase().slice(0, 4);
      return {
        text: `${kindShort} ${when}`,
        tone: isToday ? "exam-today" : "exam",
        title: `${hit.entry.classLabel}: ${hit.entry.summary || hit.entry.title} (${hit.entry.dateLabel})`,
      };
    }
    return null;
  }

  // Tageskontext-Banner für die Oberstufe: zeigt heutige Orgaplan-"upper"-Infos
  // mit Klausurbezug – aber ohne zu behaupten, welcher Kurs schreibt.
  function _todayOberstufeExamBanner(data, todayEvents, now) {
    const orgaplan = data.planDigest?.orgaplan;
    if (!orgaplan) return "";
    // Nur relevant, wenn heute überhaupt eine eigene Oberstufen-Stunde ansteht
    // (dann können an LK-Klausurtagen im eigenen Kurs Schüler:innen fehlen).
    const hasOberstufeToday = (todayEvents || []).some((ev) =>
      extractClassLabels(ev).some((l) => _isOberstufeClass(l)));
    if (!hasOberstufeToday) return "";
    const todayIso = startOfDay(now).toLocaleDateString("en-CA"); // YYYY-MM-DD lokal
    const candidates = [...(orgaplan.today_entries || []), ...(orgaplan.upcoming || [])];
    const todayEntry = candidates.find((e) => (e.isoDate || "").slice(0, 10) === todayIso);
    const upperText = (todayEntry?.upper || "").trim();
    if (!upperText) return "";
    if (!/klausur|klaus|prüf|pruef|abitur|\blk\b|\bgk\b|\bkla\b/i.test(upperText)) return "";
    return '<div class="today-oberstufe-banner">'
      + '<span class="ts-banner-icon" aria-hidden="true">🎓</span>'
      + '<span><strong>Oberstufe heute:</strong> ' + escapeHtml(upperText)
      + ' <span class="ts-banner-hint">· laut Orgaplan, ohne Kurszuordnung</span></span>'
      + '</div>';
  }

  function isWebUntisConnected(data) {
    const webuntis = (data.modules || {}).webuntis;
    return !(webuntis && webuntis.configured === false);
  }

  // Today's lessons; after the last lesson (from 15:00) and on weekends the next school day.
  function isSupervision(event) {
    return window.LehrerWebUntis ? window.LehrerWebUntis.isSupervision(event) : event.category === "Aufsicht";
  }

  function todayLessons(data) {
    const now = new Date();
    const todayStart = startOfDay(now);
    const tomorrowStart = new Date(todayStart);
    tomorrowStart.setDate(tomorrowStart.getDate() + 1);
    const allEvents = (data.webuntisCenter?.events || []).filter((e) => e.startsAt);
    const between = (from, to) => allEvents
      .filter((e) => { const s = new Date(e.startsAt); return s >= from && s < to; })
      .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));

    const events = between(todayStart, tomorrowStart);
    const isWeekend = now.getDay() === 0 || now.getDay() === 6;
    const lastEnd = events.length ? new Date(events[events.length - 1].endsAt || events[events.length - 1].startsAt) : null;
    const dayOver = !events.length ? now.getHours() >= 15 : lastEnd <= now && now.getHours() >= 15;
    if (isWeekend || dayOver) {
      const nextDay = _nextSchoolDay(now);
      const nextDayEnd = new Date(nextDay);
      nextDayEnd.setDate(nextDayEnd.getDate() + 1);
      const next = between(nextDay, nextDayEnd);
      if (next.length) {
        return { events: next, previewLabel: nextDay.toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "2-digit" }) };
      }
    }
    return { events, previewLabel: null };
  }

  function renderTodayFullSchedule(data, events, previewLabel) {
    const now = new Date();
    const oberstufeBanner = previewLabel ? "" : _todayOberstufeExamBanner(data, events, now);
    const nextIndex = previewLabel ? -1 : events.findIndex((e) => !e.cancelled && new Date(e.startsAt) > now);
    return oberstufeBanner
      + '<ol class="today-schedule-list">'
      + events.map((e, index) => {
          const start = new Date(e.startsAt);
          const end = e.endsAt ? new Date(e.endsAt) : null;
          const cancelled = !!e.cancelled;
          const isCurrent = !previewLabel && !cancelled && start <= now && (!end || end > now);
          const isPast = !previewLabel && (end ? end <= now : start < now);
          const isNext = index === nextIndex && !events.some((other) => !other.cancelled && new Date(other.startsAt) <= now && (!other.endsAt || new Date(other.endsAt) > now));
          const stateClass = (cancelled ? " is-cancelled" : "") + (isCurrent ? " is-current" : isPast ? " is-past" : "") + (isNext ? " is-next" : "");
          const startStr = start.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
          const endStr = end ? end.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "";
          let flag = "";
          if (cancelled) {
            flag = '<span class="ts-flag ts-flag--cancelled">entfällt</span>';
          } else if (isCurrent) {
            flag = '<span class="ts-flag ts-flag--now">jetzt</span>';
          } else if (!isPast) {
            const exam = _classworkFlagForEvent(data, e, now);
            if (exam) flag = `<span class="ts-flag ts-flag--${exam.tone}" title="${escapeHtml(exam.title)}">${escapeHtml(exam.text)}</span>`;
            else if (isNext) flag = '<span class="ts-flag ts-flag--next">als Nächstes</span>';
          }
          const duty = isSupervision(e);
          return `<li class="today-schedule-row${stateClass}${duty ? " is-duty" : ""}">`
            + `<span class="today-schedule-time"><span>${startStr}</span>${endStr ? `<span class="today-schedule-end">${endStr}</span>` : ""}</span>`
            + (duty
              ? `<span class="today-schedule-main"><span class="today-schedule-title">Aufsicht</span><span class="today-schedule-loc">${escapeHtml(window.LehrerWebUntis ? window.LehrerWebUntis.dutyPlace(e) : e.location || "")}</span>`
              : `<span class="today-schedule-main"><span class="today-schedule-title">${escapeHtml(e.title || "")}</span>`
                + (e.location ? `<span class="today-schedule-loc">${escapeHtml(e.location)}</span>` : ""))
            + "</span>"
            + flag
            + "</li>";
        }).join("")
      + "</ol>";
  }

  function startOfDay(date) {
    const copy = new Date(date);
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  // Phase 16: Delegate to LehrerInbox module if available
  function pickInboxBriefing(data) {
    if (window.LehrerInbox) return window.LehrerInbox.pickInboxBriefing(data);
    return "";
  }

  const TODAY_LAYOUT_IDS = ["schedule", "school", "classwork", "inbox", "upcoming", "signals", "ai", "access"];

  function getDefaultTodayLayout() {
    return {
      order: TODAY_LAYOUT_IDS.slice(),
      visibility: TODAY_LAYOUT_IDS.reduce((acc, id) => ({ ...acc, [id]: true }), {}),
    };
  }

  function sanitizeTodayLayout(layout) {
    const base = getDefaultTodayLayout();
    if (!layout || typeof layout !== "object") {
      return base;
    }
    const order = Array.isArray(layout.order) ? layout.order.filter((id) => TODAY_LAYOUT_IDS.includes(id)) : [];
    TODAY_LAYOUT_IDS.forEach((id) => {
      if (!order.includes(id)) order.push(id);
    });
    const visibility = { ...base.visibility };
    if (layout.visibility && typeof layout.visibility === "object") {
      TODAY_LAYOUT_IDS.forEach((id) => {
        if (typeof layout.visibility[id] === "boolean") visibility[id] = layout.visibility[id];
      });
    }
    return { order, visibility };
  }

  const todayWideQuery = window.matchMedia("(min-width: 1024px)");

  // Tiles go into two columns on wide screens (main: schedule, inbox …; side:
  // school, classwork, upcoming) and into one column in layout order otherwise.
  function renderTodayModuleLayout() {
    const root = elements.todayOverviewGrid;
    if (!root) return;
    let layout = null;
    if (DashboardManager && typeof DashboardManager.getTodayLayout === "function") {
      layout = DashboardManager.getTodayLayout();
    } else {
      try {
        layout = JSON.parse(localStorage.getItem("lehrerCockpit.todayLayout.local") || "null");
      } catch (_error) {
        layout = null;
      }
    }
    layout = sanitizeTodayLayout(layout);

    const main = root.querySelector('[data-today-col="main"]');
    const side = root.querySelector('[data-today-col="side"]');
    const wide = todayWideQuery.matches;
    layout.order.forEach((id) => {
      const tile = root.querySelector(`[data-today-module="${id}"]`);
      if (!tile) return;
      const modules = TODAY_TILE_MODULES[id] || [];
      const allowed = !modules.length || !isLayoutReady() || isAnyModuleVisible(modules);
      tile.classList.toggle("is-layout-hidden", layout.visibility[id] === false || !allowed);
      if (id === "access") return; // quick links stay above the board
      const column = wide && tile.dataset.col === "side" ? side : main;
      if (tile.parentElement !== column) column.appendChild(tile);
      else column.appendChild(tile); // keep layout order inside the column
    });
    side.hidden = !wide;
    root.classList.remove("layout-pending");
  }

  if (todayWideQuery.addEventListener) {
    todayWideQuery.addEventListener("change", () => renderTodayModuleLayout());
  }
  window.addEventListener("lehrer:user", () => renderPageHead());
  if (window.LehrerLinks) window.LehrerLinks.onChange(() => renderHeuteZugaenge());
  // Another device changed class lists, links or settings (encrypted vault).
  window.addEventListener("lehrer:vault-updated", () => {
    state.classworkSelectedClasses = loadStoredClassworkClasses();
    if (window.LehrerClasslist) window.LehrerClasslist.render();
    if (window.LehrerCollections) window.LehrerCollections.render();
    if (window.LehrerLinks) window.LehrerLinks.reloadLocal();
    if (state.data) renderAll();
  });

  function renderExpandableSections() {
    elements.expandToggles.forEach((button) => {
      const panelKey = button.dataset.expandToggle || "";
      const targetId = button.dataset.expandTarget || "";
      const target = targetId ? document.getElementById(targetId) : null;
      if (!target) {
        return;
      }

      const expanded = Boolean(state.expandedPanels[panelKey]);
      target.classList.toggle("is-expanded", expanded);
      target.classList.toggle("is-collapsed", !expanded);
      button.textContent = expanded ? "Weniger anzeigen" : "Mehr anzeigen";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      const totalCount = Number(target.dataset.totalCount || 0);
      const collapsedCount = Number(target.dataset.collapsedCount || totalCount);
      const hasMeaningfulContent =
        target.children.length > 1 ||
        (target.firstElementChild && !target.firstElementChild.classList.contains("empty-state"));
      button.hidden = !hasMeaningfulContent || totalCount <= collapsedCount;
    });
  }

  // Delegated to LehrerItslearning (Phase 11d)
  function renderItslearningConnector() {
    if (window.LehrerItslearning) return window.LehrerItslearning.renderItslearningConnector();
  }

  // Phase 14: Delegate to LehrerNextcloud module if available
  function renderNextcloudConnector() {
    if (window.LehrerNextcloud) return window.LehrerNextcloud.renderNextcloudConnector();
  }

  // ── SECTION: Inbox — delegated to window.LehrerInbox ────────────────────────

  function renderPriorities() {
    if (window.LehrerInbox) return window.LehrerInbox.renderPriorities();
  }

  function renderSources() {
    if (window.LehrerInbox) return window.LehrerInbox.renderSources();
  }

  function renderMessages() {
    if (window.LehrerInbox) return window.LehrerInbox.renderMessages();
  }

  function renderInboxLinks() {
    const base = state.data?.base || {};
    const mailConnection = connectionHint("mail");
    const dienstmailUrl = base.dienstmail_url || DIENSTMAIL_DEFAULT_URL;
    if (elements.dienstmailOpenLink) {
      bindExternalLink(elements.dienstmailOpenLink, dienstmailUrl, "Dienstmail öffnen ↗");
      elements.dienstmailOpenLink.target = "_blank";
      elements.dienstmailOpenLink.rel = "noreferrer";
      elements.dienstmailOpenLink.hidden = false;
    }
    if (elements.itslearningOpenLink) {
      bindExternalLink(elements.itslearningOpenLink, base.itslearning_base_url || "", "itslearning öffnen ↗");
      elements.itslearningOpenLink.hidden = !base.itslearning_base_url;
    }
    // Posteingang: without itslearning and Nextcloud there is nothing to show yet.
    const data = getData();
    const itslearning = isConnected(data, "itslearning");
    const emptyPanel = document.getElementById("inbox-empty");
    if (emptyPanel) emptyPanel.hidden = !window.MULTIUSER_ENABLED || !state.data || itslearning;
    const messagesCard = document.getElementById("inbox-section");
    if (messagesCard) messagesCard.hidden = Boolean(window.MULTIUSER_ENABLED && state.data && !itslearning);
    renderMailSetupEntry();
  }

  function renderMailSetupEntry() {
    // Berliner Dienstmail hat kein IMAP — kein lokaler Agent mehr.
    // Schulportal-Link wird direkt in renderInboxLinks gesetzt.
    if (elements.dienstmailSetupStatus) {
      elements.dienstmailSetupStatus.textContent = "Dienstmail ist über das Schulportal erreichbar.";
    }
    if (elements.dienstmailSetupButton) {
      elements.dienstmailSetupButton.hidden = true;
    }
  }

  function getRelevantInboxMessages(data) {
    // Phase 11d: Delegate to LehrerItslearning module if available
    const d = data || getData();
    if (window.LehrerItslearning) return window.LehrerItslearning.getRelevantInboxMessages(d);
    return (d.messages || []).filter((message) => message.channel === "mail" || message.channel === "itslearning");
  }

  // ── Classwork rendering — delegated to window.LehrerClasswork ───────────────

  function renderPlanDigest() {
    if (window.LehrerClasswork) return window.LehrerClasswork.renderPlanDigest();
  }

  function getActiveClassworkClass(classes, defaultClass) {
    if (window.LehrerClasswork) return window.LehrerClasswork.getActiveClassworkClass(classes, defaultClass);
    return "";
  }

  function renderClassworkList(entries) {
    if (window.LehrerClasswork) return window.LehrerClasswork.renderClassworkList(entries);
    return "";
  }

  function renderClassworkCalendar(entries) {
    if (window.LehrerClasswork) return window.LehrerClasswork.renderClassworkCalendar(entries);
    return "";
  }

  // ── Grades data accessors + rendering — delegated to window.LehrerGrades (Phase 15) ─
  // Full implementations are in src/features/grades.js.

  // Phase 15: Delegate to LehrerGrades module if available
  function getGradebookData() {
    if (window.LehrerGrades) return window.LehrerGrades.getGradebookData();
    return state.gradesData || { status: 'empty', detail: '', updatedAt: '', entries: [], classes: [] };
  }

  function getGradeClasses() {
    if (window.LehrerGrades) return window.LehrerGrades.getGradeClasses();
    return [];
  }

  function getNotesData() {
    if (window.LehrerGrades) return window.LehrerGrades.getNotesData();
    return state.notesData || { status: 'empty', detail: '', updatedAt: '', notes: [], classes: [] };
  }

  function summarizeGrades(entries) {
    if (window.LehrerGrades) return window.LehrerGrades.summarizeGrades(entries);
    return { averageLabel: '-', riskCount: 0 };
  }

  // ── SECTION: Grades & notes ──────────────────────────────────────────────────

  function renderGrades() {
    if (window.LehrerGrades) return window.LehrerGrades.renderGrades();
  }

  function renderClassNotes(classes, suggestedClass) {
    if (window.LehrerGrades) return window.LehrerGrades.renderClassNotes(classes, suggestedClass);
  }

  // ── Orgaplan + classwork utilities — delegated to window.LehrerClasswork ────

  function renderOrgaplanItem(item) {
    if (window.LehrerClasswork) return window.LehrerClasswork.renderOrgaplanItem(item);
    return "";
  }

  function truncateText(value, maxLength) {
    if (window.LehrerClasswork) return window.LehrerClasswork.truncateText(value, maxLength);
    return String(value || "").slice(0, maxLength);
  }

  // weekdayLabel (string variant) is defined further below alongside formatTime/formatDate.
  // The duplicate copy that was here (lines formerly 1264–1274) has been removed.

  // ── Documents rendering — delegated to window.LehrerDocuments ───────────────

  function renderDocuments() {
    if (window.LehrerDocuments) return window.LehrerDocuments.renderDocuments();
  }

  function isPrimaryPlanDocument(entry) {
    if (window.LehrerDocuments) return window.LehrerDocuments.isPrimaryPlanDocument(entry);
    return false;
  }

  // ── SECTION: WebUntis (controls, picker, watchlist, schedule) ───────────────

  // ── WebUntis render functions — delegated to window.LehrerWebUntis (Phase 10c) ─
  // Full implementations are in src/features/webuntis.js.
  // These stubs remain so that any direct calls within app.js still work
  // during the transition period. Original bodies kept as TODO comments.

  // WebUntis render functions — all delegated to window.LehrerWebUntis (Phase 10c)
  function renderWebUntisControls() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWebUntisControls();
  }

  function renderWebUntisPicker() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWebUntisPicker();
  }

  function renderWebUntisWatchlist() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWebUntisWatchlist();
  }

  function renderWebUntisPlanStrip() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWebUntisPlanStrip();
  }

  function renderWebUntisSchedule() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWebUntisSchedule();
  }

  function renderWeekSchedule(events, center) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWeekSchedule(events, center);
    // TODO: remove after webuntis.js verified
    return '<div class="empty-state">WebUntis-Modul nicht geladen.</div>';
  }

  function renderAgendaGroups(groups, label) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderAgendaGroups(groups, label);
    return '';
  }

  function renderAgendaGroup(group) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderAgendaGroup(group);
    return '';
  }

  function renderDayGroup(group) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderDayGroup(group);
    return '';
  }

  function renderDayEvent(event) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderDayEvent(event);
    return '';
  }

  function renderWeekEvent(event) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.renderWeekEvent(event);
    return '';
  }

  function getWebUntisEvents() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.getWebUntisEvents();
    return [];
  }

  function groupEventsByDay(events) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.groupEventsByDay(events);
    return [];
  }

  function buildWeekColumns(events, currentDate) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.buildWeekColumns(events, currentDate);
    return [];
  }

  function getWeekAnchorDate(currentDate, view) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.getWeekAnchorDate(currentDate, view);
    return new Date(currentDate + 'T00:00:00');
  }

  function getWebUntisRangeLabel(center) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.getWebUntisRangeLabel(center);
    return state.webuntisView === 'day' ? 'Heute' : (center.currentWeekLabel || 'Diese Woche');
  }

  function bindExternalLink(element, url, label) {
    if (!element) {
      return;
    }
    if (url) {
      element.href = url;
      element.textContent = label;
      element.style.pointerEvents = "auto";
      element.style.opacity = "1";
      element.hidden = false;
    } else {
      element.href = "#";
      element.textContent = label;
      element.style.pointerEvents = "none";
      element.style.opacity = "0.5";
      element.hidden = true;
    }
  }

  function respondToAssistant(question) {
    const normalizedQuestion = question.trim().toLowerCase();
    const data = getData();
    const webuntisEvents = getWebUntisEvents();

    if (!normalizedQuestion) {
      return "Ich brauche noch eine konkrete Frage, zum Beispiel zu morgen, zu deiner Dienstmail oder zu neuen Dokumenten.";
    }

    if (normalizedQuestion.includes("webuntis") || normalizedQuestion.includes("stundenplan")) {
      if (!webuntisEvents.length) {
        return "Im aktuellen WebUntis-Zeitraum liegen gerade keine Termine vor.";
      }

      return webuntisEvents
        .slice(0, 4)
        .map((event) => `${event.title} um ${event.time}. ${event.detail}`)
        .join(" ");
    }

    if (normalizedQuestion.includes("pdf") || normalizedQuestion.includes("dokument")) {
      return data.documents
        .slice(0, 2)
        .map((entry) => `${entry.title}: ${entry.summary}`)
        .join(" ");
    }

    if (normalizedQuestion.includes("mail")) {
      const mailMessages = data.messages.filter((message) => message.channel === "mail");
      if (!mailMessages.length) {
        return "Aktuell ist keine lokale Dienstmail-Vorschau angebunden. Die Dienstmail bleibt aber über das Schulportal erreichbar.";
      }
      return mailMessages.slice(0, 2).map((message) => `${message.title}: ${message.snippet}`).join(" ");
    }

    if (normalizedQuestion.includes("woche") || normalizedQuestion.includes("termine")) {
      return webuntisEvents.map((event) => `${event.dateLabel}: ${event.title} (${event.time})`).join(" ");
    }

    return "Ich antworte hier nur auf Basis der Cockpit-Daten: Stundenplan, Dokumente, Dienstmail, itslearning und aktuelle Hinweise.";
  }

  // ── SECTION: Event registration ──────────────────────────────────────────────

  function registerEvents() {
    elements.briefingButton.addEventListener("click", async () => {
      await refreshDashboard(true);
    });

    // Cards on "Heute" jump to their section (briefing lead, focus cards, previews).
    // data-plans-tab selects the tab inside "Pläne".
    const briefingRoot = elements.todayOverviewGrid || elements.briefingOutput;
    briefingRoot.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea")) return;
      const target = event.target.closest("[data-briefing-target]");
      if (!target) return;
      const sectionId = target.dataset.briefingTarget;
      if (!sectionId || !isSectionEnabled(sectionId)) return;
      // Tap feedback: brief visual acknowledgment before/during scroll
      target.classList.add("is-tapping");
      setTimeout(() => target.classList.remove("is-tapping"), 280);
      state.activeSection = sectionId;
      renderSectionFocus();
      const tab = target.dataset.plansTab && document.querySelector(`.plans-tab-btn[data-plans-tab="${target.dataset.plansTab}"]`);
      if (tab) tab.click();
      window.scrollTo({ top: 0, behavior: "instant" });
    });

    // Keyboard support for briefing anchors
    briefingRoot.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const target = event.target.closest("[data-briefing-target]");
      if (!target || event.target !== target) return;
      event.preventDefault();
      target.click();
    });

    elements.navLinks.forEach((button) => {
      button.addEventListener("click", () => {
        state.activeSection = button.dataset.sectionTarget || "overview";
        renderSectionFocus();
        // "instant", not "auto": html has scroll-behavior: smooth, which would
        // briefly show the new section scrolled halfway down.
        window.scrollTo({ top: 0, behavior: "instant" });
      });
    });

    elements.expandToggles.forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.expandToggle || "";
        if (!key) {
          return;
        }
        state.expandedPanels[key] = !state.expandedPanels[key];
        persistExpandedPanels();
        renderExpandableSections();
      });
    });

    elements.documentSearch.addEventListener("input", (event) => {
      state.documentSearch = event.target.value;
      renderDocuments();
    });

    if (elements.webuntisPickerButton) {
      elements.webuntisPickerButton.addEventListener("click", () => {
        state.webuntisPickerOpen = true;
        state.webuntisPickerCategory = null;
        renderWebUntisPicker();
        if (elements.webuntisPickerSearch) {
          window.setTimeout(() => elements.webuntisPickerSearch.focus(), 30);
        }
      });
    }

    if (elements.webuntisPickerClose) {
      elements.webuntisPickerClose.addEventListener("click", closePicker);
    }
    if (elements.webuntisPickerBackdrop) {
      elements.webuntisPickerBackdrop.addEventListener("click", closePicker);
    }
    if (elements.webuntisPickerEdit) {
      elements.webuntisPickerEdit.addEventListener("click", () => {
        if (getActivePlan(getData().webuntisCenter).id !== "personal") {
          selectPlanById(getData().webuntisCenter, "personal");
          return;
        }
        closePicker();
      });
    }
    if (elements.webuntisPickerBack) {
      elements.webuntisPickerBack.addEventListener("click", () => {
        state.webuntisPickerCategory = null;
        renderWebUntisPicker();
      });
    }
    if (elements.webuntisPickerSearch) {
      elements.webuntisPickerSearch.addEventListener("input", (event) => {
        state.webuntisPickerSearch = event.target.value;
        renderWebUntisPicker();
      });
    }
    if (elements.webuntisRefreshButton) {
      elements.webuntisRefreshButton.addEventListener("click", async () => {
        if (elements.webuntisRefreshButton.disabled) {
          return;
        }
        const originalLabel = elements.webuntisRefreshButton.textContent;
        elements.webuntisRefreshButton.disabled = true;
        elements.webuntisRefreshButton.textContent = "Aktualisiere …";
        try {
          await refreshDashboard(true);
        } finally {
          elements.webuntisRefreshButton.disabled = false;
          elements.webuntisRefreshButton.textContent = originalLabel;
        }
      });
    }
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.webuntisPickerOpen) {
        closePicker();
      }
    });

    if (elements.itslearningConnectForm) {
      elements.itslearningConnectForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveItslearningCredentials();
      });
    }

    if (elements.nextcloudConnectForm) {
      elements.nextcloudConnectForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveNextcloudCredentials();
      });
    }

    [elements.nextcloudOpenRoot, elements.nextcloudOpenQ1Q2, elements.nextcloudOpenQ3Q4].filter(Boolean).forEach((link) => {
      link.addEventListener("click", () => {
        saveNextcloudLastOpened(link.dataset.nextcloudLink, link.querySelector("strong")?.textContent || link.textContent);
        renderNextcloudConnector();
      });
    });

    if (elements.themeToggle) {
      elements.themeToggle.addEventListener("click", () => {
        state.theme = state.theme === "dark" ? "light" : "dark";
        localStorage.setItem(THEME_KEY, state.theme);
        applyTheme();
      });
    }

    if (elements.classworkUploadButton && elements.classworkUploadInput) {
      elements.classworkUploadButton.addEventListener("click", () => {
        elements.classworkUploadInput.click();
      });

      elements.classworkUploadInput.addEventListener("change", async (event) => {
        const [file] = event.target.files || [];
        if (file) {
          await uploadClassworkFile(file);
        }
        event.target.value = "";
      });
    }

    if (elements.classworkClassFilter) {
      elements.classworkClassFilter.addEventListener("change", (event) => {
        setSelectedClassworkClasses(Array.from(event.target.selectedOptions || []).map((option) => option.value));
      });
    }

    if (elements.classworkClassSearch) {
      elements.classworkClassSearch.addEventListener("input", (event) => {
        state.classworkClassSearch = String(event.target.value || "").trim();
        renderPlanDigest();
      });
    }

    if (elements.gradesForm) {
      elements.gradesForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveGradeEntry();
      });
    }

    if (elements.gradesList) {
      elements.gradesList.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-grade-delete]");
        if (!button) {
          return;
        }
        await deleteGradeEntry(button.dataset.gradeDelete);
      });
    }
  }

  // ── SECTION: Render orchestration ────────────────────────────────────────────

  // ── SECTION: Zugaenge (Today) ───────────────────────────────────────────────

  function renderHeuteZugaenge() {
    if (window.LehrerLinks) window.LehrerLinks.setDashboard(getData());
    if (!window.LehrerZugaenge) return;
    window.LehrerZugaenge.init(getData());
    if (isModuleVisible('zugaenge')) {
      window.LehrerZugaenge.render('heute-zugaenge-container');
    } else {
      var el = document.getElementById('heute-zugaenge-container');
      if (el) el.innerHTML = '';
    }
  }

  function renderAll() {
    renderWorkspace();
    renderMeta();
    renderRuntimeBanner();
    renderTodayModuleLayout();
    renderSectionFocus();
    renderToday();
    renderHeuteZugaenge();
    renderItslearningConnector();
    renderNextcloudConnector();
    renderMessages();
    renderInboxLinks();
    // Slice 3: wire inbox tabs and update unread badges
    if (window.LehrerInbox && typeof window.LehrerInbox.initInboxTabs === 'function') {
      window.LehrerInbox.initInboxTabs();
    }
    if (window.LehrerInbox && typeof window.LehrerInbox.renderBadges === 'function') {
      window.LehrerInbox.renderBadges();
    }
    renderWebUntisControls();
    renderWebUntisSchedule();
    renderPlanDigest();
    renderGrades();
    renderDocuments();
    renderExpandableSections();
    renderNavSignals();
    renderSourceAttention();
    if (window.LehrerSignals) window.LehrerSignals.render();
  }

  // ── Slice 4: App title display ────────────────────────────────────────────

  function applyAppTitle() {
    var appTitle = (state.data && state.data.base && state.data.base.app_title)
      ? state.data.base.app_title
      : 'Lehrercockpit';
    if (!appTitle) appTitle = 'Lehrercockpit';
    document.title = appTitle;
    var titleEl = document.getElementById('app-title-display');
    if (titleEl) titleEl.textContent = appTitle;
  }

  // ── Slice 4: WebUntis external link ───────────────────────────────────────

  function updateWebUntisExternalLink() {
    return;
  }

  // Background work that depends on fresh dashboard data.
  function runBackgroundSyncs() {
    if (window.LehrerSignals) {
      window.LehrerSignals.syncPreferredClasses(state.classworkSelectedClasses || []);
    }
    if (window.LehrerOneDriveSync && state.data) {
      const pending = window.LehrerOneDriveSync.maybeSync(state.data, () => refreshDashboard(true));
      if (pending) pending.catch(() => {}); // status is shown under "Verbindungen"
    }
  }

  function whenUserKnown() {
    if (!window.MULTIUSER_ENABLED || window.CURRENT_USER) return Promise.resolve();
    return new Promise((resolve) => window.addEventListener("lehrer:user", resolve, { once: true }));
  }

  async function refreshDashboard(forceRefresh = false) {
    // Stale-while-revalidate: show the last state as soon as the user is known
    // (auth check, ~0.1 s), then replace it with fresh data from the network.
    if (!forceRefresh && !state.data) {
      whenUserKnown().then(() => {
        if (state.data) return;  // fresh data was faster
        const cached = loadDashboardCache();
        if (!cached) return;
        state.data = cached;
        state.showingCache = true;
        renderAll();
        applyAppTitle();
      });
    }
    if (elements.heroNote && (forceRefresh || !state.data)) {
      elements.heroNote.textContent = "Stand wird aktualisiert …";
    }
    try {
      const fresh = await loadDashboard(forceRefresh);
      state.data = fresh;
      state.showingCache = false;
      state.offlineSince = null;
      saveDashboardCache(fresh);
      renderAll();
      applyAppTitle();
      runBackgroundSyncs();
    } catch (error) {
      if (!window.MULTIUSER_ENABLED && window.LEHRER_COCKPIT_FALLBACK_DATA) {
        state.data = normalizeDashboard(window.LEHRER_COCKPIT_FALLBACK_DATA);
        renderAll();
        applyAppTitle();
        return;
      }
      // Keep what we have (or the last stored state, however old) and say so.
      state.showingCache = false;
      state.offlineSince = state.offlineSince || new Date();
      if (!state.data) state.data = loadDashboardCache(24 * 60 * 60 * 1000);
      if (state.data) {
        renderAll();
      } else {
        if (elements.heroNote) elements.heroNote.textContent = "Keine Verbindung";
        elements.briefingOutput.innerHTML = tileEmpty("Das Cockpit ist gerade nicht erreichbar. Bitte gleich noch einmal aktualisieren.");
        renderRuntimeBanner();
      }
    }
  }

  async function saveItslearningCredentials() {
    // Phase 11d: Delegate to LehrerItslearning module if available
    if (window.LehrerItslearning) return window.LehrerItslearning.saveItslearningCredentials();
    // TODO: remove fallback after itslearning.js verified in production
    const username = elements.itslearningUsername?.value.trim() || "";
    const password = elements.itslearningPassword?.value.trim() || "";

    if (!username || !password) {
      elements.itslearningConnectFeedback.textContent = "Bitte Benutzername und Passwort eintragen.";
      elements.itslearningConnectFeedback.className = "connect-feedback warning";
      return;
    }

    elements.itslearningConnectFeedback.textContent = "Speichere itslearning-Zugangsdaten ...";
    elements.itslearningConnectFeedback.className = "connect-feedback";

    // MULTIUSER_ENABLED = true — always use v2 API (Phase 8d: if/else removed)
    try {
      const resp = await window.LehrerAPI.saveModuleConfig("itslearning", { username, password });
      const payload = await resp.json();
      if (!resp.ok) throw new Error(payload.error || "Speichern fehlgeschlagen.");
      elements.itslearningConnectFeedback.textContent = "itslearning-Zugang gespeichert.";
      elements.itslearningConnectFeedback.className = "connect-feedback success";
      elements.itslearningPassword.value = "";
      await refreshDashboard(true);
    } catch (error) {
      elements.itslearningConnectFeedback.textContent = error.message || "itslearning-Zugang konnte nicht gespeichert werden.";
      elements.itslearningConnectFeedback.className = "connect-feedback warning";
    }
  }

  // Phase 14: Delegate to LehrerNextcloud module if available
  async function saveNextcloudCredentials() {
    if (window.LehrerNextcloud) return window.LehrerNextcloud.saveNextcloudCredentials();
  }

  function loadNextcloudLastOpened() {
    if (window.LehrerNextcloud) return window.LehrerNextcloud.loadNextcloudLastOpened();
    return null;
  }

  function saveNextcloudLastOpened(id, label) {
    if (window.LehrerNextcloud) return window.LehrerNextcloud.saveNextcloudLastOpened(id, label);
  }

  async function uploadClassworkFile(file) {
    if (!file.name.toLowerCase().match(/\.(xlsx|xlsm|xls|csv)$/)) {
      state.classworkUploadFeedback = "Bitte eine XLSX-, XLSM-, XLS- oder CSV-Datei auswählen.";
      state.classworkUploadFeedbackKind = "warning";
      renderPlanDigest();
      return;
    }

    state.classworkUploadFeedback = "Importiere Klassenarbeitsplan ...";
    state.classworkUploadFeedbackKind = "";
    renderPlanDigest();

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const apiBase = window.BACKEND_API_URL || "";

      const response = await fetch(`${apiBase}/api/classwork/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Import fehlgeschlagen.");
      }

      state.classworkUploadFeedback = payload.detail || "Klassenarbeitsplan aktualisiert.";
      state.classworkUploadFeedbackKind = "success";
      await refreshDashboard(true);
    } catch (error) {
      state.classworkUploadFeedback = error.message || "Klassenarbeitsplan konnte nicht importiert werden.";
      state.classworkUploadFeedbackKind = "warning";
      renderPlanDigest();
    }
  }

  // ── Grades / Notes — delegated to window.LehrerGrades (Phase 9e) ─────────────
  // These functions are now implemented in src/features/grades.js which uses
  // v2 endpoints (GET/POST /api/v2/modules/noten/*) when MULTIUSER_ENABLED is
  // true, and falls back to v1 for local runtime.

  async function loadGradebook() {
    if (window.LehrerGrades) {
      return window.LehrerGrades.loadGradebook();
    }
    // Minimal v1 fallback if grades.js failed to load
    try {
      const response = await window.LehrerAPI.legacy.getGrades();
      if (!response.ok) return;
      state.gradesData = await response.json();
      renderGrades();
    } catch (_error) { /* lokal optional */ }
  }

  async function loadNotes() {
    if (window.LehrerGrades) {
      return window.LehrerGrades.loadNotes();
    }
    // Minimal v1 fallback if grades.js failed to load
    try {
      const response = await window.LehrerAPI.legacy.getNotes();
      if (!response.ok) return;
      state.notesData = await response.json();
      renderClassNotes(getGradeClasses(), state.gradesSelectedClass);
      renderNavSignals();
    } catch (_error) { /* lokal optional */ }
  }

  async function saveGradeEntry() {
    if (window.LehrerGrades) {
      return window.LehrerGrades.saveGradeEntry();
    }
    // Fallback: show informational message if grades.js not available
    state.gradesFeedback = "Noten-Modul nicht geladen. Bitte Seite neu laden.";
    state.gradesFeedbackKind = "warning";
    renderGrades();
  }

  async function deleteGradeEntry(entryId) {
    if (window.LehrerGrades) {
      return window.LehrerGrades.deleteGradeEntry(entryId);
    }
  }

  async function saveClassNote() {
    if (window.LehrerGrades) {
      return window.LehrerGrades.saveClassNote();
    }
    // Fallback
    state.notesFeedback = "Noten-Modul nicht geladen. Bitte Seite neu laden.";
    state.notesFeedbackKind = "warning";
    renderClassNotes(getGradeClasses(), state.notesSelectedClass);
  }

  async function clearClassNote() {
    if (window.LehrerGrades) {
      return window.LehrerGrades.clearClassNote();
    }
  }

  // ── SECTION: Heute anpassen ───────────────────────────────────────────────────

  var _heuteAnpassenWired = false;
  var _heuteDragId = null;

  function getHeuteLayoutItems() {
    var labels = {
      schedule: "Stundenplan",
      school: "Heute an der Schule",
      classwork: "Klassenarbeiten",
      inbox: "Posteingang",
      upcoming: "Demnächst",
      signals: "Neu & geändert",
      ai: "KI-Zusammenfassung",
      access: "Zugänge (Schnellzugriff)",
    };
    if (!DashboardManager || typeof DashboardManager.getTodayLayout !== "function") {
      var localLayout = null;
      try {
        localLayout = sanitizeTodayLayout(JSON.parse(localStorage.getItem("lehrerCockpit.todayLayout.local") || "null"));
      } catch (_error) {
        localLayout = sanitizeTodayLayout(null);
      }
      return localLayout.order.map(function(id) {
        return {
          id: id,
          label: labels[id],
          mandatory: false,
          visible: localLayout.visibility[id] !== false,
        };
      });
    }

    var layout = sanitizeTodayLayout(DashboardManager.getTodayLayout());

    return layout.order.map(function(id) {
      return {
        id: id,
        label: labels[id] || id,
        mandatory: false,
        visible: layout.visibility[id] !== false,
      };
    });
  }

  function renderHeuteAnpassenList(modulesContainer) {
    if (!modulesContainer) return;
    var items = getHeuteLayoutItems();
    modulesContainer.innerHTML = items.map(function(item) {
      return '<div class="heute-sort-item" draggable="true" data-heute-sort-id="' + item.id + '">'
        + '<span class="heute-sort-item__grip" aria-hidden="true">⋮⋮</span>'
        + '<span class="heute-sort-item__copy-wrap">'
        + '<span class="heute-sort-item__copy">' + item.label + '</span>'
        + (item.mandatory ? '<span class="heute-sort-item__meta">Pflichtmodul</span>' : '')
        + '</span>'
        + '<label class="heute-sort-item__toggle">'
        + '<input type="checkbox" data-heute-visible-id="' + item.id + '"' + (item.visible ? ' checked' : '') + (item.mandatory ? ' disabled' : '') + ' />'
        + '<span>' + (item.mandatory ? 'immer aktiv' : 'anzeigen') + '</span>'
        + '</label>'
        + '</div>';
    }).join('');

    modulesContainer.querySelectorAll("[data-heute-sort-id]").forEach(function(item) {
      item.addEventListener("dragstart", function() {
        _heuteDragId = item.dataset.heuteSortId;
        item.classList.add("is-dragging");
      });
      item.addEventListener("dragend", function() {
        _heuteDragId = null;
        item.classList.remove("is-dragging");
        modulesContainer.querySelectorAll("[data-heute-sort-id]").forEach(function(entry) {
          entry.classList.remove("is-drop-target");
        });
      });
      item.addEventListener("dragover", function(event) {
        event.preventDefault();
        if (_heuteDragId && _heuteDragId !== item.dataset.heuteSortId) {
          item.classList.add("is-drop-target");
        }
      });
      item.addEventListener("dragleave", function() {
        item.classList.remove("is-drop-target");
      });
      item.addEventListener("drop", function(event) {
        event.preventDefault();
        item.classList.remove("is-drop-target");
        if (!_heuteDragId || _heuteDragId === item.dataset.heuteSortId) return;
        var dragged = modulesContainer.querySelector('[data-heute-sort-id="' + _heuteDragId + '"]');
        if (!dragged) return;
        modulesContainer.insertBefore(dragged, item);
      });
    });

    modulesContainer.querySelectorAll('[data-heute-visible-id]').forEach(function(input) {
      input.addEventListener('click', function(event) {
        event.stopPropagation();
      });
    });
  }

  function _renderHeuteAnpassenClasses() {
    var section = document.getElementById('heute-anpassen-classes-section');
    var pillsEl = document.getElementById('heute-anpassen-class-pills');
    if (!section || !pillsEl) return;

    var classes = [];
    try { classes = getData().planDigest.classwork.classes || []; } catch (_e) {}
    if (!classes.length) { section.hidden = true; return; }
    section.hidden = false;
    pillsEl.innerHTML = renderClassPills(classes, 'data-ha-class');
    pillsEl.querySelectorAll('[data-ha-class]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.haClass === '*') setSelectedClassworkClasses([]);
        else toggleClassworkClass(btn.dataset.haClass, classes);
        _renderHeuteAnpassenClasses();
      });
    });
  }

  // Same pills everywhere: "Alle" plus one pill per class.
  function renderClassPills(classes, attribute) {
    var picked = hasStoredClassworkSelection() ? getSelectedClassworkClasses(classes) : [];
    var all = !picked.length || picked.length === classes.length;
    return '<button type="button" class="classwork-pill' + (all ? ' is-active' : '') + '" ' + attribute + '="*" aria-pressed="' + all + '">Alle</button>'
      + classes.map(function (label) {
        var active = !all && picked.includes(label);
        return '<button type="button" class="classwork-pill' + (active ? ' is-active' : '') + '" ' + attribute + '="' + escapeHtml(label) + '" aria-pressed="' + active + '">' + escapeHtml(label) + '</button>';
      }).join('');
  }

  function initHeuteAnpassen() {
    var panel = document.getElementById('heute-anpassen-panel');
    var modulesContainer = document.getElementById('heute-anpassen-modules');
    var openBtn = document.getElementById('settings-button');
    var closeBtn = document.getElementById('heute-anpassen-close');
    var saveBtn = document.getElementById('heute-anpassen-save');
    if (!panel || !modulesContainer) return;

    renderHeuteAnpassenList(modulesContainer);

    // Wire buttons only once
    if (!_heuteAnpassenWired) {
      _heuteAnpassenWired = true;

      if (openBtn) {
        openBtn.addEventListener('click', function() {
          renderHeuteAnpassenList(modulesContainer);
          _renderHeuteAnpassenClasses();
          panel.hidden = false;
        });
      }

      if (closeBtn) {
        closeBtn.addEventListener('click', function() {
          panel.hidden = true;
        });
      }

      if (saveBtn) {
        saveBtn.addEventListener('click', async function() {
          var errorEl = panel.querySelector('.heute-anpassen-panel__error');
          if (!errorEl) {
            errorEl = document.createElement('p');
            errorEl.className = 'heute-anpassen-panel__error';
            var footer = panel.querySelector('.heute-anpassen-panel__footer');
            if (footer) footer.appendChild(errorEl);
          }
          errorEl.textContent = '';
          saveBtn.disabled = true;
          saveBtn.textContent = 'Speichern\u2026';

          var order = Array.from(modulesContainer.querySelectorAll('[data-heute-sort-id]')).map(function(item) {
            return item.dataset.heuteSortId;
          });
          var visibility = {};
          Array.from(modulesContainer.querySelectorAll('[data-heute-visible-id]')).forEach(function(input) {
            visibility[input.dataset.heuteVisibleId] = input.checked;
          });

          try {
            var nextLayout = sanitizeTodayLayout({
              order: order,
              visibility: visibility,
            });
            var ok = true;
            if (DashboardManager && typeof DashboardManager.saveHeuteLayout === "function") {
              ok = await DashboardManager.saveHeuteLayout(nextLayout);
            } else {
              try {
                localStorage.setItem("lehrerCockpit.todayLayout.local", JSON.stringify(nextLayout));
              } catch (_storageError) {}
            }
            if (ok) {
              panel.hidden = true;
              window.dispatchEvent(new CustomEvent('dashboard-layout-changed', {
                detail: { source: 'heute-anpassen' }
              }));
              if (typeof renderAll === 'function') renderAll();
            } else {
              errorEl.textContent = 'Fehler beim Speichern. Bitte erneut versuchen.';
            }
          } catch (_e) {
            errorEl.textContent = 'Verbindungsfehler. Bitte erneut versuchen.';
          } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Speichern';
          }
        });
      }
    }
  }

  // ── SECTION: Bootstrap / initialize ──────────────────────────────────────────

  // ── Today-date / badge initialisation ──────────────────────────────────────
  // Formerly an inline <script> in index.html; moved here so it lives inside
  // the module pattern and is not scattered across the HTML file.

  function initTodayDisplay() {
    renderPageHead();
  }

  function initMailSetup() {
    // Mail-Agent-Setup entfernt: lokaler Agent zu komplex für Lehrkräfte,
    // Berliner Dienstmail hat kein IMAP. Nur Link zum Schulportal.
    renderMailSetupEntry();
  }

  function initPlansTabs() {
    const buttons = document.querySelectorAll(".plans-tab-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("aria-controls");
        buttons.forEach((b) => {
          b.classList.toggle("is-active", b === btn);
          b.setAttribute("aria-selected", b === btn ? "true" : "false");
        });
        document.querySelectorAll(".plans-block[role='tabpanel']").forEach((panel) => {
          panel.hidden = panel.id !== targetId;
        });
      });
    });
  }

  function initialize() {
    initTodayDisplay();
    normalizeLocalWebUntisState();
    applyTheme();
    registerEvents();
    window.addEventListener("dashboard-layout-changed", () => {
      if (state.data) {
        renderAll();
      } else {
        renderSectionFocus();
      }
      initHeuteAnpassen();
    });
    // Init DashboardManager for multi-user module layout
    if (DashboardManager && typeof DashboardManager.init === "function") {
      DashboardManager.init();
    }
    // Init LehrerGrades with shared state, elements, and render callbacks (Phase 9e → 15)
    if (window.LehrerGrades) {
      window.LehrerGrades.init(state, elements, {
        getData: getData,
        getVisiblePanelItems: getVisiblePanelItems,
        setExpandableMeta: setExpandableMeta,
        renderNavSignals: renderNavSignals,
      });
    }
    // Init LehrerWebUntis with shared state, elements, and utility callbacks (Phase 10c)
    if (window.LehrerWebUntis) {
      window.LehrerWebUntis.init(state, elements, {
        getData: getData,
        renderAll: renderAll,
        formatDate: formatDate,
        formatTime: formatTime,
        weekdayLabel: weekdayLabel,
        isSameDay: isSameDay,
        startOfWeek: startOfWeek,
        isoWeekNumber: isoWeekNumber,
        bindExternalLink: bindExternalLink,
      });
    }
    // Init LehrerItslearning with shared state, elements, and render callbacks (Phase 11d)
    if (window.LehrerItslearning) {
      window.LehrerItslearning.init(state, elements, {
        getData: getData,
        renderMessages: renderMessages,
        renderNavSignals: renderNavSignals,
        refreshDashboard: refreshDashboard,
        IS_LOCAL_RUNTIME: IS_LOCAL_RUNTIME,
      });
    }
    // Init LehrerNextcloud with shared state, elements, and render callbacks (Phase 14)
    if (window.LehrerNextcloud) {
      window.LehrerNextcloud.init(state, elements, {
        getData: getData,
        refreshDashboard: refreshDashboard,
        isModuleVisible: isModuleVisible,
        formatTime: formatTime,
        IS_LOCAL_RUNTIME: IS_LOCAL_RUNTIME,
      });
    }
    // Init LehrerClasswork with shared state, elements, and render callbacks
    if (window.LehrerClasswork) {
      window.LehrerClasswork.init(state, elements, {
        getData: getData,
        bindExternalLink: bindExternalLink,
        isModuleVisible: isModuleVisible,
        getVisiblePanelItems: getVisiblePanelItems,
        setExpandableMeta: setExpandableMeta,
        weekdayLabel: weekdayLabel,
        getSelectedClassworkClasses: getSelectedClassworkClasses,
        setSelectedClassworkClasses: setSelectedClassworkClasses,
        toggleClassworkClass: toggleClassworkClass,
        renderClassPills: renderClassPills,
        refreshDashboard: refreshDashboard,
      });
    }
    // Init LehrerDocuments with shared state, elements, and render callbacks
    if (window.LehrerDocuments) {
      window.LehrerDocuments.init(state, elements, {
        getData: getData,
        getVisiblePanelItems: getVisiblePanelItems,
        setExpandableMeta: setExpandableMeta,
      });
    }
    // Init LehrerInbox with shared state, elements, and render callbacks
    if (window.LehrerInbox) {
      window.LehrerInbox.init(state, elements, {
        getData: getData,
        getRelevantInboxMessages: getRelevantInboxMessages,
        getVisiblePanelItems: getVisiblePanelItems,
        setExpandableMeta: setExpandableMeta,
      });
    }
    // Klassenlisten
    if (window.LehrerClasslist) {
      var classlistRoot = document.getElementById('classlist-root');
      if (classlistRoot) window.LehrerClasslist.init(classlistRoot);
    }

    // Einsammlungen
    if (window.LehrerCollections) {
      var collectionsRoot = document.getElementById('collections-root');
      if (collectionsRoot) window.LehrerCollections.init(collectionsRoot);
    }

    if (window.LehrerConnections) {
      window.LehrerConnections.init({
        onChanged: (sectionId) => {
          if (sectionId && DashboardManager && typeof DashboardManager.markConfigured === "function") {
            DashboardManager.markConfigured(sectionId);
          }
          refreshDashboard(true);
        },
      });
    }
    if (window.LehrerSignals) {
      window.LehrerSignals.init({ getData: getData });
    }
    if (window.LehrerAI) {
      window.LehrerAI.init();
    }

    initPlansTabs();
    const afterRefresh = () => {
      if (!window.MULTIUSER_ENABLED) loadClassworkCache();  // local single-user mode only
      loadGradebook();
      loadNotes();
    };
    refreshDashboard().then(afterRefresh);
    initMailSetup();
    window.setInterval(() => {
      refreshDashboard().then(afterRefresh);
    }, AUTO_REFRESH_MS);
  }

  function connectionHint(type) {
    return getData().localConnections?.[type] || {};
  }

  function loadExpandedPanels() {
    try {
      const raw = localStorage.getItem(EXPANDED_PANELS_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function persistExpandedPanels() {
    try {
      localStorage.setItem(EXPANDED_PANELS_KEY, JSON.stringify(state.expandedPanels));
    } catch (_error) {
      // ignore local storage errors
    }
  }

  function getVisiblePanelItems(items, panelKey) {
    const list = Array.isArray(items) ? items : [];
    if (state.expandedPanels[panelKey]) {
      return list;
    }
    const limit = PANEL_COLLAPSE_LIMITS[panelKey] || list.length;
    return list.slice(0, limit);
  }

  function setExpandableMeta(element, totalCount, visibleCount) {
    if (!element) {
      return;
    }

    const panelKey = element.dataset.expandPanel || "";
    const collapsedCount = panelKey ? Math.min(PANEL_COLLAPSE_LIMITS[panelKey] || totalCount, totalCount) : totalCount;
    element.dataset.totalCount = String(totalCount);
    element.dataset.visibleCount = String(visibleCount);
    element.dataset.collapsedCount = String(collapsedCount);
  }

  function loadStoredTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function loadStoredClassworkClasses() {
    try {
      const raw = localStorage.getItem(CLASSWORK_SELECTED_CLASSES_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch (_error) {
      return [];
    }
  }

  function hasStoredClassworkSelection() {
    try { return localStorage.getItem(CLASSWORK_SELECTED_CLASSES_KEY) !== null; } catch (_e) { return false; }
  }

  // One place for "Meine Klassen": Pläne, Heute anpassen, the Heute tile and the
  // server (signals/push) all read and write the selection through here.
  // An empty selection means "alle Klassen".
  function setSelectedClassworkClasses(classes) {
    const cleaned = Array.from(new Set((classes || []).filter(Boolean)));
    state.classworkSelectedClasses = cleaned;
    try {
      if (cleaned.length) localStorage.setItem(CLASSWORK_SELECTED_CLASSES_KEY, JSON.stringify(cleaned));
      else localStorage.removeItem(CLASSWORK_SELECTED_CLASSES_KEY);
    } catch (_error) {
      // ignore local storage errors
    }
    if (window.LehrerSignals) window.LehrerSignals.syncPreferredClasses(cleaned);
    renderAll();
  }

  // Click on a class pill: from "alle" the first click picks just that class;
  // afterwards clicks toggle. Removing the last class (or picking all) means "alle".
  function toggleClassworkClass(label, classes) {
    const available = (classes || []).filter(Boolean);
    const current = hasStoredClassworkSelection()
      ? (state.classworkSelectedClasses || []).filter((c) => available.includes(c))
      : [];
    let next = current.includes(label) ? current.filter((c) => c !== label) : current.concat([label]);
    if (next.length >= available.length) next = [];
    setSelectedClassworkClasses(next);
  }

  function getSelectedClassworkClasses(classes, defaultClass = "") {
    const availableClasses = Array.isArray(classes) ? classes.filter(Boolean) : [];
    if (!availableClasses.length) return [];

    // Check if user has ever explicitly saved a selection
    const hasStoredSelection = hasStoredClassworkSelection();
    if (!hasStoredSelection) {
      // Nothing saved yet → show all classes (no filter)
      return availableClasses;
    }

    const sanitized = (state.classworkSelectedClasses || []).filter((label) => availableClasses.includes(label));
    // Saved but all selected classes were removed from available → fall back to all
    return sanitized.length ? sanitized : availableClasses;
  }

  async function loadClassworkCache() {
    try {
      const resp = await window.LehrerAPI.legacy.getClasswork();
      if (!resp.ok) return;
      const data = await resp.json();
      const hasRows = (data.entries && data.entries.length > 0) ||
                      (data.previewRows && data.previewRows.length > 0);
      if (data.status === "ok" && hasRows) {
        renderClassworkData(data);
        if (data.hasChanges) {
          setUploadStatus(`⚡ Neue Änderungen! ${data.detail}`, "ok");
        } else {
          setUploadStatus(`✓ Gespeicherter Plan geladen. ${data.detail || ""}`, "ok");
        }
      }
      // If cache is empty/warning, silently ignore — dashboard data from /api/dashboard is sufficient
    } catch (_err) {
      // Silently ignore — backend may not be available
    }
  }

  // ── Classwork Upload ───────────────────────────────────────────────────────

  function setUploadStatus(message, type) {
    if (!elements.classworkUploadStatus) return;
    elements.classworkUploadStatus.textContent = message;
    elements.classworkUploadStatus.hidden = !message;
    elements.classworkUploadStatus.dataset.type = type || "";
  }

  function formatUploadTimestamp(isoString) {
    if (!isoString) return null;
    try {
      const d = new Date(isoString);
      const date = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
      const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      return `Stand: ${date}, ${time} Uhr`;
    } catch (_) {
      return null;
    }
  }

  function renderClassworkData(data) {
    if (!state.data) {
      return;
    }

    state.data.planDigest = state.data.planDigest || {};
    state.data.planDigest.classwork = {
      ...(state.data.planDigest.classwork || {}),
      ...data,
    };
    renderPlanDigest();
    renderToday();
  }

  function renderNavSignals() {
    const data = getData();
    const unreadCount = (data.messages || []).filter((message) => message.unread).length;
    elements.navLinks.forEach((button) => {
      const target = button.dataset.sectionTarget || "";
      let count = button.querySelector(".nav-count");
      if (target !== "inbox") return;
      if (!count) {
        count = document.createElement("span");
        count.className = "nav-count";
        button.appendChild(count);
      }
      count.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
      count.hidden = !unreadCount;
    });
  }

  async function triggerClassworkUpload(file) {
    if (!file) return;
    const apiBase = getBackendApiBase();
    const uploadUrl = `${apiBase}/api/classwork/upload`;

    const labelText = elements.classworkUploadLabelText;
    if (labelText) labelText.textContent = "⏳ Wird verarbeitet…";
    if (elements.classworkUploadLabel) elements.classworkUploadLabel.style.opacity = "0.6";
    setUploadStatus(`Datei "${file.name}" wird hochgeladen…`, "loading");

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);

      const response = await fetch(uploadUrl, { method: "POST", body: formData, credentials: "include" });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setUploadStatus(`Upload-Fehler: ${data.detail || response.status}`, "error");
        return;
      }

      renderClassworkData(data);
      setUploadStatus(`✓ "${file.name}" eingelesen. ${data.detail || ""}`, "ok");
    } catch (err) {
      setUploadStatus(`Upload fehlgeschlagen: ${err.message}`, "error");
    } finally {
      if (labelText) labelText.textContent = "📂 Hochladen";
      if (elements.classworkUploadLabel) elements.classworkUploadLabel.style.opacity = "1";
    }
  }

  // ── End Classwork Upload ───────────────────────────────────────────────────

  // ── SECTION: Pure utility functions (date, event, text helpers) ───────────────

  function buildProductionApiBases() {
    const bases = [];
    const configuredBase = (window.BACKEND_API_URL || window.LEHRER_COCKPIT_API_URL || "").trim();
    const configuredFallbacks = Array.isArray(window.LEHRER_COCKPIT_API_FALLBACKS)
      ? window.LEHRER_COCKPIT_API_FALLBACKS
      : [];

    if (window.location.protocol !== "file:") {
      bases.push(window.location.origin);
    }

    if (configuredBase) {
      bases.push(configuredBase);
    }

    configuredFallbacks.forEach((entry) => {
      if (typeof entry === "string" && entry.trim()) {
        bases.push(entry.trim());
      }
    });

    return bases.filter((entry, index, items) => items.indexOf(entry) === index);
  }

  /**
   * Return the base URL for backend API POST calls (scrape, upload, settings).
   * Uses the explicitly configured backend URL (Render) rather than window.location.origin
   * (which would be the Netlify frontend and has no API endpoints).
   */
  function getBackendApiBase() {
    if (IS_LOCAL_RUNTIME) return "";
    const configured = (window.BACKEND_API_URL || window.LEHRER_COCKPIT_API_URL || "").trim();
    if (configured) return configured;
    // Last resort: try same origin (works when frontend and backend are co-hosted)
    return window.location.protocol !== "file:" ? window.location.origin : "";
  }

  // ── WebUntis localStorage helpers — delegated to window.LehrerWebUntis (Phase 10c) ─
  // loadSavedShortcuts and loadWebUntisFavorites are called at state initialization
  // time (before init), so they include fallback implementations here too.

  function loadSavedShortcuts() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.loadSavedShortcuts();
    try {
      const raw = window.localStorage.getItem(WEBUNTIS_SHORTCUTS_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter((e) => e && e.id && e.label && e.type) : [];
    } catch (_e) { return []; }
  }

  function persistShortcuts() {
    window.localStorage.setItem(WEBUNTIS_SHORTCUTS_KEY, JSON.stringify(state.shortcuts));
  }

  function loadWebUntisFavorites() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.loadWebUntisFavorites();
    try {
      const raw = window.localStorage.getItem(WEBUNTIS_FAVORITES_KEY);
      const parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? parsed.filter((e) => typeof e === 'string') : [];
    } catch (_e) { return []; }
  }

  function persistFavorites() {
    window.localStorage.setItem(WEBUNTIS_FAVORITES_KEY, JSON.stringify(state.favorites));
  }

  function loadActiveShortcutId() {
    try {
      return window.localStorage.getItem(ACTIVE_WEBUNTIS_PLAN_KEY) || "personal";
    } catch (error) {
      return "personal";
    }
  }

  function persistActiveShortcutId() {
    window.localStorage.setItem(ACTIVE_WEBUNTIS_PLAN_KEY, state.activeShortcutId);
  }

  function getWebUntisPlans(center) {
    const defaultPlans = [];

    if (center.startUrl || center.todayUrl) {
      defaultPlans.push({
        id: "personal",
        type: "teacher",
        label: center.activePlan || "Mein Plan",
        url: center.startUrl || center.todayUrl,
        fixed: true,
      });
    }

    return [...defaultPlans, ...sanitizeShortcuts(state.shortcuts)];
  }

  function getPinnedPlans(center) {
    const basePlans = getWebUntisPlans(center);
    const favoriteEntities = getFavoriteEntities(center, "");

    const merged = [...basePlans];
    favoriteEntities.forEach((entity) => {
      if (!merged.some((plan) => plan.id === entity.id)) {
        merged.push({
          id: entity.id,
          type: entity.type,
          label: entity.label,
          url: entity.url || "",
          fixed: false,
          localFilter: !entity.url,
        });
      }
    });

    return merged.slice(0, 6);
  }

  function getActivePlan(center) {
    const activeEntity = getActiveFinderEntity(center);
    if (activeEntity && !activeEntity.url) {
      return {
        id: activeEntity.id,
        type: activeEntity.type,
        label: activeEntity.label,
        url: "",
        fixed: false,
        localFilter: true,
      };
    }

    const plans = getWebUntisPlans(center);
    return (
      plans.find((plan) => plan.id === state.activeShortcutId) ||
      plans[0] || {
        id: "personal",
        type: "teacher",
        label: center.activePlan || "Mein Plan",
        url: center.startUrl || center.todayUrl || "",
        fixed: true,
      }
    );
  }

  function getActiveFinderEntity(center) {
    return (center.finder?.entities || []).find((entity) => entity.id === state.activeFinderEntityId) || null;
  }

  function isPlanChipActive(center, plan) {
    if (plan.localFilter) {
      return state.activeFinderEntityId === plan.id;
    }

    if (plan.id === "personal") {
      return state.activeShortcutId === "personal" && !state.activeFinderEntityId;
    }

    return state.activeShortcutId === plan.id;
  }

  function getPickerEntities(center, type, query) {
    const entities = (center.finder?.entities || [])
      .filter((entity) => entity.type === type)
      .filter((entity) => {
        if (!query) {
          return true;
        }
        const haystack = `${entity.label} ${entity.detail} ${entity.type}`.toLowerCase();
        return haystack.includes(query);
      });

    if (type !== "teacher") {
      return entities;
    }

    const teacherEntries = [
      {
        id: "personal",
        type: "teacher",
        label: center.activePlan || "Mein Stundenplan",
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || "",
        fixed: true,
      },
      ...entities,
    ];

    return teacherEntries.filter((entity, index, items) => items.findIndex((item) => item.id === entity.id) === index);
  }

  function getFavoriteEntities(center, query) {
    const allEntities = [
      {
        id: "personal",
        type: "teacher",
        label: center.activePlan || "Mein Stundenplan",
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || "",
        fixed: true,
      },
      ...(center.finder?.entities || []),
    ];

    return allEntities
      .filter((entity) => state.favorites.includes(entity.id))
      .filter((entity) => {
        if (!query) {
          return true;
        }
        const haystack = `${entity.label} ${entity.detail} ${entity.type}`.toLowerCase();
        return haystack.includes(query);
      });
  }

  function getGlobalPickerResults(center, query) {
    if (!query) {
      return [];
    }

    const combined = [
      {
        id: "personal",
        type: "teacher",
        label: center.activePlan || "Mein Stundenplan",
        detail: center.detail || center.note,
        url: center.startUrl || center.todayUrl || "",
        fixed: true,
      },
      ...(center.finder?.entities || []),
    ];

    return combined
      .filter((entity) => {
        const haystack = `${entity.label} ${entity.detail} ${entity.type}`.toLowerCase();
        return haystack.includes(query);
      })
      .filter((entity, index, items) => items.findIndex((item) => item.id === entity.id) === index)
      .slice(0, 8);
  }

  function isEntityActive(center, entity) {
    if (entity.id === "personal") {
      return state.activeShortcutId === "personal" && !state.activeFinderEntityId;
    }

    if (entity.url) {
      return state.activeShortcutId === entity.id || state.activeShortcutId === `picker-${entity.id}`;
    }

    return state.activeFinderEntityId === entity.id;
  }

  function renderPickerItem(entity, options = {}) {
    const { active = false, showFavorite = true, compact = false } = options;
    return `
      <article class="picker-item ${active ? "active" : ""} ${compact ? "compact" : ""}">
        <button class="picker-item-main" type="button" data-picker-select="${entity.id}">
          <span class="picker-item-icon">${pickerIcon(entity.type)}</span>
          <span class="picker-item-copy">
            <strong>${entity.label}</strong>
            ${entity.detail ? `<span>${entity.detail}</span>` : ""}
          </span>
        </button>
        ${
          showFavorite
            ? `<button class="picker-star ${state.favorites.includes(entity.id) ? "active" : ""}" type="button" data-picker-favorite="${entity.id}" aria-label="Favorit umschalten">★</button>`
            : ""
        }
      </article>
    `;
  }

  function bindPickerActions(center) {
    elements.webuntisPickerCurrent.querySelectorAll("[data-picker-select], [data-picker-favorite]").forEach((button) => {
      if (button.dataset.pickerSelect) {
        button.addEventListener("click", () => selectPlanById(center, button.dataset.pickerSelect));
      }
      if (button.dataset.pickerFavorite) {
        button.addEventListener("click", () => toggleFavorite(button.dataset.pickerFavorite));
      }
    });
    elements.webuntisPickerResults.querySelectorAll("[data-picker-select], [data-picker-favorite]").forEach((button) => {
      if (button.dataset.pickerSelect) {
        button.addEventListener("click", () => selectPlanById(center, button.dataset.pickerSelect));
      }
      if (button.dataset.pickerFavorite) {
        button.addEventListener("click", () => toggleFavorite(button.dataset.pickerFavorite));
      }
    });
    elements.webuntisPickerFavorites.querySelectorAll("[data-picker-select], [data-picker-favorite]").forEach((button) => {
      if (button.dataset.pickerSelect) {
        button.addEventListener("click", () => selectPlanById(center, button.dataset.pickerSelect));
      }
      if (button.dataset.pickerFavorite) {
        button.addEventListener("click", () => toggleFavorite(button.dataset.pickerFavorite));
      }
    });
    elements.webuntisPickerCategoryResults.querySelectorAll("[data-picker-select], [data-picker-favorite]").forEach((button) => {
      if (button.dataset.pickerSelect) {
        button.addEventListener("click", () => selectPlanById(center, button.dataset.pickerSelect));
      }
      if (button.dataset.pickerFavorite) {
        button.addEventListener("click", () => toggleFavorite(button.dataset.pickerFavorite));
      }
    });
  }

  function selectPlanById(center, planId) {
    const entity = planId === "personal"
      ? {
          id: "personal",
          type: "teacher",
          label: center.activePlan || "Mein Plan",
          url: center.startUrl || center.todayUrl || "",
        }
      : (center.finder?.entities || []).find((item) => item.id === planId) || state.shortcuts.find((item) => item.id === planId);

    if (!entity) {
      return;
    }

    if (entity.id === "personal") {
      state.activeShortcutId = "personal";
      state.activeFinderEntityId = null;
    } else if (entity.url) {
      const shortcutId = entity.id.startsWith("shortcut-") ? entity.id : `picker-${entity.id}`;
      const existing = state.shortcuts.find((shortcut) => shortcut.id === shortcutId);
      if (!existing) {
        state.shortcuts.unshift({
          id: shortcutId,
          type: entity.type,
          label: entity.label,
          url: entity.url,
        });
        persistShortcuts();
      }
      state.activeShortcutId = shortcutId;
      state.activeFinderEntityId = null;
    } else {
      state.activeShortcutId = "personal";
      state.activeFinderEntityId = entity.id;
    }

    persistActiveShortcutId();
    closePicker();
    renderAll();
  }

  function toggleFavorite(entityId) {
    if (state.favorites.includes(entityId)) {
      state.favorites = state.favorites.filter((id) => id !== entityId);
    } else {
      state.favorites.unshift(entityId);
    }
    persistFavorites();
    renderWebUntisPicker();
    renderWebUntisPlanStrip();
  }

  function closePicker() {
    state.webuntisPickerOpen = false;
    state.webuntisPickerCategory = null;
    state.webuntisPickerSearch = "";
    renderWebUntisPicker();
  }

  function normalizeLocalWebUntisState() {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.normalizeLocalWebUntisState();
  }

  function compactEventDetail(event) {
    if (window.LehrerWebUntis) return window.LehrerWebUntis.compactEventDetail(event);
    return "";
  }

  function sanitizeShortcuts(entries) {
    return entries
      .filter((entry) => entry && typeof entry === "object")
      .filter((entry) => entry.id && entry.label && entry.type)
      .filter((entry) => !isPlaceholderTeacher(entry.label))
      .filter((entry, index, items) => items.findIndex((item) => item.id === entry.id) === index);
  }

  function sanitizeFavorites(entries) {
    return entries
      .filter((entry) => typeof entry === "string" && entry)
      .filter((entry) => !entry.includes("mustermann"))
      .filter((entry, index, items) => items.indexOf(entry) === index);
  }

  function isPlaceholderTeacher(label) {
    const normalized = String(label || "").trim().toLowerCase();
    return normalized === "herr mustermann" || normalized === "frau mustermann" || normalized === "mustermann";
  }

  function eventMatchesFinderEntity(event, entity) {
    const needle = entity.label.toLowerCase();
    if (entity.type === "room") {
      return (event.location || "").toLowerCase().includes(needle);
    }

    if (entity.type === "class") {
      const haystack = `${event.title || ""} ${event.detail || ""} ${event.description || ""}`.toLowerCase();
      return haystack.includes(needle);
    }

    return false;
  }

  // priorityLabel, messagePriorityClass, compareMessageTime, statusLabel,
  // monitorStatusLabel, monitorStatusClass moved to src/features/inbox.js

  function watchStatusLabel(status) {
    return (
      {
        changed: "geändert",
        watch: "beobachten",
        synced: "live",
      }[status] || status
    );
  }

  function watchStatusClass(status) {
    return (
      {
        changed: "high",
        watch: "low",
        synced: "low",
      }[status] || ""
    );
  }

  function shortcutTypeLabel(type) {
    return (
      {
        teacher: "Lehrkraft",
        class: "Klasse",
        room: "Raum",
      }[type] || type
    );
  }

  function pickerIcon(type) {
    return (
      {
        teacher: "L",
        class: "K",
        room: "R",
      }[type] || "•"
    );
  }

  function formatTime(value) {
    return value.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }

  function formatDate(value) {
    return value.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  }

  function weekdayLabel(value) {
    if (value instanceof Date) {
      return value.toLocaleDateString("de-DE", { weekday: "long" });
    }

    const token = String(value || "").toLowerCase();
    if (token.startsWith("mon")) return "Montag";
    if (token.startsWith("tue")) return "Dienstag";
    if (token.startsWith("wed")) return "Mittwoch";
    if (token.startsWith("thu")) return "Donnerstag";
    if (token.startsWith("fri")) return "Freitag";
    if (token.startsWith("sat")) return "Samstag";
    if (token.startsWith("sun")) return "Sonntag";
    return value || "";
  }

  function isSameDay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function startOfWeek(value) {
    const result = new Date(value);
    const day = result.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    result.setDate(result.getDate() + diff);
    result.setHours(0, 0, 0, 0);
    return result;
  }

  function isoWeekNumber(value) {
    const date = new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
    const day = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        const [, base64 = ""] = result.split(",", 2);
        resolve(base64);
      };
      reader.onerror = () => reject(new Error("Datei konnte lokal nicht gelesen werden."));
      reader.readAsDataURL(file);
    });
  }

  function getEventTimingClass(event) {
    const now = new Date();
    const start = new Date(event.startsAt);
    const end = new Date(event.endsAt);
    if (end < now) {
      return "is-past";
    }
    if (start <= now && now < end) {
      return "is-current";
    }
    return "is-upcoming";
  }

  function isEventCurrent(event) {
    return getEventTimingClass(event) === "is-current";
  }

  function eventStateLabel(event) {
    if (isCancelledEvent(event)) {
      return "entfällt";
    }
    const timingClass = getEventTimingClass(event);
    if (timingClass === "is-past") {
      return "vorbei";
    }
    if (timingClass === "is-current") {
      return "jetzt";
    }
    return "kommt";
  }

  function eventStateTagClass(event) {
    if (isCancelledEvent(event)) {
      return "critical";
    }
    const timingClass = getEventTimingClass(event);
    if (timingClass === "is-past") {
      return "low";
    }
    if (timingClass === "is-current") {
      return "ok";
    }
    return "";
  }

  function isCancelledEvent(event) {
    const haystack = `${event.title || ""} ${event.description || ""} ${event.detail || ""}`.toLowerCase();
    return /(entf[aä]llt|ausfall|ausfaellt|fällt aus|faellt aus|cancelled|verlegt|vertretung)/i.test(haystack);
  }

  function findNextEventAfter(referenceIsoDate) {
    const events = (getData().webuntisCenter?.events || [])
      .filter((event) => event.startsAt)
      .filter((event) => event.startsAt.slice(0, 10) > referenceIsoDate)
      .sort((left, right) => new Date(left.startsAt) - new Date(right.startsAt));
    return events[0] || null;
  }

  function renderEmptyWeekColumn(column, hasAnyWeekEvents) {
    if (hasAnyWeekEvents) {
      return `<div class="webuntis-week-empty">Kein iCal-Eintrag für diesen Tag</div>`;
    }

    const nextEvent = findNextEventAfter(column.isoDate);
    if (nextEvent) {
      return `<div class="webuntis-week-empty">Im iCal keine Termine. Nächster Eintrag am ${formatDate(new Date(nextEvent.startsAt))}.</div>`;
    }

    return `<div class="webuntis-week-empty">Im iCal sind für diese Woche gerade keine Termine vorhanden.</div>`;
  }

  function extractClassLabels(event) {
    const haystack = `${event.title || ""} ${event.detail || ""} ${event.description || ""}`.match(/\b(?:[5-9][A-Z]?|1[0-3][A-Z]?|Q\d(?:\/Q?\d)?)\b/gi);
    return haystack ? haystack.map((token) => token.toUpperCase()) : [];
  }

  // formatNoteTimestamp moved to src/features/grades.js (Phase 15)

  initialize();
})();
