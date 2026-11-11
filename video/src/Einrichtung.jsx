// Video 2: "So richtest du es ein" – Einladungslink → WebUntis-Link → einfügen → fertig, plus iPhone-Tipp.
// Same music as video 1, started 8.5 s in, so bars fall on video frames 0, 60, 120 … and the band enters at 240.
import React from 'react';
import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import {
  ACCENT, AppIcon, Background, BrowserFrame, Caption, Center, FRAME_X, FRAME_Y, INK, MUTED, Phone, PhoneShot, Rise,
  Screen, VH, VW, BAR, clamp, ease, easeOut, fontFamily, phoneSize,
} from './common';
import { MUSIC_FILE } from './Lehrercockpit';

const MUSIC_OFFSET = 255; // frames into the track
const DROP = 240;

const STEPS = ['Einladungslink öffnen', 'Link aus WebUntis kopieren', 'Einfügen – fertig'];

const Intro = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const out = interpolate(f, [DROP - 14, DROP], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Center style={{ justifyContent: 'flex-start', paddingTop: 170 }}>
        <AppIcon size={120} delay={2} />
        <Rise delay={10} style={{ fontSize: 84, fontWeight: 700, color: INK, letterSpacing: -2.4, marginTop: 36 }}>
          So richtest du es ein
        </Rise>
        <Rise delay={20} style={{ fontSize: 40, color: MUTED, marginTop: 10 }}>
          Drei Schritte – in wenigen Minuten.
        </Rise>
        <div style={{ display: 'flex', gap: 26, marginTop: 70 }}>
          {STEPS.map((s, i) => {
            const pop = spring({ frame: f - (60 + i * 30), fps, config: { damping: 200, stiffness: 140 } });
            return (
              <div key={s} style={{
                display: 'flex', alignItems: 'center', gap: 16, background: '#fff', borderRadius: 999,
                padding: '14px 28px 14px 14px', boxShadow: '0 14px 36px rgba(17,24,39,0.1), 0 0 0 1px rgba(17,24,39,0.05)',
                opacity: Math.min(1, pop * 1.5), transform: `scale(${0.7 + 0.3 * pop})`,
              }}>
                <div style={{
                  width: 50, height: 50, borderRadius: 25, background: ACCENT, color: '#fff', fontSize: 27, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>{i + 1}</div>
                <div style={{ fontSize: 30, fontWeight: 600, color: INK }}>{s}</div>
              </div>
            );
          })}
        </div>
      </Center>
    </AbsoluteFill>
  );
};

// Window stays; content changes inside. Local frames = video frames minus FROM.
const FROM = DROP - 10;
const s = (videoFrame) => videoFrame - FROM;
const S1 = s(240);
const S2 = s(480);
const S3 = s(840);
const S4 = s(1020);
const END = s(1200);
const XFADE = 8;

const LAYERS = [
  { from: 0, src: 'setup-01-invite.png', keys: [{ f: 0, x: 720, y: 390, z: 1.34 }] },
  { from: s(330), src: 'setup-02-invite-filled.png', keys: [{ f: 0, x: 720, y: 390, z: 1.34 }] },
  { from: S2, src: 'setup-03-after-invite.png', cssH: 1305, keys: [
    { f: S2, x: 720, y: 200, z: 1.28 }, { f: S2 + 70, x: 720, y: 200, z: 1.28 },
    { f: S2 + 92, x: 700, y: 482, z: 1.32 }, { f: S2 + 200, x: 700, y: 482, z: 1.32 },
    { f: S2 + 222, x: 720, y: 792, z: 1.32 },
  ] },
  { from: S3, src: 'setup-04-link-pasted.png', cssH: 1305, keys: [
    { f: S3, x: 720, y: 1020, z: 1.32 }, { f: S3 + 30, x: 720, y: 1020, z: 1.32 }, { f: S3 + 52, x: 720, y: 1082, z: 1.6 },
  ] },
  { from: S4, src: 'setup-05-after-link.png', keys: [{ f: S4, x: 720, y: 343, z: 1.4 }] },
  { from: S4 + 90, src: 'cockpit-01-heute.png', keys: [{ f: S4 + 90, x: 720, y: 450, z: 1.0 }] },
];

const CAPTIONS = [
  { from: S1, to: S2, step: '1', title: 'Einladungslink öffnen', sub: 'Namen eintragen, eigenen Zugangscode festlegen, Häkchen setzen.' },
  { from: S2, to: S3, step: '2', title: 'Link aus WebUntis kopieren', sub: 'In WebUntis: ⋮ → „iCal-Abo verwalten“ → „Link kopieren“. Das Cockpit zeigt dir jeden Schritt mit Bild.' },
  { from: S3, to: S4, step: '3', title: 'Einfügen – fertig!', sub: 'Das Cockpit prüft den Link und lädt deinen Stundenplan.' },
  { from: S4, to: S4 + 90, title: 'Geschafft!', sub: 'itslearning, Dienstmail und Nextcloud verbindest du später – direkt über die Kacheln.' },
  { from: S4 + 90, to: END - 8, title: 'Dein Cockpit ist startklar', sub: 'Ab jetzt siehst du jeden Morgen, was ansteht.' },
];

const Setup = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const grow = spring({ frame: f - 6, fps, config: { damping: 200, stiffness: 140 } });
  const leave = interpolate(f, [END - 16, END + 6], [0, 1], { ...clamp, easing: ease });
  const scale = 0.4 + 0.6 * grow - 0.25 * leave;
  return (
    <AbsoluteFill style={{ opacity: 1 - leave }}>
      <BrowserFrame x={FRAME_X} y={FRAME_Y} scale={scale} opacity={Math.min(1, grow * 2)}>
        {LAYERS.map((l, i) => {
          const next = LAYERS[i + 1];
          if (f < l.from || (next && f > next.from + XFADE)) return null;
          const o = i === 0 ? 1 : interpolate(f, [l.from, l.from + XFADE], [0, 1], clamp);
          return <Screen key={i} src={l.src} cssH={l.cssH || 900} keys={l.keys} frame={f} opacity={o} />;
        })}
      </BrowserFrame>
      {CAPTIONS.map((c, i) => (
        <Caption key={i} from={c.from} to={c.to} eyebrow={i === 0 ? 'Einrichtung' : undefined} step={c.step} title={c.title} sub={c.sub} />
      ))}
    </AbsoluteFill>
  );
};

const TIP_LEN = 250;
const Tip = () => {
  const f = useCurrentFrame();
  const ps = phoneSize();
  const ph = interpolate(f, [0, 22], [0, 1], { ...clamp, easing: easeOut });
  const a = interpolate(f, [30, 48], [0, 1], { ...clamp, easing: easeOut });
  const b = interpolate(f, [75, 93], [0, 1], { ...clamp, easing: easeOut });
  const out = interpolate(f, [TIP_LEN - 14, TIP_LEN], [1, 0], clamp);
  const card = {
    position: 'absolute', left: 640, width: 640, borderRadius: 26, overflow: 'hidden',
    boxShadow: '0 24px 60px rgba(17,24,39,0.18), 0 0 0 1px rgba(17,24,39,0.06)', background: '#fff',
  };
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Phone x={150} y={(1080 - ps.h) / 2 + (1 - ph) * 500}>
        {(w, h) => <PhoneShot src="phone-01-heute.png" w={w} h={h} />}
      </Phone>
      <div style={{ ...card, top: 330, opacity: a, transform: `translateY(${(1 - a) * 30}px)` }}>
        <Img src={staticFile('img/iphone-share-crop.png')} style={{ width: 640, display: 'block' }} />
      </div>
      <div style={{ ...card, top: 560, opacity: b, transform: `translateY(${(1 - b) * 30}px)` }}>
        <Img src={staticFile('img/iphone-homescreen.webp')} style={{ width: 640, display: 'block' }} />
      </div>
      <Caption from={0} to={TIP_LEN + 5} eyebrow="Tipp" title="Wie eine App aufs iPhone"
        sub="In Safari: Teilen → „Zum Home-Bildschirm“. Danach startet das Cockpit mit einem Tipp." />
    </AbsoluteFill>
  );
};

const Outro = () => (
  <Center>
    <AppIcon size={150} delay={0} />
    <Rise delay={8} style={{ fontSize: 80, fontWeight: 700, color: INK, letterSpacing: -2.2, marginTop: 40 }}>
      Viel Freude mit deinem Lehrercockpit!
    </Rise>
    <Rise delay={20} style={{ fontSize: 38, color: MUTED, marginTop: 14 }}>
      Fragen? Schreib uns im Cockpit unter „Rückmeldung“.
    </Rise>
  </Center>
);

const TIP_FROM = FROM + END - 6; // ≈ 1194
const OUTRO_FROM = TIP_FROM + TIP_LEN - 4; // ≈ 1440, a bar line
const OUTRO_LEN = 150;
export const EINRICHTUNG_FRAMES = OUTRO_FROM + OUTRO_LEN;

export const Einrichtung = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ fontFamily, color: INK }}>
      <Background />
      <Sequence from={0} durationInFrames={DROP + 2}><Intro /></Sequence>
      <Sequence from={FROM} durationInFrames={END + 8}><Setup /></Sequence>
      <Sequence from={TIP_FROM} durationInFrames={TIP_LEN}><Tip /></Sequence>
      <Sequence from={OUTRO_FROM} durationInFrames={OUTRO_LEN}><Outro /></Sequence>
      <Audio
        src={staticFile(MUSIC_FILE)}
        startFrom={MUSIC_OFFSET}
        volume={(f) => interpolate(f, [0, 20, EINRICHTUNG_FRAMES - 2 * fps, EINRICHTUNG_FRAMES], [0, 0.85, 0.85, 0], clamp)}
      />
    </AbsoluteFill>
  );
};
