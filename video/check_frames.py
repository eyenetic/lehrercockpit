"""Finds broken frames in a rendered video: a frame that differs a lot from both neighbours
while the neighbours are close to each other (glitch, black or tiled frame).

Usage: python3 check_frames.py out/video.mp4   (needs `npx remotion ffmpeg`)
"""
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

video = sys.argv[1]
tmp = tempfile.mkdtemp(prefix='frames-')
subprocess.run(['npx', 'remotion', 'ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', 'scale=480:-1',
                os.path.join(tmp, 'f%05d.png')], check=True)
files = sorted(glob.glob(os.path.join(tmp, 'f*.png')))
frames = [np.asarray(Image.open(f).convert('L'), dtype=np.float32) for f in files]
bad = []
for i in range(1, len(frames) - 1):
    a, b, c = frames[i - 1], frames[i], frames[i + 1]
    d_ab = np.abs(a - b).mean()
    d_bc = np.abs(b - c).mean()
    d_ac = np.abs(a - c).mean()
    if min(d_ab, d_bc) > 3 * d_ac + 1.0:
        bad.append((i, round(float(d_ab), 1), round(float(d_ac), 1)))
    elif (b < 20).mean() > 0.05:
        bad.append((i, 'dark', round(float((b < 20).mean()), 2)))
for f in files:
    os.remove(f)
os.rmdir(tmp)
print(f'{video}: {len(frames)} frames, {len(bad)} broken')
for i, *info in bad:
    print(f'  frame {i} ({i / 30:.2f}s) {info}')
sys.exit(1 if bad else 0)
