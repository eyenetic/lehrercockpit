// Video 1: "Was ist das Lehrercockpit?" – Problem → Lösung → ein Schultag → alles an einem Ort.
// Music: kornevmusic – Upbeat Happy Corporate (Pixabay), 120 BPM: a beat every 15 frames, first beat at
// frame 15, bars start at 15 + 60·k. The full band enters at 16.5 s (frame 495) and drops at 48.5 s (1455).
import React from 'react';
import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import {
  ACCENT, AppIcon, Background, BrowserFrame, Caption, Center, FRAME_X, FRAME_Y, INK, MUTED, Phone, PhoneShot, Rise,
  Screen, VH, VW, BAR, clamp, ease, easeOut, fontFamily, phoneSize, track,
} from './common';

export const MUSIC_FILE = 'music/kornevmusic-upbeat-happy-corporate-487426.mp3';
const DROP = 495;

// ── Icons (simple line icons) ───────────────────────────────────────────────
const ICONS = {
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  swap: <><path d="M17 3l4 4-4 4" /><path d="M3 11V9a2 2 0 0 1 2-2h16" /><path d="M7 21l-4-4 4-4" /><path d="M21 13v2a2 2 0 0 1-2 2H3" /></>,
  file: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6M8 13h8M8 17h6" /></>,
  pencil: <><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M13 7l4 4" /></>,
  flag: <><path d="M5 21V4M5 4h12l-2.5 4L17 12H5" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></>,
  book: <><path d="M4 19V5a2 2 0 0 1 2-2h14v14H6a2 2 0 0 0-2 2 2 2 0 0 0 2 2h14" /></>,
  check: <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M8 12l3 3 5-6" /></>,
  calc: <><rect x="5" y="2" width="14" height="20" rx="2" /><path d="M8 6h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 19h8" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5" /></>,
  cloud: <><path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.1 9.2 4.5 4.5 0 0 0 7 18z" /></>,
  phone: <><rect x="7" y="2" width="10" height="20" rx="2.5" /><path d="M11 18h2" /></>,
  building: <><path d="M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6" /></>,
};

const Icon = ({ name, size = 30, color = '#fff', width = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width}
    strokeLinecap="round" strokeLinejoin="round">{ICONS[name]}</svg>
);

// ── Part A: the problem – everything lives somewhere else ───────────────────
const CARDS = [
  { at: 75, name: 'WebUntis', sub: 'Stundenplan', icon: 'calendar', color: '#f97316', x: 230, y: 150, r: -4 },
  { at: 135, name: 'itslearning', sub: 'Aufgaben & Abgaben', icon: 'book', color: '#7c3aed', x: 1310, y: 135, r: 3 },
  { at: 195, name: 'Dienstmail', sub: 'Mails', icon: 'mail', color: '#0d9488', x: 190, y: 770, r: 3 },
  { at: 255, name: 'Orgaplan', sub: 'PDF auf der Schulwebseite', icon: 'file', color: '#dc2626', x: 1330, y: 790, r: -3 },
  { at: 315, name: 'Klassenarbeitsplan', sub: 'Excel-Liste', icon: 'pencil', color: '#db2777', x: 770, y: 95, r: 2 },
  { at: 375, name: 'Nextcloud', sub: 'Dateien', icon: 'cloud', color: '#2563eb', x: 780, y: 850, r: -2 },
  { at: 435, name: 'Schulportal', sub: 'Anmeldung', icon: 'building', color: '#475569', x: 40, y: 460, r: -3, w: 320 },
  { at: 450, name: 'Schulwebseite', sub: 'Schultermine', icon: 'flag', color: '#16a34a', x: 1560, y: 470, r: 4, w: 320 },
];
const CARD_W = 380;
const CARD_H = 112;

const LINES = [
  { at: 15, text: 'Kennst du das?' },
  { at: 75, text: <>Der Stundenplan steht in <b>WebUntis</b>.</> },
  { at: 135, text: <>Aufgaben in <b>itslearning</b>.</> },
  { at: 195, text: <>Mails in der <b>Dienstmail</b>.</> },
  { at: 255, text: <>Termine im <b>Orgaplan-PDF</b>.</> },
  { at: 315, text: <>Klassenarbeiten in einer <b>Excel-Liste</b>.</> },
  { at: 375, text: <>Dateien in der <b>Nextcloud</b>.</> },
  { at: 435, text: <>Alles an <span style={{ color: '#dc2626' }}>verschiedenen</span> Orten.</>, big: true },
];

const Problem = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fly = interpolate(f, [462, DROP], [0, 1], { ...clamp, easing: (t) => t * t * t });
  return (
    <AbsoluteFill>
      {CARDS.map((c, i) => {
        if (f < c.at) return null;
        const pop = spring({ frame: f - c.at, fps, config: { damping: 200, stiffness: 140 } });
        const w = c.w || CARD_W;
        const jit = 0;
        const cx = c.x + w / 2;
        const cy = c.y + CARD_H / 2;
        const dx = (960 - cx) * fly;
        const dy = (560 - cy) * fly;
        return (
          <div key={c.name} style={{
            position: 'absolute', left: c.x, top: c.y, width: w, height: CARD_H, borderRadius: 22, background: '#fff',
            display: 'flex', alignItems: 'center', gap: 18, padding: '0 22px', boxSizing: 'border-box',
            boxShadow: '0 18px 44px rgba(17,24,39,0.13), 0 0 0 1px rgba(17,24,39,0.05)',
            opacity: Math.min(1, pop * 1.4) * (1 - fly),
            transform: `translate(${dx + jit}px, ${dy - jit * 0.6}px) rotate(${c.r * (1 - fly) + jit * 0.4}deg) scale(${(0.7 + 0.3 * pop) * (1 - 0.75 * fly)})`,
          }}>
            <div style={{
              width: 62, height: 62, borderRadius: 16, background: c.color, flexShrink: 0, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}><Icon name={c.icon} /></div>
            <div style={{ textAlign: 'left', minWidth: 0 }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: INK, whiteSpace: 'nowrap' }}>{c.name}</div>
              <div style={{ fontSize: 21, color: MUTED, marginTop: 3, whiteSpace: 'nowrap' }}>{c.sub}</div>
            </div>
          </div>
        );
      })}
      {LINES.map((l, i) => {
        const end = i < LINES.length - 1 ? LINES[i + 1].at : DROP - 18;
        if (f < l.at || f > end + 1) return null;
        const a = interpolate(f - l.at, [0, 12], [0, 1], { ...clamp, easing: easeOut });
        const b = interpolate(f, [end - 8, end], [1, 0], clamp);
        return (
          <Center key={i}>
            <div style={{
              opacity: a * b, transform: `translateY(${(1 - a) * 30 - (1 - b) * 24}px)`,
              fontSize: l.big ? 84 : 66, fontWeight: l.big ? 700 : 500, color: INK, letterSpacing: l.big ? -2.4 : -1.4,
              maxWidth: 1100,
            }}>{l.text}</div>
          </Center>
        );
      })}
    </AbsoluteFill>
  );
};

// ── Part B: the cockpit – one window that stays, content changes inside ─────
// Local frames (the sequence starts 15 frames before the drop).
const L_DROP = 15;
const L_DOCK = 135; // window moves from the centre to its place on the left
const SEG = 120; // one tour stop = two bars
const segStart = (i) => L_DOCK + i * SEG;
const TOUR_END = segStart(7); // 975 → global 1455, where the music drops

// Layers inside the window: each fades in over the previous one (no dip to the background)
const LAYERS = [
  { from: 0, src: 'cockpit-01-heute-full.png', cssH: 1437, keys: [
    { f: 0, x: 720, y: 450, z: 1.0 }, { f: 150, x: 720, y: 450, z: 1.0 },
    { f: 172, x: 838, y: 232, z: 1.25 }, { f: 255, x: 838, y: 232, z: 1.25 },
    { f: 277, x: 610, y: 645, z: 1.4 },
  ] },
  { from: 322, src: 'cockpit-02-woche.png', keys: [{ f: 322, x: 615, y: 695, z: 1.52 }] },
  { from: segStart(3), src: 'cockpit-03-posteingang.png', keys: [
    { f: segStart(3), x: 720, y: 300, z: 1.0 }, { f: segStart(3) + 30, x: 720, y: 300, z: 1.0 },
    { f: segStart(3) + 52, x: 700, y: 281, z: 1.6 },
  ] },
  { from: segStart(4), src: 'cockpit-01-heute-full.png', cssH: 1437, keys: [{ f: segStart(4), x: 1160, y: 765, z: 1.42 }] },
  { from: segStart(5), src: 'cockpit-04-termine.png', keys: [{ f: segStart(5), x: 760, y: 425, z: 1.0 }] },
  { from: segStart(6), src: 'cockpit-01-heute-full.png', cssH: 1437, keys: [{ f: segStart(6), x: 1166, y: 523, z: 1.5 }] },
  { from: segStart(6) + 60, src: 'page-noten.png', keys: [{ f: segStart(6) + 60, x: 838, y: 300, z: 1.22 }] },
];
const XFADE = 8;

const CAPTIONS = [
  { chip: '07:40 · Vor dem Unterricht', title: 'Sofort wissen, was ansteht', sub: 'Deine nächste Stunde mit Raum – und was danach kommt.' },
  { chip: '07:45 · Kurzer Blick', title: 'Dein Stundenplan, immer aktuell', sub: 'Direkt aus WebUntis – mit Vertretungen und Entfällen. Als Tag oder Woche.' },
  { chip: '07:55 · Auf dem Weg', title: 'Auch auf dem Handy', sub: 'Wie eine App – direkt vom Home-Bildschirm.' },
  { chip: '09:35 · In der Pause', title: 'Neue Dienstmails auf einen Blick', sub: 'Ohne dich extra anzumelden.' },
  { chip: '11:30 · Zwischendurch', title: 'Was an der Schule los ist', sub: 'Orgaplan-Termine und die Klassenarbeiten deiner Klassen – automatisch.' },
  { chip: '14:00 · Planen', title: 'Alle Termine in einem Kalender', sub: 'Orgaplan, Klassenarbeiten, Schultermine und itslearning-Abgaben.' },
  { chip: '16:00 · Am Schreibtisch', title: 'Aufgaben und Noten', sub: 'To-dos festhalten, Zeugnisnoten in Sekunden berechnen.' },
];

const Tour = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  // window: grows out of the cards on the drop, waits in the centre, then docks left; shrinks away at the end
  const grow = spring({ frame: f - 4, fps, config: { damping: 200, stiffness: 140 } });
  const dock = interpolate(f, [L_DOCK, L_DOCK + 28], [0, 1], { ...clamp, easing: ease });
  const leave = interpolate(f, [TOUR_END - 18, TOUR_END + 6], [0, 1], { ...clamp, easing: ease });
  const centerX = (1920 - VW) / 2;
  const centerY = 600 - (VH + BAR) / 2;
  const scale = (0.2 + 0.58 * grow) * (1 - dock) + 1 * dock - 0.25 * leave;
  const x = centerX + (FRAME_X - centerX) * dock;
  const y = centerY + (FRAME_Y - centerY) * dock;

  // phone overlaps the window during stop 3
  const p0 = segStart(2);
  const phoneIn = interpolate(f, [p0 - 4, p0 + 18], [0, 1], { ...clamp, easing: easeOut });
  const phoneOut = interpolate(f, [segStart(3) - 6, segStart(3) + 14], [0, 1], { ...clamp, easing: ease });
  const phoneShow = phoneIn * (1 - phoneOut);
  const ps = phoneSize();
  const dim = 0.35 * phoneShow;

  const head = interpolate(f, [L_DROP + 6, L_DROP + 22], [0, 1], { ...clamp, easing: easeOut })
    * interpolate(f, [L_DOCK - 10, L_DOCK + 6], [1, 0], clamp);

  return (
    <AbsoluteFill style={{ opacity: 1 - leave }}>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 70, textAlign: 'center', opacity: head,
        transform: `translateY(${(1 - head) * -20}px)` }}>
        <div style={{ fontSize: 70, fontWeight: 700, color: INK, letterSpacing: -2 }}>Das Lehrercockpit</div>
        <div style={{ fontSize: 36, color: MUTED, marginTop: 8 }}>Alles für deinen Schultag. An einem Ort.</div>
      </div>
      <BrowserFrame x={x} y={y} scale={scale}>
        {LAYERS.map((l, i) => {
          const next = LAYERS[i + 1];
          if (f < l.from || (next && f > next.from + XFADE)) return null;
          const o = i === 0 ? 1 : interpolate(f, [l.from, l.from + XFADE], [0, 1], clamp);
          return <Screen key={i} src={l.src} cssH={l.cssH || 900} keys={l.keys} frame={f} opacity={o} />;
        })}
        <div style={{ position: 'absolute', inset: 0, background: '#0b1220', opacity: dim }} />
      </BrowserFrame>
      {phoneShow > 0.001 ? (
        <Phone x={1020} y={(1080 - ps.h) / 2 + (1 - phoneShow) * 700} style={{ opacity: Math.min(1, phoneShow * 2) }}>
          {(w, h) => (
            <>
              <PhoneShot src="phone-01-heute.png" w={w} h={h} />
              <PhoneShot src="phone-02-scrolled.png" w={w} h={h} opacity={interpolate(f, [p0 + 60, p0 + 74], [0, 1], clamp)} />
            </>
          )}
        </Phone>
      ) : null}
      {CAPTIONS.map((c, i) => (
        <Caption key={i} from={segStart(i)} to={segStart(i + 1) - (i === 6 ? 10 : 0)} chip={c.chip} title={c.title} sub={c.sub} />
      ))}
    </AbsoluteFill>
  );
};

// ── Part C: everything in one place ──────────────────────────────────────────
const FEATURES = [
  ['calendar', 'Stundenplan'], ['swap', 'Vertretungen'], ['file', 'Orgaplan'], ['pencil', 'Klassenarbeiten'],
  ['flag', 'Schultermine'], ['mail', 'Dienstmail'], ['book', 'itslearning'], ['check', 'Aufgaben'],
  ['calc', 'Notenrechner'], ['sun', 'Ferien-Countdown'], ['cloud', 'Nextcloud'], ['phone', 'Auf dem Handy'],
];
const RECAP_LEN = 255;

const Recap = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const gather = interpolate(f, [RECAP_LEN - 24, RECAP_LEN], [0, 1], { ...clamp, easing: (t) => t * t });
  const TW = 350;
  const TH = 96;
  const GAP = 26;
  const gx = (1920 - (4 * TW + 3 * GAP)) / 2;
  const gy = 380;
  return (
    <AbsoluteFill>
      <Rise delay={8} style={{ position: 'absolute', top: 150, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ opacity: 1 - gather, fontSize: 92, fontWeight: 700, color: INK, letterSpacing: -2.6 }}>
          Alles an <span style={{ color: ACCENT }}>einem</span> Ort.
        </div>
      </Rise>
      {FEATURES.map(([icon, label], i) => {
        const at = 18 + i * 9;
        const pop = spring({ frame: f - at, fps, config: { damping: 200, stiffness: 140 } });
        const col = i % 4;
        const row = Math.floor(i / 4);
        const x = gx + col * (TW + GAP);
        const y = gy + row * (TH + GAP);
        const dx = (960 - (x + TW / 2)) * gather;
        const dy = (560 - (y + TH / 2)) * gather;
        return (
          <div key={label} style={{
            position: 'absolute', left: x, top: y, width: TW, height: TH, borderRadius: 20, background: '#fff',
            display: 'flex', alignItems: 'center', gap: 18, padding: '0 22px', boxSizing: 'border-box',
            boxShadow: '0 14px 36px rgba(17,24,39,0.1), 0 0 0 1px rgba(17,24,39,0.05)',
            opacity: Math.min(1, pop * 1.5) * (1 - gather),
            transform: `translate(${dx}px, ${dy}px) scale(${(0.6 + 0.4 * pop) * (1 - 0.7 * gather)})`,
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14, background: 'rgba(26,86,219,0.1)', display: 'flex',
              alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}><Icon name={icon} size={28} color={ACCENT} width={2.1} /></div>
            <div style={{ fontSize: 28, fontWeight: 600, color: INK, whiteSpace: 'nowrap' }}>{label}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const Outro = () => (
  <Center>
    <AppIcon size={160} delay={0} />
    <Rise delay={8} style={{ fontSize: 100, fontWeight: 700, color: INK, letterSpacing: -3, marginTop: 40 }}>
      Lehrercockpit
    </Rise>
    <Rise delay={16} style={{ fontSize: 44, color: MUTED, marginTop: 10 }}>
      Dein Schultag auf einen Blick.
    </Rise>
    <Rise delay={30} style={{
      marginTop: 46, fontSize: 30, fontWeight: 600, color: ACCENT, background: 'rgba(26,86,219,0.09)',
      padding: '14px 28px', borderRadius: 999,
    }}>
      In wenigen Minuten eingerichtet – mit deinem Einladungslink.
    </Rise>
  </Center>
);

const TOUR_FROM = DROP - L_DROP; // 480
const RECAP_FROM = TOUR_FROM + TOUR_END - 10; // 1445
const OUTRO_FROM = RECAP_FROM + RECAP_LEN - 5; // 1695, a bar line
const OUTRO_LEN = 150;
export const LC_FRAMES = OUTRO_FROM + OUTRO_LEN;

export const Lehrercockpit = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ fontFamily, color: INK }}>
      <Background />
      <Sequence from={0} durationInFrames={DROP + 2}><Problem /></Sequence>
      <Sequence from={TOUR_FROM} durationInFrames={TOUR_END + 8}><Tour /></Sequence>
      <Sequence from={RECAP_FROM} durationInFrames={RECAP_LEN}><Recap /></Sequence>
      <Sequence from={OUTRO_FROM} durationInFrames={OUTRO_LEN}><Outro /></Sequence>
      <Audio
        src={staticFile(MUSIC_FILE)}
        volume={(f) => interpolate(f, [0, LC_FRAMES - 2 * fps, LC_FRAMES], [0.85, 0.85, 0], clamp)}
      />
    </AbsoluteFill>
  );
};
