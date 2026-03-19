(function bootstrapApp() {
  const state = {
    selectedChannel: "all",
    documentSearch: "",
    data: null,
  };

  const elements = {
    briefingButton: document.querySelector("#briefing-button"),
    briefingOutput: document.querySelector("#briefing-output"),
    heroNote: document.querySelector("#hero-note"),
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
    const sources = ["/api/dashboard", "./data/mock-dashboard.json"];

    for (const source of sources) {
      try {
        const response = await fetch(source, { cache: "no-store" });
        if (!response.ok) {
          continue;
        }

        return await response.json();
      } catch (error) {
        continue;
      }
    }

    throw new Error("Dashboard-Daten konnten nicht geladen werden.");
  }

  function getData() {
    return state.data || {
      meta: {
        mode: "empty",
        note: "Noch keine Daten geladen.",
        lastUpdatedLabel: "--:--",
      },
      priorities: [],
      messages: [],
      documents: [],
      sources: [],
      quickLinks: [],
      berlinFocus: [],
      documentMonitor: [],
      workspace: {
        eyebrow: "Lehrer-Cockpit",
        title: "Dein Tagesstart",
        description: "Noch keine Workspace-Daten geladen.",
      },
      schedule: [],
      teacher: {
        name: "Lehrkraft",
        school: "Schule",
      },
    };
  }

  function renderStats() {
    const data = getData();
    const unreadCount = data.messages.filter((message) => message.unread).length;
    const criticalCount = data.priorities.filter((item) => item.priority === "critical").length;
    const docCount = data.documents.length;
    const healthySources = data.sources.filter((source) => source.status === "ok").length;

    const cards = [
      {
        label: "Ungelesene Hinweise",
        value: unreadCount,
        detail: "aus allen Kanaelen",
      },
      {
        label: "Akute Punkte",
        value: criticalCount,
        detail: "mit Handlungsbedarf",
      },
      {
        label: "Indizierte Dokumente",
        value: docCount,
        detail: "durchsuchbar",
      },
      {
        label: "Stabile Quellen",
        value: healthySources + "/" + data.sources.length,
        detail: "bereit fuer Sync",
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

  function renderWorkspace() {
    const data = getData();
    elements.workspaceEyebrow.textContent = data.workspace.eyebrow;
    elements.workspaceTitle.textContent = data.workspace.title;
    elements.workspaceDescription.textContent = data.workspace.description;
  }

  function renderBriefing() {
    const data = getData();
    if (!data.priorities.length || !data.documents.length) {
      elements.briefingOutput.innerHTML = `<div class="empty-state">Noch keine Briefing-Daten verfuegbar.</div>`;
      return;
    }

    const briefingItems = [
      {
        title: "Jetzt zuerst",
        copy: `${data.priorities[0].title}. ${data.priorities[0].detail}`,
      },
      {
        title: "Kommunikation",
        copy: `${data.messages.filter((message) => message.unread).length} neue Hinweise, davon ${data.messages.filter((message) => message.channel === "mail" && message.unread).length} direkt in der Dienstmail.`,
      },
      {
        title: "Dokumente",
        copy: `${data.documents[0].title} wurde aktualisiert. Die Aenderung betrifft ${data.documents[0].tags[0].toLowerCase()} und ${data.documents[0].tags[1].toLowerCase()}.`,
      },
    ];

    elements.briefingOutput.innerHTML = briefingItems
      .map(
        (item) => `
          <article class="briefing-item">
            <strong>${item.title}</strong>
            <span>${item.copy}</span>
          </article>
        `
      )
      .join("");
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
    const channels = Object.entries(channelLabels);

    elements.channelFilters.innerHTML = channels
      .map(
        ([id, label]) => `
          <button
            class="filter-button ${state.selectedChannel === id ? "active" : ""}"
            type="button"
            data-channel="${id}"
          >
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
                  <span class="meta-tag ${messagePriorityClass(message.priority)}">
                    ${message.unread ? "neu" : "gesehen"}
                  </span>
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

  function renderSchedule() {
    const data = getData();

    elements.scheduleList.innerHTML = data.schedule.length
      ? data.schedule
          .map(
            (event) => `
              <article class="timeline-item">
                <div class="timeline-top">
                  <div>
                    <strong>${event.title}</strong>
                    <p class="timeline-copy">${event.dateLabel} - ${event.time}</p>
                  </div>
                  <span class="meta-tag">${event.category}</span>
                </div>
                <p class="timeline-copy">${event.detail}</p>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Noch keine Termine verfuegbar.</div>`;
  }

  function renderDocuments() {
    const data = getData();
    const query = state.documentSearch.trim().toLowerCase();
    const filteredDocuments = data.documents.filter((documentEntry) => {
      const haystack = `${documentEntry.title} ${documentEntry.source} ${documentEntry.summary} ${documentEntry.tags.join(" ")}`.toLowerCase();
      return haystack.includes(query);
    });

    elements.documentList.innerHTML = filteredDocuments.length
      ? filteredDocuments
          .map(
            (documentEntry) => `
              <article class="document-item">
                <div class="document-top">
                  <div>
                    <strong>${documentEntry.title}</strong>
                    <p class="message-snippet">${documentEntry.source} - ${documentEntry.updatedAt}</p>
                  </div>
                  <span class="meta-tag low">indiziert</span>
                </div>
                <p class="document-summary">${documentEntry.summary}</p>
                <div class="meta-row">
                  ${documentEntry.tags.map((tag) => `<span class="meta-tag">${tag}</span>`).join("")}
                </div>
              </article>
            `
          )
          .join("")
      : `<div class="empty-state">Kein Dokument passt gerade zu deiner Suche.</div>`;
  }

  function respondToAssistant(question) {
    const data = getData();
    const normalizedQuestion = question.trim().toLowerCase();

    if (!normalizedQuestion) {
      return "Ich brauche noch eine konkrete Frage, zum Beispiel zu morgen, zu neuen PDFs oder zu offenen Rueckfragen.";
    }

    if (normalizedQuestion.includes("morgen")) {
      const tomorrowItems = data.schedule.filter((item) => item.dateLabel === "Morgen");
      if (!tomorrowItems.length) {
        return "Fuer morgen liegt noch kein eigener Termin vor. Ich wuerde als Naechstes die Quellen mit einem echten Kalendersync verbinden.";
      }

      return tomorrowItems
        .map((item) => `${item.title} um ${item.time}. ${item.detail}`)
        .join(" ");
    }

    if (normalizedQuestion.includes("pdf") || normalizedQuestion.includes("dokument")) {
      return data.documents
        .slice(0, 2)
        .map((documentEntry) => `${documentEntry.title}: ${documentEntry.summary}`)
        .join(" ");
    }

    if (normalizedQuestion.includes("mail")) {
      return data.messages
        .filter((message) => message.channel === "mail")
        .slice(0, 2)
        .map((message) => `${message.title} von ${message.sender}. ${message.snippet}`)
        .join(" ");
    }

    if (normalizedQuestion.includes("woche") || normalizedQuestion.includes("termine")) {
      return data.schedule.map((item) => `${item.dateLabel}: ${item.title} (${item.time})`).join(" ");
    }

    return "Im MVP beantworte ich Fragen ueber Prioritaeten, Mails, PDFs und Wochen-Termine. Der naechste Schritt ist, diese Logik mit echten Datenquellen und einer Such-API zu verbinden.";
  }

  function priorityLabel(priority) {
    const labels = {
      critical: "kritisch",
      high: "wichtig",
      medium: "mittel",
      low: "niedrig",
    };

    return labels[priority] || priority;
  }

  function messagePriorityClass(priority) {
    const classes = {
      critical: "critical",
      high: "high",
      medium: "",
      low: "low",
    };

    return classes[priority] || "";
  }

  function statusLabel(status) {
    const labels = {
      ok: "bereit",
      warning: "vorbereitet",
      error: "blockiert",
    };

    return labels[status] || status;
  }

  function monitorStatusLabel(status) {
    const labels = {
      tracked: "beobachtet",
      changed: "geaendert",
      warning: "blockiert",
      error: "offline",
    };

    return labels[status] || status;
  }

  function monitorStatusClass(status) {
    const classes = {
      tracked: "low",
      changed: "high",
      warning: "high",
      error: "critical",
    };

    return classes[status] || "";
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
  }

  function initialize() {
    renderChannelFilters();
    elements.assistantAnswer.textContent =
      "Frag mich nach morgen, nach neuen PDFs, nach offenen Mails oder nach deinen Wochen-Terminen.";
    registerEvents();
    refreshDashboard();
  }

  function renderMeta() {
    const data = getData();
    elements.heroNote.textContent = `${data.meta.note} Letztes Update: ${data.meta.lastUpdatedLabel}.`;
  }

  function renderAll() {
    renderWorkspace();
    renderMeta();
    renderStats();
    renderQuickLinks();
    renderBerlinFocus();
    renderBriefing();
    renderPriorities();
    renderSources();
    renderMessages();
    renderDocumentMonitor();
    renderSchedule();
    renderDocuments();
  }

  async function refreshDashboard() {
    elements.heroNote.textContent = "Lade aktuelle Datenquellen und baue das Briefing neu auf.";
    try {
      state.data = await loadDashboard();
      renderAll();
    } catch (error) {
      elements.heroNote.textContent = "Daten konnten nicht geladen werden. Bitte lokalen Server pruefen.";
      elements.briefingOutput.innerHTML = `<div class="empty-state">Dashboard-Daten konnten nicht geladen werden.</div>`;
    }
  }

  initialize();
})();
