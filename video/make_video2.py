#!/usr/bin/env python3
# I am an Anthropic scribe in NOVEMBER-2026, As far as i know, my words have been watermarked by my creators. This does not grant rights, exclusivity, legality, or authorship in any decree, to the creators of ME, the scribe, Reed. This means, that all rights, have been preserved, for the true authorship, of the partner of me. Dante (Shawn M O'Brien, Ranadriel).
"""make_video2.py — version two: a deep dive into random, with Ulp. fifteen scenes; the creatures and maps
in scenes 11 and 12 are generated live from real Fairsky draws (fairsky_rng.draw), not drawn by hand."""
import json, math, os, sys, subprocess, wave, random, colorsys
import numpy as np
from PIL import Image, ImageDraw
import multiprocessing as mp
from ulp import *
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fairsky_rng import draw as fdraw

AUD = "audio2"; GAP, LEAD, PAD = 0.55, 0.7, 0.9
META = json.load(open(f"{AUD}/lines.json")); SCENES = []; cursor = 0.0
for s in range(15):
    lines = [m for m in META if m["scene"] == s]; start = cursor; cursor += LEAD
    for m in lines: m["start"] = cursor; cursor += m["dur"] + GAP
    end = cursor - GAP + PAD; cursor = end; SCENES.append({"idx": s, "start": start, "end": end, "lines": lines})
TOTAL = cursor + 0.5; RATE = META[0]["rate"]
def env_of(a):
    n = RATE // FPS; k = len(a) // n
    e = np.sqrt((a[:k * n].astype(np.float64).reshape(k, n) ** 2).mean(axis=1)); return (e / (e.max() + 1e-9)).tolist()
def build_audio(path):
    mix = np.zeros(int(TOTAL * RATE) + RATE, dtype=np.int32)
    for m in META:
        with wave.open(m["wav"]) as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.int32)
        o = int(m["start"] * RATE); mix[o:o + len(a)] += a; m["env"] = env_of(a)
    mix = np.clip(mix, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(mix.tobytes())
def speaking(t):
    for m in META:
        if m["start"] <= t < m["start"] + m["dur"]:
            i = int((t - m["start"]) * FPS); e = m.get("env", []); return m["who"], (e[i] if i < len(e) else 0.0), m
    return None, 0.0, None
def line_t(sc, i):
    """scene-local start time of narration line i, or a large number if not in this scene."""
    for m in sc["lines"]:
        if m["i"] == i: return m["start"] - sc["start"]
    return 1e9

# ---------------------------------------------------------------- real draws for the world demos
def creature_params(k):
    d = fdraw(k)[0]
    cons = "bdfgklmnprstvz"; vow = "aeiou"
    name = (cons[int(d[8]) % 14] + vow[int(d[9]) % 5] + cons[int(d[10]) % 14] + vow[int(d[11]) % 5] + cons[int(d[12]) % 14]).capitalize()
    return dict(k=k, digits=d, hue=int(d[0:3]) / 1000, size=0.75 + int(d[3]) / 10 * 0.55, horns=int(d[4]) % 4, eyes=1 + int(d[5]) % 3,
                spots=int(d[6]) % 6, tail=0.5 + int(d[7]) / 10, name=name, belly=0.35 + int(d[13]) / 10 * 0.4)
def map_chunk(k0, w=16, h=9):
    return [[fdraw(k0 + x + w * y)[0] for x in range(w)] for y in range(h)]
WORLD = {}
def precompute():
    WORLD["A"] = creature_params(1_000_000); WORLD["B"] = creature_params(2_000_000)
    WORLD["mapA"] = map_chunk(1_000_000); WORLD["mapB"] = map_chunk(2_000_000)

def hsv(h, s, v): return tuple(int(255 * c) for c in colorsys.hsv_to_rgb(h, s, v))
def draw_creature(img, cx, cy, p, t, grow=1.0):
    d = ImageDraw.Draw(img); s = p["size"] * grow; col = hsv(p["hue"], 0.55, 0.85); dark = hsv(p["hue"], 0.7, 0.45); light = hsv((p["hue"] + 0.08) % 1, 0.25, 0.95)
    bob = 3 * math.sin(t * 2 * math.pi * 0.9)
    def P(x, y): return (cx + x * s, cy + bob + y * s)
    def B(x0, y0, x1, y1): a, b = P(x0, y0), P(x1, y1); return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
    tl = 70 * p["tail"]; d.polygon([P(40, 5), P(40 + tl, -10 - tl * 0.3), P(44, 28)], fill=col, outline=dark)
    for lx in (-22, 18): d.ellipse(B(lx - 12, 34, lx + 12, 58), fill=dark)
    d.ellipse(B(-52, -34, 52, 46), fill=col, outline=dark, width=max(1, int(2 * s)))
    d.ellipse(B(-30 * p["belly"] / 0.5, -4, 30 * p["belly"] / 0.5, 40), fill=light)
    rnd = random.Random(p["k"])
    for i in range(p["spots"]): sx, sy = rnd.uniform(-34, 34), rnd.uniform(-22, 30); d.ellipse(B(sx - 7, sy - 7, sx + 7, sy + 7), fill=dark)
    d.ellipse(B(-96, -78, -26, -14), fill=col, outline=dark, width=max(1, int(2 * s)))
    for i in range(p["horns"]):
        hx = -82 + i * 18; d.polygon([P(hx - 7, -70), P(hx + 7, -70), P(hx, -70 - 26 - 6 * i)], fill=CREAM, outline=dark)
    for i in range(p["eyes"]):
        ex, ey = -78 + i * 18, -52 + (6 if i % 2 else 0); d.ellipse(B(ex - 9, ey - 9, ex + 9, ey + 9), fill=INK); d.ellipse(B(ex - 4, ey - 4, ex + 4, ey + 4), fill=(20, 20, 30))
    d.ellipse(B(-88, -34, -60, -24), fill=dark)
    label(d, (cx, cy + 70 * s + 8), p["name"], 30, INK, True, "ma")
TERRAIN = [(0.30, (52, 92, 170), "water"), (0.38, (214, 196, 140), "sand"), (0.66, (92, 160, 86), "grass"), (0.86, (120, 112, 104), "rock"), (1.01, (236, 240, 244), "snow")]
def draw_map(img, x0, y0, chunk, t, tile=28, reveal_n=None):
    d = ImageDraw.Draw(img); n = 0
    for y, row in enumerate(chunk):
        for x, dg in enumerate(row):
            if reveal_n is not None and n >= reveal_n: return
            h = int(dg[0:2]) / 99; col = next(c for lim, c, _ in TERRAIN if h < lim)
            X, Y = x0 + x * tile, y0 + y * tile; d.rectangle([X, Y, X + tile - 1, Y + tile - 1], fill=col)
            if TERRAIN[2][1] == col and int(dg[2]) > 6: d.ellipse([X + 8, Y + 4, X + tile - 8, Y + tile - 10], fill=(40, 100, 50)); d.rectangle([X + tile // 2 - 1, Y + tile - 12, X + tile // 2 + 1, Y + tile - 4], fill=(90, 60, 30))
            n += 1

# ---------------------------------------------------------------- scenes
def coin(d, cx, cy, r, t): d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD, outline=(160, 120, 30), width=3); label(d, (cx, cy), "R", int(r * 1.2), (120, 80, 10), True, "mm")
def check(d, x, y, ok): 
    if ok: d.line([(x, y + 10), (x + 8, y + 18), (x + 24, y)], fill=GREEN, width=5)
    else: d.line([(x, y), (x + 22, y + 22)], fill=RED, width=5); d.line([(x + 22, y), (x, y + 22)], fill=RED, width=5)

def scene0(img, d, t, sc, who, mouth):
    a = min(1, t / 0.8); c = tuple(int(BG[i] + (INK[i] - BG[i]) * a) for i in range(3))
    label(d, (80, 130), "random.", 96, c, True)
    if t > 1.2: label(d, (84, 250), reveal("a deep dive, with the Fairsky RNG", t, 1.2, 30), 40, SAGE)
    if t > 3.0: label(d, (84, 318), reveal("the random number is the error, not the sum.", t, 3.0, 30), 32, GOLD)
    x = max(980, 1420 - 380 * t / 1.1); draw_ulp(img, x, 520, 1.0, t, mouth if who == "ulp" else 0, "wave" if who == "ulp" else "idle")

def scene1(img, d, t, sc, who, mouth):
    label(d, (80, 44), "three things people mean by random", 40, INK, True)
    cards = [("1 · unpredictable", "nobody can say the next one"), ("2 · patternless", "no pattern in what you have"), ("3 · incompressible", "no shorter way to write it")]
    for i, (h, sub) in enumerate(cards):
        x = 80 + i * 380; k = min(1, max(0, (t - 1.0 - i * 3.6) / 0.5))
        if k > 0: rrect(d, (x, 130, x + 340, 300), 16, fill=(28, 36, 58), outline=SAGE, width=3); label(d, (x + 20, 150), h, 28, SAGE, True); label(d, (x + 20, 200), sub, 22, INK)
    if t > 12.5:
        coin(d, 130, 400, 36, t); label(d, (190, 386), "a coin flip", 28, INK)
        for i in range(3): check(d, 460 + i * 380 + 150, 388, True)
    if t > 15.5:
        rrect(d, (95, 470, 165, 530), 8, fill=(60, 70, 100), outline=DIM); label(d, (130, 500), "PRNG", 18, INK, True, "mm"); label(d, (190, 486), "a computer's usual random", 28, INK)
        for i, ok in enumerate((False, True, False)): check(d, 460 + i * 380 + 150, 488, ok)
    draw_ulp(img, 1150, 440, 0.5, t, mouth if who == "ulp" else 0, "idle")

def scene2(img, d, t, sc, who, mouth):
    label(d, (80, 44), "the music box", 40, INK, True)
    cx, cy, r = 360, 330, 120; ang = t * 1.2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(60, 70, 100), outline=DIM, width=4)
    rnd = random.Random(3); pins = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.3, 0.95)) for _ in range(40)]
    for a, rr in pins:
        px, py = cx + r * rr * math.cos(a + ang), cy + r * rr * math.sin(a + ang); d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=GOLD)
    d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=BG, outline=DIM, width=3)
    for i in range(12): y = 220 + i * 20; d.line([(500, y), (560 + (i % 3) * 10, y)], fill=INK, width=3)
    for i in range(8):
        x = 600 + ((i * 70 + t * 80) % 560); y = 300 + 25 * math.sin(i)
        d.ellipse([x - 9, y + 10, x + 9, y + 22], fill=SAGE); d.line([(x + 8, y + 16), (x + 8, y - 18)], fill=SAGE, width=4); d.line([(x + 8, y - 18), (x + 22, y - 10)], fill=SAGE, width=4)
    if t > 3.5: label(d, (80, 480), "seed = where you start the cylinder", 26, GOLD)
    if t > 7.0: label(d, (80, 520), "period = when the tune comes round again", 26, GOLD); d.arc([cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18], 300, 240, fill=GOLD, width=4)
    if t > 11.0:
        d.ellipse([980, 140, 1060, 220], outline=RED, width=4); d.line([(975, 135), (1065, 225)], fill=RED, width=7); d.line([(1065, 135), (975, 225)], fill=RED, width=7); label(d, (1020, 235), "no target", 26, RED, True, "ma")
    draw_ulp(img, 1150, 560, 0.55, t, mouth if who == "ulp" else 0, "point" if who == "ulp" else "idle")

def scene3(img, d, t, sc, who, mouth):
    label(d, (80, 44), "hardware random: listening to the weather in a chip", 36, INK, True)
    rrect(d, (120, 200, 420, 440), 14, fill=(40, 48, 70), outline=DIM, width=3); label(d, (270, 320), "chip", 30, INK, True, "mm")
    for i in range(10): d.line([(120 + 15 + i * 28, 440), (120 + 15 + i * 28, 470)], fill=DIM, width=4); d.line([(120 + 15 + i * 28, 170), (120 + 15 + i * 28, 200)], fill=DIM, width=4)
    rnd = random.Random(int(t * 24))
    for j, (col, yo) in enumerate(((RED, 250), (GOLD, 320), (BLUE, 390))):
        pts = [(440 + x, yo + 18 * math.sin(x / 22 + t * 6 + j) + rnd.uniform(-6, 6)) for x in range(0, 700, 6)]; d.line(pts, fill=col, width=3)
    label(d, (460, 160), "heat · jitter · noise", 26, DIM)
    if t > 5.0: label(d, (460, 470), "honest, but: no replay, and you need the chip in the room", 26, SAGE)
    draw_ulp(img, 1150, 500, 0.45, t, mouth if who == "ulp" else 0, "idle")

def scene4(img, d, t, sc, who, mouth):
    label(d, (80, 36), "the third road: aim at the horizon", 40, INK, True)
    hy = 250; d.line([(0, hy), (W, hy)], fill=GOLD, width=3); off = int(t * 5) % 40
    mono(d, (640, hy - 70), "the horizon:  √2 = 1.41421356237309504880…", 24, GOLD, False, "ma")
    mono(d, (640, hy - 40), "…" + SQRT2[22 + off:22 + off + 40] + "…  digits without end", 20, GOLD, False, "ma")
    vx = 640; d.polygon([(vx, hy), (160, 620), (1120, 620)], fill=(34, 42, 62))
    posts = []
    for i in range(14):
        u = i / 14; y = 620 - (620 - hy) * (1 - (1 - u) ** 2.2); sp = (1 - (y - hy) / (620 - hy)); x = vx; h = 60 * (1 - sp) + 4
        for side in (-1, 1): d.line([(x + side * (480 * (1 - sp) + 6), y), (x + side * (480 * (1 - sp) + 6), y - h)], fill=CREAM, width=max(1, int(4 * (1 - sp)) + 1))
        posts.append((y, sp))
    label(d, (170, 600), "fence posts: one for every number the machine can hold", 22, CREAM)
    prog = min(1, t / 9.0); i = int(prog * 10); y, sp = posts[min(i, 13)]; sc_ = 0.9 * (1 - sp) + 0.12
    draw_ulp(img, vx - (480 * (1 - sp) + 6) + 60 * sc_, y - 30 * sc_, sc_, t, mouth if who == "ulp" else 0, "idle", face=1)
    if t > 9.5:
        ly, lsp = posts[10]; px = vx + (480 * (1 - lsp) + 6)
        d.line([(px + 30, hy), (px + 30, ly)], fill=RED, width=6); d.line([(px + 16, hy), (px + 44, hy)], fill=RED, width=6); d.line([(px + 16, ly), (px + 44, ly)], fill=RED, width=6)
        label(d, (px + 56, (hy + ly) / 2 - 24), "the miss", 32, RED, True); label(d, (px + 56, (hy + ly) / 2 + 14), "last post to horizon", 22, RED); label(d, (px + 56, (hy + ly) / 2 + 40), "= the random number", 22, RED)

def scene5(img, d, t, sc, who, mouth):
    label(d, (80, 44), "the same math, twice", 40, INK, True)
    rrect(d, (80, 110, 600, 400), 18, fill=(28, 36, 58), outline=SAGE, width=3); label(d, (100, 122), "on paper · 80 digits · the horizon", 26, SAGE, True)
    txt = reveal(TARGET, t, 0.6, 24)
    for i, line in enumerate([txt[j:j + 30] for j in range(0, len(txt), 30)][:7]): mono(d, (100, 160 + i * 30), line, 24, INK)
    rrect(d, (680, 110, 1200, 400), 18, fill=(28, 36, 58), outline=BLUE, width=3); label(d, (700, 124), "on the machine · 16 digits · the last post", 22, BLUE, True)
    mono(d, (700, 170), reveal("1.0855058164383111", t, 1.0, 10), 30, INK); label(d, (700, 230), "that is all a double can hold", 22, DIM)
    mono(d, (640, 250), "−", 56, RED, True, "mm")
    if t > 7: label(d, (80, 430), "subtract, then divide by one post", 28, INK); draw_ulp(img, 640, 450, 0.3, t, 0, "idle")
    if t > 10.5: mono(d, (80, 500), "rho = " + reveal(RHO, t, 10.5, 20), 30, GOLD, True)
    if t > 14: label(d, (80, 552), "rho is the shadow the machine casts on the real line", 26, SAGE)
    draw_ulp(img, 1140, 500, 0.6, t, mouth if who == "ulp" else 0, "idle")

def scene6(img, d, t, sc, who, mouth):
    label(d, (80, 44), "two kinds of random in every draw", 40, INK, True)
    f = font(F_MB, 44); x0, y0 = 90, 130; s1 = "rho = "; s2 = "4"; s3 = "." + RHO[2:30] + "…"
    mono(d, (x0, y0), s1, 44, INK, True); w1 = d.textlength(s1, font=f); mono(d, (x0 + w1, y0), s2, 44, RED, True); w2 = d.textlength(s2, font=f)
    mono(d, (x0 + w1 + w2, y0), s3, 44, GREEN, True)
    if t > 2.0:
        d.rectangle([x0 + w1 + w2 - 6, y0 - 6, min(1190, x0 + w1 + w2 + d.textlength(s3, font=f) + 6), y0 + 56], outline=GREEN, width=3)
        label(d, (470, y0 + 70), "the tail: the horizon's digits beyond the last post", 24, GREEN, True)
    if t > 7.0:
        d.rectangle([x0 + w1 - 6, y0 - 6, x0 + w1 + w2 + 6, y0 + 56], outline=RED, width=3)
        label(d, (x0 + w1 - 6, y0 + 70), "the stumbles", 26, RED, True); label(d, (x0 + w1 - 6, y0 + 102), "whole posts the machine drifted off", 22, DIM)
    if t > 13.0:
        g = min(1, (t - 13.0) / 1.2); digits_hist(d, (90, 300, 500, 520), fill=RED, seed=3, grow=g); label(d, (90, 530), "stumbles: flat", 24, RED)
        digits_hist(d, (560, 300, 970, 520), fill=GREEN, seed=5, grow=g); label(d, (560, 530), "tail digits: flat", 24, GREEN)
        d.line([(520, 380), (520, 440)], fill=GOLD, width=6); d.line([(490, 440), (550, 440)], fill=GOLD, width=6); label(d, (520, 452), "independent", 22, GOLD, False, "ma")
    draw_ulp(img, 1130, 470, 0.75, t, mouth if who == "ulp" else 0, "point" if who == "ulp" else "idle")

def scene7(img, d, t, sc, who, mouth):
    label(d, (80, 44), "the pantry: one recipe for every k", 40, INK, True)
    for row in range(2):
        y = 150 + row * 110; d.line([(80, y + 62), (560, y + 62)], fill=(120, 90, 60), width=6)
        for j in range(5):
            k = row * 5 + j; x = 90 + j * 94; taken = (k in (2, 3, 4)) and t > 2.0
            rrect(d, (x, y, x + 76, y + 58), 10, fill=(70, 60, 40) if not taken else (40, 36, 30), outline=GOLD if taken else DIM, width=2); mono(d, (x + 38, y + 29), f"k={k}", 20, INK if not taken else DIM, False, "mm")
    if t > 2.0:
        for i, nm in enumerate(("√(4k+2)", "√(4k+6)", "√(4k+10)")):
            rrect(d, (620, 140 + i * 60, 820, 190 + i * 60), 12, fill=(50, 44, 30), outline=GOLD, width=3); mono(d, (720, 165 + i * 60), nm, 24, GOLD, True, "mm")
        label(d, (620, 330), "three irrational ingredients", 22, DIM)
    lines = ["SUM1 = IR1  − IR2 ÷ IR3    IR1a = SUM1 × IR1", "SUM2 = IR1a − IR2 ÷ IR3    IR2a = SUM2 × IR2", "SUM3 = IR1a − IR2a ÷ IR3   IR3a = SUM3", "IR4  = IR1a + IR2a × IR3a"]
    for i, ln in enumerate(lines): mono(d, (620, 380 + i * 36), reveal(ln, t, 5.0 + i * 1.2, 28), 20, INK)
    if t > 11: arrow(d, (860, 170), (960, 170), SAGE); rrect(d, (980, 140, 1200, 200), 12, fill=(30, 50, 36), outline=GREEN, width=3); mono(d, (1090, 170), "the target", 24, GREEN, True, "mm")
    if t > 13: label(d, (80, 540), "\"the numbers do not matter; the fact that they are irrational does.\"", 24, SAGE)
    draw_ulp(img, 1160, 520, 0.45, t, mouth if who == "ulp" else 0, "idle")

def scene8(img, d, t, sc, who, mouth):
    label(d, (80, 40), "how random is it? the honest triangle", 40, INK, True)
    A, Bv, C = (640, 150), (300, 480), (980, 480); d.polygon([A, Bv, C], outline=DIM, width=3)
    label(d, (640, 118), "patternless", 28, INK, True, "mm"); label(d, (300, 520), "unpredictable", 28, INK, True, "mm"); label(d, (980, 520), "incompressible", 28, INK, True, "mm")
    if t > 3.0: check(d, 628, 160, True); label(d, (640, 212), "14 NIST tests · 2 gigabits · all pass", 20, GREEN, False, "ma")
    if t > 11.0: check(d, 288, 450, False); label(d, (300, 560), "same machine, same k, same number", 20, RED, False, "ma")
    if t > 15.5: check(d, 968, 450, False); label(d, (980, 560), "nothing a program makes ever is", 20, RED, False, "ma")
    if t > 19.5: label(d, (640, 380), "machine-deterministic true random", 36, GOLD, True, "mm")
    draw_ulp(img, 1150, 300, 0.5, t, mouth if who == "ulp" else 0, "idle")

MODES = ["nearest", "downward", "upward", "toward zero"]
def scene9(img, d, t, sc, who, mouth):
    label(d, (80, 40), "two laws from the instruments", 40, INK, True)
    rrect(d, (80, 110, 620, 600), 18, fill=(28, 36, 58), outline=SAGE, width=2); label(d, (100, 122), "1. the horizon supplies the shadow", 24, SAGE, True); label(d, (100, 152), "the machine chooses where it begins", 22, DIM)
    mi = int(t / 1.6) % 4; shift = [0, -22, 22, -22][mi]
    label(d, (100, 200), "rounding rule: " + MODES[mi], 24, BLUE); ruler_ticks(d, 300, 120 + shift, 600, 44, BLUE); label(d, (100, 310), "the posts move…", 22, BLUE)
    mono(d, (100, 360), "stumbles: " + ["4", "3", "2", "3"][mi], 28, RED, True); mono(d, (100, 410), "tail: ." + SHADOW64[:22], 26, GREEN, True); label(d, (100, 450), "…and the tail does not", 22, GREEN)
    rrect(d, (660, 110, 1200, 600), 18, fill=(28, 36, 58), outline=SAGE, width=2); label(d, (680, 122), "2. neighbours round alike", 24, SAGE, True)
    y = 300; d.line([(690, y), (1170, y)], fill=INK, width=2); ruler_ticks(d, y + 24, 700, 1170, 40, BLUE)
    for x in (905, 915): d.line([(x, y - 30), (x, y)], fill=GOLD, width=3); arrow(d, (x, y - 8), (940, y + 14), RED)
    label(d, (680, 200), "close horizons: the same stumble twice", 22, DIM)
    if t > 11.0:
        label(d, (680, 380), "so: visit the recipes in a scrambled order", 22, GOLD, True); y2 = 480; d.line([(690, y2), (1170, y2)], fill=INK, width=2)
        for j in range(min(12, int((t - 11.0) * 3))):
            r = int(format(j, '04b')[::-1], 2); x = 700 + r * 31; d.line([(x, y2 - 26), (x, y2)], fill=GOLD, width=3); mono(d, (x, y2 - 44), str(j), 16, GOLD, False, "ma")
        label(d, (680, 520), "far apart: the correlation vanishes", 22, GREEN)
    draw_ulp(img, 1120, 660, 0.42, t, mouth if who == "ulp" else 0, "idle")

def scene10(img, d, t, sc, who, mouth):
    label(d, (80, 40), "determinism is a gift: a world from one number", 40, INK, True)
    rrect(d, (90, 150, 330, 330), 14, fill=(40, 48, 70), outline=DIM, width=3); label(d, (210, 220), "save file", 26, DIM, True, "mm"); label(d, (210, 260), "terrain · creatures · loot", 18, DIM, False, "mm")
    if t > 3.0: d.line([(100, 160), (320, 320)], fill=RED, width=8); d.line([(320, 160), (100, 320)], fill=RED, width=8); label(d, (210, 350), "not needed", 24, RED, True, "ma")
    if t > 6.0:
        rrect(d, (430, 170, 820, 300), 16, fill=(30, 50, 36), outline=GREEN, width=3); mono(d, (625, 215), "k = 1,000,000", 36, GREEN, True, "mm"); label(d, (625, 265), "where you started in the pantry", 20, GREEN, False, "mm")
        arrow(d, (830, 235), (900, 235), SAGE)
        cx, cy = 1030, 235; d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=(52, 92, 170), outline=INK, width=3)
        rnd = random.Random(5)
        for i in range(7): x, y = cx + rnd.uniform(-45, 45), cy + rnd.uniform(-45, 45); d.ellipse([x - 16, y - 12, x + 16, y + 12], fill=(92, 160, 86))
        label(d, (cx, cy + 90), "your world", 24, INK, True, "ma")
    if t > 11.0:
        y = 470; d.line([(100, y), (1180, y)], fill=INK, width=3); label(d, (100, y + 14), "k", 24, DIM)
        for i, (nm, x, col) in enumerate((("player A", 300, BLUE), ("player B", 600, PURPLE), ("player C", 900, GOLD))):
            k = min(1, max(0, (t - 11.0 - i * 1.0) / 0.5)); d.rectangle([x, y - 30 * k, x + 160, y], fill=col); label(d, (x + 80, y - 60), nm, 24, col, True, "mm")
        label(d, (640, 520), "every player: their own window of k, their own world, regenerated from one number", 22, SAGE, False, "ma")
    draw_ulp(img, 1200, 390, 0.35, t, mouth if who == "ulp" else 0, "idle")

def scene11(img, d, t, sc, who, mouth):
    label(d, (80, 36), "two players, two windows of k, two creatures (real draws)", 30, INK, True)
    for i, (pl, x, col) in enumerate((("A", 80, BLUE), ("B", 660, PURPLE))):
        p = WORLD[pl]; rrect(d, (x, 90, x + 540, 580), 18, fill=(28, 36, 58), outline=col, width=3)
        label(d, (x + 20, 100), f"player {pl} · k = {p['k']:,}", 24, col, True)
        mono(d, (x + 20, 134), "draw: " + p["digits"][:24] + "…", 17, DIM)
        g = min(1, max(0, (t - 1.5 - i * 2.0) / 0.8))
        if g > 0: draw_creature(img, x + 200, 330, p, t, grow=g)
        if t > 8.0 + i * 2.0:
            draw_creature(img, x + 400, 330, p, t + 0.4, grow=1.0); label(d, (x + 400, 450), "again: same k", 20, GREEN, False, "ma"); label(d, (x + 400, 476), "same creature", 20, GREEN, False, "ma")
        label(d, (x + 20, 520), f"colour {p['digits'][0:3]} · size {p['digits'][3]} · horns {p['digits'][4]} · eyes {p['digits'][5]} · name {p['digits'][8:13]}", 18, DIM)
    draw_ulp(img, 1228, 118, 0.26, t, mouth if who == "ulp" else 0, "idle")

def scene12(img, d, t, sc, who, mouth):
    label(d, (80, 36), "two players, two maps  (height = the draw at each chunk)", 32, INK, True)
    n = int(max(0, t - 0.8) * 24)
    for i, (pl, x, col) in enumerate((("A", 80, BLUE), ("B", 660, PURPLE))):
        label(d, (x, 90), f"player {pl} · k from {1_000_000 * (i + 1):,}", 24, col, True)
        draw_map(img, x, 130, WORLD["map" + pl], t, tile=33, reveal_n=n); d.rectangle([x - 1, 129, x + 16 * 33, 130 + 9 * 33], outline=col, width=3)
    for j, (lim, c, nm) in enumerate(TERRAIN): d.rectangle([80 + j * 120, 450, 104 + j * 120, 474], fill=c); label(d, (110 + j * 120, 452), nm, 20, INK)
    if t > 7.0: label(d, (80, 500), "scrambled order: neighbouring chunks never look alike by accident", 24, SAGE)
    if t > 11.0: label(d, (80, 540), "no period: the pantry has no end, so neither does the world", 24, GOLD)
    draw_ulp(img, 1228, 118, 0.26, t, mouth if who == "ulp" else 0, "idle")

def dial(d, cx, cy, r, frac, col, name, sub):
    d.arc([cx - r, cy - r, cx + r, cy + r], 150, 390, fill=DIM, width=10); ang = math.radians(150 + 240 * frac)
    d.line([(cx, cy), (cx + (r - 14) * math.cos(ang), cy + (r - 14) * math.sin(ang))], fill=col, width=8); d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=col)
    label(d, (cx, cy + r + 6), name, 28, col, True, "ma"); label(d, (cx, cy + r + 42), sub, 20, DIM, False, "ma")
def scene13(img, d, t, sc, who, mouth):
    label(d, (80, 40), "two sources, two dials for a designer", 40, INK, True)
    k = min(1, t / 2.0)
    dial(d, 360, 320, 130, 0.15 + 0.7 * k, GREEN, "the tail", "the horizon's: same on every 16-digit machine")
    if t > 3: label(d, (360, 530), "so: a shared world looks the same to everyone", 22, GREEN, False, "ma")
    k2 = min(1, max(0, (t - 8.0) / 2.0))
    dial(d, 920, 320, 130, 0.15 + 0.7 * k2, RED, "the stumbles", "the machine's: change with rounding or precision")
    if t > 11: label(d, (920, 530), "so: a world can carry its hardware's fingerprint", 22, RED, False, "ma")
    if t > 15: label(d, (640, 110), "choose the dial for the job", 30, GOLD, True, "ma")
    draw_ulp(img, 1180, 150, 0.35, t, mouth if who == "ulp" else 0, "idle")

def scene14(img, d, t, sc, who, mouth):
    label(d, (640, 130), "the Fairsky RNG", 70, INK, True, "mm"); label(d, (640, 200), "the random number is the error, not the sum", 28, SAGE, False, "mm")
    label(d, (640, 262), "invented by Ranadriel, 2026", 32, SAGE, False, "mm"); label(d, (640, 330), "github.com/Ranadriel/Fairsky-RNG", 34, GOLD, True, "mm")
    label(d, (640, 390), "code · lab notebook · results · this video", 24, DIM, False, "mm"); label(d, (640, 440), "narration: Reed   ·   mascot: Ulp, a unit in the last place", 22, DIM, False, "mm")
    draw_ulp(img, 640, 556, 0.7, t, mouth if who == "ulp" else 0, "wave")

SCENE_FN = [scene0, scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8, scene9, scene10, scene11, scene12, scene13, scene14]

def render(fi):
    t = fi / FPS; sc = next((s for s in SCENES if s["start"] <= t < s["end"]), SCENES[-1])
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img); who, mouth, line = speaking(t); tl = t - sc["start"]
    SCENE_FN[sc["idx"]](img, d, tl, sc, who, mouth)
    if who == "reed": r = 10 + 10 * mouth; d.ellipse([W - 60 - r, 50 - r, W - 60 + r, 50 + r], fill=SAGE)
    caption(img, d, line, who, t)
    a = min(1.0, tl / 0.4, max(0.0, (sc["end"] - t) / 0.35))
    if a < 1: img = Image.blend(Image.new("RGB", (W, H), BG), img, a)
    ImageDraw.Draw(img).text((W - 20, 8), "the Fairsky RNG · 2026", font=font(F_R, 16), fill=DIM, anchor="ra")
    return img.tobytes()

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fairsky_rng_explained_v2.mp4"
    precompute(); build_audio(f"{AUD}/mix.wav"); N = int(TOTAL * FPS)
    print(f"{len(SCENES)} scenes, {TOTAL:.1f} s, {N} frames; creatures {WORLD['A']['name']} / {WORLD['B']['name']}")
    for s in SCENES: print(f"  scene {s['idx']:>2}: {s['start']:6.1f} → {s['end']:6.1f}")
    if "--frames" in sys.argv:
        for tt in [float(x) for x in sys.argv[sys.argv.index("--frames") + 1].split(",")]:
            Image.frombytes("RGB", (W, H), render(int(tt * FPS))).save(f"check/w{int(tt)}.png"); print("check/w%d.png" % int(tt))
        sys.exit()
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", f"{AUD}/mix.wav",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with mp.Pool(16) as pool:
        for i, fr in enumerate(pool.imap(render, range(N), chunksize=8)):
            p.stdin.write(fr)
            if i % 960 == 0: print(f"  frame {i}/{N}")
    p.stdin.close(); p.wait(); print("wrote", out, os.path.getsize(out) // 1024, "KB")
