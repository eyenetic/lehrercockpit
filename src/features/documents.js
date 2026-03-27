/**
 * src/features/documents.js — Documents section rendering
 *
 * Extracted from src/app.js. Owns:
 *   - renderDocuments()    — extra document list rendering
 *   - isPrimaryPlanDocument() — classifier for plan documents
 *
 * Initialization:
 *   window.LehrerDocuments.init(state, elements, { getData, getVisiblePanelItems, setExpandableMeta })
 *
 * Exports (to window.LehrerDocuments):
 *   renderDocuments, isPrimaryPlanDocument, init
 */
var LehrerDocuments = (function () {
  'use strict';

  var _state = null;
  var _elements = null;
  var _getData = null;
  var _getVisiblePanelItems = null;
  var _setExpandableMeta = null;

  function init(state, elements, callbacks) {
    _state = state;
    _elements = elements;
    _getData = callbacks.getData;
    _getVisiblePanelItems = callbacks.getVisiblePanelItems;
    _setExpandableMeta = callbacks.setExpandableMeta;
  }

  function isPrimaryPlanDocument(entry) {
    var title = String(entry.title || '').toLowerCase();
    var source = String(entry.source || '').toLowerCase();
    return title.includes('orgaplan') || title.includes('klassenarbeitsplan') || source.includes('orgaplan');
  }

  function renderDocuments() {
    if (!_elements || !_elements.documentList) return;
    var data = _getData();
    var query = (_state.documentSearch || '').trim().toLowerCase();
    var changedDocuments = new Set(
      (data.documentMonitor || []).filter(function (item) { return item.changed; }).map(function (item) { return item.id; })
    );
    var extraDocuments = (data.documents || []).filter(function (entry) { return !isPrimaryPlanDocument(entry); });
    var filteredDocuments = extraDocuments.filter(function (entry) {
      var haystack = [entry.title, entry.source, entry.summary].concat(entry.tags || []).join(' ').toLowerCase();
      return haystack.includes(query);
    });
    var visibleDocuments = _getVisiblePanelItems(filteredDocuments, 'documents');
    _setExpandableMeta(_elements.documentList, filteredDocuments.length, visibleDocuments.length);
    // Always show the search input once there are extra documents to search through.
    if (_elements.documentSearchWrap) _elements.documentSearchWrap.hidden = extraDocuments.length === 0;
    // Keep the extra-documents block visible even on zero results so the empty-
    // state message inside it is shown instead of silently hiding the whole area.
    if (_elements.documentsExtraBlock) _elements.documentsExtraBlock.hidden = extraDocuments.length === 0;

    _elements.documentList.innerHTML = filteredDocuments.length
      ? visibleDocuments.map(function (entry) {
          var isChanged = changedDocuments.has(entry.id === 'doc-1' ? 'orgaplan' : entry.id);
          return '<article class="document-item">'
            + '<div class="document-top">'
            + '<div>'
            + '<strong>' + entry.title + '</strong>'
            + '<p class="message-snippet">' + entry.source + ' - Stand ' + entry.updatedAt + '</p>'
            + '</div>'
            + '<span class="meta-tag ' + (isChanged ? 'warning' : 'low') + '">' + (isChanged ? 'neu' : 'bereit') + '</span>'
            + '</div>'
            + '<p class="document-summary">' + entry.summary + '</p>'
            + '<div class="meta-row">'
            + (entry.tags || []).map(function (tag) { return '<span class="meta-tag">' + tag + '</span>'; }).join('')
            + '</div>'
            + '</article>';
        }).join('')
      : '<div class="empty-state">Kein Dokument passt gerade zu deiner Suche.</div>';
  }

  return {
    init: init,
    renderDocuments: renderDocuments,
    isPrimaryPlanDocument: isPrimaryPlanDocument,
  };
})();

window.LehrerDocuments = LehrerDocuments;
