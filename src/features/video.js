/**
 * Erklärvideos: ein Klick auf ein Element mit data-video="lehrercockpit|einrichtung" öffnet das Video
 * groß in einem Fenster über der Seite (mit Ton, schließbar mit ×, Esc oder Klick daneben).
 * Die Videos liegen auf dem eigenen Server – kein YouTube, kein Tracking. Nichts startet von selbst.
 *
 *   LehrerVideo.teaser('lehrercockpit')  → Karte mit Vorschaubild („Erst ansehen“)
 *   LehrerVideo.button('einrichtung')    → kleiner Knopf „▶ Video ansehen (50 s)“
 */
(function () {
  var BASE = './src/assets/video/';
  var VIDEOS = {
    lehrercockpit: { title: 'Was ist das Lehrercockpit?', length: '1 Min.', file: 'lehrercockpit' },
    einrichtung: { title: 'So richtest du es ein', length: '50 s', file: 'einrichtung' },
  };

  var CSS = '' +
    '.lcv-teaser{display:flex;align-items:center;gap:14px;width:100%;padding:10px;margin:0 0 18px;border:1px solid var(--line-strong,rgba(0,0,0,.12));' +
    'border-radius:var(--radius-lg,14px);background:var(--panel,#fff);color:var(--ink,#111);font:inherit;text-align:left;cursor:pointer;' +
    'transition:border-color .15s,box-shadow .15s}' +
    '.lcv-teaser:hover,.lcv-teaser:focus-visible{border-color:var(--accent,#1a56db);box-shadow:0 0 0 3px var(--accent-soft,rgba(26,86,219,.1));outline:none}' +
    '.lcv-thumb{position:relative;flex:0 0 112px;height:63px;border-radius:8px;overflow:hidden;background:var(--panel-soft,#f3f3f1)}' +
    '.lcv-thumb img{width:100%;height:100%;object-fit:cover;display:block}' +
    '.lcv-thumb::after{content:"";position:absolute;inset:0;background:rgba(17,24,39,.18)}' +
    '.lcv-play{position:absolute;left:50%;top:50%;z-index:1;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;' +
    'background:rgba(255,255,255,.95);box-shadow:0 2px 8px rgba(0,0,0,.25)}' +
    '.lcv-play::before{content:"";position:absolute;left:12px;top:9px;border-style:solid;border-width:6px 0 6px 9px;' +
    'border-color:transparent transparent transparent var(--accent,#1a56db)}' +
    '.lcv-text{display:flex;flex-direction:column;gap:2px;min-width:0}' +
    '.lcv-eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent,#1a56db)}' +
    '.lcv-title{font-weight:600;font-size:.95rem}' +
    '.lcv-meta{font-size:.8rem;color:var(--muted,#595959)}' +
    '.lcv-button{display:inline-flex;align-items:center;gap:8px}' +
    '.lcv-button .lcv-dot{position:relative;width:18px;height:18px;border-radius:50%;background:var(--accent,#1a56db);flex:0 0 18px}' +
    '.lcv-button .lcv-dot::before{content:"";position:absolute;left:7px;top:5px;border-style:solid;border-width:4px 0 4px 6px;' +
    'border-color:transparent transparent transparent #fff}' +
    '.lcv-backdrop{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;padding:16px;' +
    'background:rgba(10,12,16,.82);animation:lcv-in .18s ease-out}' +
    '@keyframes lcv-in{from{opacity:0}to{opacity:1}}' +
    '.lcv-box{position:relative;width:min(1100px,100%);max-height:100%}' +
    '.lcv-box video{display:block;width:100%;max-height:calc(100vh - 32px);border-radius:12px;background:#000;box-shadow:0 30px 80px rgba(0,0,0,.5)}' +
    '.lcv-close{position:absolute;right:-6px;top:-46px;width:38px;height:38px;border:0;border-radius:50%;cursor:pointer;' +
    'background:rgba(255,255,255,.14);color:#fff;font-size:24px;line-height:38px;text-align:center}' +
    '.lcv-close:hover,.lcv-close:focus-visible{background:rgba(255,255,255,.28);outline:none}' +
    '@media (max-height:520px){.lcv-close{top:6px;right:6px;z-index:1;background:rgba(0,0,0,.5)}}';

  function injectStyle() {
    if (document.getElementById('lcv-style')) return;
    var style = document.createElement('style');
    style.id = 'lcv-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  var openBackdrop = null;

  function close() {
    if (!openBackdrop) return;
    var backdrop = openBackdrop;
    openBackdrop = null;
    var video = backdrop.querySelector('video');
    if (video) { video.pause(); video.removeAttribute('src'); video.load(); }
    document.removeEventListener('keydown', onKey, true);
    backdrop.remove();
    document.body.style.overflow = backdrop._overflow || '';
    if (backdrop._returnFocus && backdrop._returnFocus.focus) backdrop._returnFocus.focus();
  }

  // Capture phase: Esc closes only the video, not a dialog underneath (e.g. „Verbindungen“).
  function onKey(event) {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    close();
  }

  function open(id) {
    var v = VIDEOS[id];
    if (!v || openBackdrop) return;
    injectStyle();
    var backdrop = document.createElement('div');
    backdrop.className = 'lcv-backdrop';
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-label', v.title);
    backdrop.innerHTML = '<div class="lcv-box">' +
      '<button class="lcv-close" type="button" aria-label="Video schließen">×</button>' +
      '<video controls autoplay playsinline preload="auto" poster="' + BASE + v.file + '.jpg">' +
      '<source src="' + BASE + v.file + '.mp4" type="video/mp4" /></video></div>';
    backdrop._returnFocus = document.activeElement;
    backdrop._overflow = document.body.style.overflow;
    backdrop.addEventListener('click', function (event) {
      if (event.target === backdrop) close();
    });
    backdrop.querySelector('.lcv-close').addEventListener('click', close);
    document.body.appendChild(backdrop);
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey, true);
    openBackdrop = backdrop;
    backdrop.querySelector('.lcv-close').focus();
  }

  function teaser(id, eyebrow) {
    var v = VIDEOS[id];
    injectStyle();
    return '<button class="lcv-teaser" type="button" data-video="' + id + '">' +
      '<span class="lcv-thumb"><img src="' + BASE + v.file + '.jpg" alt="" width="112" height="63" loading="lazy" /><span class="lcv-play"></span></span>' +
      '<span class="lcv-text"><span class="lcv-eyebrow">' + esc(eyebrow || 'Erst ansehen') + '</span>' +
      '<span class="lcv-title">' + esc(v.title) + '</span><span class="lcv-meta">Video · ' + esc(v.length) + ' · mit Ton</span></span></button>';
  }

  function button(id, extraClass) {
    var v = VIDEOS[id];
    injectStyle();
    return '<button class="btn btn-secondary btn-sm lcv-button' + (extraClass ? ' ' + extraClass : '') + '" type="button" data-video="' + id + '">' +
      '<span class="lcv-dot" aria-hidden="true"></span>Video ansehen (' + esc(v.length) + ')</button>';
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest && event.target.closest('[data-video]');
    if (!trigger) return;
    event.preventDefault();
    open(trigger.getAttribute('data-video'));
  });

  // Platzhalter <div data-video-teaser="lehrercockpit"></div> in statischem HTML füllen
  function fillPlaceholders() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-video-teaser]'), function (el) {
      el.outerHTML = teaser(el.getAttribute('data-video-teaser'), el.getAttribute('data-eyebrow'));
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fillPlaceholders);
  else fillPlaceholders();

  window.LehrerVideo = { open: open, close: close, teaser: teaser, button: button };
})();
