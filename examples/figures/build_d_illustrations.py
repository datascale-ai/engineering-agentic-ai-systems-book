"""Original editorial illustrations for Wang Ke's Chinese book chapters.

All artwork consists of editable SVG paths, geometric shapes and live text.
Scenes illustrate fictional teaching cases; they contain no measured results.
Run from any directory. No external fonts, images or icon assets are bundled.
"""

from contextlib import contextmanager
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INK = "#273A49"
BLUE = "#287DA6"
DARKBLUE = "#24536D"
SKY = "#D9EBF0"
LIGHT = "#F0F6F7"
CREAM = "#F6F0E6"
SAND = "#E7D5B9"
ORANGE = "#CB7B45"
PALEORANGE = "#F2DECA"
TEAL = "#57877C"
PALETEAL = "#DDEAE4"
GRAY = "#9DAEB5"
WHITE = "#FFFFFF"
FONT = "Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif"


class Art:
    def __init__(self, chapter, number, slug, title, description):
        self.chapter, self.number, self.slug = chapter, number, slug
        self.title, self.description = title, description
        self.labels, self.groups = [], []
        self.parts = [
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="description">{escape(description)}</desc>',
            '<rect width="1200" height="700" fill="white"/>',
        ]

    def raw(self, content):
        self.parts.append(content)

    @contextmanager
    def group(self, key, transform=None):
        self.groups.append(key)
        self.raw(
            f'<g id="{key}"' + (f' transform="{transform}"' if transform else "") + ">"
        )
        yield
        self.raw("</g>")

    def path(self, d, fill="none", stroke=INK, sw=3, **attrs):
        self.raw(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
            + "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
            + "/>"
        )

    def rect(self, x, y, w, h, fill=WHITE, stroke=INK, sw=3, rx=0, **attrs):
        self.raw(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'
            + "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
            + "/>"
        )

    def ellipse(self, x, y, rx, ry, fill=WHITE, stroke="none", sw=3):
        self.raw(
            f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def circle(self, x, y, r, fill=WHITE, stroke=INK, sw=3):
        self.ellipse(x, y, r, r, fill, stroke, sw)

    def line(self, x1, y1, x2, y2, color=INK, sw=3, **attrs):
        self.path(f"M{x1} {y1} L{x2} {y2}", stroke=color, sw=sw, **attrs)

    def text(self, x, y, text, size=23, color=INK, anchor="start", weight=500):
        self.labels.append(text)
        self.raw(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{escape(text)}</text>'
        )

    def ground(self, y=605):
        self.ellipse(600, y + 9, 475, 28, LIGHT)
        self.line(85, y, 1120, y, GRAY, 2)
        for x in [95, 130, 1070, 1105]:
            self.line(x, y + 17, x + 20, y + 17, SKY, 2)

    def check(self, x, y, size=20, color=TEAL):
        self.path(
            f"M{x - size * 0.5} {y} l{size * 0.35} {size * 0.35} l{size * 0.7} -{size * 0.8}",
            stroke=color,
            sw=4,
        )

    def cross(self, x, y, size=15, color=ORANGE):
        self.line(x - size / 2, y - size / 2, x + size / 2, y + size / 2, color, 4)
        self.line(x - size / 2, y + size / 2, x + size / 2, y - size / 2, color, 4)

    def save(self):
        name = f"fig-{self.chapter}-{self.number:02d}-{self.slug}"
        path = ROOT / f"docs/images/ch{self.chapter}/{name}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700" role="img" aria-labelledby="title description">'
            + "".join(self.parts)
            + "</svg>\n"
        )
        return {
            "figure_id": f"Fig-{self.chapter}-{self.number:02d}",
            "title": self.title,
            "path": str(path.relative_to(ROOT)),
            "kind": "original editorial scene illustration",
            "format": "editable pure SVG",
            "license": "MIT",
            "description": self.description,
            "labels": self.labels,
            "groups": self.groups,
            "source": "Original artwork based on the fictional case in this chapter; no third-party assets",
            "contains_results": False,
        }


def paper(a, x, y, w, h, title="", lines=4, fill=WHITE, rotate=0):
    with a.group(f"paper-{len(a.groups)}", f"translate({x} {y}) rotate({rotate})"):
        a.path(f"M0 0 H{w - 24} L{w} 24 V{h} H0 Z", fill, INK, 2.5)
        a.path(f"M{w - 24} 0 V24 H{w}", CREAM, INK, 2)
        if title:
            a.text(15, 38, title, 22, weight=600)
        for i in range(lines):
            a.line(16, 64 + i * 22, w - 18 - (i % 2) * 20, 64 + i * 22, GRAY, 2)


def mug(a, x, y, color=ORANGE):
    a.path(
        f"M{x} {y} H{x + 42} V{y + 43} Q{x + 21} {y + 58} {x} {y + 43} Z",
        color,
        INK,
        2.5,
    )
    a.path(
        f"M{x + 42} {y + 8} C{x + 72} {y + 3} {x + 73} {y + 43} {x + 42} {y + 35}",
        stroke=INK,
        sw=3,
    )
    a.ellipse(x + 21, y, 21, 6, CREAM, INK, 2)
    a.path(
        f"M{x + 15} {y - 16} q-8 -10 0 -20 M{x + 30} {y - 13} q-8 -10 0 -20",
        stroke=GRAY,
        sw=2,
    )


def plant(a, x, y, s=1):
    with a.group(f"plant-{len(a.groups)}", f"translate({x} {y}) scale({s})"):
        a.path("M0 0 L12 60 H60 L72 0 Z", SAND, INK, 3)
        a.line(36, 0, 36, -100, TEAL, 4)
        a.path("M35 -45 C-30 -50 -20 -110 35 -70", PALETEAL, TEAL, 3)
        a.path("M36 -65 C90 -130 104 -60 36 -35", TEAL, INK, 2)
        a.path("M36 -95 C-10 -145 42 -175 42 -108", PALETEAL, TEAL, 3)


def desk(a, x, y, w=650):
    # A shallow perspective tabletop and tapered legs.
    a.path(f"M{x} {y} l25 -23 H{x + w + 25} l-25 23 Z", CREAM, INK, 3)
    a.rect(x, y, w, 18, SAND, INK, 3, 3)
    a.path(f"M{x + 34} {y + 18} l-12 172 h22 l14 -172 Z", DARKBLUE, INK, 3)
    a.path(f"M{x + w - 58} {y + 18} l14 172 h22 l-12 -172 Z", DARKBLUE, INK, 3)


def robot(a, x, y, s=1, pose="read", color=BLUE):
    # Coordinates are centered on the face; gestures use curved limbs.
    with a.group(f"assistant-{len(a.groups)}", f"translate({x} {y}) scale({s})"):
        a.ellipse(0, 262, 88, 15, SKY)
        a.path("M-45 188 L-48 245 Q-68 247 -73 258 H-13 L-11 190", DARKBLUE, INK, 3)
        a.path("M13 190 L18 249 H75 Q70 237 43 237 L45 187", DARKBLUE, INK, 3)
        a.path("M-62 79 Q0 56 62 79 L72 184 Q0 211 -72 184 Z", color, INK, 3)
        a.rect(-36, 108, 72, 60, CREAM, INK, 2.5, 10)
        for i in range(3):
            a.line(-22, 124 + i * 13, 22, 124 + i * 13, GRAY, 2)
        a.path("M-62 90 Q-92 87 -100 142 L-82 171", stroke=INK, sw=22)
        a.path("M-62 90 Q-92 87 -100 142 L-82 171", stroke=SKY, sw=15)
        if pose == "point":
            a.path("M63 94 Q102 109 117 63 L153 48", stroke=INK, sw=22)
            a.path("M63 94 Q102 109 117 63 L153 48", stroke=SKY, sw=15)
            a.circle(153, 48, 12, CREAM)
        elif pose == "hold":
            a.path("M62 94 Q103 120 114 80", stroke=INK, sw=22)
            a.path("M62 94 Q103 120 114 80", stroke=SKY, sw=15)
            a.circle(114, 80, 12, CREAM)
        else:
            a.path("M62 93 Q92 110 95 164 L72 177", stroke=INK, sw=22)
            a.path("M62 93 Q92 110 95 164 L72 177", stroke=SKY, sw=15)
        a.circle(-82, 171, 12, CREAM)
        a.line(0, -48, 0, -76, INK, 3)
        a.circle(0, -83, 8, ORANGE)
        a.rect(-79, -16, 17, 40, SAND, INK, 3, 7)
        a.rect(62, -16, 17, 40, SAND, INK, 3, 7)
        a.path("M-62 -40 Q0 -63 62 -40 V38 Q0 64 -62 38 Z", CREAM, INK, 3)
        a.rect(-48, -24, 96, 61, DARKBLUE, INK, 2.5, 21)
        a.ellipse(-20, 4, 6, 9, WHITE)
        a.ellipse(20, 4, 6, 9, WHITE)
        a.path("M-9 22 Q0 27 9 22", stroke=SKY, sw=2)
        a.line(-20, 49, -20, 65, INK, 3)
        a.line(20, 49, 20, 65, INK, 3)


def human(a, x, y, s=1, color=ORANGE, pose="point", hair="short", flip=False):
    with a.group(
        f"person-{len(a.groups)}", f"translate({x} {y}) scale({-s if flip else s} {s})"
    ):
        a.ellipse(0, 280, 76, 14, SKY)
        a.path("M-38 174 L-43 260 H-5 L7 177", DARKBLUE, INK, 3)
        a.path("M8 176 L20 260 H59 L42 169", DARKBLUE, INK, 3)
        a.path("M-43 254 Q-61 264 -61 274 H-2 L-5 254", INK, INK, 3)
        a.path("M20 254 L18 274 H83 Q78 260 59 254", INK, INK, 3)
        a.path("M-49 72 Q-5 50 41 72 L57 176 Q0 191 -56 174 Z", color, INK, 3)
        a.path("M-38 83 Q-74 100 -78 163 L-56 184", stroke=INK, sw=23)
        a.path("M-38 83 Q-74 100 -78 163 L-56 184", stroke=color, sw=17)
        a.circle(-56, 184, 10, PALEORANGE)
        if pose == "point":
            a.path("M39 85 Q69 103 85 68 L118 46", stroke=INK, sw=23)
            a.path("M39 85 Q69 103 85 68 L118 46", stroke=color, sw=17)
            a.circle(118, 46, 11, PALEORANGE)
            a.line(118, 46, 134, 37, PALEORANGE, 9)
        elif pose == "sign":
            a.path("M40 84 Q73 99 73 134 L121 145", stroke=INK, sw=23)
            a.path("M40 84 Q73 99 73 134 L121 145", stroke=color, sw=17)
            a.circle(121, 145, 10, PALEORANGE)
            a.line(126, 130, 119, 165, INK, 4)
        else:
            a.path("M41 82 Q77 117 63 176", stroke=INK, sw=23)
            a.path("M41 82 Q77 117 63 176", stroke=color, sw=17)
            a.circle(63, 176, 10, PALEORANGE)
        a.rect(-14, 35, 29, 35, PALEORANGE, INK, 2, 8)
        a.ellipse(0, 2, 35, 44, PALEORANGE, INK, 3)
        if hair == "long":
            a.path(
                "M-34 6 Q-52 -52 -6 -56 Q51 -58 41 25 L27 13 Q22 -22 10 -27 Q-6 -10 -34 6",
                DARKBLUE,
                INK,
                3,
            )
            a.path("M-30 14 Q-26 53 -45 57 Q-60 27 -34 -9", DARKBLUE, INK, 2)
        else:
            a.path(
                "M-35 -2 Q-50 -52 -10 -52 Q16 -68 37 -33 L38 -2 L21 -18 L11 -33 Q-11 -9 -35 -2",
                DARKBLUE,
                INK,
                3,
            )
        a.circle(10, 0, 2.3, INK, "none")
        a.path("M21 10 l-7 2 M7 25 q8 4 15 -2", stroke=INK, sw=2)
        a.path("M-11 71 l12 23 l14 -23", CREAM, INK, 2)


def book(a, x, y, w, h, title, fill=BLUE, rotate=0):
    with a.group(f"book-{len(a.groups)}", f"translate({x} {y}) rotate({rotate})"):
        a.path(f"M0 0 H{w} V{h} H0 Q-13 {h - 12} 0 {h - 24} Z", fill, INK, 3)
        a.rect(10, 0, 10, h - 23, fill, "none")
        a.line(18, 12, 18, h - 32, WHITE, 1.5)
        a.path(f"M0 {h - 23} H{w} V{h} H0 Q-12 {h - 11} 0 {h - 23}", CREAM, INK, 2.5)
        a.line(8, h - 12, w - 8, h - 12, GRAY, 1)
        for i, t in enumerate(title.split("|")):
            a.text(
                w / 2,
                50 + i * 31,
                t,
                24,
                INK if fill in {GRAY, SAND, PALETEAL} else WHITE,
                "middle",
                600,
            )


def lock(a, x, y, s=1):
    with a.group(f"lock-{len(a.groups)}", f"translate({x} {y}) scale({s})"):
        a.path("M10 20 V0 C10 -35 65 -35 65 0 V20", stroke=INK, sw=8)
        a.rect(0, 15, 76, 61, SAND, INK, 3, 10)
        a.circle(38, 39, 7, INK, "none")
        a.line(38, 44, 38, 57, INK, 5)


def gear(a, x, y, r=46, color=SAND, rotation=0):
    import math

    points = []
    for i in range(48):
        theta = 2 * math.pi * i / 48 + rotation
        rr = r if i % 4 in [1, 2] else r * 0.82
        points.append((x + rr * math.cos(theta), y + rr * math.sin(theta)))
    a.path(
        "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + " Z", color, INK, 2.5
    )
    a.circle(x, y, r * 0.34, WHITE, INK, 3)


def chair(a, x, y):
    a.path(f"M{x} {y} q-20 -120 30 -130 h45 q45 10 20 130", SKY, INK, 3)
    a.rect(x - 3, y, 110, 15, BLUE, INK, 3, 8)
    a.line(x + 50, y + 15, x + 50, y + 100, INK, 5)
    a.line(x + 50, y + 94, x + 5, y + 116, INK, 4)
    a.line(x + 50, y + 94, x + 99, y + 116, INK, 4)
    for cx in [x + 5, x + 99]:
        a.circle(cx, y + 117, 7, INK, "none")


def window(a, x, y, w=240, h=170):
    a.rect(x, y, w, h, LIGHT, SKY, 3, 36)
    a.ellipse(x + w * 0.7, y + h * 0.3, 22, 22, CREAM)
    a.path(
        f"M{x} {y + h - 40} Q{x + w * 0.3} {y + 40} {x + w * 0.5} {y + h - 50} Q{x + w * 0.75} {y + 60} {x + w} {y + h - 25} V{y + h} H{x} Z",
        SKY,
        "none",
    )
    a.line(x + w / 2, y, x + w / 2, y + h, WHITE, 5)
    a.line(x, y + h / 2, x + w, y + h / 2, WHITE, 5)


def calendar(a, x, y, label="本次", day="中午"):
    a.rect(x, y, 185, 158, WHITE, INK, 3, 9)
    a.path(
        f"M{x} {y + 38} V{y + 10} Q{x} {y} {x + 10} {y} H{x + 175} Q{x + 185} {y} {x + 185} {y + 10} V{y + 38} Z",
        ORANGE,
        INK,
        2,
    )
    for dx in [35, 150]:
        a.line(x + dx, y - 10, x + dx, y + 14, INK, 6)
    a.text(x + 92, y + 27, label, 21, WHITE, "middle", 600)
    a.text(x + 92, y + 92, day, 32, INK, "middle", 600)
    a.line(x + 35, y + 120, x + 150, y + 120, SAND, 2)
    a.text(x + 92, y + 144, "仅此会话", 17, INK, "middle")


def monitor(a, x, y, w=180, h=130, kind="text"):
    a.rect(x, y, w, h, DARKBLUE, INK, 3, 10)
    a.rect(x + 10, y + 10, w - 20, h - 28, LIGHT, "none", rx=4)
    if kind == "check":
        a.circle(x + w / 2, y + h / 2 - 10, 29, PALETEAL, TEAL, 2)
        a.check(x + w / 2, y + h / 2 - 10, 25, TEAL)
    else:
        for i in range(4):
            a.circle(x + 27, y + 30 + i * 18, 3, BLUE, "none")
            a.line(
                x + 40,
                y + 30 + i * 18,
                x + w - 22 - (i % 2) * 25,
                y + 30 + i * 18,
                GRAY,
                3,
            )
    a.path(
        f"M{x + w / 2 - 14} {y + h} l-5 28 h-25 M{x + w / 2 + 14} {y + h} l5 28 h25",
        stroke=INK,
        sw=3,
    )
    a.line(x + w / 2 - 45, y + h + 28, x + w / 2 + 45, y + h + 28, INK, 4)


def suitcase(a, x, y, s=1):
    with a.group(f"suitcase-{len(a.groups)}", f"translate({x} {y}) scale({s})"):
        a.path("M35 0 V-25 Q35 -35 48 -35 H77 Q88 -35 88 -25 V0", stroke=INK, sw=5)
        a.rect(0, 0, 125, 160, SAND, INK, 3, 15)
        a.line(30, 14, 30, 145, ORANGE, 3)
        a.line(95, 14, 95, 145, ORANGE, 3)
        a.rect(46, 34, 34, 47, WHITE, INK, 2, 4)
        a.line(54, 45, 73, 45, GRAY, 2)
        a.line(54, 56, 68, 56, GRAY, 2)
        for cx in [23, 102]:
            a.circle(cx, 166, 8, INK, "none")


manifest = []
# 14: A grounded task desk, where a tempting summary is less reliable than the clipboard.
a = Art(
    14,
    3,
    "task-desk-scene",
    "工作桌上的摘要与当前任务",
    "助手面对散落摘要便笺、待审批任务夹板和行李，强调当前任务事实不能由便笺替代。",
)
a.path(
    "M90 530 C45 310 130 112 390 120 C510 55 770 115 832 230 C1100 200 1185 465 1060 570 Z",
    LIGHT,
    "none",
)
a.ground()
window(a, 790, 105, 240, 166)
chair(a, 305, 470)
robot(a, 365, 282, 0.94, "point")
# Behind-desk task clipboard is prominent.
with a.group("current-task-clipboard", "translate(761 170) rotate(6)"):
    a.rect(0, 0, 260, 315, SAND, INK, 3, 14)
    a.rect(16, 17, 228, 280, WHITE, INK, 2, 6)
    a.rect(79, -10, 104, 35, DARKBLUE, INK, 2, 9)
    a.text(130, 77, "当前任务", 29, INK, "middle", 600)
    a.line(40, 101, 218, 101, SKY, 3)
    a.text(38, 142, "金额", 23)
    a.text(215, 142, "499 元", 23, anchor="end")
    a.text(38, 182, "批准", 23)
    a.text(215, 182, "待审批", 23, anchor="end")
    a.rect(41, 211, 177, 53, PALEORANGE, ORANGE, 2, 7)
    a.text(130, 246, "暂不提交", 24, INK, "middle", 600)
desk(a, 180, 474, 650)
# Desktop notebooks, small papers, cup; avoid connecting arrows.
paper(a, 195, 405, 130, 96, "摘要", 1, CREAM, -10)
mug(a, 662, 430, BLUE)
a.path("M404 459 Q468 432 530 455 V484 Q468 467 404 489 Z", CREAM, INK, 2.5)
a.path("M530 455 Q588 431 632 451 V482 Q580 463 530 484 Z", WHITE, INK, 2.5)
a.line(530, 455, 530, 484, INK, 2)
paper(a, 123, 237, 155, 106, "已批准？", 0, PALEORANGE, -12)
a.line(136, 308, 231, 288, ORANGE, 3)
paper(a, 549, 145, 128, 101, "省略条件", 1, WHITE, 10)
suitcase(a, 947, 437, 0.94)
a.text(956, 646, "出差申请", 21, INK, "middle")
manifest.append(a.save())

# 15: The one-trip calendar must not become the permanent profile.
a = Art(
    15,
    3,
    "memory-library-scene",
    "临时车票与长期偏好",
    "档案柜保留本人默认，墙上日历与车票只描述本次出行；人物和助手在同一阅读场景中检查范围。",
)
a.path("M80 565 V210 Q100 105 235 118 H990 Q1130 130 1105 320 V565 Z", CREAM, "none")
a.ground()
# Cabinet with visible material, not abstract data nodes.
with a.group("personal-memory-cabinet"):
    a.rect(99, 164, 325, 393, SKY, INK, 3, 10)
    a.rect(116, 180, 291, 105, WHITE, INK, 2, 4)
    for x, w, h, c in [
        (132, 39, 73, BLUE),
        (177, 32, 85, SAND),
        (216, 42, 78, TEAL),
        (268, 35, 82, ORANGE),
        (310, 76, 68, PALETEAL),
    ]:
        a.rect(x, 281 - h, w, h, c, INK, 2, 3)
        a.line(x + 8, 281 - h + 12, x + w - 8, 281 - h + 12, WHITE, 2)
    a.text(261, 147, "个人记忆", 26, INK, "middle", 600)
    for y, label in [(307, "情景 · 发生过什么"), (391, "语义 · 默认上午")]:
        a.rect(116, y, 291, 65, CREAM, INK, 2, 5)
        a.rect(233, y + 12, 53, 9, WHITE, INK, 2, 3)
        a.text(261, y + 48, label, 22, INK, "middle")
    a.rect(116, 475, 291, 64, WHITE, INK, 2, 5)
    a.text(261, 516, "程序 · 如何处理", 22, INK, "middle")
calendar(a, 812, 130, "本次出差", "中午")
human(a, 639, 285, 0.95, ORANGE, "point", "long")
robot(a, 914, 350, 0.75, "read")
suitcase(a, 442, 449, 0.87)
with a.group("current-trip-ticket", "translate(578 463) rotate(18)"):
    a.rect(-54, 0, 70, 82, WHITE, INK, 2.5, 4)
    a.text(-19, 31, "车票", 21, INK, "middle")
    a.line(-43, 45, 5, 45, GRAY, 2)
    a.line(-43, 58, -8, 58, GRAY, 2)
plant(a, 1061, 530, 0.65)
a.text(740, 641, "临时要求只属于本次旅程", 24, INK, "middle", 600)
manifest.append(a.save())

# 16: A researcher investigates the actual current policy, with a locked annex.
a = Art(
    16,
    3,
    "evidence-reading-scene",
    "把答案放回原始材料",
    "旧版政策退到后景，当前条款在放大镜下可读；上锁附件表现部门边界，而不是额外的答案。",
)
a.path(
    "M80 548 C28 344 90 175 296 128 C487 37 794 105 880 197 C1148 159 1192 468 1090 563 Z",
    LIGHT,
    "none",
)
a.ground()
# Rear shelf and annex.
a.line(830, 277, 1110, 277, INK, 5)
book(a, 853, 142, 118, 131, "部门 A|附件", GRAY, -5)
lock(a, 1002, 203, 0.8)
book(a, 113, 201, 195, 246, "住宿政策|旧版 · v1", GRAY, -8)
a.text(188, 474, "已被替代", 22, INK, "middle")
robot(a, 1033, 351, 0.72, "read")
desk(a, 245, 476, 659)
# Open book in foreground, literal printed rule not a schematic.
with a.group("open-current-policy"):
    a.path("M346 292 Q440 254 582 298 L582 509 Q448 474 346 510 Z", SKY, INK, 3)
    a.path("M582 298 Q704 252 835 292 L835 510 Q705 473 582 509 Z", CREAM, INK, 3)
    a.path("M358 303 Q449 273 570 308 L570 492 Q455 463 358 495 Z", WHITE, INK, 2)
    a.path("M594 308 Q710 272 823 303 L823 495 Q708 464 594 492 Z", WHITE, INK, 2)
    a.text(389, 340, "当前 · v2", 27, INK, weight=600)
    for y in [369, 390, 411, 432]:
        a.line(386, y, 543, y + 4, GRAY, 2)
    a.rect(625, 359, 165, 59, PALETEAL, "none", rx=8)
    a.text(706, 398, "500 元／晚", 25, INK, "middle", 600)
    a.line(582, 298, 582, 508, INK, 3)
# Magnifying glass is foreground but doesn't distort or duplicate evidence.
a.circle(701, 382, 87, "none", INK, 11)
a.circle(701, 382, 79, "none", BLUE, 3)
a.path("M761 444 L824 509", stroke=INK, sw=23)
a.path("M761 444 L824 509", stroke=SAND, sw=15)
a.path("M647 328 Q671 309 696 310", stroke=WHITE, sw=7)
mug(a, 278, 414, ORANGE)
manifest.append(a.save())

# 17: A repair bench illustrates a candidate tested on both task types.
a = Art(
    17,
    3,
    "repair-workbench-scene",
    "修好一处，也要检查其他地方",
    "助手把候选齿轮送到双项检测台，研究者观察原任务与保留任务；拒绝的零件留在托盘中。",
)
a.path(
    "M76 562 Q26 288 255 182 Q508 61 749 154 Q1047 83 1122 341 V565 Z", CREAM, "none"
)
a.ground()
# Pegboard and tools.
a.rect(461, 102, 371, 146, LIGHT, GRAY, 2, 16)
for x in range(487, 820, 36):
    for y in [125, 160, 195, 230]:
        a.circle(x, y, 2.5, GRAY, "none")
a.path(
    "M554 123 q-19 22 0 42 v53 h17 v-53 q17 -22 -1 -42 l-2 25 h-12 Z", SAND, INK, 2.5
)
a.path("M672 124 l32 0 v22 h-14 v73 h-16 v-73 h-2 Z", BLUE, INK, 2.5)
a.path("M755 139 l19 -17 l14 13 l-17 20 l-32 62 l-13 -8 Z", ORANGE, INK, 2.5)
robot(a, 269, 325, 0.9, "hold")
human(a, 993, 300, 0.9, TEAL, "sign", "long", flip=True)
desk(a, 352, 472, 572)
# Test fixture with two physical sockets, lever and feet.
a.path("M500 312 l38 -29 h308 l25 29 v136 H500 Z", SKY, INK, 3)
a.rect(518, 324, 335, 98, WHITE, INK, 2.5, 8)
a.line(686, 325, 686, 421, GRAY, 2)
for x, label in [(601, "原任务"), (769, "保留任务")]:
    a.circle(x, 365, 25, CREAM, INK, 3)
    a.path(f"M{x - 12} 362 h24 M{x} 350 v24", stroke=GRAY, sw=3)
    a.text(x, 410, label, 21, INK, "middle")
a.circle(584, 302, 7, TEAL, INK, 2)
a.circle(773, 302, 7, ORANGE, INK, 2)
a.line(842, 312, 870, 270, INK, 5)
a.circle(872, 266, 10, ORANGE)
a.rect(525, 449, 43, 24, DARKBLUE, INK, 2, 3)
a.rect(800, 449, 43, 24, DARKBLUE, INK, 2, 3)
gear(a, 394, 370, 55, ORANGE)
a.text(382, 286, "候选修复", 23, INK, "middle")
# Rejected parts in shallow tray in front.
a.path("M461 499 h242 l-23 59 H476 Z", PALEORANGE, INK, 2.5)
gear(a, 523, 528, 28, GRAY)
gear(a, 620, 530, 25, SAND)
a.cross(620, 530, 17, ORANGE)
a.text(583, 593, "未通过的候选保留记录", 21, INK, "middle")
manifest.append(a.save())

# 33: A cross-section office, people keep decision ownership.
a = Art(
    33,
    3,
    "enterprise-office-scene",
    "跨部门服务中的人机分工",
    "两部门拥有各自档案与访问边界；共享服务桌上，助手准备材料，人类负责人签核具体申请。",
)
a.ground()
# Building shell, windows and partition make actual rooms.
a.path(
    "M83 557 V165 Q83 142 106 142 H1094 Q1117 142 1117 165 V557",
    fill=CREAM,
    stroke=GRAY,
    sw=3,
)
a.path("M90 157 H569 V557 H90 Z", LIGHT, "none")
a.line(577, 143, 577, 345, GRAY, 8)
a.path("M553 145 L577 129 L602 145", fill=SAND, stroke=GRAY, sw=2)
window(a, 124, 183, 150, 118)
window(a, 911, 183, 150, 118)
a.text(315, 115, "部门 A", 29, INK, "middle", 600)
a.text(883, 115, "部门 B", 29, INK, "middle", 600)
# Cabinets preserve separate knowledge domains.
for x, c, label in [(134, SKY, "A"), (947, PALEORANGE, "B")]:
    a.rect(x, 342, 110, 208, c, INK, 3, 6)
    for yy in [365, 430, 495]:
        a.rect(x + 12, yy, 86, 46, WHITE, INK, 2, 4)
        a.line(x + 41, yy + 12, x + 69, yy + 12, GRAY, 3)
    a.text(x + 55, 328, label, 21, INK, "middle", 600)
lock(a, 142, 469, 0.44)
# Behind desk, official and requester; the agent sits in foreground.
human(a, 760, 314, 0.78, ORANGE, "sign", "long", flip=True)
human(a, 388, 332, 0.69, TEAL, "neutral")
desk(a, 337, 466, 545)
monitor(a, 364, 340, 140, 98)
paper(a, 691, 420, 107, 76, "申请", 0, WHITE, -4)
a.path("M816 428 h30 l-2 30 h-26 Z", ORANGE, INK, 2.5)
a.ellipse(831, 426, 19, 8, SAND, INK, 2)
a.path("M822 416 v-18 q10 -9 18 0 v18", SAND, INK, 2.5)
robot(a, 553, 456, 0.63, "read")
a.text(899, 678, "批准与责任由人承担", 23, INK, "middle", 600)
a.text(251, 678, "共享服务，保留数据边界", 22, INK, "middle")
manifest.append(a.save())

# 34: Three tangible engineering environments on a continuous workshop floor.
a = Art(
    34,
    5,
    "project-workshop-scene",
    "从桌面助手到协作工作室与运行平台",
    "同一间工程工作室里，单人助手、角色协作和持久运行机柜表现三项目的工程尺度，未使用流程箭头。",
)
a.path("M72 553 V214 Q72 178 106 178 H1095 Q1130 178 1130 214 V553 Z", LIGHT, "none")
a.ground()
a.line(100, 178, 1100, 178, GRAY, 3)
for x, t in [(230, "PRJ-1"), (597, "PRJ-2"), (978, "PRJ-3")]:
    a.line(x, 178, x, 142, INK, 2)
    a.path(f"M{x - 61} 112 H{x + 61} V149 H{x - 61} Z", CREAM, INK, 2)
    a.text(x, 139, t, 23, INK, "middle", 600)
# Small desk with single assistant.
robot(a, 165, 357, 0.62, "read")
desk(a, 103, 470, 280)
monitor(a, 231, 365, 124, 78)
a.path("M128 465 l22 -12 l48 8 v15 l-47 -5 Z", WHITE, INK, 2)
# Round collaboration table and paired assistants.
robot(a, 510, 327, 0.58, "point", TEAL)
human(a, 687, 308, 0.66, ORANGE, "sign", "long", flip=True)
a.ellipse(604, 470, 155, 40, SAND, INK, 3)
a.path("M464 469 v14 q140 80 281 0 v-14", CREAM, INK, 3)
a.path("M568 506 l-14 100 h20 l31 -87 l30 87 h22 l-17 -103", DARKBLUE, INK, 3)
paper(a, 561, 427, 74, 58, "证据", 0, WHITE, -5)
a.line(661, 448, 689, 443, BLUE, 3)
# Persistent platform: literal server rack, console and service engineer.
a.rect(900, 239, 158, 340, DARKBLUE, INK, 3, 10)
a.rect(911, 251, 136, 294, INK, GRAY, 2, 5)
for yy in [269, 334, 399, 464]:
    a.rect(922, yy, 114, 49, SKY, INK, 2, 4)
    for dx in [934, 947, 960]:
        a.circle(dx, yy + 13, 3, TEAL, "none")
    for dy in [yy + 28, yy + 34]:
        a.line(934, dy, 1020, dy, GRAY, 2)
a.rect(922, 555, 114, 12, GRAY, INK, 2, 2)
robot(a, 1090, 414, 0.48, "read")
a.path("M800 500 l47 -24 l43 24 v31 h-90 Z", SAND, INK, 3)
a.rect(799, 388, 90, 96, DARKBLUE, INK, 3, 6)
a.rect(809, 400, 70, 69, LIGHT, "none", rx=2)
a.check(844, 432, 22, TEAL)
a.line(843, 485, 843, 510, INK, 4)
a.text(239, 682, "证据与工具", 22, INK, "middle")
a.text(602, 682, "角色与验收", 22, INK, "middle")
a.text(975, 682, "持久运行与控制", 22, INK, "middle")
manifest.append(a.save())

# 35: An editorial landscape, open horizon instead of a triumphal finish.
a = Art(
    35,
    3,
    "long-horizon-expedition",
    "走向长程自主的研究旅程",
    "研究者和助手站在曲折山路起点，远方观测站、沿途检查点与未搭完的桥表现仍需验证的长程能力。",
)
a.ellipse(884, 174, 58, 58, CREAM)
a.path(
    "M65 378 L243 155 L402 349 L567 118 L772 352 L918 204 L1138 402 V595 H65 Z",
    SKY,
    "none",
)
a.path("M189 222 L243 155 L300 224 L270 210 L244 234 L220 211 Z", WHITE, "none")
a.path("M507 197 L567 118 L636 218 L596 202 L572 225 L543 196 Z", WHITE, "none")
a.path(
    "M60 485 Q242 302 445 422 Q642 274 854 400 Q1025 322 1142 458 V612 H60 Z",
    PALETEAL,
    "none",
)
a.path(
    "M67 613 Q315 557 425 539 Q589 507 603 475 Q614 449 548 439 Q481 428 588 401 Q701 372 801 389 Q878 405 932 350",
    stroke=SAND,
    sw=42,
)
a.path(
    "M67 613 Q315 557 425 539 Q589 507 603 475 Q614 449 548 439 Q481 428 588 401 Q701 372 801 389 Q878 405 932 350",
    stroke=WHITE,
    sw=2,
    stroke_dasharray="3 16",
)
# Distant observatory: a question to investigate, not a finish flag.
a.path("M916 307 Q953 244 992 307 Z", LIGHT, INK, 2)
a.rect(925, 307, 59, 42, WHITE, INK, 2, 3)
a.rect(949, 327, 15, 22, DARKBLUE, INK, 2, 2)
a.line(951, 275, 974, 249, INK, 3)
a.path("M969 243 l13 11 l18 -19 l-13 -12 Z", BLUE, INK, 2)
# Sketchy cloud obscures the beyond.
a.path(
    "M784 135 Q765 106 793 93 Q799 57 836 75 Q862 48 887 75 Q929 67 935 102 Q971 114 951 139 Z",
    LIGHT,
    "none",
)
# Checkpoint, half-built bridge and terrain objects.
a.line(701, 389, 701, 335, INK, 3)
a.path("M701 335 h55 l-11 15 l11 15 h-55 Z", ORANGE, INK, 2)
a.rect(500, 483, 29, 13, DARKBLUE, INK, 2, 3)
a.line(505, 496, 499, 517, INK, 2)
a.line(524, 496, 531, 516, INK, 2)
for x in [552, 573, 594]:
    a.path(f"M{x} 489 l16 -5 l8 13 l-17 5 Z", CREAM, INK, 2)
a.path("M1024 544 l35 -57 l34 57 Z", SAND, INK, 2)
a.path("M1046 600 l26 -39 l25 39 Z", SKY, INK, 2)
# Foreground explorers.
human(a, 236, 365, 0.89, ORANGE, "point", "long")
robot(a, 450, 432, 0.63, "read")
a.path("M181 449 q-44 -1 -38 61 l7 49 l33 -9 Z", TEAL, INK, 3)
a.path("M184 446 q-9 63 -4 101", stroke=INK, sw=3)
a.circle(199, 514, 15, CREAM, INK, 2)
a.path("M196 504 l9 9 l-10 11 l-5 -10 Z", BLUE, INK, 1.5)
a.path("M351 580 l42 -20 l41 12 l-45 23 Z", CREAM, INK, 2.5)
a.line(372, 580, 388, 569, GRAY, 2)
a.line(391, 584, 409, 575, GRAY, 2)
a.text(859, 594, "长期 · 迁移 · 责任", 25, INK, "middle", 600)
a.text(859, 631, "每一段路都需要新的证据", 22, INK, "middle")
manifest.append(a.save())

path = ROOT / "examples/figures/d_illustration_manifest.json"
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(f"Created {len(manifest)} original editable SVG illustrations")
