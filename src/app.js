(function bootstrapApp() {
  const WEBUNTIS_SHORTCUTS_KEY = "lehrerCockpit.webuntis.shortcuts";
  const WEBUNTIS_FAVORITES_KEY = "lehrerCockpit.webuntis.favorites";
  const ACTIVE_WEBUNTIS_PLAN_KEY = "lehrerCockpit.webuntis.activePlan";
  const AUTO_REFRESH_MS = 180000;
  const IS_LOCAL_RUNTIME =
    window.location.protocol === "file:" ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";
  const PRODUCTION_API_BASES = buildProductionApiBases();

  const state = {
    activeSection: "overview",
    selectedChannel: "all",
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
    classworkActiveMonth: null,
  };

  const elements = {
    briefingButton: document.querySelector("#briefing-button"),
    briefingOutput: document.querySelector("#briefing-output"),
    heroNote: document.querySelector("#hero-note"),
    runtimeBanner: document.querySelector("#runtime-banner"),
    navLinks: Array.from(document.querySelectorAll("[data-section-target]")),
    viewSections: Array.from(document.querySelectorAll("[data-view-section]")),
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
    priorityList: document.querySelector("#priority-list"),
    sourceList: document.querySelector("#source-list"),
    channelFilters: document.querySelector("#channel-filters"),
    messageList: document.querySelector("#message-list"),
    monitorList: document.querySelector("#monitor-list"),
    scheduleList: document.querySelector("#schedule-list"),
    webuntisViewSwitch: document.querySelector("#webuntis-view-switch"),
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
    classworkUploadLabel: document.querySelector("#classwork-upload-label"),
    classworkUploadLabelText: document.querySelector("#classwork-upload-label-text"),
    classworkScrapeButton: document.querySelector("#classwork-scrape-button"),
    classworkScrapeButtonLabel: document.querySelector("#classwork-scrape-button .scrape-button-label"),
    classworkScrapeButtonSpinner: document.querySelector("#classwork-scrape-button .scrape-button-spinner"),
    classworkScrapeStatus: document.querySelector("#classwork-scrape-status"),
    classworkDigestDetail: document.querySelector("#classwork-digest-detail"),
    classworkTableContainer: document.querySelector("#classwork-table-container"),
    classworkMonthTabs: document.querySelector("#classwork-month-tabs"),
    classworkTable: document.querySelector("#classwork-table"),
    classworkPreviewList: document.querySelector("#classwork-preview-list"),
    documentList: document.querySelector("#document-list"),
    documentSearch: document.querySelector("#document-search"),
    assistantForm: document.querySelector("#assistant-form"),
    assistantInput: document.querySelector("#assistant-input"),
    assistantAnswer: document.querySelector("#assistant-answer"),
  };

  const channelLabels = {
    all: "Alle",
    mail: "Dienstmail",
    itslearning: "itslearning",
    webuntis: "WebUntis",
    website: "Webseite",
  };

  async function loadDashboard() {
    const sources = IS_LOCAL_RUNTIME
      ? ["/api/dashboard", "./data/mock-dashboard.json"]
      : [...PRODUCTION_API_BASES.map((base) => `${base}/api/dashboard`), "./data/mock-dashboard.json"];

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
        structuredRows: [],
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
            structuredRows: [],
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

  function renderWorkspace() {
    const data = getData();
    elements.workspaceEyebrow.textContent = data.workspace.eyebrow;
    elements.workspaceTitle.textContent = data.workspace.title;
    elements.workspaceDescription.textContent = data.workspace.description;
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
    elements.heroNote.textContent = `${data.meta.note} Letztes Update: ${data.meta.lastUpdatedLabel}.`;
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
    const briefingItems = [];
    const nextEvent = findNextLesson(data);
    const orgaplanItem = pickOrgaplanBriefing(data);
    const classworkItem = pickClassworkBriefing(data);
    const inboxItem = pickInboxBriefing(data);

    if (nextEvent) {
      briefingItems.push({
        title: "Naechste Stunde",
        copy: `${nextEvent.title} um ${nextEvent.time}${nextEvent.location ? ` in ${nextEvent.location}` : ""}.`,
      });
    }

    if (orgaplanItem) {
      briefingItems.push({
        title: "Orgaplan",
        copy: `${orgaplanItem.label}: ${orgaplanItem.copy}`,
      });
    }

    if (classworkItem) {
      briefingItems.push({
        title: "Klassenarbeitsplan",
        copy: classworkItem,
      });
    }

    if (inboxItem) {
      briefingItems.push({
        title: "Inbox",
        copy: inboxItem,
      });
    }

    elements.briefingOutput.innerHTML = briefingItems.length
      ? briefingItems
          .map(
            (item) => `
              <article class="briefing-item">
                <strong>${item.title}</strong>
                <span>${item.copy}</span>
              </article>
            `
          )
          .join("")
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

  function pickClassworkBriefing(data) {
    const classwork = data.planDigest?.classwork;
    if (!classwork) {
      return "";
    }

    if (classwork.structuredRows?.length) {
      const first = classwork.structuredRows[0];
      const values = Object.values(first).filter(Boolean);
      return values.slice(0, 3).join(" | ") || classwork.detail || "";
    }
    return classwork.previewRows?.[0] || classwork.detail || "";
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
    elements.quickLinkGrid.innerHTML = data.quickLinks.length
      ? data.quickLinks
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

  function renderItslearningConnector() {
    if (!elements.itslearningConnectCard) {
      return;
    }

    if (!IS_LOCAL_RUNTIME) {
      elements.itslearningConnectCard.hidden = true;
      return;
    }

    const source = getData().sources.find((item) => item.id === "itslearning");
    elements.itslearningConnectCard.hidden = false;
    elements.itslearningConnectStatus.className = `pill ${source?.status === "ok" ? "pill-live" : "pill-positive"}`;
    elements.itslearningConnectStatus.textContent = source?.status === "ok" ? "verbunden" : "lokal";
    elements.itslearningConnectCopy.textContent =
      source?.detail ||
      "Lokale Verbindung fuer Benutzername und Passwort. Gespeichert wird nur in deiner .env.local auf diesem Mac.";
    if (!elements.itslearningUsername.value && source?.status === "ok") {
      elements.itslearningUsername.placeholder = "Benutzername bereits lokal gespeichert";
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
    elements.channelFilters.innerHTML = Object.entries(channelLabels)
      .map(
        ([id, label]) => `
          <button class="filter-button ${state.selectedChannel === id ? "active" : ""}" type="button" data-channel="${id}">
            ${label}
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
    const data = getData();
    const filteredMessages = data.messages
      .filter((message) => {
      return state.selectedChannel === "all" || message.channel === state.selectedChannel;
      })
      .sort((left, right) => compareMessageTime(right.timestamp, left.timestamp));

    elements.messageList.innerHTML = filteredMessages.length
      ? filteredMessages
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

    bindExternalLink(elements.orgaplanOpenLink, orgaplan.sourceUrl, "PDF oeffnen");
    bindExternalLink(elements.classworkOpenLink, classwork.sourceUrl, "Plan online im Viewer öffnen");

    elements.orgaplanDigestDetail.textContent = summarizeOrgaplanDigest(orgaplan);
    elements.classworkDigestDetail.textContent = summarizeClassworkDigest(classwork);

    const orgaplanItems = orgaplan.upcoming.length ? orgaplan.upcoming : orgaplan.highlights;

    elements.orgaplanUpcomingList.innerHTML = orgaplanItems.length
      ? orgaplanItems
          .map((item) => renderOrgaplanItem(item))
          .join("")
      : `<div class="empty-state">Noch keine Orgaplan-Highlights erkannt.</div>`;

    if (classwork.structuredRows && classwork.structuredRows.length && elements.classworkTableContainer && elements.classworkTable) {
      _lastClassworkRows = classwork.structuredRows;
      elements.classworkTableContainer.hidden = false;
      elements.classworkPreviewList.hidden = true;
      elements.classworkTable.innerHTML = renderClassworkTable(classwork.structuredRows, state.classworkActiveMonth);
    } else if (classwork.previewRows && classwork.previewRows.length) {
      if (elements.classworkTableContainer) elements.classworkTableContainer.hidden = true;
      if (elements.classworkPreviewList) elements.classworkPreviewList.hidden = false;
      elements.classworkPreviewList.innerHTML = classwork.previewRows
        .map((row) => `<article class="priority-item"><p class="priority-copy">${row}</p></article>`)
        .join("");
    } else {
      if (elements.classworkTableContainer) elements.classworkTableContainer.hidden = true;
      if (elements.classworkPreviewList) elements.classworkPreviewList.hidden = false;
      elements.classworkPreviewList.innerHTML = `<div class="empty-state">Der Klassenarbeitsplan ist verlinkt, aber aktuell noch nicht automatisch auslesbar.</div>`;
    }
  }

  function renderClassworkTable(allRows, activeMonth) {
    if (!allRows.length) return "";

    // Detect if rows have a _sheet (multi-month) structure
    const hasSheets = allRows.some((r) => r._sheet);
    const months = hasSheets
      ? [...new Set(allRows.map((r) => r._sheet).filter(Boolean))]
      : [];

    // Auto-select current or first month
    if (hasSheets && !activeMonth) {
      const now = new Date();
      const monthName = now.toLocaleDateString("en-US", { month: "long" });
      const yearSuffix = now.getFullYear().toString();
      const currentSheet = months.find(
        (m) => m.toLowerCase().includes(monthName.toLowerCase()) && m.includes(yearSuffix)
      );
      activeMonth = currentSheet || months[0];
    }

    // Render month tabs
    if (elements.classworkMonthTabs) {
      if (months.length > 1) {
        elements.classworkMonthTabs.hidden = false;
        elements.classworkMonthTabs.innerHTML = months
          .map(
            (m) =>
              `<button class="segment-button ${m === activeMonth ? "active" : ""}" type="button" data-classwork-month="${escapeHtml(m)}">${escapeHtml(m)}</button>`
          )
          .join("");
        elements.classworkMonthTabs.querySelectorAll("[data-classwork-month]").forEach((btn) => {
          btn.addEventListener("click", () => {
            state.classworkActiveMonth = btn.dataset.classworkMonth;
            const cached = _lastClassworkRows;
            if (cached && elements.classworkTable) {
              elements.classworkTable.innerHTML = renderClassworkTable(cached, state.classworkActiveMonth);
            }
          });
        });
      } else {
        elements.classworkMonthTabs.hidden = true;
        elements.classworkMonthTabs.innerHTML = "";
      }
    }

    // Filter rows to active month
    const rows = hasSheets ? allRows.filter((r) => r._sheet === activeMonth) : allRows;

    // Build headers: exclude _sheet, exclude columns that are empty for all filtered rows
    const allKeys = rows.length ? Object.keys(rows[0]).filter((k) => k !== "_sheet") : [];
    const headers = allKeys.filter((h) => rows.some((r) => String(r[h] || "").trim()));

    if (!headers.length) return `<tr><td colspan="2" class="empty-state">Keine Eintraege fuer diesen Monat.</td></tr>`;

    const thead = `<thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${rows
      .map(
        (row) =>
          `<tr>${headers.map((h) => `<td>${escapeHtml(String(row[h] || ""))}</td>`).join("")}</tr>`
      )
      .join("")}</tbody>`;
    return thead + tbody;
  }

  // Cache for month-tab switching
  let _lastClassworkRows = null;

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
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
    const detail = orgaplan.detail || "";
    const month = orgaplan.monthLabel ? `${orgaplan.monthLabel}: ` : "";
    return truncateText(`${month}${detail}`, 160);
  }

  function summarizeClassworkDigest(classwork) {
    if (classwork.status === "ok" && classwork.structuredRows?.length) {
      return `Live aus Google Sheets gelesen. ${classwork.structuredRows.length} Eintraege werden als Tabelle angezeigt.`;
    }
    if (classwork.status === "ok" && classwork.previewRows?.length) {
      return "Live gelesen. Vorschau fuer die ersten relevanten Zeilen ist unten sichtbar.";
    }
    return truncateText(classwork.detail || "Klassenarbeitsplan ist aktuell nicht automatisch auslesbar.", 140);
  }

  function truncateText(value, maxLength) {
    const clean = String(value || "").replace(/\s+/g, " ").trim();
    if (clean.length <= maxLength) {
      return clean;
    }
    return `${clean.slice(0, maxLength - 1).trimEnd()}…`;
  }

  function renderDocuments() {
    const data = getData();
    const query = state.documentSearch.trim().toLowerCase();
    const filteredDocuments = data.documents.filter((entry) => {
      const haystack = `${entry.title} ${entry.source} ${entry.summary} ${entry.tags.join(" ")}`.toLowerCase();
      return haystack.includes(query);
    });

    elements.documentList.innerHTML = filteredDocuments.length
      ? filteredDocuments
          .map(
            (entry) => `
              <article class="document-item">
                <div class="document-top">
                  <div>
                    <strong>${entry.title}</strong>
                    <p class="message-snippet">${entry.source} - ${entry.updatedAt}</p>
                  </div>
                  <span class="meta-tag low">bereit</span>
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
      "Persoenlicher Plan ueber WebUntis-iCal. Im Cockpit kompakt, fuer Details direkt in WebUntis weiter.";
    elements.webuntisRangeLabel.textContent = getWebUntisRangeLabel(center);
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

    if (!events.length) {
      elements.scheduleList.innerHTML = `<div class="empty-state">Im gewaehlten WebUntis-Zeitraum liegen gerade keine Termine vor.</div>`;
      return;
    }

    if (state.webuntisView !== "day") {
      elements.scheduleList.innerHTML = renderWeekSchedule(events, getData().webuntisCenter);
      return;
    }

    const grouped = groupEventsByDay(events);
    elements.scheduleList.innerHTML = grouped.map((group) => renderDayGroup(group)).join("");
  }

  function renderWeekSchedule(events, center) {
    const columns = buildWeekColumns(events, getWeekAnchorDate(center.currentDate, state.webuntisView));

    return `
      <div class="webuntis-week-grid">
        ${columns
          .map(
            (column) => `
              <section class="webuntis-week-column">
                <div class="webuntis-week-head">
                  <span class="webuntis-weekday">${column.weekday}</span>
                  <strong>${column.date}</strong>
                </div>
                <div class="webuntis-week-stack">
                  ${
                    column.events.length
                      ? column.events.map((event) => renderWeekEvent(event)).join("")
                      : `<div class="webuntis-week-empty">frei</div>`
                  }
                </div>
              </section>
            `
          )
          .join("")}
      </div>
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
    return `
      <article class="webuntis-event">
        <div class="webuntis-event-time">${event.time}</div>
        <div>
          <strong>${event.title}</strong>
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
    return `
      <article class="webuntis-week-event">
        <div class="webuntis-week-time">${event.time.replace(" - ", "–")}</div>
        <strong>${event.title}</strong>
        ${event.location ? `<div class="webuntis-week-meta">${event.location}</div>` : ""}
        ${event.description ? `<div class="webuntis-week-meta">${event.description}</div>` : ""}
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
      return "Ich brauche noch eine konkrete Frage, zum Beispiel zu morgen, zu WebUntis oder zu neuen PDFs.";
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

    return "Im Cockpit beantworte ich dir gerade Fragen zu WebUntis, Dokumenten, Hinweisen und Terminen.";
  }

  function registerEvents() {
    elements.briefingButton.addEventListener("click", async () => {
      await refreshDashboard();
    });

    if (elements.classworkUploadInput) {
      elements.classworkUploadInput.addEventListener("change", async (event) => {
        const file = event.target.files && event.target.files[0];
        if (file) {
          await triggerClassworkUpload(file);
          // Reset input so same file can be re-uploaded
          event.target.value = "";
        }
      });
    }

    if (elements.classworkScrapeButton) {
      elements.classworkScrapeButton.addEventListener("click", async () => {
        await triggerClassworkScrape();
      });
    }

    elements.navLinks.forEach((button) => {
      button.addEventListener("click", () => {
        state.activeSection = button.dataset.sectionTarget || "overview";
        renderSectionFocus();
        window.scrollTo({ top: 0, behavior: "smooth" });
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
  }

  function renderAll() {
    renderWorkspace();
    renderMeta();
    renderRuntimeBanner();
    renderSectionFocus();
    renderBriefing();
    renderQuickLinks();
    renderItslearningConnector();
    renderChannelFilters();
    renderMessages();
    renderWebUntisControls();
    renderWebUntisSchedule();
    renderPlanDigest();
    renderDocuments();
  }

  async function refreshDashboard() {
    elements.heroNote.textContent = "Lade aktuelle Datenquellen und aktualisiere Cockpit, WebUntis und Inbox.";
    try {
      state.data = await loadDashboard();
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
      await refreshDashboard();
    } catch (error) {
      elements.itslearningConnectFeedback.textContent = error.message || "itslearning-Zugang konnte nicht gespeichert werden.";
      elements.itslearningConnectFeedback.className = "connect-feedback warning";
    }
  }

  function initialize() {
    normalizeLocalWebUntisState();
    elements.assistantAnswer.textContent =
      "Frag mich nach der Woche, nach dem Orgaplan, nach Dokumenten oder nach deiner Inbox.";
    registerEvents();
    refreshDashboard();
    loadClassworkCache();
    window.setInterval(() => {
      refreshDashboard();
    }, AUTO_REFRESH_MS);
  }

  async function loadClassworkCache() {
    const apiBase = IS_LOCAL_RUNTIME ? "" : getBackendApiBase();
    if (!apiBase && !IS_LOCAL_RUNTIME) return;
    try {
      const resp = await fetch(`${apiBase}/api/classwork`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.status === "ok" || data.status === "warning") {
        renderClassworkScrapeResult(data);
        if (data.hasChanges) {
          setScrapeStatus(`⚡ Neue Änderungen! ${data.detail}`, "ok");
        } else if (data.status === "ok") {
          const age = data.cacheAgeMinutes != null ? ` (vor ${Math.round(data.cacheAgeMinutes)} Min)` : "";
          setScrapeStatus(`✓ Letzte Daten${age}: ${data.detail}`, "ok");
        }
      }
    } catch (_err) {
      // Silently ignore — backend may not be available
    }
  }

  // ── Classwork Scraper ──────────────────────────────────────────────────────

  async function triggerClassworkScrape() {
    if (!elements.classworkScrapeButton) return;

    const apiBase = getBackendApiBase();
    const scrapeUrl = `${apiBase}/api/classwork/scrape`;
    const pollUrl = `${apiBase}/api/classwork`;

    setScrapeButtonLoading(true);
    setScrapeStatus("Scrape wird gestartet…", "loading");

    try {
      const response = await fetch(scrapeUrl, { method: "POST" });

      if (response.status === 202) {
        // Accepted — scrape running in background, start polling
        setScrapeStatus("Scrape läuft. Daten werden geladen…", "loading");
        await pollClassworkResult(pollUrl);
      } else if (response.status === 200) {
        // Synchronous result (busy/cache)
        const data = await response.json();
        renderClassworkScrapeResult(data);
        setScrapeButtonLoading(false);
      } else {
        const err = await response.json().catch(() => ({}));
        setScrapeStatus(`Fehler: ${err.detail || response.status}`, "error");
        setScrapeButtonLoading(false);
      }
    } catch (err) {
      setScrapeStatus(`Netzwerkfehler: ${err.message}`, "error");
      setScrapeButtonLoading(false);
    }
  }

  async function pollClassworkResult(pollUrl, maxAttempts = 20, intervalMs = 3000) {
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
      try {
        const response = await fetch(pollUrl);
        if (!response.ok) continue;
        const data = await response.json();

        if (data.scrapeInProgress) {
          const elapsed = ((i + 1) * intervalMs / 1000).toFixed(0);
          setScrapeStatus(`Scrape läuft noch… (${elapsed}s)`, "loading");
          continue;
        }

        renderClassworkScrapeResult(data);
        setScrapeButtonLoading(false);
        return;
      } catch (_err) {
        // continue polling
      }
    }
    setScrapeStatus("Timeout — Scrape dauert zu lang. Bitte erneut versuchen.", "error");
    setScrapeButtonLoading(false);
  }

  function renderClassworkScrapeResult(data) {
    const status = data.status || "warning";
    const rows = data.structuredRows || [];
    const preview = data.previewRows || [];
    const detail = data.detail || "";
    const scrapedAt = data.scrapedAt ? new Date(data.scrapedAt).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "";

    if (status === "ok" && rows.length) {
      setScrapeStatus(`✓ ${rows.length} Einträge geladen${scrapedAt ? ` (${scrapedAt})` : ""}.`, "ok");
    } else if (status === "ok" && preview.length) {
      setScrapeStatus(`✓ Vorschau geladen${scrapedAt ? ` (${scrapedAt})` : ""}.`, "ok");
    } else {
      setScrapeStatus(truncateText(detail || "Keine Daten. Mögliche Ursache: Microsoft-Login nötig.", 120), "warning");
    }

    // Update the digest display
    if (elements.classworkDigestDetail) {
      elements.classworkDigestDetail.textContent = detail;
    }

    if (rows.length && elements.classworkTableContainer && elements.classworkTable) {
      _lastClassworkRows = rows;
      state.classworkActiveMonth = null;
      elements.classworkTableContainer.hidden = false;
      if (elements.classworkPreviewList) elements.classworkPreviewList.hidden = true;
      elements.classworkTable.innerHTML = renderClassworkTable(rows, null);
    } else if (preview.length && elements.classworkPreviewList) {
      if (elements.classworkTableContainer) elements.classworkTableContainer.hidden = true;
      elements.classworkPreviewList.hidden = false;
      elements.classworkPreviewList.innerHTML = preview
        .map((row) => `<article class="priority-item"><p class="priority-copy">${row}</p></article>`)
        .join("");
    }

    if (data.sourceUrl && elements.classworkOpenLink) {
      elements.classworkOpenLink.href = data.sourceUrl;
      elements.classworkOpenLink.textContent = "Plan online im Viewer öffnen";
      elements.classworkOpenLink.hidden = false;
    }
  }

  function setScrapeButtonLoading(loading) {
    if (!elements.classworkScrapeButton) return;
    elements.classworkScrapeButton.disabled = loading;
    if (elements.classworkScrapeButtonLabel) {
      elements.classworkScrapeButtonLabel.textContent = loading ? "Lädt…" : "Jetzt abrufen";
    }
    if (elements.classworkScrapeButtonSpinner) {
      elements.classworkScrapeButtonSpinner.hidden = !loading;
    }
  }

  function setScrapeStatus(message, type) {
    if (!elements.classworkScrapeStatus) return;
    elements.classworkScrapeStatus.textContent = message;
    elements.classworkScrapeStatus.hidden = !message;
    elements.classworkScrapeStatus.dataset.type = type || "";
  }

  async function triggerClassworkUpload(file) {
    if (!file) return;
    const apiBase = getBackendApiBase();
    const uploadUrl = `${apiBase}/api/classwork/upload`;

    const labelText = elements.classworkUploadLabelText;
    if (labelText) labelText.textContent = "⏳ Wird verarbeitet…";
    if (elements.classworkUploadLabel) elements.classworkUploadLabel.style.opacity = "0.6";
    setScrapeStatus(`Datei "${file.name}" wird hochgeladen…`, "loading");

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);

      const response = await fetch(uploadUrl, { method: "POST", body: formData });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setScrapeStatus(`Upload-Fehler: ${data.detail || response.status}`, "error");
        return;
      }

      renderClassworkScrapeResult(data);
      setScrapeStatus(`✓ "${file.name}" eingelesen. ${data.detail || ""}`, "ok");
    } catch (err) {
      setScrapeStatus(`Upload fehlgeschlagen: ${err.message}`, "error");
    } finally {
      if (labelText) labelText.textContent = "📂 Hochladen";
      if (elements.classworkUploadLabel) elements.classworkUploadLabel.style.opacity = "1";
    }
  }

  // ── End Classwork Scraper ──────────────────────────────────────────────────

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
    return value.toLocaleDateString("de-DE", { weekday: "long" });
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

  initialize();
})();
