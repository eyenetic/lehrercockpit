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
    var month = orgaplan.monthLabel || 'diesem Monat';
    return count + ' relevante Hinweise fuer ' + month + '. Hier stehen nur die naechsten Punkte, nicht der ganze Plan.';
  }

  function summarizeClassworkDigest(classwork) {
    if (classwork.status === 'ok') {
      var classCount = (classwork.classes || []).length;
      var entryCount = (classwork.entries || []).length;
      return entryCount + ' Eintraege fuer ' + classCount + ' Klassen erkannt. Unten arbeitest du nur mit der Klasse, die du gerade brauchst.';
    }
    return truncateText(classwork.detail || 'Der Klassenarbeitsplan ist verlinkt, aber noch nicht automatisch lesbar.', 140);
  }

  // ── Classwork class selection ────────────────────────────────────────────────

  function getSelectedClasses(classes, defaultClass) {
    if (_getSelectedClassworkClasses) {
      return _getSelectedClassworkClasses(classes, defaultClass);
    }
    if (!classes.length) {
      _state.classworkSelectedClasses = [];
      return [];
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
    return _state.classworkSelectedClasses;
  }

  // ── Selector + view switch ───────────────────────────────────────────────────

  function renderClassworkSelector(classes, defaultClass) {
    if (!_elements.classworkClassFilter) return;
    var activeClasses = getSelectedClasses(classes, defaultClass);
    _elements.classworkClassFilter.disabled = !classes.length;
    if (!classes.length) {
      _elements.classworkClassFilter.innerHTML = '<option value="">Keine Klasse erkannt</option>';
      return;
    }
    _elements.classworkClassFilter.size = Math.min(Math.max(classes.length, 3), 8);
    _elements.classworkClassFilter.innerHTML = classes.map(function (classLabel) {
      return '<option value="' + classLabel + '"' + (activeClasses.includes(classLabel) ? ' selected' : '') + '>' + classLabel + '</option>';
    }).join('');
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

  function renderOrgaplanItem(item) {
    var sections = [
      { label: 'Allgemein', value: item.general },
      { label: 'Mittelstufe', value: joinOrgaplanSection(item.middle, item.middleNotes) },
      { label: 'Oberstufe', value: joinOrgaplanSection(item.upper, item.upperNotes) },
    ].filter(function (s) { return s.value; });

    if (!sections.length) {
      return '<article class="priority-item">'
        + '<div class="priority-top">'
        + '<strong>' + item.title + '</strong>'
        + '<span class="meta-tag low">' + item.dateLabel + '</span>'
        + '</div>'
        + '<p class="priority-copy">' + (item.detail || item.text) + '</p>'
        + '</article>';
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
      _bindExternalLink(_elements.orgaplanOpenLink, orgaplan.sourceUrl, 'PDF oeffnen');
      _elements.orgaplanDigestDetail.textContent = summarizeOrgaplanDigest(orgaplan);
    }
    if (showClasswork) {
      _bindExternalLink(_elements.classworkOpenLink, classwork.sourceUrl, 'Plan online im Viewer oeffnen');
      _elements.classworkDigestDetail.textContent = summarizeClassworkDigest(classwork);
    }
    _elements.classworkUploadFeedback.textContent = _state.classworkUploadFeedback;
    _elements.classworkUploadFeedback.className = 'connect-feedback' + (_state.classworkUploadFeedbackKind ? ' ' + _state.classworkUploadFeedbackKind : '');

    if (showClasswork) {
      renderClassworkSelector(classes, classwork.defaultClass || '');
      renderClassworkViewSwitch();
    }

    var orgaplanItems = orgaplan.upcoming.length ? orgaplan.upcoming : orgaplan.highlights;
    if (showOrgaplan) {
      _elements.orgaplanUpcomingList.innerHTML = orgaplanItems.length
        ? orgaplanItems.map(renderOrgaplanItem).join('')
        : '<div class="empty-state">Noch keine Orgaplan-Highlights erkannt.</div>';
    }

    var activeClasses = getSelectedClasses(classes, classwork.defaultClass || '');
    var classEntries = entries
      .filter(function (entry) { return !activeClasses.length || activeClasses.includes(entry.classLabel); })
      .sort(function (left, right) { return (left.isoDate || '').localeCompare(right.isoDate || ''); });
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
          : '<div class="empty-state">Noch keine Klassenarbeiten fuer diese Auswahl erkannt.</div>';
    }
  }

  return {
    init: init,
    renderPlanDigest: renderPlanDigest,
    renderClassworkList: renderClassworkList,
    renderClassworkCalendar: renderClassworkCalendar,
    renderOrgaplanItem: renderOrgaplanItem,
    getActiveClassworkClass: function (classes, defaultClass) {
      return getSelectedClasses(classes, defaultClass)[0] || '';
    },
    truncateText: truncateText,
  };
})();

window.LehrerClasswork = LehrerClasswork;
