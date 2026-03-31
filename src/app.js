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
// This file owns: loadDashboard(), renderAll(), renderBriefing(), renderStats(),
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
    webuntisView: "week",
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
    todayBriefingFocus: document.querySelector("#today-briefing-focus"),
    todaySchedulePreview: document.querySelector("#today-schedule-preview"),
    todayInboxPreview: document.querySelector("#today-inbox-preview"),
    todayDocumentsPreview: document.querySelector("#today-documents-preview"),
    todayGradesPreview: document.querySelector("#today-grades-preview"),
    todayAssistantPreview: document.querySelector("#today-assistant-preview"),
    heroNote: document.querySelector("#hero-note"),
    runtimeBanner: document.querySelector("#runtime-banner"),
    settingsButton: document.querySelector("#settings-button"),
    themeToggle: document.querySelector("#theme-toggle"),
    themeToggleLabel: document.querySelector(".theme-toggle-label"),
    navLinks: Array.from(document.querySelectorAll("[data-section-target]")),
    viewSections: Array.from(document.querySelectorAll("[data-view-section]")),
    viewDividers: Array.from(document.querySelectorAll("[data-divider-for]")),
    todayOverviewGrid: document.querySelector("#today-overview-grid"),
    todayModuleCards: Array.from(document.querySelectorAll("[data-today-module]")),
    expandToggles: Array.from(document.querySelectorAll("[data-expand-toggle]")),
    workspaceEyebrow: document.querySelector("#workspace-eyebrow"),
    workspaceTitle: document.querySelector("#workspace-title"),
    statsGrid: document.querySelector("#stats-grid"),
    quickLinkGrid: document.querySelector("#quick-link-grid"),
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
    classworkBrowserFetchButton: document.querySelector("#classwork-browser-fetch-button"),
    classworkUploadStatus: document.querySelector("#classwork-upload-status"),
    classworkDigestDetail: document.querySelector("#classwork-digest-detail"),
    classworkClassFilter: document.querySelector("#classwork-class-filter"),
    classworkViewSwitch: document.querySelector("#classwork-view-switch"),
    classworkPreviewList: document.querySelector("#classwork-preview-list"),
    classworkUploadButton: document.querySelector("#classwork-upload-button"),
    classworkUploadFeedback: document.querySelector("#classwork-upload-feedback"),
    gradesDetail: document.querySelector("#grades-detail"),
    gradesSummaryClass: document.querySelector("#grades-summary-class"),
    gradesSummaryCount: document.querySelector("#grades-summary-count"),
    gradesSummaryAverage: document.querySelector("#grades-summary-average"),
    gradesSummaryRisk: document.querySelector("#grades-summary-risk"),
    gradesClassInput: document.querySelector("#grades-class-input"),
    gradesTypeInput: document.querySelector("#grades-type-input"),
    gradesStudentInput: document.querySelector("#grades-student-input"),
    gradesTitleInput: document.querySelector("#grades-title-input"),
    gradesValueInput: document.querySelector("#grades-value-input"),
    gradesDateInput: document.querySelector("#grades-date-input"),
    gradesCommentInput: document.querySelector("#grades-comment-input"),
    gradesFeedback: document.querySelector("#grades-feedback"),
    gradesForm: document.querySelector("#grades-form"),
    gradesClassFilter: document.querySelector("#grades-class-filter"),
    gradesList: document.querySelector("#grades-list"),
    notesForm: document.querySelector("#class-notes-form"),
    notesClassFilter: document.querySelector("#class-notes-class-filter"),
    notesInput: document.querySelector("#class-notes-input"),
    notesFeedback: document.querySelector("#class-notes-feedback"),
    notesList: document.querySelector("#class-notes-list"),
    notesClearButton: document.querySelector("#class-notes-clear"),
    documentList: document.querySelector("#document-list"),
    documentsExtraBlock: document.querySelector("#documents-extra-block"),
    documentSearch: document.querySelector("#document-search"),
    documentSearchWrap: document.querySelector("#document-search-wrap"),
    assistantForm: document.querySelector("#assistant-form"),
    assistantInput: document.querySelector("#assistant-input"),
    assistantAnswer: document.querySelector("#assistant-answer"),
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
  // renderStats() and renderBriefing() skip module-derived content until this returns true.
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
      case "assistant":
        return true;
      case "grades":
        return DashboardManager && typeof DashboardManager.isModuleVisible === 'function'
          ? DashboardManager.isModuleVisible('noten')
          : true;
      case "access":
        return false;
      default:
        return true;
    }
  }

  // ── SECTION: API / data loading ─────────────────────────────────────────────

  async function loadDashboard(forceRefresh = false) {
    // ── Phase 12: v2 PRIMARY path ──────────────────────────────────────────
    // When running in multi-user SaaS mode, call GET /api/v2/dashboard/data
    // first. The response includes a 'base' section (quickLinks, workspace,
    // berlinFocus) plus all per-module data. normalizeV2Dashboard() maps the
    // v2 response to the same shape all render functions expect.
    // If the v2 call fails for any reason, fall through to the v1 path below.
    if (window.MULTIUSER_ENABLED && window.LehrerAPI) {
      try {
        const resp = await window.LehrerAPI.getDashboardData();
        if (resp.ok) {
          const v2Json = await resp.json();
          if (v2Json.ok) {
            return normalizeV2Dashboard(v2Json);
          }
        }
      } catch (e) {
        console.warn('[Dashboard] v2 primary failed, falling back to v1:', e.message);
      }
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
      shortcutHint: "WebUntis-Links koennen hier als Schnellzugriff gespeichert werden.",
    };

    data.planDigest = data.planDigest || {
      orgaplan: {
        status: "warning",
        title: "Orgaplan",
        detail: "Noch kein Orgaplan-Digest verfuegbar.",
        monthLabel: "",
        updatedAt: formatTime(now),
        highlights: [],
        upcoming: [],
        sourceUrl: "",
      },
      classwork: {
        status: "warning",
        title: "Klassenarbeitsplan",
        detail: "Noch kein Klassenarbeitsplan-Digest verfuegbar.",
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
    // v2 = ItslearningSyncResult dict: {source, messages[], priorities[], mode, note}
    if (!v2) return;
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
    // v2 = {url, pdf_url, highlights, upcoming, today_entries, week_entries, status, monthLabel, ...}
    // Also accepts wrapped form: {digest: {...}}
    if (!v2) return;
    var digest = v2.digest || v2;
    if (digest.status === 'ok' || digest.highlights || digest.upcoming) {
      data.planDigest = data.planDigest || {};
      data.planDigest.orgaplan = Object.assign({}, data.planDigest.orgaplan, digest, {
        today_entries: digest.today_entries || [],
        week_entries: digest.week_entries || [],
      });
    }
  }

  function _applyClassworkV2Data(data, v2) {
    // v2 = {url, status, entries[], previewRows[], classes[], ...}
    if (!v2) return;
    if (v2.status === 'ok') {
      data.planDigest = data.planDigest || {};
      data.planDigest.classwork = Object.assign({}, data.planDigest.classwork, v2);
    }
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
  // All render functions (renderWorkspace, renderStats, renderBriefing, etc.)
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
          shortcutHint: "WebUntis-Links koennen hier als Schnellzugriff gespeichert werden.",
        },
        planDigest: {
          orgaplan: {
            status: "warning",
            title: "Orgaplan",
            detail: "Noch kein Orgaplan-Digest verfuegbar.",
            monthLabel: "",
            updatedAt: formatTime(new Date()),
            highlights: [],
            upcoming: [],
            sourceUrl: "",
          },
          classwork: {
            status: "warning",
            title: "Klassenarbeitsplan",
            detail: "Noch kein Klassenarbeitsplan-Digest verfuegbar.",
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
    const schoolName =
      data.base?.school_name ||
      data.teacher?.school ||
      (titleFromWorkspace.startsWith("Dein Tagesstart fuer ")
        ? titleFromWorkspace.replace("Dein Tagesstart fuer ", "")
        : "");
    if (elements.workspaceEyebrow) {
      elements.workspaceEyebrow.textContent = data.workspace.eyebrow || "Berlin Lehrer-Cockpit";
    }
    if (elements.workspaceTitle) {
      elements.workspaceTitle.textContent = schoolName || titleFromWorkspace || "Lehrer-Cockpit";
    }
  }

  function applyTheme() {
    document.documentElement.dataset.theme = state.theme;
    if (elements.themeToggle) {
      const isDark = state.theme === "dark";
      elements.themeToggle.setAttribute("aria-pressed", String(isDark));
      elements.themeToggle.classList.toggle("is-dark", isDark);
      if (elements.themeToggleLabel) {
        elements.themeToggleLabel.textContent = isDark ? "Dunkles Theme" : "Helles Theme";
      }
    }
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
  }

  function renderMeta() {
    const data = getData();
    if (elements.heroNote) {
      elements.heroNote.textContent = `Stand ${data.meta.lastUpdatedLabel}`;
    }
  }

  function renderRuntimeBanner() {
    const data = getData();

    if (window.location.protocol === "file:") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        "Direktdatei geoeffnet. Fuer Live-Daten bitte http://127.0.0.1:4173 nutzen.";
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

  function renderStats() {
    if (!elements.statsGrid) return;
    const layoutReady = isLayoutReady();
    const showWebuntis = layoutReady && isModuleVisible("webuntis");
    const showInbox = layoutReady && isAnyModuleVisible(["itslearning", "mail"]);
    elements.statsGrid.hidden = true;
    elements.statsGrid.innerHTML = "";
  }

  // ── Briefing helpers ────────────────────────────────────────────────────────

  /**
   * Build the lead item object from available data sources.
   * Returns { kicker, title, copy, timingClass } or null.
   */
  function buildBriefingLead({ nextEvent, todaySummary, orgaplanItem }) {
    if (nextEvent) {
      return {
        kicker: isEventCurrent(nextEvent) ? "laeuft gerade" : "naechste Stunde",
        title: nextEvent.title,
        copy: `${nextEvent.time}${nextEvent.location ? ` · ${nextEvent.location}` : ""}${nextEvent.description ? ` · ${nextEvent.description}` : ""}`,
        timingClass: getEventTimingClass(nextEvent),
      };
    }
    if (todaySummary) {
      return { kicker: "heute", title: todaySummary.title, copy: todaySummary.copy, timingClass: "is-upcoming" };
    }
    if (orgaplanItem) {
      return { kicker: "heute wichtig", title: orgaplanItem.label || "Orgaplan", copy: orgaplanItem.copy, timingClass: "is-upcoming" };
    }
    return null;
  }

  /**
   * Build the compact secondary briefing items array (max 3).
   */
  function buildBriefingItems() {
    return [];
  }

  /**
   * Build the compact metadata line beneath the lead title.
   * Returns a "·"-joined string of up to 3 operational tokens.
   */
  function buildLeadMeta(data, { showWebuntis, showInbox, showClasswork, nextEvent }) {
    const todayEventCount = showWebuntis
      ? (data.webuntisCenter?.events || []).filter((ev) => {
          if (!ev.startsAt) return false;
          return isSameDay(new Date(ev.startsAt), new Date(data.generatedAt || Date.now()));
        }).length
      : 0;

    const unreadCount = showInbox
      ? (data.messages || []).filter((m) => m.unread).length
      : 0;

    let classworkMeta = null;
    if (showClasswork && data.planDigest?.classwork?.entries) {
      const now = new Date();
      const todayIso = now.toISOString().slice(0, 10);
      const tomorrowIso = (() => { const d = new Date(now); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); })();
      const weekEndIso = (() => { const d = new Date(now); d.setDate(d.getDate() + 6); return d.toISOString().slice(0, 10); })();
      const upcoming = (data.planDigest.classwork.entries || []).filter((e) => e.isoDate && e.isoDate > todayIso);
      const tomorrow = upcoming.filter((e) => e.isoDate === tomorrowIso);
      const week = upcoming.filter((e) => e.isoDate <= weekEndIso);
      if (tomorrow.length === 1) {
        classworkMeta = `morgen: ${tomorrow[0].classLabel || tomorrow[0].title || "Klassenarbeit"}`;
      } else if (tomorrow.length > 1) {
        classworkMeta = `${tomorrow.length} Arbeiten morgen`;
      } else if (week.length > 0) {
        classworkMeta = `${week.length} Arbeit${week.length === 1 ? "" : "en"} diese Woche`;
      }
    }

    return [
      todayEventCount > 0 ? `${todayEventCount} Stunde${todayEventCount === 1 ? "" : "n"} heute` : null,
      nextEvent && isEventCurrent(nextEvent) ? "läuft gerade" : null,
      unreadCount > 0 ? `${unreadCount} ungelesen` : null,
      classworkMeta,
    ].filter(Boolean).slice(0, 3).join(" · ");
  }

  function renderBriefing() {
    const data = getData();
    // Gate all module-derived briefing items behind isLayoutReady() to prevent first-load flash.
    const layoutReady = isLayoutReady();
    const showWebuntis = layoutReady && isModuleVisible("webuntis");
    const showOrgaplan = layoutReady && isModuleVisible("orgaplan");
    const showClasswork = layoutReady && isModuleVisible("klassenarbeitsplan");
    const showInbox = layoutReady && isAnyModuleVisible(["itslearning", "mail"]);

    const nextEvent = showWebuntis ? findNextLesson(data) : null;
    const orgaplanItem = showOrgaplan ? pickOrgaplanBriefing(data) : null;
    const classworkItem = showClasswork ? pickClassworkBriefing(data) : null;
    const todaySummary = showWebuntis ? pickTodayScheduleBriefing(data, nextEvent) : null;

    const lead = buildBriefingLead({ nextEvent, todaySummary, orgaplanItem });
    const briefingItems = buildBriefingItems();
    const leadMeta = buildLeadMeta(data, { showWebuntis, showInbox, showClasswork, nextEvent });
    const leadSection = nextEvent || todaySummary ? "schedule" : orgaplanItem ? "documents" : null;

    elements.briefingOutput.innerHTML = lead || briefingItems.length
      ? `
        ${lead ? `
          <article class="briefing-lead ${lead.timingClass}"${leadSection && isSectionEnabled(leadSection) ? ` data-briefing-target="${leadSection}" role="button" tabindex="0"` : ""}>
            <span class="briefing-lead-kicker">${lead.kicker}</span>
            <strong>${lead.title}</strong>
            <p>${lead.copy}</p>
            ${leadMeta ? `<span class="briefing-lead-meta">${leadMeta}</span>` : ""}
          </article>
        ` : ""}
        ${briefingItems.length ? `
        <div class="briefing-grid">
          ${briefingItems
            .map(
              (item) => `
                <article class="briefing-item briefing-item-${item.tone || "default"}"${item.section && isSectionEnabled(item.section) ? ` data-briefing-target="${item.section}" role="button" tabindex="0"` : ""}>
                  <strong>${item.title}</strong>
                  <span>${item.copy}</span>
                </article>
              `
            )
            .join("")}
        </div>` : ""}
      `
      : (!layoutReady
          ? `<div class="briefing-loading">Lade Briefing&hellip;</div>`
          : `<div class="briefing-empty"><span>Heute keine Eintraege - guter Tag.</span></div>`);

    renderTodayBriefingFocus(data, {
      todaySummary,
      orgaplanItem,
      classworkItem,
      showWebuntis,
      showOrgaplan,
      showClasswork,
    });
  }

  function renderTodayBriefingFocus(data, context) {
    if (!elements.todayBriefingFocus) return;

    const classwork = data.planDigest?.classwork || {};
    const selectedClasses = context.showClasswork
      ? getSelectedClassworkClasses(classwork.classes || [], classwork.defaultClass || "")
      : [];
    const todayIso = data.webuntisCenter?.currentDate || new Date(data.generatedAt || Date.now()).toISOString().slice(0, 10);
    const todayClassworkEntries = (classwork.entries || [])
      .filter((entry) => entry.isoDate === todayIso && (!selectedClasses.length || selectedClasses.includes(entry.classLabel)))
      .sort((left, right) => `${left.classLabel || ""}${left.summary || left.title || ""}`.localeCompare(`${right.classLabel || ""}${right.summary || right.title || ""}`));

    const classSelectionLabel = selectedClasses.length
      ? (selectedClasses.length <= 3 ? selectedClasses.join(", ") : `${selectedClasses.length} Klassen gewaehlt`)
      : "Noch keine Klasse gewaehlt";

    const cards = [
      {
        title: "Stundenplan fuer den Tag",
        tone: "schedule",
        section: "schedule",
        copy: context.showWebuntis && context.todaySummary
          ? `${context.todaySummary.title}. ${context.todaySummary.copy}`
          : "Noch kein Tagesplan aus WebUntis verfuegbar.",
      },
      {
        title: "Orgaplan fuer den aktuellen Tag",
        tone: "orgaplan",
        section: "documents",
        copy: context.showOrgaplan && context.orgaplanItem
          ? `${context.orgaplanItem.label}: ${context.orgaplanItem.copy}`
          : "Heute wurde noch kein gesonderter Orgaplan-Hinweis erkannt.",
      },
      {
        title: "Klassenarbeiten fuer den aktuellen Tag",
        tone: "classwork",
        section: "documents",
        meta: classSelectionLabel,
        copy: context.showClasswork
          ? (
              todayClassworkEntries.length
                ? todayClassworkEntries
                    .map((entry) => `${entry.classLabel}: ${entry.summary || entry.title}`)
                    .slice(0, 3)
                    .join(" · ")
                : `Heute keine Klassenarbeiten fuer ${classSelectionLabel.toLowerCase()}.`
            )
          : "Noch kein Klassenarbeitsplan verbunden.",
      },
    ];

    elements.todayBriefingFocus.innerHTML = cards
      .map((card) => `
        <article class="today-focus-card today-focus-card-${card.tone}"${card.section ? ` data-briefing-target="${card.section}" role="button" tabindex="0"` : ""}>
          <strong>${card.title}</strong>
          ${card.meta ? `<span class="today-focus-meta">${card.meta}</span>` : ""}
          <p>${card.copy}</p>
        </article>
      `)
      .join("");
  }

  function renderTodaySupplementCards() {
    const data = getData();
    const nextEvent = isModuleVisible("webuntis") ? findNextLesson(data) : null;
    const inboxItems = getRelevantInboxMessages(data)
      .slice()
      .sort((left, right) => {
        const leftKey = left?.sortKey ? String(left.sortKey) : "";
        const rightKey = right?.sortKey ? String(right.sortKey) : "";
        if (leftKey && rightKey && leftKey !== rightKey) {
          return rightKey.localeCompare(leftKey);
        }
        return String(right?.timestamp || "").localeCompare(String(left?.timestamp || ""));
      })
      .slice(0, 3);
    const orgaplan = data.planDigest?.orgaplan || {};
    const classwork = data.planDigest?.classwork || {};

    if (elements.todaySchedulePreview) {
      elements.todaySchedulePreview.innerHTML = nextEvent
        ? `<article class="today-mini-card">
            <strong>${nextEvent.title}</strong>
            <p>${nextEvent.time}${nextEvent.location ? ` · ${nextEvent.location}` : ""}</p>
            <span class="meta-tag low">Naechster Termin</span>
          </article>`
        : `<div class="empty-state">Heute liegt kein weiterer Termin vor.</div>`;
    }

    if (elements.todayInboxPreview) {
      elements.todayInboxPreview.innerHTML = inboxItems.length
        ? inboxItems.map((item) => `
            <article class="today-mini-card">
              <strong>${item.title}</strong>
              <p>${item.sender} · ${item.timestamp}</p>
              <span class="meta-tag low">${item.channelLabel}</span>
            </article>
          `).join("")
        : `<div class="empty-state">Keine neuen Hinweise im Posteingang.</div>`;
    }

    if (elements.todayDocumentsPreview) {
      elements.todayDocumentsPreview.innerHTML = `
        <article class="today-mini-card">
          <strong>Orgaplan</strong>
          <p>${orgaplan.detail || "Noch kein Orgaplan-Hinweis."}</p>
        </article>
        <article class="today-mini-card">
          <strong>Klassenarbeitsplan</strong>
          <p>${classwork.detail || "Noch kein Klassenarbeitsplan verbunden."}</p>
        </article>
      `;
    }

    if (elements.todayGradesPreview) {
      elements.todayGradesPreview.innerHTML = `
        <article class="today-mini-card">
          <strong>Gewichtungen und Teilnoten</strong>
          <p>Schneller Einstieg in Notenberechnung fuer gewichtete Teilnoten und einfache Kombinationen.</p>
        </article>
      `;
    }

    if (elements.todayAssistantPreview) {
      elements.todayAssistantPreview.innerHTML = `
        <article class="today-mini-card">
          <strong>Suche im Cockpit</strong>
          <p>Fragen zu Stundenplan, Plaenen, Inbox und Dokumenten direkt aus dem Cockpit beantworten lassen.</p>
        </article>
      `;
    }
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

  function pickOrgaplanBriefing(data) {
    const orgaplan = data.planDigest?.orgaplan;
    if (!orgaplan) {
      return null;
    }

    // Prefer today_entries (computed server-side) for the briefing
    const todayEntries = orgaplan.today_entries || [];
    if (todayEntries.length) {
      const item = todayEntries[0];
      return {
        label: item.dateLabel || item.title || "Heute",
        copy: item.general || item.detail || item.text || "Heute ist im Orgaplan ein Hinweis eingetragen.",
      };
    }

    // Fallback: search upcoming/highlights by date token
    const now = new Date(data.generatedAt || Date.now());
    const dayToken = now.getDate().toString().padStart(2, "0");
    const monthToken = (now.getMonth() + 1).toString().padStart(2, "0");
    const candidates = [...(orgaplan.upcoming || []), ...(orgaplan.highlights || [])];
    const todayCandidate = candidates.find((item) => {
      const haystack = `${item.dateLabel || ""} ${item.title || ""}`.toLowerCase();
      return haystack.includes(`${dayToken}.${monthToken}`) || haystack.includes(` ${dayToken} `);
    });
    const chosen = todayCandidate || candidates[0];

    if (!chosen) {
      return null;
    }

    return {
      label: chosen.dateLabel || chosen.title || "Hinweis",
      copy: chosen.detail || chosen.general || chosen.text || "Kein weiterer Hinweis im Orgaplan erkannt.",
    };
  }

  function hasTodayOrgaplanHint(data) {
    const orgaplan = data.planDigest?.orgaplan;
    if (!orgaplan) {
      return false;
    }

    const now = new Date(data.generatedAt || Date.now());
    const dayToken = now.getDate().toString().padStart(2, "0");
    const monthToken = (now.getMonth() + 1).toString().padStart(2, "0");
    const candidates = [...(orgaplan.upcoming || []), ...(orgaplan.highlights || [])];

    return candidates.some((item) => {
      const haystack = `${item.dateLabel || ""} ${item.title || ""}`.toLowerCase();
      return haystack.includes(`${dayToken}.${monthToken}`) || haystack.includes(` ${dayToken} `);
    });
  }

  function pickClassworkBriefing(data) {
    const classwork = data.planDigest?.classwork;
    if (!classwork) {
      return "";
    }

    const now = new Date();
    const nextEntry = (classwork.entries || [])
      .filter((entry) => entry.isoDate)
      .sort((left, right) => (left.isoDate || "").localeCompare(right.isoDate || ""))
      .find((entry) => new Date(`${entry.isoDate}T00:00:00`) >= startOfDay(now));
    if (nextEntry) {
      return `${nextEntry.classLabel}: ${nextEntry.dateLabel} ${nextEntry.title}`;
    }
    return classwork.previewRows?.[0] || classwork.detail || "";
  }

  function pickWeeklyPreview(data) {
    const now = new Date();
    if (now.getDay() !== 1) {
      return "";
    }

    const center = data.webuntisCenter || {};
    const weekStart = getWeekAnchorDate(center.currentDate || now.toISOString().slice(0, 10), "week");
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 7);
    const weekEvents = (center.events || []).filter((event) => {
      const startsAt = new Date(event.startsAt);
      return startsAt >= weekStart && startsAt < weekEnd;
    });
    const classworkCount = (data.planDigest?.classwork?.entries || []).filter((entry) => {
      const date = new Date(`${entry.isoDate}T00:00:00`);
      return date >= weekStart && date < weekEnd;
    }).length;
    const classes = new Set(
      weekEvents.flatMap((event) => extractClassLabels(event))
    );

    if (!weekEvents.length && !classworkCount) {
      return "";
    }

    return `${weekEvents.length} Termine, ${classworkCount} Arbeiten und ${classes.size || 0} Klassen diese Woche.`;
  }

  function pickTodayScheduleBriefing(data, nextEvent) {
    const center = data.webuntisCenter || {};
    const now = new Date();
    const todayStart = startOfDay(now);
    const tomorrowStart = new Date(todayStart);
    tomorrowStart.setDate(tomorrowStart.getDate() + 1);
    const todayEvents = (center.events || [])
      .filter((event) => event.startsAt)
      .filter((event) => {
        const startsAt = new Date(event.startsAt);
        return startsAt >= todayStart && startsAt < tomorrowStart;
      })
      .sort((left, right) => new Date(left.startsAt) - new Date(right.startsAt));

    if (!todayEvents.length) {
      return {
        title: "Heute sind keine iCal-Termine eingetragen",
        copy: "Wenn Unterricht stattfindet, liegt die Luecke wahrscheinlich an der WebUntis-iCal-Quelle und nicht am Cockpit.",
      };
    }

    const remaining = todayEvents.filter((event) => new Date(event.endsAt || event.startsAt) >= now);
    if (nextEvent && remaining.length) {
      return {
        title: `${todayEvents.length} Termine heute`,
        copy: `${remaining.length} davon liegen noch vor dir. Danach kommt ${nextEvent.title}.`,
      };
    }

    return {
      title: `${todayEvents.length} Termine heute`,
      copy: remaining.length ? `${remaining.length} Termine sind heute noch offen.` : "Der heutige Plan ist bereits durchlaufen.",
    };
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

  function renderQuickLinks() {
    const data = getData();
    const quickLinks = data.quickLinks || [];
    if (!elements.quickLinkGrid) {
      return;
    }
    const visibleQuickLinks = getVisiblePanelItems(quickLinks, "access");
    setExpandableMeta(elements.quickLinkGrid, quickLinks.length, visibleQuickLinks.length);
    elements.quickLinkGrid.innerHTML = quickLinks.length
      ? visibleQuickLinks
          .map(
            (link) => `
              <a class="quick-link-card" href="${link.url}" target="_blank" rel="noreferrer">
                <span class="meta-tag low">${link.kind}</span>
                <strong>${link.title}</strong>
                <p class="priority-copy">${link.note}</p>
                <span class="quick-link-action">oeffnen</span>
              </a>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine Direktzugriffe konfiguriert.</div>`;
  }

  function getDefaultTodayLayout() {
    return {
      order: ["briefing", "access", "schedule", "inbox", "documents", "grades", "assistant"],
      visibility: {
        briefing: true,
        access: true,
        schedule: true,
        inbox: true,
        documents: true,
        grades: true,
        assistant: true,
      },
    };
  }

  function sanitizeTodayLayout(layout) {
    const base = getDefaultTodayLayout();
    if (!layout || typeof layout !== "object") {
      return base;
    }

    const knownIds = base.order.slice();
    const order = Array.isArray(layout.order)
      ? layout.order.filter((id) => knownIds.includes(id))
      : [];
    knownIds.forEach((id) => {
      if (!order.includes(id)) {
        order.push(id);
      }
    });

    const visibility = { ...base.visibility };
    if (layout.visibility && typeof layout.visibility === "object") {
      knownIds.forEach((id) => {
        if (typeof layout.visibility[id] === "boolean") {
          visibility[id] = layout.visibility[id];
        }
      });
    }
    visibility.briefing = true;
    visibility.access = true;

    return { order, visibility };
  }

  function renderTodayModuleLayout() {
    if (!elements.todayOverviewGrid || !elements.todayModuleCards.length) return;
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

    const cardMap = new Map(
      elements.todayModuleCards.map((card) => [card.dataset.todayModule || "", card])
    );

    (layout.order || []).forEach((moduleId) => {
      const card = cardMap.get(moduleId);
      if (!card) return;
      card.hidden = layout.visibility && layout.visibility[moduleId] === false;
      elements.todayOverviewGrid.appendChild(card);
    });

    elements.todayModuleCards.forEach((card) => {
      const moduleId = card.dataset.todayModule || "";
      if ((layout.order || []).includes(moduleId)) return;
      card.hidden = false;
      elements.todayOverviewGrid.appendChild(card);
    });
  }

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
    if (elements.dienstmailOpenLink) {
      bindExternalLink(elements.dienstmailOpenLink, "https://outlook.office.com/mail/", "Dienstmail öffnen");
    }
    if (elements.itslearningOpenLink) {
      bindExternalLink(elements.itslearningOpenLink, base.itslearning_base_url || "", "itslearning öffnen");
      elements.itslearningOpenLink.hidden = !base.itslearning_base_url;
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
        return "Aktuell ist keine Live-Dienstmail angebunden.";
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

    // Briefing-to-section scroll anchors: delegate clicks on data-briefing-target
    elements.briefingOutput.addEventListener("click", (event) => {
      const target = event.target.closest("[data-briefing-target]");
      if (!target) return;
      const sectionId = target.dataset.briefingTarget;
      if (!sectionId || !isSectionEnabled(sectionId)) return;
      // Tap feedback: brief visual acknowledgment before/during scroll
      target.classList.add("is-tapping");
      setTimeout(() => target.classList.remove("is-tapping"), 280);
      state.activeSection = sectionId;
      renderSectionFocus();
      // Scroll to section card (desktop) or top (mobile)
      const sectionEl = document.querySelector(`[data-view-section="${sectionId}"]`);
      if (sectionEl) {
        sectionEl.scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });

    // Keyboard support for briefing anchors
    elements.briefingOutput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const target = event.target.closest("[data-briefing-target]");
      if (!target) return;
      event.preventDefault();
      target.click();
    });

    elements.navLinks.forEach((button) => {
      button.addEventListener("click", () => {
        state.activeSection = button.dataset.sectionTarget || "overview";
        renderSectionFocus();
        window.scrollTo({ top: 0, behavior: "auto" });
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

    elements.assistantForm.addEventListener("submit", (event) => {
      event.preventDefault();
      elements.assistantAnswer.textContent = respondToAssistant(elements.assistantInput.value);
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

    if (elements.classworkBrowserFetchButton) {
      elements.classworkBrowserFetchButton.addEventListener("click", async () => {
        await triggerClassworkBrowserFetch();
      });
    }

    if (elements.classworkClassFilter) {
      elements.classworkClassFilter.addEventListener("change", (event) => {
        state.classworkSelectedClasses = Array.from(event.target.selectedOptions || [])
          .map((option) => option.value)
          .filter(Boolean);
        persistClassworkSelectedClasses();
        renderPlanDigest();
        renderBriefing();
      });
    }

    if (elements.gradesForm) {
      elements.gradesForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveGradeEntry();
      });
    }

    if (elements.gradesClassFilter) {
      elements.gradesClassFilter.addEventListener("change", (event) => {
        state.gradesSelectedClass = event.target.value;
        renderGrades();
      });
    }

    if (elements.gradesClassInput) {
      elements.gradesClassInput.addEventListener("change", (event) => {
        if (event.target.value) {
          state.gradesSelectedClass = event.target.value;
          renderGrades();
        }
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

    if (elements.notesForm) {
      elements.notesForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveClassNote();
      });
    }

    if (elements.notesClassFilter) {
      elements.notesClassFilter.addEventListener("change", (event) => {
        state.notesSelectedClass = event.target.value;
        renderClassNotes(getGradeClasses(), state.notesSelectedClass);
        renderNavSignals();
      });
    }

    if (elements.notesClearButton) {
      elements.notesClearButton.addEventListener("click", async () => {
        await clearClassNote();
      });
    }
  }

  // ── SECTION: Render orchestration ────────────────────────────────────────────

  // ── SECTION: Zugaenge (Today) ───────────────────────────────────────────────

  function renderHeuteZugaenge() {
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
    renderStats();
    renderBriefing();
    renderTodaySupplementCards();
    renderQuickLinks();
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

  async function refreshDashboard(forceRefresh = false) {
    if (elements.heroNote) {
      elements.heroNote.textContent = "Stand wird aktualisiert …";
    }
    try {
      state.data = await loadDashboard(forceRefresh);
      renderAll();
      applyAppTitle();
      updateWebUntisExternalLink();
    } catch (error) {
      if (window.LEHRER_COCKPIT_FALLBACK_DATA) {
        state.data = normalizeDashboard(window.LEHRER_COCKPIT_FALLBACK_DATA);
        renderAll();
        applyAppTitle();
        updateWebUntisExternalLink();
        return;
      }

      if (elements.heroNote) {
        elements.heroNote.textContent = `Stand ${formatTime(new Date())}`;
      }
      elements.briefingOutput.innerHTML = `<div class="empty-state">Dashboard-Daten konnten nicht geladen werden.</div>`;
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
    if (!file.name.toLowerCase().match(/\.(xlsx|xlsm)$/)) {
      state.classworkUploadFeedback = "Bitte eine XLSX- oder XLSM-Datei auswaehlen.";
      state.classworkUploadFeedbackKind = "warning";
      renderPlanDigest();
      return;
    }

    state.classworkUploadFeedback = "Importiere Klassenarbeitsplan lokal ...";
    state.classworkUploadFeedbackKind = "";
    renderPlanDigest();

    try {
      const contentBase64 = await fileToBase64(file);
      const response = await fetch("/api/local-settings/classwork-upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: file.name,
          contentBase64,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Lokaler Import fehlgeschlagen.");
      }

      state.classworkUploadFeedback = payload.detail || "Klassenarbeitsplan importiert.";
      state.classworkUploadFeedbackKind = "success";
      await refreshDashboard(true);
    } catch (error) {
      state.classworkUploadFeedback = error.message || "Klassenarbeitsplan konnte nicht importiert werden.";
      state.classworkUploadFeedbackKind = "warning";
      renderPlanDigest();
    }
  }

  async function triggerClassworkBrowserFetch() {
    if (!IS_LOCAL_RUNTIME) {
      setUploadStatus(
        "Online-Abruf ist nur lokal verfuegbar, nicht auf dem gehosteten Server.",
        "warning"
      );
      return;
    }

    setUploadStatus("⏳ Browser-Abruf laeuft … Bitte warten (ca. 20–30 s).", "loading");

    try {
      const response = await fetch("/api/classwork/browser-fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: "" }),
      });

      const payload = await response.json();

      if (payload.status === "login_required") {
        setUploadStatus(
          "🔐 Bitte zuerst im Browser bei Microsoft einloggen – dann erneut versuchen.",
          "warning"
        );
        return;
      }

      if (payload.status === "error") {
        setUploadStatus(
          `⚠️ Beta-Abruf fehlgeschlagen: ${payload.detail || "Unbekannter Fehler"}`,
          "warning"
        );
        return;
      }

      if (payload.status === "ok") {
        setUploadStatus(
          `✓ ${payload.detail || "Daten erfolgreich geladen."}`,
          "ok"
        );
        await refreshDashboard(true);
        await loadClassworkCache();
      }
    } catch (error) {
      setUploadStatus(
        `⚠️ Verbindungsfehler: ${error.message || "Server nicht erreichbar."}`,
        "warning"
      );
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
      briefing: "Tagesbriefing",
      access: "Zugaenge",
      schedule: "Stundenplan",
      inbox: "Posteingang",
      documents: "Plaene",
      grades: "Notenberechnung",
      assistant: "Assistenz",
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
          mandatory: id === "briefing" || id === "access",
          visible: localLayout.visibility[id] !== false,
        };
      });
    }

    var layout = sanitizeTodayLayout(DashboardManager.getTodayLayout());

    return layout.order.map(function(id) {
      return {
        id: id,
        label: labels[id] || id,
        mandatory: id === "briefing" || id === "access",
        visible: layout.visibility[id] !== false,
      };
    });
  }

  function renderHeuteAnpassenList(modulesContainer) {
    if (!modulesContainer) return;
    var items = getHeuteLayoutItems();
    modulesContainer.innerHTML = items.map(function(item) {
      return '<button class="heute-sort-item" type="button" draggable="true" data-heute-sort-id="' + item.id + '">'
        + '<span class="heute-sort-item__grip" aria-hidden="true">⋮⋮</span>'
        + '<span class="heute-sort-item__copy-wrap">'
        + '<span class="heute-sort-item__copy">' + item.label + '</span>'
        + (item.mandatory ? '<span class="heute-sort-item__meta">Pflichtmodul</span>' : '')
        + '</span>'
        + '<label class="heute-sort-item__toggle">'
        + '<input type="checkbox" data-heute-visible-id="' + item.id + '"' + (item.visible ? ' checked' : '') + (item.mandatory ? ' disabled' : '') + ' />'
        + '<span>' + (item.mandatory ? 'immer aktiv' : 'anzeigen') + '</span>'
        + '</label>'
        + '</button>';
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
    const now = new Date();
    const weekday = now.toLocaleDateString("de-DE", { weekday: "long" });
    const date = now.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
    const weekdayEl = document.getElementById("today-weekday");
    const dateEl = document.getElementById("today-date-display");
    const badgeEl = document.getElementById("today-nav-badge");
    if (weekdayEl) weekdayEl.textContent = weekday;
    if (dateEl) dateEl.textContent = date;
    if (badgeEl) badgeEl.textContent = "";
  }

  function initialize() {
    initTodayDisplay();
    normalizeLocalWebUntisState();
    applyTheme();
    elements.assistantAnswer.textContent =
      "Frag mich nach der Woche, nach dem Orgaplan, nach Dokumenten oder nach deiner Inbox.";
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
    refreshDashboard().then(() => {
      loadClassworkCache();
      loadGradebook();
      loadNotes();
    });
    window.setInterval(() => {
      refreshDashboard().then(() => {
        loadClassworkCache();
        loadGradebook();
        loadNotes();
      });
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
    return "light";
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

  function persistClassworkSelectedClasses() {
    try {
      localStorage.setItem(
        CLASSWORK_SELECTED_CLASSES_KEY,
        JSON.stringify((state.classworkSelectedClasses || []).filter(Boolean))
      );
    } catch (_error) {
      // ignore local storage errors
    }
  }

  function getSelectedClassworkClasses(classes, defaultClass = "") {
    const availableClasses = Array.isArray(classes) ? classes.filter(Boolean) : [];
    if (!availableClasses.length) {
      state.classworkSelectedClasses = [];
      return [];
    }

    const sanitized = (state.classworkSelectedClasses || []).filter((label) => availableClasses.includes(label));
    if (sanitized.length) {
      state.classworkSelectedClasses = sanitized;
      return sanitized;
    }

    const nextSelection = defaultClass && availableClasses.includes(defaultClass)
      ? [defaultClass]
      : [availableClasses[0]];

    state.classworkSelectedClasses = nextSelection;
    persistClassworkSelectedClasses();
    return nextSelection;
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
    renderBriefing();
  }

  function renderNavSignals() {
    const data = getData();
    const unreadCount = (data.messages || []).filter((message) => message.unread).length;
    const changedDocuments = (data.documentMonitor || []).filter((item) => item.changed).length;
    const classworkToday = (data.planDigest?.classwork?.entries || []).some((entry) => entry.isoDate === (data.webuntisCenter?.currentDate || ""));
    const orgaplanToday = hasTodayOrgaplanHint(data);
    const nextEvent = findNextLesson(data);
    const allGrades = (getGradebookData().entries || []);
    const noteCount = (getNotesData().notes || []).length;
    const gradeRisk = summarizeGrades(allGrades).riskCount;

    const statuses = {
      overview: nextEvent || unreadCount || changedDocuments || classworkToday ? "accent" : "",
      schedule: nextEvent ? (isEventCurrent(nextEvent) ? "live" : "accent") : "",
      inbox: unreadCount ? "warning" : "",
      documents: changedDocuments ? "danger" : (classworkToday || orgaplanToday ? "warning" : ""),
      grades: gradeRisk ? "danger" : (noteCount ? "accent" : ""),
      assistant: "",
    };

    elements.navLinks.forEach((button) => {
      const target = button.dataset.sectionTarget || "";
      const statusKind = statuses[target] || "";
      const baseLabel = button.dataset.baseLabel || (target === "overview" ? "Heute" : button.textContent.replace(/\s*·\s*\d+$/, "").trim());
      button.dataset.baseLabel = baseLabel;
      button.classList.toggle("has-status", Boolean(statusKind));
      if (statusKind) {
        button.dataset.statusKind = statusKind;
      } else {
        delete button.dataset.statusKind;
      }

      if (target === "inbox") {
        button.textContent = unreadCount > 0 ? `${baseLabel} · ${unreadCount}` : baseLabel;
      } else {
        button.textContent = baseLabel;
      }
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

      const response = await fetch(uploadUrl, { method: "POST", body: formData });
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
        changed: "geaendert",
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
      return "entfaellt";
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
      return `<div class="webuntis-week-empty">Kein iCal-Eintrag fuer diesen Tag</div>`;
    }

    const nextEvent = findNextEventAfter(column.isoDate);
    if (nextEvent) {
      return `<div class="webuntis-week-empty">Im iCal keine Termine. Naechster Eintrag am ${formatDate(new Date(nextEvent.startsAt))}.</div>`;
    }

    return `<div class="webuntis-week-empty">Im iCal sind fuer diese Woche gerade keine Termine vorhanden.</div>`;
  }

  function extractClassLabels(event) {
    const haystack = `${event.title || ""} ${event.detail || ""} ${event.description || ""}`.match(/\b(?:[5-9][A-Z]?|1[0-3][A-Z]?|Q\d(?:\/Q?\d)?)\b/gi);
    return haystack ? haystack.map((token) => token.toUpperCase()) : [];
  }

  // formatNoteTimestamp moved to src/features/grades.js (Phase 15)

  initialize();
})();
