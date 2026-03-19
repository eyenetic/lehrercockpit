(function bootstrapApp() {
  const WEBUNTIS_SHORTCUTS_KEY = "lehrerCockpit.webuntis.shortcuts";
  const API_BASE = window.RAILWAY_API_URL || "";

  const state = {
    selectedChannel: "all",
    documentSearch: "",
    webuntisView: "day",
    data: null,
    shortcuts: loadSavedShortcuts(),
  };

  const elements = {
    briefingButton: document.querySelector("#briefing-button"),
    briefingOutput: document.querySelector("#briefing-output"),
    heroNote: document.querySelector("#hero-note"),
    runtimeBanner: document.querySelector("#runtime-banner"),
    workspaceEyebrow: document.querySelector("#workspace-eyebrow"),
    workspaceTitle: document.querySelector("#workspace-title"),
    workspaceDescription: document.querySelector("#workspace-description"),
    statsGrid: document.querySelector("#stats-grid"),
    quickLinkGrid: document.querySelector("#quick-link-grid"),
    berlinFocusList: document.querySelector("#berlin-focus-list"),
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
    webuntisShortcutHint: document.querySelector("#webuntis-shortcut-hint"),
    webuntisShortcutList: document.querySelector("#webuntis-shortcut-list"),
    webuntisShortcutForm: document.querySelector("#webuntis-shortcut-form"),
    webuntisShortcutType: document.querySelector("#webuntis-shortcut-type"),
    webuntisShortcutLabel: document.querySelector("#webuntis-shortcut-label"),
    webuntisShortcutUrl: document.querySelector("#webuntis-shortcut-url"),
    orgaplanOpenLink: document.querySelector("#orgaplan-open-link"),
    orgaplanDigestDetail: document.querySelector("#orgaplan-digest-detail"),
    orgaplanUpcomingList: document.querySelector("#orgaplan-upcoming-list"),
    classworkOpenLink: document.querySelector("#classwork-open-link"),
    classworkDigestDetail: document.querySelector("#classwork-digest-detail"),
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
    const sources = [API_BASE + "/api/dashboard", "./data/mock-dashboard.json"];

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

  function renderMeta() {
    const data = getData();
    elements.heroNote.textContent = `${data.meta.note} Letztes Update: ${data.meta.lastUpdatedLabel}.`;
  }

  function renderRuntimeBanner() {
    const usingFileProtocol = window.location.protocol === "file:";
    const data = getData();

    if (usingFileProtocol) {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        "Direktdatei geoeffnet. Fuer Live-Daten bitte http://127.0.0.1:4173 nutzen.";
      return;
    }

    if (data.meta.mode === "snapshot") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        `Railway ist gerade nicht erreichbar. Du siehst den zuletzt synchronisierten Stand von ${data.meta.lastUpdatedLabel}.`;
      return;
    }

    if (data.meta.mode !== "live") {
      elements.runtimeBanner.hidden = false;
      elements.runtimeBanner.textContent =
        "Fallback aktiv. Die Zeit aktualisiert sich, aber Live-Daten kommen nur ueber den lokalen Server.";
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
    const webuntisEvents = getWebUntisEvents();

    const briefingItems = [];

    if (data.priorities[0]) {
      briefingItems.push({
        title: "Jetzt zuerst",
        copy: `${data.priorities[0].title}. ${data.priorities[0].detail}`,
      });
    }

    if (webuntisEvents[0]) {
      briefingItems.push({
        title: "WebUntis",
        copy: `${state.webuntisView === "day" ? "Heute" : "Diese Woche"}: ${webuntisEvents[0].title} um ${webuntisEvents[0].time}.`,
      });
    }

    if (data.documents[0]) {
      briefingItems.push({
        title: "Dokumente",
        copy: `${data.documents[0].title}: ${data.documents[0].summary}`,
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
    const filteredMessages = data.messages.filter((message) => {
      return state.selectedChannel === "all" || message.channel === state.selectedChannel;
    });

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
    bindExternalLink(elements.classworkOpenLink, classwork.sourceUrl, "Datei oeffnen");

    elements.orgaplanDigestDetail.textContent = orgaplan.detail;
    elements.classworkDigestDetail.textContent = classwork.detail;

    const orgaplanItems = orgaplan.upcoming.length ? orgaplan.upcoming : orgaplan.highlights;

    elements.orgaplanUpcomingList.innerHTML = orgaplanItems.length
      ? orgaplanItems
          .map((item) => renderOrgaplanItem(item))
          .join("")
      : `<div class="empty-state">Noch keine Orgaplan-Highlights erkannt.</div>`;

    elements.classworkPreviewList.innerHTML = classwork.previewRows.length
      ? classwork.previewRows
          .map(
            (row) => `
              <article class="priority-item">
                <p class="priority-copy">${row}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Der Klassenarbeitsplan ist verlinkt, aber aktuell noch nicht automatisch auslesbar.</div>`;
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
        <div class="orgaplan-entry-date">${item.dateLabel}</div>
        <div class="orgaplan-entry-copy">
          ${sections
            .map(
              (section) => `
                <div class="orgaplan-row">
                  <span class="orgaplan-label">${section.label}</span>
                  <p>${section.value}</p>
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
      { id: "day", label: "Tag" },
      { id: "week", label: `Woche ${center.currentWeekLabel || ""}`.trim() },
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
        renderStats();
      });
    });

    bindExternalLink(elements.webuntisOpenToday, center.todayUrl, "Heute in WebUntis");
    bindExternalLink(elements.webuntisOpenBase, center.startUrl, "WebUntis oeffnen");

    elements.webuntisActivePlan.textContent = center.activePlan || "Mein WebUntis-Plan";
    elements.webuntisDetail.textContent = center.detail || center.note;
    elements.webuntisRangeLabel.textContent = state.webuntisView === "day" ? "Tag" : center.currentWeekLabel || "Woche";
    elements.webuntisShortcutHint.textContent = center.shortcutHint;
  }

  function renderWebUntisSchedule() {
    const events = getWebUntisEvents();

    if (!events.length) {
      elements.scheduleList.innerHTML = `<div class="empty-state">Im gewaehlten WebUntis-Zeitraum liegen gerade keine Termine vor.</div>`;
      return;
    }

    const grouped = groupEventsByDay(events);
    elements.scheduleList.innerHTML = grouped
      .map(
        (group) => `
          <section class="webuntis-day-group">
            <div class="webuntis-day-label">
              <span>${group.label}</span>
              <span>${group.events.length} Eintraege</span>
            </div>
            ${group.events
              .map(
                (event) => `
                  <article class="webuntis-event">
                    <div class="webuntis-event-time">${event.time}</div>
                    <div>
                      <strong>${event.title}</strong>
                      <p class="webuntis-event-copy">${event.detail || "Kein weiterer Kontext."}</p>
                      <div class="meta-row">
                        <span class="meta-tag">${event.category}</span>
                        ${event.location ? `<span class="meta-tag">${event.location}</span>` : ""}
                      </div>
                    </div>
                  </article>
                `
              )
              .join("")}
          </section>
        `
      )
      .join("");
  }

  function renderWebUntisShortcuts() {
    const center = getData().webuntisCenter;
    const defaultShortcuts = [];

    if (center.todayUrl) {
      defaultShortcuts.push({
        id: "system-today",
        type: "teacher",
        label: "Mein Plan heute",
        url: center.todayUrl,
        fixed: true,
      });
    }

    if (center.startUrl) {
      defaultShortcuts.push({
        id: "system-start",
        type: "teacher",
        label: "WebUntis Start",
        url: center.startUrl,
        fixed: true,
      });
    }

    const shortcuts = [...defaultShortcuts, ...state.shortcuts];

    elements.webuntisShortcutList.innerHTML = shortcuts.length
      ? shortcuts
          .map(
            (shortcut) => `
              <article class="priority-item">
                <div class="shortcut-item-top">
                  <strong>${shortcut.label}</strong>
                  <span class="meta-tag">${shortcutTypeLabel(shortcut.type)}</span>
                </div>
                <p class="priority-copy">${shortcut.url}</p>
                <div class="shortcut-actions">
                  <a class="shortcut-link-button" href="${shortcut.url}" target="_blank" rel="noreferrer">oeffnen</a>
                  ${
                    shortcut.fixed
                      ? ""
                      : `<button class="shortcut-remove-button" type="button" data-remove-shortcut="${shortcut.id}">entfernen</button>`
                  }
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine WebUntis-Schnellzugriffe gespeichert.</div>`;

    elements.webuntisShortcutList.querySelectorAll("[data-remove-shortcut]").forEach((button) => {
      button.addEventListener("click", () => {
        state.shortcuts = state.shortcuts.filter((shortcut) => shortcut.id !== button.dataset.removeShortcut);
        persistShortcuts();
        renderWebUntisShortcuts();
      });
    });
  }

  function getWebUntisEvents() {
    const center = getData().webuntisCenter;
    const referenceDate = new Date(`${center.currentDate}T00:00:00`);
    const events = (center.events || []).filter((event) => event.startsAt);

    if (!events.length) {
      return [];
    }

    if (state.webuntisView === "day") {
      return events.filter((event) => isSameDay(new Date(event.startsAt), referenceDate));
    }

    const weekStart = startOfWeek(referenceDate);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 7);

    return events.filter((event) => {
      const startsAt = new Date(event.startsAt);
      return startsAt >= weekStart && startsAt < weekEnd;
    });
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

    elements.documentSearch.addEventListener("input", (event) => {
      state.documentSearch = event.target.value;
      renderDocuments();
    });

    elements.assistantForm.addEventListener("submit", (event) => {
      event.preventDefault();
      elements.assistantAnswer.textContent = respondToAssistant(elements.assistantInput.value);
    });

    elements.webuntisShortcutForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const type = elements.webuntisShortcutType.value;
      const label = elements.webuntisShortcutLabel.value.trim();
      const url = elements.webuntisShortcutUrl.value.trim();

      if (!label || !url) {
        elements.heroNote.textContent = `Bitte Bezeichnung und WebUntis-Link ausfuellen. Letztes Update: ${getData().meta.lastUpdatedLabel}.`;
        return;
      }

      state.shortcuts.unshift({
        id: `shortcut-${Date.now()}`,
        type,
        label,
        url,
      });
      persistShortcuts();
      elements.webuntisShortcutForm.reset();
      renderWebUntisShortcuts();
      renderMeta();
    });
  }

  function renderAll() {
    renderWorkspace();
    renderMeta();
    renderRuntimeBanner();
    renderStats();
    renderQuickLinks();
    renderBerlinFocus();
    renderBriefing();
    renderPriorities();
    renderSources();
    renderChannelFilters();
    renderMessages();
    renderWebUntisControls();
    renderWebUntisSchedule();
    renderWebUntisShortcuts();
    renderDocumentMonitor();
    renderPlanDigest();
    renderDocuments();
  }

  async function refreshDashboard() {
    elements.heroNote.textContent = "Lade aktuelle Datenquellen und aktualisiere WebUntis.";
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

  function initialize() {
    elements.assistantAnswer.textContent =
      "Frag mich nach WebUntis, nach PDFs oder nach Terminen dieser Woche.";
    registerEvents();
    refreshDashboard();
  }

  function loadSavedShortcuts() {
    try {
      const raw = window.localStorage.getItem(WEBUNTIS_SHORTCUTS_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function persistShortcuts() {
    window.localStorage.setItem(WEBUNTIS_SHORTCUTS_KEY, JSON.stringify(state.shortcuts));
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

  function shortcutTypeLabel(type) {
    return (
      {
        teacher: "Lehrkraft",
        class: "Klasse",
        room: "Raum",
      }[type] || type
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

  initialize();
})();
