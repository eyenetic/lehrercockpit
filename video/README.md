# Erklärvideos

Zwei kurze Videos (1920×1080) für Kolleg:innen. Nur Testdaten („Anna Beispiel“, „Beispiel-Schule“) – keine echten Namen oder Links.

1. **Lehrercockpit** (`src/Lehrercockpit.jsx`, ~61 s): Problem (alles verstreut) → „alles an einem Ort“ → ein Schultag → Funktionsüberblick.
2. **Einrichtung** (`src/Einrichtung.jsx`, ~53 s): Einladungslink → WebUntis-Link kopieren → einfügen → fertig, plus iPhone-Tipp.

- `src/common.jsx` – gemeinsame Bausteine (Browserfenster, Kamerafahrten, Texte, iPhone)
- `capture.mjs` – nimmt die Screenshots (`public/shots/`) aus der lokalen Testumgebung auf
- `testenv/` – Testumgebung: Mehrbenutzer-App gegen PGlite auf Port 8095, mit Test-Stundenplan,
  Test-Orgaplan/-Klassenarbeiten/-Mails und fester Uhrzeit im Browser (07:42)
- Musik: „Upbeat Happy Corporate“ von kornevmusic, [Pixabay](https://pixabay.com/music/corporate-upbeat-happy-corporate-487426/)
  (Pixabay Content License, ohne Namensnennung). 120 BPM – die Schnitte liegen auf dem Takt.
  Die MP3 liegt nicht im Repo (keine Weitergabe als Einzeldatei): von Pixabay laden nach
  `public/music/kornevmusic-upbeat-happy-corporate-487426.mp3`.

```
npm install
npm run studio      # Vorschau
npm run render:1    # out/lehrercockpit-video1.mp4
npm run render:2    # out/lehrercockpit-video2-einrichtung.mp4
```

Gerendert wird mit Remotions eigener „Chrome Headless Shell“ (`npx remotion browser ensure`), nicht mit dem
installierten Chrome: der lieferte zufällig schwarze oder gekachelte Einzelbilder („Wackeln“).
`check_frames.py` prüft nach jedem Render jedes Bild auf solche Fehlbilder.
