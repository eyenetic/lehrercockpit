/**
 * src/features/classwork.js — Plan-digest and Classwork section rendering
 *
 * Extracted from src/app.js. Owns:
 *   - renderPlanDigest()          — orgaplan + classwork digest cards
 *   - renderClassworkSelector()   — class filter dropdown
 *   - renderClassworkViewSwitch() — list/calendar toggle buttons
 *   - renderClassworkList()       — list view HTML builder
 *   - renderClassworkCalendar()   — calendar view HTML builder
 *   - renderOrgaplanItem()        — single orgaplan entry HTML
 *   - getActiveClassworkClass()   — active class selection logic
 *   - summarizeOrgaplanDigest()   — orgaplan detail string
 *   - summarizeClassworkDigest()  — classwork detail string
 *   - joinOrgaplanSection()       — orgaplan section text combiner
 *   - truncateText()              — shared text utility
 *
 * Initialization:
 *   window.LehrerClasswork.init(state, elements, {
 *     getData, bindExternalLink, isModuleVisible,
 *     getVisiblePanelItems, setExpandableMeta, weekdayLabel
 *   })
 *
 * Exports (to window.LehrerClasswork):
 *   init, renderPlanDigest, renderClassworkList, renderClassworkCalendar,
 *   renderOrgaplanItem, getActiveClassworkClass, truncateText
 */
var LehrerClasswork = (function () {
  'use strict';

  var _state = null;
  var _elements = null;
  var _getData = null;
  var _bindExternalLink = null;
  var _isModuleVisible = null;
  var _getVisiblePanelItems = null;
  var _setExpandableMeta = null;
  var _weekdayLabel = null;
  var _getSelectedClassworkClasses = null;
  var _refreshDashboard = null;

  function init(state, elements, callbacks) {
    _state = state;
    _elements = elements;
    _getData = callbacks.getData;
    _bindExternalLink = callbacks.bindExternalLink;
    _isModuleVisible = callbacks.isModuleVisible;
    _getVisiblePanelItems = callbacks.getVisiblePanelItems;
    _setExpandableMeta = callbacks.setExpandableMeta;
    _weekdayLabel = callbacks.weekdayLabel;
    _getSelectedClassworkClasses = callbacks.getSelectedClassworkClasses;
    _refreshDashboard = callbacks.refreshDashboard || null;

    // Grab classwork-specific elements not in the shared elements map
    _elements.classworkUploadInfo = document.querySelector('#classwork-upload-info');
    _elements.classworkSourceUrl  = document.querySelector('#classwork-source-url');
    _elements.classworkFetchButton = document.querySelector('#classwork-fetch-button');
    _elements.classworkClassPills = document.querySelector('#classwork-class-pills');
    _elements.classworkPillSection = document.querySelector('#classwork-pill-section');

    _initClassworkFetch();
  }

  // ── Auto-fetch from OneDrive URL ─────────────────────────────────────────────

  function _initClassworkFetch() {
    var btn = _elements.classworkFetchButton;
    var urlInput = _elements.classworkSourceUrl;
    if (!btn || !urlInput) return;

    // Restore saved URL if any
    var saved = localStorage.getItem('lc.classworkSourceUrl') || '';
    if (saved) urlInput.value = saved;

    btn.addEventListener('click', function () {
      var url = urlInput.value.trim();
      if (!url) {
        _showFeedback('Bitte einen OneDrive-Link einfügen.', 'warning');
        return;
      }
      localStorage.setItem('lc.classworkSourceUrl', url);
      btn.disabled = true;
      btn.textContent = 'Wird geladen …';
      _showFeedback('', '');

      if (window.LehrerAPI) {
        window.LehrerAPI.fetchClassworkFromUrl(url)
          .then(function (resp) { return resp.json(); })
          .then(function (json) {
            btn.disabled = false;
            btn.textContent = 'Abrufen';
            if (json.ok) {
              _showFeedback('Klassenarbeitsplan erfolgreich aktualisiert.', 'success');
              if (_refreshDashboard) _refreshDashboard(true);
            } else {
              _showFeedback(json.error || 'Abruf fehlgeschlagen.', 'warning');
            }
          })
          .catch(function (err) {
            btn.disabled = false;
            btn.textContent = 'Abrufen';
            _showFeedback('Netzwerkfehler: ' + err.message, 'warning');
          });
      }
    });
  }

  function _showFeedback(msg, kind) {
    if (!_elements.classworkUploadFeedback) return;
    _elements.classworkUploadFeedback.textContent = msg;
    _elements.classworkUploadFeedback.className = 'connect-feedback' + (kind ? ' ' + kind : '');
  }

  // ── Upload-Info anzeigen (wer hat wann hochgeladen) ──────────────────────────

  function renderClassworkUploadInfo(classwork) {
    var el = _elements.classworkUploadInfo;
    if (!el) return;
    var by = classwork.uploadedBy || '';
    var at = classwork.uploadedAt || classwork.updatedAt || '';
    var src = classwork.uploadSource || '';
    if (!at) { el.hidden = true; return; }
    var srcLabel = src === 'auto' ? 'Automatisch abgerufen' : 'Hochgeladen';
    var byPart = by ? ' von <strong>' + by + '</strong>' : '';
    el.innerHTML = '<span class="classwork-info-icon">✓</span>'
      + srcLabel + byPart + ' am ' + at;
    el.hidden = false;
  }

  // ── Utility ─────────────────────────────────────────────────────────────────

  function truncateText(value, maxLength) {
    var clean = String(value || '').replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLength) return clean;
    return clean.slice(0, maxLength - 1).trimEnd() + '\u2026';
  }

  function joinOrgaplanSection(primary, notes) {
    if (!primary && !notes) return '';
    if (primary && notes) return primary + ' (' + notes + ')';
    return primary || notes;
  }

  function summarizeOrgaplanDigest(orgaplan) {
    var count = (orgaplan.upcoming || []).length || (orgaplan.highlights || []).length;
    if (!count) {
      return orgaplan.sourceUrl
        ? 'Der Orgaplan ist verlinkt. Sobald Hinweise erkannt werden, erscheinen sie hier kompakt.'
        : 'Noch kein Orgaplan-Link hinterlegt.';
    }
    var month = orgaplan.monthLabel || 'diesem Monat';
    return count + ' relevante Hinweise für ' + month + '. Hier stehen nur die nächsten Punkte, nicht der ganze Plan.';
  }

  function summarizeClassworkDigest(classwork) {
    if (classwork.status === 'ok') {
      var classCount = (classwork.classes || []).length;
      var entryCount = (classwork.entries || []).length;
      return entryCount + ' Einträge für ' + classCount + ' Klassen erkannt. Lade bei Bedarf eine neue Datei hoch oder arbeite mit dem zuletzt gemeinsam importierten Stand.';
    }
    return truncateText(classwork.detail || 'Der Klassenarbeitsplan ist verlinkt, aber noch nicht automatisch lesbar.', 140);
  }

  // ── Classwork class selection ────────────────────────────────────────────────

  var _CLASSES_STORAGE_KEY = 'lc.classworkSelectedClasses';

  function _saveSelectedClasses(classes) {
    try { localStorage.setItem(_CLASSES_STORAGE_KEY, JSON.stringify(classes)); } catch (e) {}
  }

  function _loadSelectedClasses() {
    try { return JSON.parse(localStorage.getItem(_CLASSES_STORAGE_KEY) || 'null'); } catch (e) { return null; }
  }

  function getSelectedClasses(classes, defaultClass) {
    if (_getSelectedClassworkClasses) {
      return _getSelectedClassworkClasses(classes, defaultClass);
    }
    if (!classes.length) {
      _state.classworkSelectedClasses = [];
      return [];
    }
    // Restore from localStorage if not yet set in memory
    if (!Array.isArray(_state.classworkSelectedClasses) || !_state.classworkSelectedClasses.length) {
      var saved = _loadSelectedClasses();
      if (Array.isArray(saved) && saved.length) {
        _state.classworkSelectedClasses = saved;
      }
    }
    if (Array.isArray(_state.classworkSelectedClasses) && _state.classworkSelectedClasses.length) {
      var selected = _state.classworkSelectedClasses.filter(function (label) {
        return classes.includes(label);
      });
      if (selected.length) {
        _state.classworkSelectedClasses = selected;
        return selected;
      }
    }
    _state.classworkSelectedClasses = [(defaultClass && classes.includes(defaultClass)) ? defaultClass : classes[0]];
    _saveSelectedClasses(_state.classworkSelectedClasses);
    return _state.classworkSelectedClasses;
  }

  // ── Selector + view switch ───────────────────────────────────────────────────

  function renderClassworkSelector(classes, defaultClass) {
    var pillContainer = _elements.classworkClassPills;
    var pillSection = _elements.classworkPillSection;

    if (!pillContainer) {
      // Fallback: old select-based rendering
      if (!_elements.classworkClassFilter) return;
      var activeClasses = getSelectedClasses(classes, defaultClass);
      _elements.classworkClassFilter.disabled = !classes.length;
      if (!classes.length) {
        _elements.classworkClassFilter.innerHTML = '<option value="">Keine Klasse erkannt</option>';
        return;
      }
      _elements.classworkClassFilter.innerHTML = classes.map(function (c) {
        return '<option value="' + c + '"' + (activeClasses.includes(c) ? ' selected' : '') + '>' + c + '</option>';
      }).join('');
      return;
    }

    if (!classes.length) {
      if (pillSection) pillSection.hidden = true;
      return;
    }
    if (pillSection) pillSection.hidden = false;

    var active = getSelectedClasses(classes, defaultClass);
    pillContainer.innerHTML = classes.map(function (label) {
      var isActive = active.includes(label);
      return '<button type="button" class="classwork-pill' + (isActive ? ' is-active' : '') + '"'
        + ' data-classwork-class="' + label + '">' + label + '</button>';
    }).join('');

    pillContainer.querySelectorAll('[data-classwork-class]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var label = btn.dataset.classworkClass;
        var current = getSelectedClasses(classes, defaultClass);
        if (current.includes(label)) {
          _state.classworkSelectedClasses = current.filter(function (c) { return c !== label; });
          if (!_state.classworkSelectedClasses.length) _state.classworkSelectedClasses = [label];
        } else {
          _state.classworkSelectedClasses = current.concat([label]);
        }
        _saveSelectedClasses(_state.classworkSelectedClasses);
        renderClassworkSelector(classes, defaultClass);
        renderPlanDigest();
      });
    });
  }

  function renderClassworkViewSwitch() {
    if (!_elements.classworkViewSwitch) return;
    var options = [
      { id: 'list', label: 'Liste' },
      { id: 'calendar', label: 'Kalender' },
    ];
    _elements.classworkViewSwitch.innerHTML = options.map(function (option) {
      return '<button class="filter-button ' + (_state.classworkView === option.id ? 'active' : '') + '" type="button" data-classwork-view="' + option.id + '">' + option.label + '</button>';
    }).join('');
    _elements.classworkViewSwitch.querySelectorAll('[data-classwork-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        _state.classworkView = button.dataset.classworkView;
        renderPlanDigest();
      });
    });
  }

  // ── List + calendar HTML builders ────────────────────────────────────────────

  function renderClassworkList(entries) {
    return entries.map(function (entry) {
      return '<article class="classwork-entry">'
        + '<div class="classwork-entry-top">'
        + '<div><strong>' + entry.dateLabel + '</strong><p>' + _weekdayLabel(entry.weekdayLabel) + '</p></div>'
        + '<span class="meta-tag low">' + entry.kind + '</span>'
        + '</div>'
        + '<p class="classwork-entry-title">' + (entry.summary || entry.title) + '</p>'
        + '<div class="meta-row"><span class="meta-tag">' + entry.classLabel + '</span></div>'
        + '</article>';
    }).join('');
  }

  function renderClassworkCalendar(entries) {
    var grouped = new Map();
    entries.forEach(function (entry) {
      var key = entry.isoDate;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(entry);
    });
    return '<div class="classwork-calendar">'
      + Array.from(grouped.entries()).map(function (pair) {
          var dayEntries = pair[1];
          return '<section class="classwork-day">'
            + '<div class="classwork-day-head">'
            + '<span class="webuntis-weekday">' + _weekdayLabel(dayEntries[0].weekdayLabel) + '</span>'
            + '<strong>' + dayEntries[0].dateLabel + '</strong>'
            + '</div>'
            + '<div class="classwork-day-items">'
            + dayEntries.map(function (entry) {
                return '<article class="classwork-calendar-item">'
                  + '<span class="meta-tag low">' + entry.kind + '</span>'
                  + '<strong>' + (entry.summary || entry.title) + '</strong>'
                  + '</article>';
              }).join('')
            + '</div></section>';
        }).join('')
      + '</div>';
  }

  // ── Orgaplan item HTML ───────────────────────────────────────────────────────

  function _orgaplanLevelTags(item) {
    var levels = [];
    if (item.general) levels.push('Allgemein');
    if (joinOrgaplanSection(item.middle, item.middleNotes)) levels.push('Mittelstufe');
    if (joinOrgaplanSection(item.upper, item.upperNotes)) levels.push('Oberstufe');
    if (!levels.length) return '';
    return levels.map(function (l) {
      return '<span class="meta-tag orgaplan-level-tag">' + l + '</span>';
    }).join('');
  }

  function renderOrgaplanItem(item) {
    var sections = [
      { label: 'Allgemein', value: item.general },
      { label: 'Mittelstufe', value: joinOrgaplanSection(item.middle, item.middleNotes) },
      { label: 'Oberstufe', value: joinOrgaplanSection(item.upper, item.upperNotes) },
    ].filter(function (s) { return s.value; });

    var levelTags = _orgaplanLevelTags(item);

    if (!sections.length) {
      return '<article class="orgaplan-entry">'
        + '<div class="orgaplan-entry-head">'
        + '<strong class="orgaplan-entry-date">' + item.dateLabel + '</strong>'
        + '<span class="meta-tag low">' + (item.title || 'Orgaplan') + '</span>'
        + '</div>'
        + (levelTags ? '<div class="orgaplan-level-row">' + levelTags + '</div>' : '')
        + '<div class="orgaplan-entry-copy">'
        + '<p>' + truncateText(item.detail || item.text || '', 220) + '</p>'
        + '</div></article>';
    }

    return '<article class="orgaplan-entry">'
      + '<div class="orgaplan-entry-head">'
      + '<strong class="orgaplan-entry-date">' + item.dateLabel + '</strong>'
      + '<span class="meta-tag low">' + (item.title || 'Orgaplan') + '</span>'
      + '</div>'
      + '<div class="orgaplan-entry-copy">'
      + sections.map(function (section) {
          return '<div class="orgaplan-row">'
            + '<span class="orgaplan-label">' + section.label + '</span>'
            + '<p>' + truncateText(section.value, 220) + '</p>'
            + '</div>';
        }).join('')
      + '</div></article>';
  }

  // ── Orgaplan today card (single highlighted date entry) ──────────────────────

  function renderOrgaplanTodayCard(todayEntries) {
    if (!todayEntries || !todayEntries.length) {
      return '<div class="orgaplan-today-empty">'
        + '<span class="orgaplan-today-empty-icon">✓</span>'
        + '<p>Heute keine besonderen Orgaplan-Hinweise</p>'
        + '</div>';
    }
    return todayEntries.map(function (item) {
      var sections = [
        { label: 'Allgemein', value: item.general },
        { label: 'Mittelstufe', value: joinOrgaplanSection(item.middle, item.middleNotes) },
        { label: 'Oberstufe', value: joinOrgaplanSection(item.upper, item.upperNotes) },
      ].filter(function (s) { return s.value; });

      var bodyHtml = sections.length
        ? sections.map(function (s) {
            return '<div class="orgaplan-row orgaplan-row--today">'
              + '<span class="orgaplan-label">' + s.label + '</span>'
              + '<p>' + truncateText(s.value, 280) + '</p>'
              + '</div>';
          }).join('')
        : '<p class="orgaplan-text">' + truncateText(item.detail || item.text || '', 280) + '</p>';

      return '<article class="orgaplan-today-item">'
        + '<div class="orgaplan-today-item__head">'
        + '<span class="orgaplan-today-item__badge pill pill-attention">Heute</span>'
        + '<strong class="orgaplan-today-item__title">' + (item.title || 'Hinweis') + '</strong>'
        + '</div>'
        + '<div class="orgaplan-today-item__body">' + bodyHtml + '</div>'
        + '</article>';
    }).join('');
  }

  // ── Orgaplan week section (Mon–Sun overview) ─────────────────────────────────

  function renderOrgaplanWeekSection(weekEntries) {
    if (!weekEntries || !weekEntries.length) {
      return '<div class="empty-state">Keine Orgaplan-Einträge für diese Woche.</div>';
    }
    // Group by isoDate
    var grouped = {};
    var order = [];
    weekEntries.forEach(function (item) {
      var key = item.isoDate || item.dateLabel;
      if (!grouped[key]) { grouped[key] = []; order.push(key); }
      grouped[key].push(item);
    });
    return order.map(function (key) {
      var items = grouped[key];
      var dateLabel = items[0].dateLabel || key;
      return '<section class="orgaplan-week-day">'
        + '<div class="orgaplan-week-day__head">'
        + '<strong class="orgaplan-week-day__date">' + dateLabel + '</strong>'
        + '</div>'
        + '<div class="orgaplan-week-day__items">'
        + items.map(function (item) {
            var sections = [
              { label: 'Allgemein', value: item.general },
              { label: 'Mittelstufe', value: joinOrgaplanSection(item.middle, item.middleNotes) },
              { label: 'Oberstufe', value: joinOrgaplanSection(item.upper, item.upperNotes) },
            ].filter(function (s) { return s.value; });
            var bodyHtml = sections.length
              ? sections.map(function (s) {
                  return '<div class="orgaplan-row">'
                    + '<span class="orgaplan-label">' + s.label + '</span>'
                    + '<p>' + truncateText(s.value, 200) + '</p>'
                    + '</div>';
                }).join('')
              : '<p class="orgaplan-text">' + truncateText(item.detail || item.text || '', 200) + '</p>';
            return '<article class="orgaplan-week-item">'
              + '<div class="orgaplan-week-item__title">'
              + '<span class="meta-tag low">' + (item.title || 'Hinweis') + '</span>'
              + '</div>'
              + '<div class="orgaplan-entry-copy">' + bodyHtml + '</div>'
              + '</article>';
          }).join('')
        + '</div></section>';
    }).join('');
  }

  // ── Plan digest (orchestrates classwork + orgaplan card rendering) ───────────

  function renderPlanDigest() {
    if (!_elements || !_state) return;
    var digest = _getData().planDigest;
    var orgaplan = digest.orgaplan;
    var classwork = digest.classwork;
    var showOrgaplan = _isModuleVisible('orgaplan');
    var showClasswork = _isModuleVisible('klassenarbeitsplan');
    var classes = classwork.classes || [];
    var entries = classwork.entries || [];

    if (_elements.orgaplanDigestCard) _elements.orgaplanDigestCard.hidden = !showOrgaplan;
    if (_elements.classworkDigestCard) _elements.classworkDigestCard.hidden = !showClasswork;

    if (showOrgaplan) {
      _bindExternalLink(_elements.orgaplanOpenLink, orgaplan.sourceUrl, 'PDF öffnen');
      _elements.orgaplanDigestDetail.textContent = summarizeOrgaplanDigest(orgaplan);
      // Today's entries
      if (_elements.orgaplanTodayList) {
        _elements.orgaplanTodayList.innerHTML = renderOrgaplanTodayCard(orgaplan.today_entries || []);
      }
      // This week's entries
      if (_elements.orgaplanWeekList) {
        _elements.orgaplanWeekList.innerHTML = renderOrgaplanWeekSection(orgaplan.week_entries || []);
      }
    }
    if (showClasswork) {
      _bindExternalLink(_elements.classworkOpenLink, classwork.sourceUrl, 'Plan online öffnen');
      _elements.classworkDigestDetail.textContent = summarizeClassworkDigest(classwork);
      renderClassworkUploadInfo(classwork);
      if (_elements.classworkUploadStatus) {
        _elements.classworkUploadStatus.hidden = true;
      }
    } else if (_elements.classworkUploadInfo) {
      _elements.classworkUploadInfo.hidden = true;
    }
    if (!_state.classworkUploadFeedback) {
      // Don't overwrite feedback set by fetch button handler
    } else {
      _elements.classworkUploadFeedback.textContent = _state.classworkUploadFeedback;
      _elements.classworkUploadFeedback.className = 'connect-feedback' + (_state.classworkUploadFeedbackKind ? ' ' + _state.classworkUploadFeedbackKind : '');
    }

    if (showClasswork) {
      renderClassworkSelector(classes, classwork.defaultClass || '');
      renderClassworkViewSwitch();
    }

    var orgaplanItems = (orgaplan.upcoming.length ? orgaplan.upcoming : orgaplan.highlights)
      .slice()
      .sort(function (a, b) { return (a.isoDate || a.dateLabel || '').localeCompare(b.isoDate || b.dateLabel || ''); });
    if (showOrgaplan) {
      _elements.orgaplanUpcomingList.innerHTML = orgaplanItems.length
        ? orgaplanItems.map(renderOrgaplanItem).join('')
        : '<div class="empty-state">Noch keine Orgaplan-Highlights erkannt.</div>';
    }

    var activeClasses = getSelectedClasses(classes, classwork.defaultClass || '');
    var today = new Date();
    var weekStart = new Date(today);
    var weekdayIndex = (weekStart.getDay() + 6) % 7;
    weekStart.setDate(weekStart.getDate() - weekdayIndex);
    weekStart.setHours(0, 0, 0, 0);
    var weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    var weekStartIso = weekStart.toISOString().slice(0, 10);
    var weekEndIso = weekEnd.toISOString().slice(0, 10);
    var classEntries = entries
      .filter(function (entry) { return !activeClasses.length || activeClasses.includes(entry.classLabel); })
      .filter(function (entry) { return !entry.isoDate || (entry.isoDate >= weekStartIso && entry.isoDate <= weekEndIso); })
      .sort(function (left, right) { return (left.isoDate || '').localeCompare(right.isoDate || ''); });
    if (!classEntries.length) {
      classEntries = entries
        .filter(function (entry) { return !activeClasses.length || activeClasses.includes(entry.classLabel); })
        .sort(function (left, right) { return (left.isoDate || '').localeCompare(right.isoDate || ''); })
        .slice(0, 8);
    }
    var visibleClassEntries = _getVisiblePanelItems(classEntries, 'classwork');

    if (showClasswork) {
      _setExpandableMeta(_elements.classworkPreviewList, classEntries.length, visibleClassEntries.length);
      _elements.classworkPreviewList.innerHTML = classEntries.length
        ? (_state.classworkView === 'calendar'
            ? renderClassworkCalendar(visibleClassEntries)
            : renderClassworkList(visibleClassEntries))
        : classwork.previewRows.length
          ? classwork.previewRows.map(function (row) {
              return '<article class="priority-item"><p class="priority-copy">' + row + '</p></article>';
            }).join('')
          : '<div class="empty-state">Noch keine Klassenarbeiten für diese Auswahl erkannt.</div>';
    }
  }

  return {
    init: init,
    renderPlanDigest: renderPlanDigest,
    renderClassworkList: renderClassworkList,
    renderClassworkCalendar: renderClassworkCalendar,
    renderOrgaplanItem: renderOrgaplanItem,
    renderOrgaplanTodayCard: renderOrgaplanTodayCard,
    renderOrgaplanWeekSection: renderOrgaplanWeekSection,
    getActiveClassworkClass: function (classes, defaultClass) {
      return getSelectedClasses(classes, defaultClass)[0] || '';
    },
    truncateText: truncateText,
  };
})();

window.LehrerClasswork = LehrerClasswork;
