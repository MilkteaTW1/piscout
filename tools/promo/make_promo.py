"""Render the piscout promo video (1280x720, 30 fps, 30 s) with PIL + numpy and mux with ffmpeg."""
import math, subprocess, sys, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1280, 720, 30
BPM = 128
BEAT = 60 / BPM
SCENE = 8 * BEAT            # 3.75 s
N = 8
DUR = SCENE * N             # 30 s
SPEED = 1.7                 # playback speed: animation timeline runs this much faster
OUT = sys.argv[1] if len(sys.argv) > 1 else "piscout-promo.mp4"

F = "C:/Windows/Fonts/"
def font(path, size): return ImageFont.truetype(F + path, size)
CJK = lambda s: font("msjhbd.ttc", s)
CJKR = lambda s: font("msjh.ttc", s)
MONO = lambda s: font("consolab.ttf", s)

BG = (10, 16, 13); GREEN = (97, 222, 140); PINK = (232, 33, 86); WHITE = (240, 248, 243)
DIM = (140, 170, 152); CARD = (22, 38, 29); LINE = (39, 74, 55); AMBER = (255, 190, 80)


def ease(t): t = max(0, min(1, t)); return 1 - (1 - t) ** 3
def back(t):
    t = max(0, min(1, t)); c = 1.70158; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

def text(d, xy, s, f, fill=WHITE, anchor="la"): d.text(xy, s, font=f, fill=fill, anchor=anchor)

def glow(img, box, color, radius=30, alpha=120):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, 24, fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)))

def grid_bg(t):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    off = (t * 40) % 60
    for x in range(-60, W + 60, 60): d.line([(x + off, 0), (x + off, H)], fill=(18, 30, 24), width=1)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=(18, 30, 24), width=1)
    return img

def headline(img, en, zh, t, y=70, color=WHITE):
    k = back(t * 3)
    a = int(255 * min(1, t * 6))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    text(ld, (W / 2, y + (1 - k) * 40), en, CJK(58), color + (a,), "mt")
    text(ld, (W / 2, y + 74 + (1 - k) * 40), zh, CJKR(30), GREEN + (a,), "mt")
    img.alpha_composite(layer)

def rect(d, box, fill, outline=None, r=16, w=2): d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


def overlay_text(img, items):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    for args in items: text(ld, *args)
    img.alpha_composite(layer)

# ---------------------------------------------------------------- scenes (t = seconds in scene)
def s_title(t):
    img = grid_bg(t)
    k = back(t * 2.4)
    size = int(220 * k)
    if size > 4:
        glow(img, (W / 2 - 130, 120, W / 2 + 130, 380), PINK, 50, int(160 * ease(t * 3)))
        d = ImageDraw.Draw(img)
        rect(d, (W / 2 - 110, 130 + (1 - k) * 60, W / 2 + 110, 350 + (1 - k) * 60), PINK, r=50)
        text(d, (W / 2, 240 + (1 - k) * 60), "π", CJK(size), WHITE, "mm")
    overlay_text(img, [
        ((W / 2, 450), "piscout", CJK(120), WHITE + (int(255 * ease((t - 0.5) * 2.5)),), "mm"),
        ((W / 2, 548), "一個視窗，管好你所有的樹莓派", CJK(38), GREEN + (int(255 * ease((t - 1.1) * 2.5)),), "mm"),
        ((W / 2, 600), "Find, control and flash every Raspberry Pi - from one Windows window.", CJKR(24),
         DIM + (int(255 * ease((t - 1.6) * 2.5)),), "mm"),
    ])
    return img

def s_scan(t):
    img = grid_bg(t)
    headline(img, "Where is your Pi?", "不用再去路由器翻 IP", t)
    d = ImageDraw.Draw(img)
    cx, cy, R = 330, 440, 210
    for r in (70, 140, 210): d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=LINE, width=2)
    ang = t * 5.2
    sweep = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sweep)
    for i in range(40):
        a0 = ang - i * 0.03
        sd.line([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0))], fill=GREEN + (int(110 * (1 - i / 40)),), width=6)
    img.alpha_composite(sweep); d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    pts = [(rnd.uniform(0.2, 0.95), rnd.uniform(0, 6.28)) for _ in range(5)]
    for i, (rr, aa) in enumerate(pts):
        if t > 0.6 + i * 0.35:
            px, py = cx + R * rr * math.cos(aa), cy + R * rr * math.sin(aa)
            pulse = 8 + 6 * math.sin((t - i) * 8)
            d.ellipse((px - pulse, py - pulse, px + pulse, py + pulse), outline=PINK, width=3)
            d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=PINK)
    names = [("raspberrypi", "192.168.0.31", "Pi 3 Model B"), ("garage-pi", "192.168.0.77", "Pi 4 Model B"),
             ("kitchen-pi", "192.168.0.52", "Pi Zero 2 W")]
    for i, (n, ip, m) in enumerate(names):
        k = back((t - 1.0 - i * 0.4) * 2.2)
        if k <= 0: continue
        x = 640 + (1 - min(1, k)) * 500; y = 300 + i * 112
        glow(img, (x, y, x + 580, y + 92), GREEN, 20, 40); d = ImageDraw.Draw(img)
        rect(d, (x, y, x + 580, y + 92), CARD, LINE)
        text(d, (x + 24, y + 14), n, CJK(30)); text(d, (x + 24, y + 54), f"{ip}  ·  {m}", CJKR(20), DIM)
        rect(d, (x + 440, y + 26, x + 560, y + 66), PINK, r=20); text(d, (x + 500, y + 46), "Raspberry Pi", CJK(17), WHITE, "mm")
    return img

def s_term(t):
    img = grid_bg(t)
    headline(img, "A real terminal. VS Code-style hints.", "內建終端機，打字就跳補齊", t)
    box = (150, 220, 1130, 640)
    glow(img, box, GREEN, 30, 50); d = ImageDraw.Draw(img)
    rect(d, box, (12, 14, 20), LINE, r=14)
    d.ellipse((172, 238, 186, 252), fill=(255, 95, 86)); d.ellipse((196, 238, 210, 252), fill=(255, 189, 46)); d.ellipse((220, 238, 234, 252), fill=(39, 201, 63))
    f = MONO(30)
    text(d, (180, 290), "Linux raspberrypi 6.12 aarch64", f, DIM)
    prompt = "pi@raspberrypi:~ $ "
    text(d, (180, 350), prompt, f, GREEN)
    typed = "cd Do"
    n = min(len(typed), int(max(0, t - 0.5) * 7))
    px = 180 + d.textlength(prompt, font=f)
    done_t = 2.2
    if t < done_t:
        text(d, (px, 350), typed[:n], f, WHITE)
        cx = px + d.textlength(typed[:n], font=f)
        if int(t * 3) % 2 == 0: d.rectangle((cx + 2, 352, cx + 16, 386), fill=WHITE)
    if n >= len(typed) and t < done_t:
        tt = t - (0.5 + len(typed) / 7)
        items = ["Documents/", "Downloads/", "Desktop/"]
        sel = 0 if tt < 0.5 else 1
        if ease(tt * 5) > 0:
            bx, by = px + d.textlength("cd ", font=f), 396
            rect(d, (bx, by, bx + 330, by + 12 + 52 * len(items)), (30, 33, 44), (70, 76, 100), r=10)
            for i, it in enumerate(items):
                yy = by + 8 + i * 52
                if i == sel: rect(d, (bx + 6, yy, bx + 324, yy + 46), PINK, r=8)
                text(d, (bx + 20, yy + 7), ">", MONO(26), WHITE)
                text(d, (bx + 52, yy + 6), it, MONO(28), WHITE)
    if t >= done_t:
        text(d, (px, 350), "cd Downloads/", f, WHITE)
        text(d, (180, 420), "Up / Down  ·  Tab to accept  ·  Esc to close", f, AMBER)
    return img

def s_drop(t):
    img = grid_bg(t)
    headline(img, "Drag a file. It lands in your folder.", "拖進視窗，直接傳到目前資料夾", t)
    win = (140, 230, 1140, 650)
    glow(img, win, GREEN, 30, 50); d = ImageDraw.Draw(img)
    rect(d, win, (12, 14, 20), LINE, r=14)
    f = MONO(28)
    text(d, (170, 270), "pi@raspberrypi:~/Downloads $ ls", f, GREEN)
    got = t >= 3.0
    text(d, (170, 320), "photo-album.zip" if got else "(empty)", f, WHITE if got else DIM)
    k = ease(t / 1.3)
    fx = 100 + k * 480; fy = 90 + k * 160 + math.sin(t * 6) * 6 * (1 - k)
    if t < 1.5:
        rect(d, (fx, fy, fx + 140, fy + 170), (240, 248, 243), r=14)
        d.polygon([(fx + 100, fy), (fx + 140, fy + 40), (fx + 100, fy + 40)], fill=(180, 200, 188))
        text(d, (fx + 70, fy + 110), "ZIP", MONO(40), BG, "mm")
    if 1.5 <= t < 3.0:
        p = min(1, (t - 1.5) / 1.4)
        rect(d, (260, 440, 1020, 560), CARD, GREEN, r=18)
        text(d, (290, 456), "photo-album.zip  ->  ~/Downloads", CJK(26))
        rect(d, (290, 506, 990, 530), (28, 52, 38), r=12)
        rect(d, (290, 506, 290 + max(24, 700 * p), 530), GREEN, r=12)
        text(d, (990, 462), f"{int(p * 100)}%", MONO(26), GREEN, "ra")
    if t >= 3.0:
        a = ease((t - 3.0) * 4)
        overlay_text(img, [((W / 2, 480), "Done", CJK(72), GREEN + (int(255 * a),), "mm"),
                           ((W / 2, 550), "完成", CJKR(32), GREEN + (int(255 * a),), "mm")])
    return img

def s_flash(t):
    img = grid_bg(t)
    headline(img, "Flash SD cards. Verified.", "燒錄 SD 卡，寫入後逐塊校驗", t)
    d = ImageDraw.Draw(img)
    cx, cy, r = 390, 450, 150
    p = min(1, t / 2.8)
    d.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=(28, 52, 38), width=26)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * p, fill=GREEN if p >= 1 else PINK, width=26)
    text(d, (cx, cy), f"{int(p * 100)}%", CJK(80), WHITE, "mm")
    steps = [("Download official image", 0.0), ("Write to SD card", 0.9), ("Read back + SHA-256", 1.8), ("Write first-boot settings", 2.5)]
    for i, (s, t0) in enumerate(steps):
        k = ease((t - t0) * 3)
        x = 700 + (1 - k) * 200; y = 330 + i * 80
        if k <= 0: continue
        done = t > t0 + 0.8
        rect(d, (x, y, x + 440, y + 62), CARD, GREEN if done else LINE)
        text(d, (x + 22, y + 31), ("[OK]  " if done else "...   ") + s, CJK(24), GREEN if done else WHITE, "lm")
    if t > 3.0:
        a = ease((t - 3.0) * 4)
        overlay_text(img, [((W / 2, 655), "Verified on a real Pi 3B  ·  已在真機驗證", CJKR(26), AMBER + (int(255 * a),), "mm")])
    return img

def s_ai(t):
    img = grid_bg(t)
    headline(img, "Let your AI drive the Pi.", "內建 MCP，AI 直接操作樹莓派", t)
    box = (120, 220, 1160, 650)
    glow(img, box, PINK, 30, 40); d = ImageDraw.Draw(img)
    rect(d, box, (12, 14, 20), LINE, r=14)
    lines = [("you", "Which Pi is running hot? Reboot it.", WHITE),
             ("ai", "-> pi_list()", GREEN),
             ("", "   raspberrypi 192.168.0.31  temp 71.2C", DIM),
             ("ai", "-> pi_run(\"192.168.0.31\", \"sudo reboot\")", GREEN),
             ("", "   rebooting...", AMBER)]
    f = MONO(27)
    y = 255
    for i, (who, s, col) in enumerate(lines):
        n = int(max(0, t - i * 0.65) * 38)
        if n <= 0: continue
        text(d, (150, y), who, f, PINK if who == "you" else DIM)
        text(d, (230, y), s[:n], f, col)
        y += 62
    text(d, (W / 2, 620), "piscout.exe --mcp", MONO(30), AMBER, "mm")
    return img

def s_end(t):
    img = grid_bg(t)
    k = back(t * 2.5)
    glow(img, (W / 2 - 90, 90, W / 2 + 90, 270), PINK, 40, 150); d = ImageDraw.Draw(img)
    rect(d, (W / 2 - 80, 100 + (1 - k) * 50, W / 2 + 80, 260 + (1 - k) * 50), PINK, r=36)
    text(d, (W / 2, 180 + (1 - k) * 50), "π", CJK(130), WHITE, "mm")
    overlay_text(img, [
        ((W / 2, 340), "piscout", CJK(110), WHITE + (int(255 * ease((t - 0.3) * 3)),), "mm"),
        ((W / 2, 440), "Free  ·  Open source  ·  MIT  ·  免費開源", CJK(36), GREEN + (int(255 * ease((t - 0.7) * 3)),), "mm"),
        ((W / 2, 520), "github.com/MilkteaTW1/piscout", MONO(44), WHITE + (int(255 * ease((t - 1.1) * 3)),), "mm"),
        ((W / 2, 600), "Windows 10/11  ·  No telemetry  ·  Bilingual 中文 / English", CJKR(24), DIM + (int(255 * ease((t - 1.5) * 3)),), "mm"),
        ((W / 2, 660), "Independent project - not affiliated with Raspberry Pi Ltd.", CJKR(18), (90, 120, 104, int(255 * ease((t - 1.8) * 3))), "mm"),
    ])
    return img

# slots: title, scan (2 slots = 7.5 s), terminal, drop, flash, ai, end
ORDER = [0, 1, 1, 2, 3, 4, 5, 6]
SCENES = [s_title, s_scan, s_term, s_drop, s_flash, s_ai, s_end]

def frame(sec):
    idx = min(int(sec / SCENE), N - 1)
    t = sec - idx * SCENE
    if idx == 2: t += SCENE            # second slot of the scan scene continues it
    img = SCENES[ORDER[idx]](t)
    ImageDraw.Draw(img).rectangle((0, H - 6, int(W * sec / DUR), H), fill=PINK)
    return img.convert("RGB")

# ---------------------------------------------------------------- audio
SR = 44100

def synth():
    n = int(DUR * SR); out = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(1)
    def add(start, sig, gain=1.0):
        i = int(start * SR); j = min(n, i + len(sig))
        if i < n: out[i:j] += sig[:j - i] * gain
    def kick():
        t = np.linspace(0, 0.28, int(0.28 * SR), False)
        return np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-t * 28)) / SR) * np.exp(-t * 11)
    def noise(dur, decay):
        t = np.linspace(0, dur, int(dur * SR), False)
        return rng.uniform(-1, 1, len(t)) * np.exp(-t * decay)
    def snare():
        t = np.linspace(0, 0.2, int(0.2 * SR), False)
        return (rng.uniform(-1, 1, len(t)) * 0.8 + np.sin(2 * np.pi * 190 * t) * 0.4) * np.exp(-t * 20)
    def tone(freq, dur, saw=True):
        t = np.linspace(0, dur, int(dur * SR), False)
        w = 2 * ((t * freq) % 1) - 1 if saw else np.sign(np.sin(2 * np.pi * freq * t))
        return w * np.minimum(1, t * 80) * np.exp(-t * 6)
    K, S, HC, HO = kick(), snare(), noise(0.05, 80), noise(0.25, 14)
    roots = [55.0, 43.65, 65.41, 49.0]   # A1 F1 C2 G1
    arps = [[220, 261.63, 329.63, 440], [174.61, 220, 261.63, 349.23], [261.63, 329.63, 392, 523.25], [196, 246.94, 293.66, 392]]
    for b in range(int(DUR / BEAT)):
        t0 = b * BEAT
        bar = (b // 4) % 4
        sect = b // 16
        if b >= 4: add(t0, K, 0.9)
        if b % 2 == 1 and b >= 8: add(t0, S, 0.45)
        if b >= 8:
            add(t0, HC, 0.18); add(t0 + BEAT / 2, HC, 0.18)
        if b % 2 == 1: add(t0 + BEAT / 2, HO, 0.12)
        if b >= 4:
            for e in range(2): add(t0 + e * BEAT / 2, tone(roots[bar], BEAT / 2 * 0.95), 0.32)
        if b >= 8:
            a = arps[bar]
            for e in range(4):
                add(t0 + e * BEAT / 4, tone(a[(e + b) % 4] * (2 if sect % 2 else 1), BEAT / 4 * 0.9, saw=False), 0.11)
        if b % 8 == 7:
            m = int(BEAT * SR); add(t0, rng.uniform(-1, 1, m) * np.linspace(0, 1, m) ** 2, 0.22)
    t = np.linspace(0, 1.2, int(1.2 * SR), False)
    add(0, np.sin(2 * np.pi * 38 * t) * np.exp(-t * 4), 0.9)
    out *= np.minimum(1, (DUR - np.arange(n) / SR) / 1.5)
    out = np.tanh(out * 1.4)
    out /= max(1e-9, np.abs(out).max()); out *= 0.9
    return (out * 32767).astype(np.int16)

def main():
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
          "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", OUT]
    p = subprocess.Popen(ff, stdin=subprocess.PIPE)
    total = int(DUR / SPEED * FPS)
    for i in range(total):
        p.stdin.write(frame(i / FPS * SPEED).tobytes())
        if i % 90 == 0: print(i, "/", total, flush=True)
    p.stdin.close(); p.wait()
    print("done", OUT)

if __name__ == "__main__":
    main()
