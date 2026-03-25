// ─────────────────────────────────────────────────────────────────────────────
// src/app.js — Lehrer-Cockpit frontend (monolithic IIFE)
//
// TODO: Split this file into smaller modules to reduce merge conflicts.
// Planned structure (use ordered <script> tags, no build tool needed):
//
//   src/state.js        — constants, state object, localStorage helpers
//   src/api.js          — loadDashboard, loadGrades, loadNotes, loadClasswork, postJSON
//   src/features/
//     inbox.js          — renderPriorities, renderSources, renderMessages (lines ~895–1083)
//     classwork.js      — renderClasswork* functions (lines ~1085–1241)
//     grades.js         — renderGrades, grade form logic (lines ~1243–1553)
//     documents.js      — renderDocuments (lines ~1555–1601)
//     webuntis.js       — renderWebUntis*, picker, shortcuts (lines ~1603–2075)
//   src/render.js       — renderAll, renderBriefing, renderWorkspace (lines ~2283+)
//   src/events.js       — registerEvents, initialize (lines ~2077, 2715)
//
// Until the split happens, all code stays in this IIFE so the closure scope
// and global variable model remain unchanged.
// ─────────────────────────────────────────────────────────────────────────────

(function bootstrapApp() {
  // ── SECTION: State & constants ──────────────────────────────────────────────
  const WEBUNTIS_SHORTCUTS_KEY = "lehrerCockpit.webuntis.shortcuts";
  const WEBUNTIS_FAVORITES_KEY = "lehrerCockpit.webuntis.favorites";
  const ACTIVE_WEBUNTIS_PLAN_KEY = "lehrerCockpit.webuntis.activePlan";
  const THEME_KEY = "lehrerCockpit.theme";
  const NEXTCLOUD_LAST_OPENED_KEY = "lehrerCockpit.nextcloud.lastOpened";
  const EXPANDED_PANELS_KEY = "lehrerCockpit.expandedPanels";
  const AUTO_REFRESH_MS = 180000;
  const PANEL_COLLAPSE_LIMITS = {
    inbox: 4,
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
    classworkSelectedClass: "",
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
    heroNote: document.querySelector("#hero-note"),
    runtimeBanner: document.querySelector("#runtime-banner"),
    themeToggle: document.querySelector("#theme-toggle"),
    themeToggleLabel: document.querySelector(".theme-toggle-label"),
    navLinks: Array.from(document.querySelectorAll("[data-section-target]")),
    viewSections: Array.from(document.querySelectorAll("[data-view-section]")),
    expandToggles: Array.from(document.querySelectorAll("[data-expand-toggle]")),
    workspaceEyebrow: document.querySelector("#workspace-eyebrow"),
    workspaceTitle: document.querySelector("#workspace-title"),
    workspaceDescription: document.querySelector("#workspace-description"),
    statsGrid: document.querySelector("#stats-grid"),
    quickLinkGrid: document.querySelector("#quick-link-grid"),
    berlinFocusList: document.querySelector("#berlin-focus-list"),
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
    channelFilters: document.querySelector("#channel-filters"),
    messageList: document.querySelector("#message-list"),
    monitorList: document.querySelector("#monitor-list"),
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
    orgaplanDigestDetail: document.querySelector("#orgaplan-digest-detail"),
    orgaplanUpcomingList: document.querySelector("#orgaplan-upcoming-list"),
    classworkOpenLink: document.querySelector("#classwork-open-link"),
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

  const channelLabels = {
    mail: "Dienstmail",
    itslearning: "itslearning",
  };

  // ── SECTION: API / data loading ─────────────────────────────────────────────

  async function loadDashboard(forceRefresh = false) {
    const sources = IS_LOCAL_RUNTIME
      ? [`/api/dashboard${forceRefresh ? "?refresh=1" : ""}`, "./data/mock-dashboard.json"]
      : [...PRODUCTION_API_BASES.map((base) => `${base}/api/dashboard${forceRefresh ? "?refresh=1" : ""}`), "./data/mock-dashboard.json"];

    for (const source of sources) {
      try {
        const response = await fetch(source, { cache: "no-store" });
        if (!response.ok) {
          continue;
        }

        return normalizeDashboard(await response.json());
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
    elements.workspaceEyebrow.textContent = data.workspace.eyebrow;
    elements.workspaceTitle.textContent = data.workspace.title;
    elements.workspaceDescription.textContent = data.workspace.description;
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
    const active = state.activeSection || "overview";

    elements.navLinks.forEach((button) => {
      button.classList.toggle("active", button.dataset.sectionTarget === active);
    });

    elements.viewSections.forEach((section) => {
      const sectionId = section.dataset.viewSection;
      section.hidden = active !== "overview" && sectionId !== active;
    });
  }

  function renderMeta() {
    const data = getData();
    elements.heroNote.textContent = `Stand ${data.meta.lastUpdatedLabel}. ${data.meta.note}`;
  }

  function renderRuntimeBanner() {
    const data = getData();

    if (window.location.protocol === "file:") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        "Direktdatei geoeffnet. Fuer Live-Daten bitte http://127.0.0.1:4173 nutzen.";
      return;
    }

    if (IS_LOCAL_RUNTIME && data.meta.mode === "live") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent = `Lokaler Live-Modus aktiv. Neu geladen um ${data.meta.lastUpdatedLabel}.`;
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
    const data = getData();
    const webuntisEvents = getWebUntisEvents();

    const cards = [
      {
        label: "Hinweise",
        value: data.messages.filter((message) => message.unread).length,
        detail: "offene Eintraege",
      },
      {
        label: "Prioritaeten",
        value: data.priorities.length,
        detail: "heute im Fokus",
      },
      {
        label: "WebUntis",
        value: webuntisEvents.length,
        detail: state.webuntisView === "day" ? "Termine heute" : "Termine diese Woche",
      },
      {
        label: "Dokumente",
        value: data.documents.length,
        detail: "sichtbar im Cockpit",
      },
    ];

    elements.statsGrid.innerHTML = cards
      .map(
        (card) => `
          <article class="stat-card">
            <p class="stat-label">${card.label}</p>
            <strong>${card.value}</strong>
            <p>${card.detail}</p>
          </article>
        `
      )
      .join("");
  }

  function renderBriefing() {
    const data = getData();
    const nextEvent = findNextLesson(data);
    const orgaplanItem = pickOrgaplanBriefing(data);
    const classworkItem = pickClassworkBriefing(data);
    const inboxItem = pickInboxBriefing(data);
    const todaySummary = pickTodayScheduleBriefing(data, nextEvent);
    const weeklyPreview = pickWeeklyPreview(data);
    const lead = nextEvent
      ? {
          kicker: isEventCurrent(nextEvent) ? "laeuft gerade" : "naechste Stunde",
          title: nextEvent.title,
          copy: `${nextEvent.time}${nextEvent.location ? ` · ${nextEvent.location}` : ""}${nextEvent.description ? ` · ${nextEvent.description}` : ""}`,
          timingClass: getEventTimingClass(nextEvent),
        }
      : todaySummary
        ? {
            kicker: "heute",
            title: todaySummary.title,
            copy: todaySummary.copy,
            timingClass: "is-upcoming",
          }
      : orgaplanItem
        ? {
            kicker: "heute wichtig",
            title: orgaplanItem.label || "Orgaplan",
            copy: orgaplanItem.copy,
            timingClass: "is-upcoming",
          }
        : null;

    const briefingItems = [
      orgaplanItem
        ? {
            title: "Orgaplan",
            copy: `${orgaplanItem.label}: ${orgaplanItem.copy}`,
            tone: "orgaplan",
          }
        : null,
      classworkItem
        ? {
            title: "Klassenarbeiten",
            copy: classworkItem,
            tone: "classwork",
          }
        : null,
      inboxItem
        ? {
            title: "Inbox",
            copy: inboxItem,
            tone: "inbox",
          }
        : null,
      weeklyPreview
        ? {
            title: "Wochenvorschau",
            copy: weeklyPreview,
            tone: "week",
          }
        : null,
    ]
      .filter(Boolean)
      .slice(0, 3);

    elements.briefingOutput.innerHTML = lead || briefingItems.length
      ? `
        ${lead ? `
          <article class="briefing-lead ${lead.timingClass}">
            <span class="briefing-lead-kicker">${lead.kicker}</span>
            <strong>${lead.title}</strong>
            <p>${lead.copy}</p>
          </article>
        ` : ""}
        <div class="briefing-grid">
          ${briefingItems
            .map(
              (item) => `
                <article class="briefing-item briefing-item-${item.tone || "default"}">
                  <strong>${item.title}</strong>
                  <span>${item.copy}</span>
                </article>
              `
            )
            .join("")}
        </div>
      `
      : `<div class="empty-state">Noch keine Briefing-Daten verfuegbar.</div>`;
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

  function pickInboxBriefing(data) {
    const unread = (data.messages || []).filter((message) => message.unread);
    if (!unread.length) {
      return "";
    }

    const mailMessages = unread.filter((message) => message.channel === "mail");
    if (mailMessages.length) {
      return `${mailMessages.length} neue Mail${mailMessages.length === 1 ? "" : "s"}, zuerst: ${mailMessages[0].title}.`;
    }

    return `${unread.length} neue Hinweise, zuerst: ${unread[0].title}.`;
  }

  function renderQuickLinks() {
    const data = getData();
    const quickLinks = (data.quickLinks || []).filter((link) => !String(link.id || "").startsWith("nextcloud-"));
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

  function renderItslearningConnector() {
    if (!elements.itslearningConnectCard) {
      return;
    }

    if (!IS_LOCAL_RUNTIME) {
      elements.itslearningConnectCard.hidden = true;
      return;
    }

    const source = getData().sources.find((item) => item.id === "itslearning");
    const connection = getData().localConnections?.itslearning || {};
    elements.itslearningConnectCard.hidden = false;
    elements.itslearningConnectStatus.className = `pill ${
      source?.status === "ok" ? "pill-live" : connection.configured ? "pill-attention" : "pill-positive"
    }`;
    elements.itslearningConnectStatus.textContent = source?.status === "ok" ? "verbunden" : connection.configured ? "gespeichert" : "lokal";
    const updateCount = getRelevantInboxMessages().filter((message) => message.channel === "itslearning").length;
    elements.itslearningConnectCopy.textContent =
      source?.status === "ok"
        ? `${updateCount} Update${updateCount === 1 ? "" : "s"} erscheinen oben im Kommunikationsbereich. Zugang bleibt lokal auf diesem Mac gespeichert.`
        : source?.detail ||
          "Lokale Verbindung fuer Benutzername und Passwort. Updates erscheinen danach oben im Kommunikationsbereich.";
    if (!elements.itslearningUsername.value && connection.username) {
      elements.itslearningUsername.value = connection.username;
    }
    if (connection.configured) {
      elements.itslearningPassword.placeholder = "Passwort lokal gespeichert";
    }
  }

  function renderNextcloudConnector() {
    if (!elements.nextcloudConnectCard) {
      return;
    }

    if (!IS_LOCAL_RUNTIME) {
      elements.nextcloudConnectCard.hidden = true;
      return;
    }

    const source = getData().sources.find((item) => item.id === "nextcloud");
    const connection = getData().localConnections?.nextcloud || {};
    const workspaceUrl = connection.workspaceUrl || connection.baseUrl || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/";
    const q1q2Url = connection.q1q2Url || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901";
    const q3q4Url = connection.q3q4Url || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900";
    const workspaceLinks = Array.isArray(connection.workspaceLinks) ? connection.workspaceLinks : [];
    const lastOpened = loadNextcloudLastOpened();

    elements.nextcloudConnectCard.hidden = false;
    elements.nextcloudConnectStatus.className = `pill ${
      source?.status === "ok" ? "pill-live" : connection.configured ? "pill-attention" : "pill-positive"
    }`;
    elements.nextcloudConnectStatus.textContent =
      source?.status === "ok"
        ? (connection.configured ? "verbunden" : "bereit")
        : connection.configured
          ? "gespeichert"
          : "lokal";
    elements.nextcloudConnectCopy.textContent =
      source?.detail ||
      "Nextcloud ist als Arbeitsbereich vorbereitet. Von hier aus oeffnest du die Fehlzeiten-Dateien direkt im Browser.";

    if (elements.nextcloudOpenRoot) {
      elements.nextcloudOpenRoot.href = workspaceUrl;
    }
    if (elements.nextcloudOpenQ1Q2) {
      elements.nextcloudOpenQ1Q2.href = q1q2Url;
    }
    if (elements.nextcloudOpenQ3Q4) {
      elements.nextcloudOpenQ3Q4.href = q3q4Url;
    }
    if (elements.nextcloudCustomLinks) {
      elements.nextcloudCustomLinks.hidden = !workspaceLinks.length;
      elements.nextcloudCustomLinks.innerHTML = workspaceLinks
        .map(
          (link) => `
            <a class="nextcloud-work-card" href="${link.url}" target="_blank" rel="noreferrer" data-nextcloud-link="${link.id}">
              <span class="meta-tag low">Arbeitslink</span>
              <strong>${link.label}</strong>
              <p>Direkt in Nextcloud oeffnen</p>
              <span class="quick-link-action">oeffnen</span>
            </a>
          `
        )
        .join("");
      elements.nextcloudCustomLinks.querySelectorAll("[data-nextcloud-link]").forEach((link) => {
        link.addEventListener("click", () => {
          saveNextcloudLastOpened(link.dataset.nextcloudLink, link.querySelector("strong")?.textContent || link.textContent);
          renderNextcloudConnector();
        });
      });
    }
    if (elements.nextcloudLastOpened) {
      elements.nextcloudLastOpened.textContent = lastOpened
        ? `${lastOpened.label} - ${lastOpened.when}`
        : "Noch kein Zugriff gespeichert";
    }
    if (elements.nextcloudWorkspaceUrl && !elements.nextcloudWorkspaceUrl.value) {
      elements.nextcloudWorkspaceUrl.value = workspaceUrl;
    }
    if (!elements.nextcloudUsername.value && connection.username) {
      elements.nextcloudUsername.value = connection.username;
    }
    if (elements.nextcloudQ1Q2UrlInput && !elements.nextcloudQ1Q2UrlInput.value) {
      elements.nextcloudQ1Q2UrlInput.value = q1q2Url;
    }
    if (elements.nextcloudQ3Q4UrlInput && !elements.nextcloudQ3Q4UrlInput.value) {
      elements.nextcloudQ3Q4UrlInput.value = q3q4Url;
    }
    if (elements.nextcloudLink1Label && !elements.nextcloudLink1Label.value) {
      elements.nextcloudLink1Label.value = workspaceLinks[0]?.label || "";
    }
    if (elements.nextcloudLink1Url && !elements.nextcloudLink1Url.value) {
      elements.nextcloudLink1Url.value = workspaceLinks[0]?.url || "";
    }
    if (elements.nextcloudLink2Label && !elements.nextcloudLink2Label.value) {
      elements.nextcloudLink2Label.value = workspaceLinks[1]?.label || "";
    }
    if (elements.nextcloudLink2Url && !elements.nextcloudLink2Url.value) {
      elements.nextcloudLink2Url.value = workspaceLinks[1]?.url || "";
    }
    if (elements.nextcloudLink3Label && !elements.nextcloudLink3Label.value) {
      elements.nextcloudLink3Label.value = workspaceLinks[2]?.label || "";
    }
    if (elements.nextcloudLink3Url && !elements.nextcloudLink3Url.value) {
      elements.nextcloudLink3Url.value = workspaceLinks[2]?.url || "";
    }
    if (connection.configured) {
      elements.nextcloudPassword.placeholder = "Passwort lokal gespeichert";
    }
  }

  function renderBerlinFocus() {
    const data = getData();
    elements.berlinFocusList.innerHTML = data.berlinFocus.length
      ? data.berlinFocus
          .map(
            (item) => `
              <article class="priority-item">
                <div class="priority-top">
                  <strong>${item.title}</strong>
                  <span class="meta-tag low">Berlin</span>
                </div>
                <p class="priority-copy">${item.detail}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine Berlin-Hinweise verfuegbar.</div>`;
  }

  // ── SECTION: Inbox (priorities, sources, messages) ──────────────────────────

  function renderPriorities() {
    const data = getData();
    elements.priorityList.innerHTML = data.priorities.length
      ? data.priorities
          .map(
            (item) => `
              <article class="priority-item">
                <div class="priority-top">
                  <strong>${item.title}</strong>
                  <span class="meta-tag ${item.priority}">${priorityLabel(item.priority)}</span>
                </div>
                <p class="priority-copy">${item.detail}</p>
                <div class="meta-row">
                  <span class="meta-tag">${item.source}</span>
                  <span class="meta-tag">${item.due}</span>
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine priorisierten Hinweise verfuegbar.</div>`;
  }

  function renderSources() {
    const data = getData();
    elements.sourceList.innerHTML = data.sources.length
      ? data.sources
          .map(
            (source) => `
              <article class="source-item">
                <div class="source-top">
                  <div>
                    <strong>${source.name}</strong>
                    <p class="source-detail">${source.type} - letzter Sync ${source.lastSync} - ${source.cadence}</p>
                  </div>
                  <span class="source-status ${source.status}">${statusLabel(source.status)}</span>
                </div>
                <p class="source-detail">${source.detail}</p>
                <p class="source-detail"><strong>Naechster Schritt:</strong> ${source.nextStep}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine Quellen eingerichtet.</div>`;
  }

  function renderChannelFilters() {
    const availableChannels = getRelevantInboxMessages()
      .map((message) => message.channel)
      .filter((channel, index, array) => channel && array.indexOf(channel) === index);

    if (!availableChannels.length) {
      elements.channelFilters.hidden = true;
      elements.channelFilters.innerHTML = "";
      return;
    }

    if (!availableChannels.includes(state.selectedChannel)) {
      state.selectedChannel = availableChannels[0];
    }

    elements.channelFilters.hidden = availableChannels.length <= 1;
    elements.channelFilters.innerHTML = availableChannels
      .map(
        (id) => `
          <button class="filter-button ${state.selectedChannel === id ? "active" : ""}" type="button" data-channel="${id}">
            ${channelLabels[id]}
          </button>
        `
      )
      .join("");

    elements.channelFilters.querySelectorAll("[data-channel]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedChannel = button.dataset.channel;
        renderChannelFilters();
        renderMessages();
      });
    });
  }

  function renderMessages() {
    const filteredMessages = getRelevantInboxMessages()
      .filter((message) => message.channel === state.selectedChannel)
      .sort((left, right) => compareMessageTime(right.timestamp, left.timestamp));
    const visibleMessages = getVisiblePanelItems(filteredMessages, "inbox");
    setExpandableMeta(elements.messageList, filteredMessages.length, visibleMessages.length);

    elements.messageList.innerHTML = filteredMessages.length
      ? visibleMessages
          .map(
            (message) => `
              <article class="message-item">
                <div class="message-top">
                  <div>
                    <strong>${message.title}</strong>
                    <p class="message-snippet">${message.sender} - ${message.timestamp}</p>
                  </div>
                  <span class="meta-tag ${messagePriorityClass(message.priority)}">${message.unread ? "neu" : "gesehen"}</span>
                </div>
                <p class="message-snippet">${message.snippet}</p>
                <div class="meta-row">
                  <span class="meta-tag">${message.channelLabel}</span>
                  <span class="meta-tag">${priorityLabel(message.priority)}</span>
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Fuer diesen Kanal liegen gerade keine Hinweise vor.</div>`;
  }

  function getRelevantInboxMessages(data = getData()) {
    return (data.messages || []).filter((message) => message.channel === "mail" || message.channel === "itslearning");
  }

  function renderDocumentMonitor() {
    const data = getData();
    elements.monitorList.innerHTML = data.documentMonitor.length
      ? data.documentMonitor
          .map(
            (item) => `
              <article class="priority-item">
                <div class="priority-top">
                  <strong>${item.title}</strong>
                  <span class="meta-tag ${monitorStatusClass(item.status)}">${monitorStatusLabel(item.status)}</span>
                </div>
                <p class="priority-copy">${item.detail}</p>
                <div class="meta-row">
                  <span class="meta-tag">${item.type}</span>
                  <span class="meta-tag">${item.checkedAt}</span>
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine beobachteten Dokumente konfiguriert.</div>`;
  }

  function renderPlanDigest() {
    const digest = getData().planDigest;
    const orgaplan = digest.orgaplan;
    const classwork = digest.classwork;
    const classes = classwork.classes || [];
    const entries = classwork.entries || [];

    bindExternalLink(elements.orgaplanOpenLink, orgaplan.sourceUrl, "PDF oeffnen");
    bindExternalLink(elements.classworkOpenLink, classwork.sourceUrl, "Plan online im Viewer oeffnen");

    elements.orgaplanDigestDetail.textContent = summarizeOrgaplanDigest(orgaplan);
    elements.classworkDigestDetail.textContent = summarizeClassworkDigest(classwork);
    elements.classworkUploadFeedback.textContent = state.classworkUploadFeedback;
    elements.classworkUploadFeedback.className = `connect-feedback${state.classworkUploadFeedbackKind ? ` ${state.classworkUploadFeedbackKind}` : ""}`;

    renderClassworkSelector(classes, classwork.defaultClass || "");
    renderClassworkViewSwitch();

    const orgaplanItems = orgaplan.upcoming.length ? orgaplan.upcoming : orgaplan.highlights;

    elements.orgaplanUpcomingList.innerHTML = orgaplanItems.length
      ? orgaplanItems
          .map((item) => renderOrgaplanItem(item))
          .join("")
      : `<div class="empty-state">Noch keine Orgaplan-Highlights erkannt.</div>`;

    const activeClass = getActiveClassworkClass(classes, classwork.defaultClass || "");
    const classEntries = entries
      .filter((entry) => entry.classLabel === activeClass)
      .sort((left, right) => (left.isoDate || "").localeCompare(right.isoDate || ""));
    const visibleClassEntries = getVisiblePanelItems(classEntries, "classwork");
    setExpandableMeta(elements.classworkPreviewList, classEntries.length, visibleClassEntries.length);

    elements.classworkPreviewList.innerHTML = classEntries.length
      ? state.classworkView === "calendar"
        ? renderClassworkCalendar(visibleClassEntries)
        : renderClassworkList(visibleClassEntries)
      : classwork.previewRows.length
        ? classwork.previewRows
            .map(
              (row) => `
                <article class="priority-item">
                  <p class="priority-copy">${row}</p>
                </article>
              `
            )
            .join("")
        : `<div class="empty-state">Noch keine Klassenarbeiten fuer diese Klasse erkannt.</div>`;
  }

  // ── SECTION: Classwork ───────────────────────────────────────────────────────

  function renderClassworkSelector(classes, defaultClass) {
    if (!elements.classworkClassFilter) {
      return;
    }

    const activeClass = getActiveClassworkClass(classes, defaultClass);
    elements.classworkClassFilter.disabled = !classes.length;

    if (!classes.length) {
      elements.classworkClassFilter.innerHTML = `<option value="">Keine Klasse erkannt</option>`;
      return;
    }

    elements.classworkClassFilter.innerHTML = classes
      .map(
        (classLabel) => `
          <option value="${classLabel}" ${classLabel === activeClass ? "selected" : ""}>${classLabel}</option>
        `
      )
      .join("");
  }

  function getActiveClassworkClass(classes, defaultClass) {
    if (!classes.length) {
      state.classworkSelectedClass = "";
      return "";
    }

    if (state.classworkSelectedClass && classes.includes(state.classworkSelectedClass)) {
      return state.classworkSelectedClass;
    }

    state.classworkSelectedClass = defaultClass && classes.includes(defaultClass) ? defaultClass : classes[0];
    return state.classworkSelectedClass;
  }

  function renderClassworkViewSwitch() {
    if (!elements.classworkViewSwitch) {
      return;
    }

    const options = [
      { id: "list", label: "Liste" },
      { id: "calendar", label: "Kalender" },
    ];

    elements.classworkViewSwitch.innerHTML = options
      .map(
        (option) => `
          <button class="filter-button ${state.classworkView === option.id ? "active" : ""}" type="button" data-classwork-view="${option.id}">
            ${option.label}
          </button>
        `
      )
      .join("");

    elements.classworkViewSwitch.querySelectorAll("[data-classwork-view]").forEach((button) => {
      button.addEventListener("click", () => {
        state.classworkView = button.dataset.classworkView;
        renderPlanDigest();
      });
    });
  }

  function renderClassworkList(entries) {
    return entries
      .map(
        (entry) => `
          <article class="classwork-entry">
            <div class="classwork-entry-top">
              <div>
                <strong>${entry.dateLabel}</strong>
                <p>${weekdayLabel(entry.weekdayLabel)}</p>
              </div>
              <span class="meta-tag low">${entry.kind}</span>
            </div>
            <p class="classwork-entry-title">${entry.summary || entry.title}</p>
            <div class="meta-row">
              <span class="meta-tag">${entry.classLabel}</span>
            </div>
          </article>
        `
      )
      .join("");
  }

  function renderClassworkCalendar(entries) {
    const grouped = new Map();
    entries.forEach((entry) => {
      const key = entry.isoDate;
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key).push(entry);
    });

    return `
      <div class="classwork-calendar">
        ${Array.from(grouped.entries())
          .map(
            ([isoDate, dayEntries]) => `
              <section class="classwork-day">
                <div class="classwork-day-head">
                  <span class="webuntis-weekday">${weekdayLabel(dayEntries[0].weekdayLabel)}</span>
                  <strong>${dayEntries[0].dateLabel}</strong>
                </div>
                <div class="classwork-day-items">
                  ${dayEntries
                    .map(
                      (entry) => `
                        <article class="classwork-calendar-item">
                          <span class="meta-tag low">${entry.kind}</span>
                          <strong>${entry.summary || entry.title}</strong>
                        </article>
                      `
                    )
                    .join("")}
                </div>
              </section>
            `
          )
          .join("")}
      </div>
    `;
  }

  function getGradebookData() {
    return (
      state.gradesData || {
        status: "empty",
        detail: "Noch keine lokalen Noten erfasst.",
        updatedAt: "",
        entries: [],
        classes: [],
      }
    );
  }

  function getGradeClasses() {
    const gradeClasses = getGradebookData().classes || [];
    const classworkClasses = getData().planDigest?.classwork?.classes || [];
    return Array.from(new Set([...gradeClasses, ...classworkClasses])).sort();
  }

  function getActiveGradeClass(classes) {
    if (!classes.length) {
      state.gradesSelectedClass = "";
      return "";
    }

    if (state.gradesSelectedClass && classes.includes(state.gradesSelectedClass)) {
      return state.gradesSelectedClass;
    }

    state.gradesSelectedClass = classes[0];
    return state.gradesSelectedClass;
  }

  // ── SECTION: Grades & notes ──────────────────────────────────────────────────

  function renderGrades() {
    if (!elements.gradesList) {
      return;
    }

    const gradebook = getGradebookData();
    const classes = getGradeClasses();
    const activeClass = getActiveGradeClass(classes);
    const entries = (gradebook.entries || [])
      .filter((entry) => !activeClass || entry.classLabel === activeClass)
      .sort((left, right) => (right.date || "").localeCompare(left.date || ""));
    const visibleEntries = getVisiblePanelItems(entries, "grades");

    const summary = summarizeGrades(entries);

    elements.gradesDetail.textContent = gradebook.updatedAt
      ? `${gradebook.detail} Letzter lokaler Stand: ${gradebook.updatedAt}.`
      : gradebook.detail;
    elements.gradesSummaryClass.textContent = activeClass || "Keine Klasse";
    elements.gradesSummaryCount.textContent = String(entries.length);
    elements.gradesSummaryAverage.textContent = summary.averageLabel;
    elements.gradesSummaryRisk.textContent = String(summary.riskCount);
    elements.gradesFeedback.textContent = state.gradesFeedback;
    elements.gradesFeedback.className = `connect-feedback${state.gradesFeedbackKind ? ` ${state.gradesFeedbackKind}` : ""}`;

    renderGradeClassOptions(elements.gradesClassInput, classes, activeClass, true);
    renderGradeClassOptions(elements.gradesClassFilter, classes, activeClass, false);
    renderClassNotes(classes, activeClass);

    if (elements.gradesDateInput && !elements.gradesDateInput.value) {
      elements.gradesDateInput.value = new Date().toISOString().slice(0, 10);
    }

    setExpandableMeta(elements.gradesList, entries.length, visibleEntries.length);
    elements.gradesList.innerHTML = entries.length
      ? visibleEntries.map((entry) => renderGradeItem(entry)).join("")
      : `<div class="empty-state">Noch keine lokalen Noten fuer diese Klasse erfasst.</div>`;
  }

  function getNotesData() {
    return (
      state.notesData || {
        status: "empty",
        detail: "Noch keine Klassen-Notizen erfasst.",
        updatedAt: "",
        notes: [],
        classes: [],
      }
    );
  }

  function getNoteClasses() {
    const notesClasses = getNotesData().classes || [];
    return Array.from(new Set([...getGradeClasses(), ...notesClasses])).sort();
  }

  function getActiveNoteClass(classes, suggestedClass) {
    if (!classes.length) {
      state.notesSelectedClass = "";
      return "";
    }

    if (state.notesSelectedClass && classes.includes(state.notesSelectedClass)) {
      return state.notesSelectedClass;
    }

    if (suggestedClass && classes.includes(suggestedClass)) {
      state.notesSelectedClass = suggestedClass;
      return suggestedClass;
    }

    state.notesSelectedClass = classes[0];
    return state.notesSelectedClass;
  }

  function renderClassNotes(classes, suggestedClass) {
    if (!elements.notesList) {
      return;
    }

    const notesData = getNotesData();
    const noteClasses = getNoteClasses();
    const activeClass = getActiveNoteClass(noteClasses, suggestedClass);
    const notes = (notesData.notes || [])
      .slice()
      .sort((left, right) => String(right.updatedAt || "").localeCompare(String(left.updatedAt || "")));
    const currentNote = notes.find((item) => item.classLabel === activeClass) || null;

    renderGradeClassOptions(elements.notesClassFilter, noteClasses, activeClass, false);
    if (elements.notesInput && !elements.notesInput.matches(":focus")) {
      elements.notesInput.value = currentNote?.text || "";
    }

    elements.notesFeedback.textContent = state.notesFeedback;
    elements.notesFeedback.className = `connect-feedback${state.notesFeedbackKind ? ` ${state.notesFeedbackKind}` : ""}`;

    const prioritizedNotes = currentNote
      ? [currentNote, ...notes.filter((item) => item.classLabel !== activeClass)]
      : notes.slice();
    const visibleNotes = getVisiblePanelItems(prioritizedNotes, "notes");
    setExpandableMeta(elements.notesList, prioritizedNotes.length, visibleNotes.length);

    elements.notesList.innerHTML = visibleNotes.length
      ? visibleNotes
          .map(
            (note) => `
              <article class="grade-item note-item ${note.classLabel === activeClass ? "active" : ""}">
                <div class="grade-item-top">
                  <div>
                    <strong>${note.classLabel}</strong>
                    <p class="message-snippet">${formatNoteTimestamp(note.updatedAt)}</p>
                  </div>
                  <span class="meta-tag low">${note.classLabel === activeClass ? "aktiv" : "notiz"}</span>
                </div>
                <p class="classwork-entry-title">${note.text}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine Klassen-Notizen erfasst.</div>`;
  }

  function renderGradeClassOptions(element, classes, activeClass, includePlaceholder) {
    if (!element) {
      return;
    }

    if (!classes.length) {
      element.innerHTML = includePlaceholder
        ? `<option value="">Klasse waehlen</option>`
        : `<option value="">Keine Klasse</option>`;
      element.disabled = !includePlaceholder;
      return;
    }

    element.disabled = false;
    element.innerHTML = `${includePlaceholder ? `<option value="">Klasse waehlen</option>` : ""}${classes
      .map(
        (classLabel) => `<option value="${classLabel}" ${classLabel === activeClass ? "selected" : ""}>${classLabel}</option>`
      )
      .join("")}`;
  }

  function summarizeGrades(entries) {
    const numericGrades = entries
      .map((entry) => parseGradeValue(entry.gradeValue))
      .filter((value) => Number.isFinite(value));
    const average = numericGrades.length
      ? numericGrades.reduce((sum, value) => sum + value, 0) / numericGrades.length
      : null;
    const riskCount = numericGrades.filter((value) => value >= 4).length;
    return {
      averageLabel: average ? average.toFixed(2).replace(".", ",") : "-",
      riskCount,
    };
  }

  function parseGradeValue(value) {
    const token = String(value || "").trim();
    if (!token) {
      return Number.NaN;
    }

    const mapping = {
      "1+": 0.7,
      "1": 1,
      "1-": 1.3,
      "2+": 1.7,
      "2": 2,
      "2-": 2.3,
      "3+": 2.7,
      "3": 3,
      "3-": 3.3,
      "4+": 3.7,
      "4": 4,
      "4-": 4.3,
      "5+": 4.7,
      "5": 5,
      "5-": 5.3,
      "6": 6,
    };

    if (mapping[token] !== undefined) {
      return mapping[token];
    }

    const numeric = Number(token.replace(",", "."));
    return Number.isFinite(numeric) ? numeric : Number.NaN;
  }

  function renderGradeItem(entry) {
    return `
      <article class="grade-item">
        <div class="grade-item-top">
          <div>
            <strong>${entry.studentName}</strong>
            <p class="message-snippet">${entry.classLabel} · ${entry.type} · ${formatGradeDate(entry.date)}</p>
          </div>
          <div class="grade-item-actions">
            <span class="meta-tag low">${entry.gradeValue || "-"}</span>
            <button class="filter-button" type="button" data-grade-delete="${entry.id}">Entfernen</button>
          </div>
        </div>
        <p class="classwork-entry-title">${entry.title}</p>
        <div class="meta-row">
          ${entry.points ? `<span class="meta-tag">${entry.points}</span>` : ""}
          ${entry.comment ? `<span class="meta-tag">${entry.comment}</span>` : ""}
        </div>
      </article>
    `;
  }

  function formatGradeDate(value) {
    if (!value) {
      return "ohne Datum";
    }
    try {
      const date = new Date(`${value}T00:00:00`);
      return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
    } catch (_error) {
      return value;
    }
  }

  function renderOrgaplanItem(item) {
    const sections = [
      { label: "Allgemein", value: item.general },
      { label: "Mittelstufe", value: joinOrgaplanSection(item.middle, item.middleNotes) },
      { label: "Oberstufe", value: joinOrgaplanSection(item.upper, item.upperNotes) },
    ].filter((section) => section.value);

    if (!sections.length) {
      return `
        <article class="priority-item">
          <div class="priority-top">
            <strong>${item.title}</strong>
            <span class="meta-tag low">${item.dateLabel}</span>
          </div>
          <p class="priority-copy">${item.detail || item.text}</p>
        </article>
      `;
    }

    return `
      <article class="orgaplan-entry">
        <div class="orgaplan-entry-head">
          <strong class="orgaplan-entry-date">${item.dateLabel}</strong>
          <span class="meta-tag low">${item.title || "Orgaplan"}</span>
        </div>
        <div class="orgaplan-entry-copy">
          ${sections
            .map(
              (section) => `
                <div class="orgaplan-row">
                  <span class="orgaplan-label">${section.label}</span>
                  <p>${truncateText(section.value, 220)}</p>
                </div>
              `
            )
            .join("")}
        </div>
      </article>
    `;
  }

  function joinOrgaplanSection(primary, notes) {
    if (!primary && !notes) {
      return "";
    }

    if (primary && notes) {
      return `${primary} (${notes})`;
    }

    return primary || notes;
  }

  function summarizeOrgaplanDigest(orgaplan) {
    const count = (orgaplan.upcoming || []).length || (orgaplan.highlights || []).length;
    const month = orgaplan.monthLabel || "diesem Monat";
    return `${count} relevante Hinweise fuer ${month}. Hier stehen nur die naechsten Punkte, nicht der ganze Plan.`;
  }

  function summarizeClassworkDigest(classwork) {
    if (classwork.status === "ok") {
      const classCount = (classwork.classes || []).length;
      const entryCount = (classwork.entries || []).length;
      return `${entryCount} Eintraege fuer ${classCount} Klassen erkannt. Unten arbeitest du nur mit der Klasse, die du gerade brauchst.`;
    }
    return truncateText(classwork.detail || "Der Klassenarbeitsplan ist verlinkt, aber noch nicht automatisch lesbar.", 140);
  }

  function weekdayLabel(value) {
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

  function truncateText(value, maxLength) {
    const clean = String(value || "").replace(/\s+/g, " ").trim();
    if (clean.length <= maxLength) {
      return clean;
    }
    return `${clean.slice(0, maxLength - 1).trimEnd()}…`;
  }

  // ── SECTION: Documents ───────────────────────────────────────────────────────

  function renderDocuments() {
    const data = getData();
    const query = state.documentSearch.trim().toLowerCase();
    const changedDocuments = new Set((data.documentMonitor || []).filter((item) => item.changed).map((item) => item.id));
    const extraDocuments = data.documents.filter((entry) => !isPrimaryPlanDocument(entry));
    const filteredDocuments = extraDocuments.filter((entry) => {
      const haystack = `${entry.title} ${entry.source} ${entry.summary} ${entry.tags.join(" ")}`.toLowerCase();
      return haystack.includes(query);
    });
    const visibleDocuments = getVisiblePanelItems(filteredDocuments, "documents");
    setExpandableMeta(elements.documentList, filteredDocuments.length, visibleDocuments.length);
    // Always show the search input once there are extra documents to search through.
    elements.documentSearchWrap.hidden = extraDocuments.length === 0;
    // Keep the extra-documents block visible even on zero results so the empty-
    // state message inside it is shown instead of silently hiding the whole area.
    elements.documentsExtraBlock.hidden = extraDocuments.length === 0;

    elements.documentList.innerHTML = filteredDocuments.length
      ? visibleDocuments
          .map(
            (entry) => `
              <article class="document-item">
                <div class="document-top">
                  <div>
                    <strong>${entry.title}</strong>
                    <p class="message-snippet">${entry.source} - Stand ${entry.updatedAt}</p>
                  </div>
                  <span class="meta-tag ${changedDocuments.has(entry.id === "doc-1" ? "orgaplan" : entry.id) ? "warning" : "low"}">
                    ${changedDocuments.has(entry.id === "doc-1" ? "orgaplan" : entry.id) ? "neu" : "bereit"}
                  </span>
                </div>
                <p class="document-summary">${entry.summary}</p>
                <div class="meta-row">
                  ${entry.tags.map((tag) => `<span class="meta-tag">${tag}</span>`).join("")}
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Kein Dokument passt gerade zu deiner Suche.</div>`;
  }

  function isPrimaryPlanDocument(entry) {
    const title = String(entry.title || "").toLowerCase();
    const source = String(entry.source || "").toLowerCase();
    return title.includes("orgaplan") || title.includes("klassenarbeitsplan") || source.includes("orgaplan");
  }

  // ── SECTION: WebUntis (controls, picker, watchlist, schedule) ───────────────

  function renderWebUntisControls() {
    const center = getData().webuntisCenter;
    const buttons = [
      { id: "day", label: "Heute" },
      { id: "week", label: center.currentWeekLabel || "Diese Woche" },
      { id: "next-week", label: nextWeekLabel(center.currentDate) },
    ];

    elements.webuntisViewSwitch.innerHTML = buttons
      .map(
        (button) => `
          <button class="segment-button ${state.webuntisView === button.id ? "active" : ""}" type="button" data-webuntis-view="${button.id}">
            ${button.label}
          </button>
        `
      )
      .join("");

    elements.webuntisViewSwitch.querySelectorAll("[data-webuntis-view]").forEach((button) => {
      button.addEventListener("click", () => {
        state.webuntisView = button.dataset.webuntisView;
        renderWebUntisControls();
        renderWebUntisSchedule();
      });
    });

    bindExternalLink(elements.webuntisOpenToday, center.todayUrl, "Heute in WebUntis");
    bindExternalLink(elements.webuntisOpenBase, center.startUrl || center.todayUrl, "WebUntis oeffnen");

    elements.webuntisActivePlan.textContent = "Mein Stundenplan";
    elements.webuntisDetail.textContent =
      "Persoenlicher Plan ueber WebUntis-iCal. Vergangene, laufende und kommende Stunden werden hier markiert. Ausfaelle erscheinen nur, wenn WebUntis sie im iCal mitsendet.";
    elements.webuntisRangeLabel.textContent = getWebUntisRangeLabel(center);
    elements.webuntisPlanStrip.hidden = true;
    elements.webuntisPlanStrip.innerHTML = "";
  }

  function renderWebUntisPicker() {
    const center = getData().webuntisCenter;
    const finder = center.finder || {
      status: "warning",
      note: "Planfinder ist vorbereitet.",
      availableTypes: [
        { id: "teacher", label: "Mein Plan" },
        { id: "class", label: "Klasse" },
        { id: "room", label: "Raum" },
      ],
      entities: [],
      watchlist: [],
      searchPlaceholder: "Klasse oder Raum aus deinem Plan suchen",
    };
    const query = state.webuntisPickerSearch.trim().toLowerCase();
    const currentPlan = {
      id: "personal",
      type: "teacher",
      label: center.activePlan || "Mein Stundenplan",
      detail: center.detail || center.note,
      favorite: state.favorites.includes("personal"),
    };
    const searchResults = getGlobalPickerResults(center, query);
    const categories = (finder.availableTypes || center.planTypes || []).map((category) => ({
      ...category,
      count: getPickerEntities(center, category.id, query).length,
    }));
    const activePlan = getActivePlan(center);

    elements.webuntisPickerOverlay.hidden = !state.webuntisPickerOpen;
    elements.webuntisPickerSearch.value = state.webuntisPickerSearch;
    elements.webuntisPickerSearch.placeholder = finder.searchPlaceholder || "Stundenplan suchen";
    elements.webuntisPickerEdit.textContent = activePlan.id === "personal" ? "Fertig" : "Zuruecksetzen";

    const favorites = getFavoriteEntities(center, query);
    elements.webuntisPickerCurrent.innerHTML = renderPickerItem(currentPlan, {
      active: !state.activeFinderEntityId && state.activeShortcutId === "personal",
      compact: false,
      showFavorite: true,
      action: "select",
    });
    elements.webuntisPickerResultsSection.hidden = !query;
    elements.webuntisPickerResultsLabel.textContent = query ? `Treffer fuer "${state.webuntisPickerSearch}"` : "Suche";
    elements.webuntisPickerResults.innerHTML = query
      ? searchResults.length
        ? searchResults
            .map((entity) => renderPickerItem(entity, { active: isEntityActive(center, entity), showFavorite: entity.id !== "personal" }))
            .join("")
        : `<div class="empty-state">Keine passenden Plaene gefunden.</div>`
      : "";
    elements.webuntisPickerFavorites.innerHTML = favorites.length
      ? favorites.map((entity) => renderPickerItem(entity, { active: isEntityActive(center, entity), showFavorite: true, action: "select" })).join("")
      : `<div class="empty-state">Noch keine Favoriten gespeichert.</div>`;
    elements.webuntisPickerCategories.innerHTML = categories
      .map(
        (category) => `
          <button class="picker-category-item" type="button" data-picker-category="${category.id}">
            <span>${category.label}</span>
            <span>${category.count}</span>
          </button>
        `
      )
      .join("");

    elements.webuntisPickerCategories.querySelectorAll("[data-picker-category]").forEach((button) => {
      button.addEventListener("click", () => {
        state.webuntisPickerCategory = button.dataset.pickerCategory;
        renderWebUntisPicker();
      });
    });

    const showCategory = Boolean(state.webuntisPickerCategory);
    elements.webuntisPickerHome.hidden = showCategory;
    elements.webuntisPickerCategoryView.hidden = !showCategory;

    if (showCategory) {
      const category = categories.find((item) => item.id === state.webuntisPickerCategory);
      const categoryItems = getPickerEntities(center, state.webuntisPickerCategory, query);
      elements.webuntisPickerCategoryKicker.textContent = "Stundenplaene";
      elements.webuntisPickerCategoryTitle.textContent = category?.label || "Auswahl";
      elements.webuntisPickerCategoryNote.textContent =
        state.webuntisPickerCategory === "teacher"
          ? "Kolleg:innen-Listen folgen erst mit echter WebUntis-Session. Aktuell bleibt dein persoenlicher Plan die stabile Basis."
          : "Auswaehlen wechselt die Anzeige im Cockpit. Klassen und Raeume stammen derzeit aus deinem persoenlichen Plan.";
      elements.webuntisPickerCategoryResults.innerHTML = categoryItems.length
        ? categoryItems
            .map((entity) =>
              renderPickerItem(entity, {
                active: isEntityActive(center, entity),
                showFavorite: entity.id !== "personal",
                action: "select",
              })
            )
            .join("")
        : `<div class="empty-state">In dieser Kategorie gibt es aktuell keine weiteren Live-Eintraege.</div>`;
    }

    bindPickerActions(center);
  }

  function renderWebUntisWatchlist() {
    const finder = getData().webuntisCenter.finder || { watchlist: [] };
    elements.webuntisWatchlist.innerHTML = (finder.watchlist || []).length
      ? finder.watchlist
          .map(
            (item) => `
              <article class="priority-item">
                <div class="priority-top">
                  <strong>${item.title}</strong>
                  <span class="meta-tag ${watchStatusClass(item.status)}">${watchStatusLabel(item.status)}</span>
                </div>
                <p class="priority-copy">${item.detail}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine geoeffneten Plaene im Radar.</div>`;
  }

  function renderWebUntisPlanStrip() {
    const center = getData().webuntisCenter;
    const plans = getPinnedPlans(center);
    const visiblePlans = plans.filter((plan) => !(plan.id === "personal" && plans.length === 1));

    elements.webuntisPlanStrip.hidden = visiblePlans.length === 0;

    elements.webuntisPlanStrip.innerHTML = visiblePlans.length
      ? visiblePlans
          .map(
            (plan) => `
              <button class="plan-chip ${isPlanChipActive(center, plan) ? "active" : ""}" type="button" data-plan-chip="${plan.id}">
                <span class="plan-chip-type">${shortcutTypeLabel(plan.type)}</span>
                <strong>${plan.label}</strong>
              </button>
            `
          )
      .join("")
      : `<div class="empty-state">Noch keine Plaene gespeichert.</div>`;

    elements.webuntisPlanStrip.querySelectorAll("[data-plan-chip]").forEach((button) => {
      button.addEventListener("click", () => selectPlanById(getData().webuntisCenter, button.dataset.planChip));
    });
  }

  function renderWebUntisSchedule() {
    const events = getWebUntisEvents();
    const center = getData().webuntisCenter;

    if (!events.length) {
      if (state.webuntisView === "day") {
        elements.scheduleList.innerHTML = `<div class="empty-state">Heute liegen im WebUntis-iCal keine Termine vor.</div>`;
        return;
      }
      elements.scheduleList.innerHTML = renderWeekSchedule([], center);
      return;
    }

    if (state.webuntisView !== "day") {
      elements.scheduleList.innerHTML = renderWeekSchedule(events, center);
      return;
    }

    const grouped = groupEventsByDay(events);
    elements.scheduleList.innerHTML = renderAgendaGroups(grouped, "Heute");
  }

  function renderWeekSchedule(events, center) {
    const columns = buildWeekColumns(events, getWeekAnchorDate(center.currentDate, state.webuntisView));
    const hasAnyWeekEvents = columns.some((column) => column.events.length);
    const nextFutureEvent = findNextEventAfter(columns[columns.length - 1]?.isoDate || center.currentDate);
    return `
      <div class="webuntis-week-board">
        <div class="webuntis-agenda-head">
          <strong>${getWebUntisRangeLabel(center)}</strong>
          <span>${
            hasAnyWeekEvents
              ? `${columns.reduce((sum, column) => sum + column.events.length, 0)} Eintraege`
              : nextFutureEvent
                ? `Naechster bekannter Termin: ${formatDate(new Date(nextFutureEvent.startsAt))}`
                : "keine Eintraege im iCal"
          }</span>
        </div>
        <div class="webuntis-week-columns">
          ${columns
            .map(
              (column) => `
                <section class="webuntis-week-column">
                  <div class="webuntis-week-column-head">
                    <span class="webuntis-weekday">${column.weekday}</span>
                    <strong>${column.date}</strong>
                  </div>
                  <div class="webuntis-week-column-items">
                    ${
                      column.events.length
                        ? column.events.map((event) => renderWeekEvent(event)).join("")
                        : renderEmptyWeekColumn(column, hasAnyWeekEvents)
                    }
                  </div>
                </section>
              `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderAgendaGroups(groups, label) {
    return `
      <div class="webuntis-agenda">
        <div class="webuntis-agenda-head">
          <strong>${label}</strong>
          <span>${groups.reduce((sum, group) => sum + group.events.length, 0)} Eintraege</span>
        </div>
        ${groups.map((group) => renderAgendaGroup(group)).join("")}
      </div>
    `;
  }

  function renderAgendaGroup(group) {
    return `
      <section class="webuntis-agenda-group">
        <div class="webuntis-agenda-label">
          <span>${group.label}</span>
          <span>${group.events.length ? `${group.events.length} Termine` : "frei"}</span>
        </div>
        <div class="webuntis-agenda-items">
          ${
            group.events.length
              ? group.events.map((event) => renderWeekEvent(event)).join("")
              : `<div class="webuntis-week-empty">Keine Termine</div>`
          }
        </div>
      </section>
    `;
  }

  function renderDayGroup(group) {
    return `
      <section class="webuntis-day-group">
        <div class="webuntis-day-label">
          <span>${group.label}</span>
          <span>${group.events.length} Eintraege</span>
        </div>
        ${group.events.map((event) => renderDayEvent(event)).join("")}
      </section>
    `;
  }

  function renderDayEvent(event) {
    const timingClass = getEventTimingClass(event);
    return `
      <article class="webuntis-event ${timingClass} ${isCancelledEvent(event) ? "is-cancelled" : ""}">
        <div class="webuntis-event-time">${event.time}</div>
        <div>
          <div class="webuntis-event-head">
            <strong>${event.title}</strong>
            <span class="meta-tag ${eventStateTagClass(event)}">${eventStateLabel(event)}</span>
          </div>
          <p class="webuntis-event-copy">${compactEventDetail(event)}</p>
          <div class="meta-row">
            <span class="meta-tag">${event.category}</span>
            ${event.location ? `<span class="meta-tag">${event.location}</span>` : ""}
            ${event.description ? `<span class="meta-tag">${event.description}</span>` : ""}
          </div>
        </div>
      </article>
    `;
  }

  function renderWeekEvent(event) {
    const timingClass = getEventTimingClass(event);
    return `
      <article class="webuntis-week-event ${timingClass} ${isCancelledEvent(event) ? "is-cancelled" : ""}">
        <div class="webuntis-week-time">${event.time.replace(" - ", "–")}</div>
        <div class="webuntis-week-copy">
          <div class="webuntis-week-head">
            <strong>${event.title}</strong>
            <span class="meta-tag ${eventStateTagClass(event)}">${eventStateLabel(event)}</span>
          </div>
          ${event.location ? `<div class="webuntis-week-meta">${event.location}</div>` : ""}
          ${event.description ? `<div class="webuntis-week-meta">${event.description}</div>` : ""}
        </div>
      </article>
    `;
  }

  function getWebUntisEvents() {
    const center = getData().webuntisCenter;
    const referenceDate = new Date(`${center.currentDate}T00:00:00`);
    let events = (center.events || []).filter((event) => event.startsAt);

    if (!events.length) {
      return [];
    }

    if (state.webuntisView === "day") {
      events = events.filter((event) => isSameDay(new Date(event.startsAt), referenceDate));
    } else {
      const weekStart = getWeekAnchorDate(center.currentDate, state.webuntisView);
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 7);

      events = events.filter((event) => {
        const startsAt = new Date(event.startsAt);
        return startsAt >= weekStart && startsAt < weekEnd;
      });
    }
    return events;
  }

  function groupEventsByDay(events) {
    const groups = new Map();

    events.forEach((event) => {
      const date = new Date(event.startsAt);
      const key = date.toISOString().slice(0, 10);
      const label = `${weekdayLabel(date)} ${formatDate(date)}`;
      if (!groups.has(key)) {
        groups.set(key, { key, label, events: [] });
      }
      groups.get(key).events.push(event);
    });

    return Array.from(groups.values());
  }

  function buildWeekColumns(events, currentDate) {
    const weekStart = startOfWeek(currentDate instanceof Date ? currentDate : new Date(`${currentDate}T00:00:00`));
    const byKey = new Map();

    events.forEach((event) => {
      const date = new Date(event.startsAt);
      const key = date.toISOString().slice(0, 10);
      if (!byKey.has(key)) {
        byKey.set(key, []);
      }
      byKey.get(key).push(event);
    });

    return Array.from({ length: 5 }, (_, index) => {
      const day = new Date(weekStart);
      day.setDate(weekStart.getDate() + index);
      const key = day.toISOString().slice(0, 10);
      return {
        key,
        weekday: day.toLocaleDateString("de-DE", { weekday: "short" }),
        date: formatDate(day),
        isoDate: key,
        events: byKey.get(key) || [],
      };
    });
  }

  function getWeekAnchorDate(currentDate, view) {
    const referenceDate = new Date(`${currentDate}T00:00:00`);
    const weekStart = startOfWeek(referenceDate);
    if (view === "next-week") {
      const nextWeek = new Date(weekStart);
      nextWeek.setDate(nextWeek.getDate() + 7);
      return nextWeek;
    }
    return weekStart;
  }

  function nextWeekLabel(currentDate) {
    const nextWeek = getWeekAnchorDate(currentDate, "next-week");
    const weekNumber = isoWeekNumber(nextWeek);
    return `Naechste KW ${weekNumber}`;
  }

  function getWebUntisRangeLabel(center) {
    if (state.webuntisView === "day") {
      return "Heute";
    }
    if (state.webuntisView === "next-week") {
      return nextWeekLabel(center.currentDate);
    }
    return center.currentWeekLabel || "Diese Woche";
  }

  function bindExternalLink(element, url, label) {
    if (url) {
      element.href = url;
      element.textContent = label;
      element.style.pointerEvents = "auto";
      element.style.opacity = "1";
    } else {
      element.href = "#";
      element.textContent = `${label} nicht verfuegbar`;
      element.style.pointerEvents = "none";
      element.style.opacity = "0.5";
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
        state.classworkSelectedClass = event.target.value;
        renderPlanDigest();
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

  function renderAll() {
    renderWorkspace();
    renderMeta();
    renderRuntimeBanner();
    renderSectionFocus();
    renderBriefing();
    renderQuickLinks();
    renderItslearningConnector();
    renderNextcloudConnector();
    renderChannelFilters();
    renderMessages();
    renderWebUntisControls();
    renderWebUntisSchedule();
    renderPlanDigest();
    renderGrades();
    renderDocuments();
    renderExpandableSections();
    renderNavSignals();
    renderDocumentMonitor();
  }

  async function refreshDashboard(forceRefresh = false) {
    elements.heroNote.textContent = "Lade aktuelle Datenquellen und aktualisiere Cockpit, WebUntis und Inbox.";
    try {
      state.data = await loadDashboard(forceRefresh);
      renderAll();
    } catch (error) {
      if (window.LEHRER_COCKPIT_FALLBACK_DATA) {
        state.data = normalizeDashboard(window.LEHRER_COCKPIT_FALLBACK_DATA);
        renderAll();
        return;
      }

      elements.heroNote.textContent = `Daten konnten nicht geladen werden. Letzter Versuch: ${formatTime(new Date())}.`;
      elements.briefingOutput.innerHTML = `<div class="empty-state">Dashboard-Daten konnten nicht geladen werden.</div>`;
    }
  }

  async function saveItslearningCredentials() {
    const username = elements.itslearningUsername?.value.trim() || "";
    const password = elements.itslearningPassword?.value.trim() || "";

    if (!username || !password) {
      elements.itslearningConnectFeedback.textContent = "Bitte Benutzername und Passwort eintragen.";
      elements.itslearningConnectFeedback.className = "connect-feedback warning";
      return;
    }

    elements.itslearningConnectFeedback.textContent = "Speichere lokale itslearning-Zugangsdaten ...";
    elements.itslearningConnectFeedback.className = "connect-feedback";

    try {
      const response = await fetch("/api/local-settings/itslearning", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          baseUrl: "https://berlin.itslearning.com",
          username,
          password,
          maxUpdates: 6,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Lokales Speichern fehlgeschlagen.");
      }

      elements.itslearningConnectFeedback.textContent = payload.detail || "itslearning-Zugang gespeichert.";
      elements.itslearningConnectFeedback.className = "connect-feedback success";
      elements.itslearningPassword.value = "";
      await refreshDashboard(true);
    } catch (error) {
      elements.itslearningConnectFeedback.textContent = error.message || "itslearning-Zugang konnte nicht gespeichert werden.";
      elements.itslearningConnectFeedback.className = "connect-feedback warning";
    }
  }

  async function saveNextcloudCredentials() {
    const username = elements.nextcloudUsername?.value.trim() || "";
    const password = elements.nextcloudPassword?.value.trim() || "";
    const workspaceUrl = elements.nextcloudWorkspaceUrl?.value.trim() || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/";
    const q1q2Url = elements.nextcloudQ1Q2UrlInput?.value.trim() || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901";
    const q3q4Url = elements.nextcloudQ3Q4UrlInput?.value.trim() || "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900";

    elements.nextcloudConnectFeedback.textContent = "Speichere Nextcloud-Arbeitsbereich lokal ...";
    elements.nextcloudConnectFeedback.className = "connect-feedback";

    try {
      const response = await fetch("/api/local-settings/nextcloud", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          baseUrl: "https://nextcloud-g2.b-sz-heos.logoip.de",
          workspaceUrl,
          username,
          password,
          q1q2Url,
          q3q4Url,
          link1Label: elements.nextcloudLink1Label?.value.trim() || "",
          link1Url: elements.nextcloudLink1Url?.value.trim() || "",
          link2Label: elements.nextcloudLink2Label?.value.trim() || "",
          link2Url: elements.nextcloudLink2Url?.value.trim() || "",
          link3Label: elements.nextcloudLink3Label?.value.trim() || "",
          link3Url: elements.nextcloudLink3Url?.value.trim() || "",
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Lokales Speichern fehlgeschlagen.");
      }

      elements.nextcloudConnectFeedback.textContent = payload.detail || "Nextcloud-Arbeitsbereich gespeichert.";
      elements.nextcloudConnectFeedback.className = "connect-feedback success";
      elements.nextcloudPassword.value = "";
      await refreshDashboard(true);
    } catch (error) {
      elements.nextcloudConnectFeedback.textContent = error.message || "Nextcloud-Zugang konnte nicht gespeichert werden.";
      elements.nextcloudConnectFeedback.className = "connect-feedback warning";
    }
  }

  function loadNextcloudLastOpened() {
    try {
      const raw = localStorage.getItem(NEXTCLOUD_LAST_OPENED_KEY);
      if (!raw) return null;
      const payload = JSON.parse(raw);
      if (!payload || !payload.label || !payload.when) return null;
      return payload;
    } catch (_error) {
      return null;
    }
  }

  function saveNextcloudLastOpened(id, label) {
    const normalizedLabel =
      id === "root" ? "Nextcloud" : id === "q1q2" ? "Q1 / Q2" : id === "q3q4" ? "Q3 / Q4" : (label || "Nextcloud");
    const payload = {
      id: id || "nextcloud",
      label: normalizedLabel,
      when: formatTime(new Date()),
    };
    localStorage.setItem(NEXTCLOUD_LAST_OPENED_KEY, JSON.stringify(payload));
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

  async function loadGradebook() {
    try {
      const response = await fetch("/api/grades");
      if (!response.ok) {
        return;
      }
      state.gradesData = await response.json();
      renderGrades();
    } catch (_error) {
      // lokal optional
    }
  }

  async function loadNotes() {
    try {
      const response = await fetch("/api/notes");
      if (!response.ok) {
        return;
      }
      state.notesData = await response.json();
      renderClassNotes(getGradeClasses(), state.gradesSelectedClass);
      renderNavSignals();
    } catch (_error) {
      // lokal optional
    }
  }

  async function saveGradeEntry() {
    if (!IS_LOCAL_RUNTIME) {
      state.gradesFeedback = "Die Noten-Beta ist nur lokal verfuegbar.";
      state.gradesFeedbackKind = "warning";
      renderGrades();
      return;
    }

    const payload = {
      classLabel: elements.gradesClassInput?.value.trim() || "",
      type: elements.gradesTypeInput?.value.trim() || "Sonstiges",
      studentName: elements.gradesStudentInput?.value.trim() || "",
      title: elements.gradesTitleInput?.value.trim() || "",
      gradeValue: elements.gradesValueInput?.value.trim() || "",
      date: elements.gradesDateInput?.value || "",
      comment: elements.gradesCommentInput?.value.trim() || "",
    };

    if (!payload.classLabel || !payload.studentName || !payload.title) {
      state.gradesFeedback = "Klasse, Schueler:in und Titel werden benoetigt.";
      state.gradesFeedbackKind = "warning";
      renderGrades();
      return;
    }

    state.gradesFeedback = "Speichere lokalen Noteneintrag ...";
    state.gradesFeedbackKind = "";
    renderGrades();

    try {
      const response = await fetch("/api/local-settings/grades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Noteneintrag konnte nicht gespeichert werden.");
      }

      state.gradesData = result;
      state.gradesSelectedClass = payload.classLabel;
      state.gradesFeedback = result.detail || "Note lokal gespeichert.";
      state.gradesFeedbackKind = "success";
      if (elements.gradesForm) {
        elements.gradesForm.reset();
      }
      if (elements.gradesDateInput) {
        elements.gradesDateInput.value = new Date().toISOString().slice(0, 10);
      }
      renderGrades();
    } catch (error) {
      state.gradesFeedback = error.message || "Noteneintrag konnte nicht gespeichert werden.";
      state.gradesFeedbackKind = "warning";
      renderGrades();
    }
  }

  async function deleteGradeEntry(entryId) {
    if (!entryId || !IS_LOCAL_RUNTIME) {
      return;
    }
    try {
      const response = await fetch("/api/local-settings/grades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "delete", id: entryId }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Eintrag konnte nicht entfernt werden.");
      }
      state.gradesData = result;
      state.gradesFeedback = result.detail || "Eintrag entfernt.";
      state.gradesFeedbackKind = "success";
      renderGrades();
    } catch (error) {
      state.gradesFeedback = error.message || "Eintrag konnte nicht entfernt werden.";
      state.gradesFeedbackKind = "warning";
      renderGrades();
    }
  }

  async function saveClassNote() {
    if (!IS_LOCAL_RUNTIME) {
      state.notesFeedback = "Klassen-Notizen sind nur lokal verfuegbar.";
      state.notesFeedbackKind = "warning";
      renderClassNotes(getGradeClasses(), state.notesSelectedClass);
      return;
    }

    const classLabel = elements.notesClassFilter?.value.trim() || state.notesSelectedClass || state.gradesSelectedClass || "";
    const text = elements.notesInput?.value.trim() || "";

    if (!classLabel) {
      state.notesFeedback = "Bitte zuerst eine Klasse waehlen.";
      state.notesFeedbackKind = "warning";
      renderClassNotes(getGradeClasses(), state.notesSelectedClass);
      return;
    }

    state.notesFeedback = "Speichere Klassen-Notiz lokal ...";
    state.notesFeedbackKind = "";
    renderClassNotes(getGradeClasses(), classLabel);

    try {
      const response = await fetch("/api/local-settings/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ classLabel, text }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Notiz konnte nicht gespeichert werden.");
      }
      state.notesData = result;
      state.notesSelectedClass = classLabel;
      state.notesFeedback = result.detail || "Notiz lokal gespeichert.";
      state.notesFeedbackKind = "success";
      renderClassNotes(getGradeClasses(), classLabel);
      renderNavSignals();
    } catch (error) {
      state.notesFeedback = error.message || "Notiz konnte nicht gespeichert werden.";
      state.notesFeedbackKind = "warning";
      renderClassNotes(getGradeClasses(), classLabel);
    }
  }

  async function clearClassNote() {
    if (!IS_LOCAL_RUNTIME) {
      return;
    }

    const classLabel = elements.notesClassFilter?.value.trim() || state.notesSelectedClass || "";
    if (!classLabel) {
      return;
    }

    try {
      const response = await fetch("/api/local-settings/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "delete", classLabel }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Notiz konnte nicht entfernt werden.");
      }
      state.notesData = result;
      state.notesFeedback = result.detail || "Notiz entfernt.";
      state.notesFeedbackKind = "success";
      if (elements.notesInput) {
        elements.notesInput.value = "";
      }
      renderClassNotes(getGradeClasses(), classLabel);
      renderNavSignals();
    } catch (error) {
      state.notesFeedback = error.message || "Notiz konnte nicht entfernt werden.";
      state.notesFeedbackKind = "warning";
      renderClassNotes(getGradeClasses(), classLabel);
    }
  }

  // ── SECTION: Bootstrap / initialize ──────────────────────────────────────────

  function initialize() {
    normalizeLocalWebUntisState();
    applyTheme();
    elements.assistantAnswer.textContent =
      "Frag mich nach der Woche, nach dem Orgaplan, nach Dokumenten oder nach deiner Inbox.";
    registerEvents();
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

  async function loadClassworkCache() {
    const apiBase = IS_LOCAL_RUNTIME ? "" : getBackendApiBase();
    if (!apiBase && !IS_LOCAL_RUNTIME) return;
    try {
      const resp = await fetch(`${apiBase}/api/classwork`);
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
      access: "",
      assistant: "",
    };

    elements.navLinks.forEach((button) => {
      const target = button.dataset.sectionTarget || "";
      const statusKind = statuses[target] || "";
      button.classList.toggle("has-status", Boolean(statusKind));
      if (statusKind) {
        button.dataset.statusKind = statusKind;
      } else {
        delete button.dataset.statusKind;
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

  function loadSavedShortcuts() {
    try {
      const raw = window.localStorage.getItem(WEBUNTIS_SHORTCUTS_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? sanitizeShortcuts(parsed) : [];
    } catch (error) {
      return [];
    }
  }

  function persistShortcuts() {
    window.localStorage.setItem(WEBUNTIS_SHORTCUTS_KEY, JSON.stringify(state.shortcuts));
  }

  function loadWebUntisFavorites() {
    try {
      const raw = window.localStorage.getItem(WEBUNTIS_FAVORITES_KEY);
      const parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? sanitizeFavorites(parsed) : [];
    } catch (error) {
      return [];
    }
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
    if (state.shortcuts.length) {
      state.shortcuts = [];
      persistShortcuts();
    }

    if (state.favorites.length) {
      state.favorites = [];
      persistFavorites();
    }

    state.activeShortcutId = "personal";
    state.activeFinderEntityId = null;
    persistActiveShortcutId();
  }

  function compactEventDetail(event) {
    const parts = [];
    if (event.location) {
      parts.push(`Ort ${event.location}`);
    }
    if (event.description) {
      parts.push(event.description);
    }
    return parts.join(" • ") || "Persoenlicher WebUntis-Termin";
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

  function priorityLabel(priority) {
    return (
      {
        critical: "kritisch",
        high: "wichtig",
        medium: "mittel",
        low: "niedrig",
      }[priority] || priority
    );
  }

  function messagePriorityClass(priority) {
    return (
      {
        critical: "critical",
        high: "high",
        medium: "",
        low: "low",
      }[priority] || ""
    );
  }

  function compareMessageTime(left, right) {
    const [leftHour = 0, leftMinute = 0] = String(left || "00:00").split(":").map((value) => Number(value) || 0);
    const [rightHour = 0, rightMinute = 0] = String(right || "00:00").split(":").map((value) => Number(value) || 0);
    return leftHour * 60 + leftMinute - (rightHour * 60 + rightMinute);
  }

  function statusLabel(status) {
    return (
      {
        ok: "bereit",
        warning: "vorbereitet",
        error: "blockiert",
      }[status] || status
    );
  }

  function monitorStatusLabel(status) {
    return (
      {
        tracked: "beobachtet",
        changed: "geaendert",
        warning: "blockiert",
        error: "offline",
      }[status] || status
    );
  }

  function monitorStatusClass(status) {
    return (
      {
        tracked: "low",
        changed: "high",
        warning: "high",
        error: "critical",
      }[status] || ""
    );
  }

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

  function formatNoteTimestamp(value) {
    if (!value) {
      return "ohne Zeitstempel";
    }
    try {
      const date = new Date(value);
      return `zuletzt aktualisiert ${date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} · ${date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
    } catch (_error) {
      return value;
    }
  }

  initialize();
})();
