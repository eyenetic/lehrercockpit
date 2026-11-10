/**
 * LehrerTerms — Nutzungsbedingungen und Datenschutz.
 *
 * Eine Quelle für den Text: login.html (Häkchen bei der Einrichtung) und
 * index.html (einmalige Abfrage für bestehende Konten). Wird der Text inhaltlich
 * geändert, VERSION hier und in backend/terms.py gleich hochsetzen – dann wird
 * jede Lehrkraft beim nächsten Öffnen erneut gefragt.
 */
(function () {
  'use strict';

  var VERSION = '2026-11-10';

  var CHECKBOX = 'Ich habe die Nutzungsbedingungen und Datenschutzhinweise gelesen. Ich trage keine Namen '
    + 'oder anderen personenbezogenen Daten von Schülerinnen und Schülern ein und nutze das Lehrercockpit '
    + 'auf eigene Verantwortung.';

  var HTML = ''
    + '<h3>1. Was das Lehrercockpit ist</h3>'
    + '<p>Das Lehrercockpit ist ein privat betriebenes, kostenloses Hilfsmittel. Es ist kein offizielles Angebot '
    + 'der Schule oder der Senatsverwaltung. Du nutzt es freiwillig und auf eigene Verantwortung.</p>'
    + '<h3>2. Keine Daten von Schülerinnen und Schülern</h3>'
    + '<p>Trage keine Namen oder anderen Angaben ein, mit denen sich Schülerinnen und Schüler erkennen lassen. '
    + 'Das gilt in Klassenlisten, Sitzplänen, Einsammlungen und Notizen. Verwende stattdessen Nummern oder Kürzel. '
    + 'Besonders schützenswerte Angaben gehören nie ins Cockpit, auch nicht mit Kürzel: Noten, Gesundheit, '
    + 'Förderbedarf, Fehlzeiten, Verhalten.</p>'
    + '<div class="terms-tip"><p class="terms-tip-title">So geht es ohne Namen</p>'
    + '<ul>'
    + '<li><strong>Nummer aus der Klassenliste</strong>, z. B. „9a-07“ – empfohlen. Die Zuordnung steht ohnehin in WebUntis oder im Klassenbuch.</li>'
    + '<li><strong>Neutrale Codes</strong>, die du selbst vergibst, z. B. „Komet“ oder „K3“. Die Zuordnungsliste bleibt auf Papier.</li>'
    + '<li>Nicht geeignet: echte Spitznamen („Mo“) und Initialen („M. K.“) – in einer Klasse erkennt man sie fast immer wieder.</li>'
    + '</ul>'
    + '<p>Auch Nummern bleiben personenbezogen, solange es eine Zuordnungsliste gibt. Sie senken das Risiko aber '
    + 'deutlich, vor allem wenn diese Liste nicht im Cockpit liegt.</p></div>'
    + '<h3>3. Wenn du trotzdem personenbezogene Daten einträgst</h3>'
    + '<p>… bist du allein dafür verantwortlich. Nach den Berliner Vorgaben brauchst du für Schülerdaten auf '
    + 'privaten Geräten eine Genehmigung der Schulleitung. Solche Daten löschst du, sobald du sie nicht mehr '
    + 'brauchst, spätestens zum Ende des Schuljahres.</p>'
    + '<h3>4. Deine Zugänge</h3>'
    + '<p>Halte deinen Zugangscode geheim und sperre deine Geräte. Gib Kalender-Abo-Links nicht weiter. Wenn du '
    + 'vermutest, dass jemand deinen Code kennt, ändere ihn sofort.</p>'
    + '<h3>5. Keine Gewähr für Inhalte</h3>'
    + '<p>Das Cockpit zeigt Daten aus anderen Quellen an, zum Beispiel aus Orgaplan, WebUntis, itslearning und dem '
    + 'Klassenarbeitsplan. Diese Daten können unvollständig, verspätet oder fehlerhaft sein. Verbindlich sind immer '
    + 'die Originalquellen.</p>'
    + '<h3>6. Haftung</h3>'
    + '<p>Der Betreiber haftet für Vorsatz und grobe Fahrlässigkeit sowie bei Verletzung von Leben, Körper oder '
    + 'Gesundheit. Im Übrigen ist die Haftung ausgeschlossen, soweit das Gesetz es erlaubt.</p>'
    + '<h3>7. Deine Zustimmung wird gespeichert</h3>'
    + '<p>Gespeichert werden Datum, Uhrzeit und Version dieser Bedingungen. Ändern sich die Bedingungen, wirst du '
    + 'erneut gefragt.</p>';

  function api() { return window.BACKEND_API_URL || ''; }

  /**
   * Blocking dialog for accounts that have not agreed to this version yet.
   * Resolves once the agreement is stored; "Abmelden" leaves for the login page.
   */
  function gate() {
    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.className = 'modal-overlay terms-gate';
      overlay.innerHTML = ''
        + '<div class="modal terms-panel" role="dialog" aria-modal="true" aria-labelledby="terms-gate-title">'
        +   '<div class="modal-header"><h2 class="modal-title" id="terms-gate-title">Nutzungsbedingungen und Datenschutz</h2></div>'
        +   '<p class="terms-lead">Bevor es weitergeht: Bitte lies die Bedingungen einmal und stimme ihnen zu.</p>'
        +   '<div class="terms-body">' + HTML + '</div>'
        +   '<label class="terms-check"><input type="checkbox" id="terms-gate-check" /> <span>' + CHECKBOX + '</span></label>'
        +   '<p class="terms-error" id="terms-gate-error" role="alert" hidden></p>'
        +   '<div class="modal-actions">'
        +     '<button class="btn btn-secondary" type="button" data-terms="logout">Abmelden</button>'
        +     '<button class="btn btn-primary" type="button" data-terms="accept" disabled>Zustimmen und weiter</button>'
        +   '</div>'
        + '</div>';
      document.body.appendChild(overlay);
      var check = overlay.querySelector('#terms-gate-check');
      var accept = overlay.querySelector('[data-terms="accept"]');
      var errorEl = overlay.querySelector('#terms-gate-error');
      check.addEventListener('change', function () { accept.disabled = !check.checked; });

      overlay.querySelector('[data-terms="logout"]').addEventListener('click', function () {
        fetch(api() + '/api/v2/auth/logout', { method: 'POST', credentials: 'include' })
          .catch(function () {})
          .then(function () { window.location.href = './login.html'; });
      });

      accept.addEventListener('click', function () {
        accept.disabled = true;
        errorEl.hidden = true;
        fetch(api() + '/api/v2/auth/me/terms', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ accept: true, version: VERSION }),
        }).then(function (resp) {
          return resp.json().catch(function () { return {}; }).then(function (data) {
            if (!resp.ok || !data.ok) throw new Error(data.error || 'Das hat nicht geklappt.');
            overlay.remove();
            resolve(data.terms);
          });
        }).catch(function (err) {
          errorEl.textContent = err && err.message && err.message !== 'Failed to fetch'
            ? err.message : 'Keine Verbindung zum Server. Bitte gleich noch einmal versuchen.';
          errorEl.hidden = false;
          accept.disabled = !check.checked;
        });
      });
    });
  }

  window.LehrerTerms = { VERSION: VERSION, HTML: HTML, CHECKBOX: CHECKBOX, gate: gate };
})();
