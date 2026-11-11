import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Geist';

export const { fontFamily } = loadFont('normal', { weights: ['400', '500', '600', '700'], subsets: ['latin', 'latin-ext'] });

export const ACCENT = '#1a56db';
export const INK = '#111827';
export const MUTED = '#4b5563';
export const FADE = 12;

// Browser window (left) and text panel (right)
export const VW = 1300;
export const VH = 812;
export const BAR = 40;
export const FRAME_X = 70;
export const FRAME_Y = (1080 - VH - BAR) / 2;
export const PANEL_X = 1430;
export const PANEL_W = 430;

export const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' };
export const ease = Easing.bezier(0.45, 0, 0.2, 1);
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);

// Value that moves between keyframes [[frame, value], ...] with easing
export function track(frame, pts, easing = ease) {
  if (frame <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) {
    const [fa, a] = pts[i];
    const [fb, b] = pts[i + 1];
    if (frame <= fb) return a + (b - a) * easing((frame - fa) / Math.max(1, fb - fa));
  }
  return pts[pts.length - 1][1];
}

// Camera keyframes {f, x, y, z}: page point (CSS px) in the middle, z = zoom over "fit width"
export function camera(keys, frame) {
  if (frame <= keys[0].f) return keys[0];
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (frame <= b.f) {
      const t = ease((frame - a.f) / Math.max(1, b.f - a.f));
      return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t };
    }
  }
  return keys[keys.length - 1];
}

export const Screen = ({ src, cssW = 1440, cssH = 900, keys, frame: frameProp, vw = VW, vh = VH, opacity = 1 }) => {
  const own = useCurrentFrame();
  const frame = frameProp ?? own;
  const c = camera(keys, frame);
  const s = (vw / cssW) * c.z;
  let tx = vw / 2 - c.x * s;
  let ty = vh / 2 - c.y * s;
  tx = Math.min(0, Math.max(vw - cssW * s, tx));
  ty = cssH * s <= vh ? 0 : Math.min(0, Math.max(vh - cssH * s, ty));
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', opacity }}>
      <Img
        src={staticFile('shots/' + src)}
        style={{
          position: 'absolute', left: 0, top: 0, width: cssW, height: cssH, transformOrigin: '0 0',
          transform: `translate(${tx}px, ${ty}px) scale(${s})`,
        }}
      />
    </div>
  );
};

export const Background = () => (
  <AbsoluteFill style={{ background: 'linear-gradient(155deg, #f3f6fd 0%, #eef2fb 45%, #f7f6f3 100%)' }}>
    <div style={{
      position: 'absolute', width: 900, height: 900, borderRadius: '50%', right: -260, top: -320,
      background: 'radial-gradient(circle, rgba(26,86,219,0.13) 0%, rgba(26,86,219,0) 70%)',
    }} />
    <div style={{
      position: 'absolute', width: 800, height: 800, borderRadius: '50%', left: -300, bottom: -380,
      background: 'radial-gradient(circle, rgba(26,86,219,0.08) 0%, rgba(26,86,219,0) 70%)',
    }} />
  </AbsoluteFill>
);

// Fades a whole scene in/out (used only where the next scene covers the screen anyway)
export const Fade = ({ dur, fadeIn = true, fadeOut = true, children }) => {
  const f = useCurrentFrame();
  const a = fadeIn ? interpolate(f, [0, FADE], [0, 1], clamp) : 1;
  const b = fadeOut ? interpolate(f, [dur - FADE, dur], [1, 0], clamp) : 1;
  return <AbsoluteFill style={{ opacity: a * b }}>{children}</AbsoluteFill>;
};

// Browser window; position/scale are driven by the caller (scale around its centre)
export const BrowserFrame = ({ x = FRAME_X, y = FRAME_Y, scale = 1, opacity = 1, children }) => (
  <div style={{
    position: 'absolute', left: x, top: y, width: VW, height: VH + BAR, borderRadius: 18, background: '#fff',
    overflow: 'hidden', opacity, transform: `scale(${scale})`, transformOrigin: 'center center',
    boxShadow: '0 30px 80px rgba(17,24,39,0.16), 0 6px 18px rgba(17,24,39,0.08), 0 0 0 1px rgba(17,24,39,0.06)',
  }}>
    <div style={{
      height: BAR, background: '#f1f1ef', borderBottom: '1px solid #e4e4e1', display: 'flex', alignItems: 'center',
      padding: '0 16px', gap: 8, position: 'relative',
    }}>
      {['#ff5f57', '#febc2e', '#28c840'].map((c) => (
        <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />
      ))}
      <div style={{
        position: 'absolute', left: '50%', transform: 'translateX(-50%)', top: 8, height: 24, padding: '0 60px',
        borderRadius: 7, background: '#fff', border: '1px solid #e4e4e1', display: 'flex', alignItems: 'center',
        gap: 8, fontSize: 14, color: MUTED, fontWeight: 500,
      }}>
        <Img src={staticFile('img/icon-512.png')} style={{ width: 14, height: 14, borderRadius: 3 }} />
        Lehrercockpit
      </div>
    </div>
    <div style={{ position: 'relative', width: VW, height: VH }}>{children}</div>
  </div>
);

const Clock = ({ size = 22, color = ACCENT }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

// Text block in the right panel, visible from `from` to `to` (frames, local)
export const Caption = ({ from, to, eyebrow, chip, step, title, sub, x = PANEL_X, w = PANEL_W }) => {
  const f = useCurrentFrame();
  if (f < from - 1 || f > to + 1) return null;
  const local = f - from;
  const out = interpolate(f, [to - 9, to], [1, 0], clamp);
  const outShift = interpolate(f, [to - 9, to], [0, -18], clamp);
  const inA = interpolate(local, [2, 16], [0, 1], { ...clamp, easing: easeOut });
  const inB = interpolate(local, [9, 23], [0, 1], { ...clamp, easing: easeOut });
  return (
    <div style={{
      position: 'absolute', left: x, width: w, top: 0, bottom: 0, display: 'flex', flexDirection: 'column',
      justifyContent: 'center', opacity: out, transform: `translateY(${outShift}px)`,
    }}>
      {eyebrow ? (
        <div style={{
          opacity: inA, fontSize: 21, fontWeight: 600, letterSpacing: 2.4, textTransform: 'uppercase', color: ACCENT,
          marginBottom: 22,
        }}>{eyebrow}</div>
      ) : null}
      {chip ? (
        <div style={{
          opacity: inA, transform: `translateX(${(1 - inA) * -16}px)`, alignSelf: 'flex-start', display: 'flex',
          alignItems: 'center', gap: 10, padding: '9px 16px 9px 12px', borderRadius: 999, background: 'rgba(26,86,219,0.09)',
          color: ACCENT, fontSize: 23, fontWeight: 600, marginBottom: 26,
        }}>
          <Clock />{chip}
        </div>
      ) : null}
      {step ? (
        <div style={{
          opacity: inA, transform: `scale(${0.6 + 0.4 * inA})`, transformOrigin: 'left center', width: 64, height: 64,
          borderRadius: 32, background: ACCENT, color: '#fff', fontSize: 34, fontWeight: 700, display: 'flex',
          alignItems: 'center', justifyContent: 'center', marginBottom: 26, boxShadow: '0 10px 24px rgba(26,86,219,0.3)',
        }}>{step}</div>
      ) : null}
      <div style={{
        opacity: inA, transform: `translateY(${(1 - inA) * 24}px)`, fontSize: 54, lineHeight: 1.08, fontWeight: 700,
        color: INK, letterSpacing: -1.2,
      }}>{title}</div>
      {sub ? (
        <div style={{
          opacity: inB, transform: `translateY(${(1 - inB) * 20}px)`, fontSize: 30, lineHeight: 1.38, color: MUTED,
          marginTop: 22, fontWeight: 400,
        }}>{sub}</div>
      ) : null}
    </div>
  );
};

export const Center = ({ children, style }) => (
  <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', textAlign: 'center', ...style }}>{children}</AbsoluteFill>
);

export const AppIcon = ({ size = 150, delay = 0 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ frame: f - delay, fps, config: { damping: 200, stiffness: 140 } });
  return (
    <Img src={staticFile('img/icon-512.png')} style={{
      width: size, height: size, borderRadius: size * 0.23, transform: `scale(${sp})`,
      boxShadow: '0 24px 60px rgba(26,86,219,0.25), 0 0 0 1px rgba(17,24,39,0.06)',
    }} />
  );
};

export const Rise = ({ delay = 0, children, style }) => {
  const f = useCurrentFrame();
  const t = interpolate(f - delay, [0, 16], [0, 1], { ...clamp, easing: easeOut });
  return <div style={{ opacity: t, transform: `translateY(${(1 - t) * 26}px)`, ...style }}>{children}</div>;
};

export const PHONE_K = 0.86;
export const STATUS = 50;
export const phoneSize = (k = PHONE_K) => ({ w: 390 * k + 28, h: (844 + STATUS) * k + 28 });

export const Phone = ({ children, x, y, k = PHONE_K, style }) => {
  const w = 390 * k;
  const h = 844 * k;
  const bar = STATUS * k;
  return (
    <div style={{
      position: 'absolute', left: x, top: y, width: w + 28, height: h + bar + 28, borderRadius: 64 * k + 14,
      background: '#16181d', padding: 14, boxShadow: '0 40px 90px rgba(17,24,39,0.28), 0 0 0 2px #3a3d45 inset', ...style,
    }}>
      <div style={{ position: 'relative', width: w, height: h + bar, borderRadius: 52 * k, overflow: 'hidden', background: '#f7f7f5' }}>
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 0, height: bar, display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', padding: `0 ${30 * k}px`, fontSize: 15 * k + 2, fontWeight: 600, color: INK,
        }}>
          <span>7:55</span>
          <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
            {[6, 9, 12, 15].map((hh) => <span key={hh} style={{ width: 3.5, height: hh * k, background: INK, borderRadius: 1 }} />)}
            <span style={{ width: 24 * k, height: 11 * k, border: `1.5px solid ${INK}`, borderRadius: 4, marginLeft: 6, padding: 1.5 }}>
              <span style={{ display: 'block', width: '75%', height: '100%', background: INK, borderRadius: 2 }} />
            </span>
          </span>
        </div>
        <div style={{ position: 'absolute', left: 0, top: bar, width: w, height: h, overflow: 'hidden' }}>{children(w, h)}</div>
        <div style={{
          position: 'absolute', top: 11 * k, left: '50%', transform: 'translateX(-50%)', width: 118 * k, height: 34 * k,
          borderRadius: 20, background: '#000',
        }} />
      </div>
    </div>
  );
};

export const PhoneShot = ({ src, w, h, opacity = 1 }) => (
  <Img src={staticFile('shots/' + src)} style={{ position: 'absolute', inset: 0, width: w, height: h, opacity }} />
);
