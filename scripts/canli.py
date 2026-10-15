"""Yaşayan Mezzanotte: çatı sahnesinden kesintisiz döngülü banner.

usage: canli.py <kaynak.png> <cikti_dizini> [genislik]
Kareler cikti_dizini/f000.png ... olarak yazılır.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], Path(sys.argv[2])
OUT_W = int(sys.argv[3]) if len(sys.argv) > 3 else 1672
OUT.mkdir(parents=True, exist_ok=True)

N = 40                      # kare sayısı (döngü)
Y0, Y1 = 205, 762           # banner kesiti (orijinal koordinat)
rng = np.random.default_rng(7)

base = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)[Y0:Y1]
H, W, _ = base.shape


def oy(y):  # orijinal y -> kesit y
    return y - Y0


# --- maskeler ---------------------------------------------------------------
R, G, B = base[..., 0], base[..., 1], base[..., 2]
redness = (R > 140) & (R > G * 2.2)
yy, xx = np.mgrid[0:H, 0:W]

fig_box = (xx >= 735) & (xx <= 962) & (yy >= oy(325)) & (yy <= oy(575))
wall = (R > 190) & (G < 95) & (yy >= oy(215)) & (yy <= oy(335)) & ~fig_box
city = redness & (yy > oy(405)) & (yy < oy(575)) & ~fig_box
tent = redness & (xx >= 735) & (xx <= 800) & (yy >= oy(328)) & (yy <= oy(402))
floor_top = oy(600)

# Blackwall: hücre başına titreme deseni
CW, CH = 56, 52
ncx, ncy = W // CW + 1, H // CH + 1
cell = np.zeros((ncy, ncx, N), np.float32)
for cy in range(ncy):
    for cx in range(ncx):
        ph = rng.uniform(0, 2 * math.pi)
        f = rng.choice([1, 2, 3])
        cell[cy, cx] = 1.0 + 0.10 * np.sin(2 * math.pi * f * np.arange(N) / N + ph)
        for _ in range(rng.integers(0, 3)):           # ani sönme / parlama
            t = rng.integers(0, N)
            k = rng.choice([0.5, 1.5])
            cell[cy, cx, t] = k
            cell[cy, cx, (t + 1) % N] = (k + 1) / 2
cell_idx_y = np.clip(yy // CH, 0, ncy - 1)
cell_idx_x = np.clip(xx // CW, 0, ncx - 1)

# Şehir pencereleri: küçük bir kısmı yanıp söner
win_pat = rng.random((ncy * 4, ncx * 4, N)) < 0.04
win_y = np.clip(yy // (CH // 4), 0, ncy * 4 - 1)
win_x = np.clip(xx // (CW // 4), 0, ncx * 4 - 1)

# --- yağmur -----------------------------------------------------------------
drops = []
for _ in range(420):
    depth = rng.random()
    drops.append(dict(
        x=int(rng.integers(0, W)),
        y=rng.uniform(0, H),
        k=1 + int(depth * 2.2),                    # döngüde H'nin kaç katı yol (1..3)
        L=int(5 + depth * 12),
        a=0.25 + depth * 0.5,
        w=1 if depth < 0.55 else 2,
        c=(255, 70, 85) if rng.random() < 0.8 else (255, 200, 205),
    ))
splashes = [(int(rng.integers(0, W)), int(rng.integers(floor_top + 10, H - 4)), int(rng.integers(0, N)))
            for _ in range(70)]

GLITCH = {24: 0.75, 25: 0.4, 9: 0.3}       # kare -> şiddet


def blend(img, mask_xy, color, alpha):
    img[mask_xy] = img[mask_xy] * (1 - alpha) + np.array(color, np.float32) * alpha


for t in range(N):
    ph = 2 * math.pi * t / N
    img = base.copy()

    # Blackwall fayansları
    m = cell[cell_idx_y, cell_idx_x, t]
    gain = np.where(wall, m, 1.0)[..., None]
    img = np.clip(img * gain + np.where(wall & (m > 1.2), 40, 0)[..., None], 0, 255)

    # şehir pencereleri
    off = city & win_pat[win_y, win_x, t]
    img[off] *= 0.35

    # zemin yansımaları: hafif dalga
    for y in range(floor_top, H):
        s = int(round(1.6 * math.sin(y * 0.33 + ph * 2)))
        if s:
            row = img[y].copy()
            refl = (row[:, 0] > 110) & (row[:, 0] > row[:, 1] * 2)
            shifted = np.roll(row, s, axis=0)
            img[y][refl] = shifted[refl]

    # dokunaçlar: kıpırdayan ışık
    tg = 1.0 + 0.22 * np.sin(ph * 3 + yy[tent] * 0.25)
    img[tent] = np.clip(img[tent] * tg[:, None], 0, 255)

    # küp: nabız (döngüde 2 atış)
    beat = max(0.0, math.sin(ph * 2)) ** 3
    cx, cyy = 888, oy(375)
    d = np.sqrt((xx - cx) ** 2 + (yy - cyy) ** 2)
    glow = np.exp(-(d / (6 + 7 * beat)) ** 2) * (0.2 + 0.55 * beat)
    img = np.clip(img + glow[..., None] * np.array([255, 40, 55], np.float32) * 0.9, 0, 255)
    core = np.exp(-(d / 3.2) ** 2) * beat
    img = np.clip(img + core[..., None] * np.array([255, 230, 225], np.float32), 0, 255)

    # yağmur
    rain = np.zeros((H, W), np.float32)
    rain_c = np.zeros((H, W, 3), np.float32)
    for dr in drops:
        y = (dr["y"] + dr["k"] * H * t / N) % H
        y0, y1 = int(y), min(H, int(y) + dr["L"])
        for xo in range(dr["w"]):
            x = dr["x"] + xo
            if x >= W:
                continue
            seg = slice(y0, y1)
            fade = np.linspace(0.3, 1.0, y1 - y0)
            a = dr["a"] * fade
            upd = a > rain[seg, x]
            rain[seg, x] = np.where(upd, a, rain[seg, x])
            rain_c[seg, x] = np.where(upd[:, None], np.array(dr["c"], np.float32), rain_c[seg, x])
    img = img * (1 - rain[..., None]) + rain_c * rain[..., None]

    # sıçramalar
    for sx, sy, st in splashes:
        age = (t - st) % N
        if age < 2:
            r = 1 + age
            a = 0.7 if age == 0 else 0.35
            for dx in (-r, r):
                if 0 <= sx + dx < W:
                    img[sy, sx + dx] = img[sy, sx + dx] * (1 - a) + np.array([255, 80, 95]) * a
            img[sy - 1, sx] = img[sy - 1, sx] * (1 - a) + np.array([255, 120, 130]) * a

    # pelerin glitch'i
    g = GLITCH.get(t, 0)
    if g:
        x0, x1, gy0, gy1 = 735, 962, oy(325), oy(575)
        box = img[gy0:gy1, x0:x1].copy()
        out = box.copy()
        yb = 0
        while yb < box.shape[0]:
            h = int(rng.integers(3, 14))
            if rng.random() < 0.55 * g + 0.15:
                s = int(rng.integers(-10, 11) * g)
                out[yb:yb + h] = np.roll(box[yb:yb + h], s, axis=1)
            yb += h
        sh = max(1, int(4 * g))
        out[..., 0] = np.roll(out[..., 0], sh, axis=1)
        out[..., 2] = np.roll(out[..., 2], -sh, axis=1)
        # kutu kenarı görünmesin: figür maskesi + yumuşak kenar
        lum = box.sum(2)
        fig = (lum < 170) | (box[..., 0] > box[..., 1] * 2.4)
        bh, bw = fig.shape
        ex = np.minimum(np.arange(bw), np.arange(bw)[::-1]) / 18.0
        ey = np.minimum(np.arange(bh), np.arange(bh)[::-1]) / 18.0
        edge = np.clip(np.minimum(ey[:, None], ex[None, :]), 0, 1)
        al = (fig * edge)[..., None]
        img[gy0:gy1, x0:x1] = box * (1 - al) + out * al

    frame = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if OUT_W != W:
        frame = frame.resize((OUT_W, round(H * OUT_W / W)), Image.LANCZOS)
    frame.save(OUT / f"f{t:03d}.png")
    print(t, end=" ", flush=True)
print()
