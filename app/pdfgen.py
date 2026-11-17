"""PDF report rendering (ReportLab). Works only from a snapshot dict - never touches the database -
so every stored report version can be regenerated exactly."""
import io

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Unicode fonts: use a TrueType family if the machine has one (so names such as "Dlamini-Nkosi", "Đorđević", "Müller" print
# correctly); otherwise fall back to the built-in Helvetica (Western European text only).
_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial Italic.ttf"),
]
FONT, FONT_B, FONT_I, UNICODE = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", False
for _r, _b, _i in _CANDIDATES:
    if all(Path(x).exists() for x in (_r, _b, _i)):
        try:
            pdfmetrics.registerFont(TTFont("FDPA-Sans", _r))
            pdfmetrics.registerFont(TTFont("FDPA-Sans-Bold", _b))
            pdfmetrics.registerFont(TTFont("FDPA-Sans-Italic", _i))
            FONT, FONT_B, FONT_I, UNICODE = "FDPA-Sans", "FDPA-Sans-Bold", "FDPA-Sans-Italic", True
            break
        except Exception:
            pass

NAVY, GREEN, BLUE = HexColor("#0b2a55"), HexColor("#1f9d3a"), HexColor("#2f6fd0")
LIGHT, RED, GREY, AMBER = HexColor("#eef3fa"), HexColor("#d64545"), HexColor("#6b7280"), HexColor("#d98c00")
LINE = HexColor("#c9d2de")
W, H = landscape(A4)
M = 18
FOOT = 24
HEAD = 74


def S(t):
    """Make text safe for the built-in PDF fonts (Latin-1/cp1252)."""
    if t is None:
        return ""
    if UNICODE:
        return str(t)
    return str(t).encode("cp1252", "replace").decode("cp1252")


def wrap(text, font, size, width):
    out = []
    for para in S(text).split("\n"):
        words, line = para.split(" "), ""
        for w in words:
            t = (line + " " + w).strip()
            if stringWidth(t, font, size) <= width or not line:
                line = t
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


# ------------------------------------------------------------------------------- blocks
class Block:
    def height(self, w):
        raise NotImplementedError

    def draw(self, c, x, y, w):          # y = top
        raise NotImplementedError


class KV(Block):
    def __init__(self, rows, size=8.5):
        self.rows, self.size = rows, size

    def _lw(self, w):
        lw = max([stringWidth(S(k), FONT, self.size) for k, _ in self.rows] + [30]) + 8
        return min(lw, w * 0.62)

    def height(self, w):
        vw = w - self._lw(w)
        return sum(max(1, len(wrap(v, FONT_B, self.size, vw))) * 11.5 for _, v in self.rows) + 2

    def draw(self, c, x, y, w):
        lw = self._lw(w)
        for k, v in self.rows:
            lines = wrap(v, FONT_B, self.size, w - lw)
            c.setFont(FONT, self.size)
            c.setFillColor(GREY)
            c.drawString(x, y - 9, S(k))
            c.setFont(FONT_B, self.size)
            muted = str(v) in ("Not collected", "N/A", "Unavailable")
            c.setFillColor(GREY if muted else NAVY)
            for i, ln in enumerate(lines):
                c.drawString(x + lw, y - 9 - i * 11.5, ln)
            y -= max(1, len(lines)) * 11.5


class Bullets(Block):
    def __init__(self, items, size=8.5, color=NAVY, mark="\u2022"):
        self.items, self.size, self.color, self.mark = [i for i in items if i], size, color, mark

    def height(self, w):
        if not self.items:
            return 12
        return sum(len(wrap(i, FONT, self.size, w - 12)) * (self.size + 2.5) + 2 for i in self.items)

    def draw(self, c, x, y, w):
        if not self.items:
            c.setFont(FONT_I, self.size)
            c.setFillColor(GREY)
            c.drawString(x, y - 9, "Nothing recorded.")
            return
        for it in self.items:
            lines = wrap(it, FONT, self.size, w - 12)
            c.setFillColor(GREEN)
            c.setFont(FONT_B, self.size)
            c.drawString(x, y - self.size - 0.5, "\u2022" if self.mark == "\u2022" else S(self.mark))
            c.setFillColor(self.color)
            c.setFont(FONT, self.size)
            for i, ln in enumerate(lines):
                c.drawString(x + 10, y - self.size - 0.5 - i * (self.size + 2.5), ln)
            y -= len(lines) * (self.size + 2.5) + 2


class Text(Block):
    def __init__(self, text, size=8.5, font=FONT, color=NAVY):
        self.text, self.size, self.font, self.color = text, size, font, color

    def height(self, w):
        return len(wrap(self.text, self.font, self.size, w)) * (self.size + 2.5) + 2

    def draw(self, c, x, y, w):
        c.setFont(self.font, self.size)
        c.setFillColor(self.color)
        for i, ln in enumerate(wrap(self.text, self.font, self.size, w)):
            c.drawString(x, y - self.size - i * (self.size + 2.5), ln)


class Table(Block):
    def __init__(self, headers, rows, fracs=None, size=7.8, align=None):
        self.headers, self.rows, self.size = headers, rows, size
        self.fracs = fracs or [1 / len(headers)] * len(headers)
        self.align = align or ["l"] + ["c"] * (len(headers) - 1)

    def height(self, w):
        return 13 * (len(self.rows) + 1) + 2

    def draw(self, c, x, y, w):
        xs = [x]
        for f in self.fracs:
            xs.append(xs[-1] + f * w)
        c.setFillColor(LIGHT)
        c.rect(x, y - 12, w, 12, fill=1, stroke=0)
        c.setFont(FONT_B, self.size)
        c.setFillColor(NAVY)
        for i, h in enumerate(self.headers):
            self._cell(c, S(h), xs[i], xs[i + 1], y - 9, self.align[i])
        y -= 12
        for r in self.rows:
            for i, v in enumerate(r):
                s = S(v)
                muted = s in ("Not collected", "N/A", "Unavailable", "-")
                c.setFont(FONT_I if muted else FONT, self.size)
                c.setFillColor(GREY if muted else NAVY)
                while stringWidth(s, FONT, self.size) > (xs[i + 1] - xs[i] - 4) and len(s) > 3:
                    s = s[:-2]
                self._cell(c, s, xs[i], xs[i + 1], y - 9, self.align[i])
            c.setStrokeColor(LINE)
            c.setLineWidth(0.3)
            c.line(x, y - 13, x + w, y - 13)
            y -= 13

    @staticmethod
    def _cell(c, s, x0, x1, y, al):
        if al == "c":
            c.drawCentredString((x0 + x1) / 2, y, s)
        elif al == "r":
            c.drawRightString(x1 - 2, y, s)
        else:
            c.drawString(x0 + 2, y, s)


class Tiles(Block):
    def __init__(self, tiles):
        self.tiles = tiles

    def height(self, w):
        return 50

    def draw(self, c, x, y, w):
        n = len(self.tiles)
        gap = 5
        tw = (w - gap * (n - 1)) / n
        for i, (label, value, sub) in enumerate(self.tiles):
            tx = x + i * (tw + gap)
            c.setFillColor(LIGHT)
            c.setStrokeColor(LINE)
            c.roundRect(tx, y - 48, tw, 48, 3, fill=1, stroke=1)
            c.setFont(FONT_B, 7.5)
            c.setFillColor(NAVY)
            c.drawCentredString(tx + tw / 2, y - 10, S(label))
            v = S(value)
            muted = v in ("Not collected", "N/A")
            c.setFont(FONT_I if muted else FONT_B, 10 if muted else 18)
            c.setFillColor(GREY if muted else GREEN)
            c.drawCentredString(tx + tw / 2, y - 31, v)
            if sub:
                c.setFont(FONT, 6.5)
                c.setFillColor(GREY)
                c.drawCentredString(tx + tw / 2, y - 42, S(sub)[:40])


class Bars(Block):
    """Mirrored comparison bars: rows of (label, home_text, away_text, home_num, away_num)."""
    def __init__(self, rows, home, away):
        self.rows, self.home, self.away = rows, home, away

    def height(self, w):
        return 14 * len(self.rows) + 16

    def draw(self, c, x, y, w):
        c.setFont(FONT_B, 8)
        c.setFillColor(NAVY)
        c.drawString(x, y - 9, S(self.home)[:28])
        c.drawRightString(x + w, y - 9, S(self.away)[:28])
        y -= 16
        mid, half = x + w / 2, w * 0.27
        for label, ht, at, hn, an in self.rows:
            c.setFont(FONT, 7.8)
            c.setFillColor(NAVY)
            c.drawCentredString(mid, y - 8, S(label))
            c.setFont(FONT_B, 8)
            for txt, side in ((ht, "l"), (at, "r")):
                muted = txt in ("Not collected", "N/A")
                c.setFont(FONT_I if muted else FONT_B, 7.5 if muted else 8)
                c.setFillColor(GREY if muted else NAVY)
                (c.drawString(x, y - 8, S(txt)) if side == "l" else c.drawRightString(x + w, y - 8, S(txt)))
            if hn is not None and an is not None and (hn + an) > 0:
                tot = hn + an
                bw = w * 0.2
                c.setFillColor(LIGHT)
                c.rect(x + w * 0.17, y - 10, bw, 7, fill=1, stroke=0)
                c.rect(x + w - w * 0.17 - bw, y - 10, bw, 7, fill=1, stroke=0)
                c.setFillColor(GREEN)
                c.rect(x + w * 0.17 + bw * (1 - hn / tot), y - 10, bw * hn / tot, 7, fill=1, stroke=0)
                c.setFillColor(BLUE)
                c.rect(x + w - w * 0.17 - bw, y - 10, bw * an / tot, 7, fill=1, stroke=0)
            y -= 14


class Img(Block):
    def __init__(self, png, max_h=150):
        self.png, self.max_h = png, max_h
        r = ImageReader(io.BytesIO(png))
        self.iw, self.ih = r.getSize()

    def _dims(self, w):
        s = min(w / self.iw, self.max_h / self.ih)
        return self.iw * s, self.ih * s

    def height(self, w):
        return self._dims(w)[1] + 2

    def draw(self, c, x, y, w):
        dw, dh = self._dims(w)
        c.drawImage(ImageReader(io.BytesIO(self.png)), x + (w - dw) / 2, y - dh, dw, dh)


class Timeline(Block):
    def __init__(self, events, duration=90):
        self.events, self.duration = events, duration

    def height(self, w):
        return 62

    def draw(self, c, x, y, w):
        d = max(self.duration, max([e["minute"] for e in self.events if e.get("minute") is not None] + [self.duration]))
        ax = y - 30
        c.setStrokeColor(NAVY)
        c.setLineWidth(2)
        c.line(x + 6, ax, x + w - 6, ax)
        c.setFont(FONT, 6.5)
        c.setFillColor(GREY)
        for mnt in range(0, int(d) + 1, 15):
            px = x + 6 + (w - 12) * mnt / d
            c.line(px, ax - 3, px, ax + 3)
            c.drawCentredString(px, ax - 11, f"{mnt}'")
        col = {"goal": GREEN, "own_goal": GREEN, "penalty": GREEN, "card_y": AMBER, "card_r": RED, "sub": BLUE}
        for e in self.events:
            if e.get("minute") is None:
                continue
            px = x + 6 + (w - 12) * e["minute"] / d
            k = e["kind"]
            c.setFillColor(col.get(k, NAVY))
            c.setStrokeColor(col.get(k, NAVY))
            if k in ("card_y", "card_r"):
                c.rect(px - 2.5, ax + 6, 5, 7, fill=1, stroke=0)
            elif k == "sub":
                c.setLineWidth(1)
                c.line(px, ax + 5, px, ax + 13)
            else:
                c.circle(px, ax + 10, 3.5, fill=1, stroke=0)
            c.setFont(FONT, 6)
            c.setFillColor(NAVY)
            c.drawCentredString(px, ax + 17, S(e.get("short", ""))[:14])


class Note(Block):
    def __init__(self, text):
        self.t = Text(text, 7.5, FONT_I, GREY)

    def height(self, w):
        return self.t.height(w)

    def draw(self, c, x, y, w):
        self.t.draw(c, x, y, w)


# ------------------------------------------------------------------------------- page engine
class Doc:
    def __init__(self, snap, watermark=None):
        self.snap, self.wm = snap, watermark
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=landscape(A4))
        self.c.setTitle(S(snap["title"]))
        self.c.setAuthor(S(snap.get("analyst", "")))
        self.page = 0
        self.y = 0
        self.new_page()

    # ---- decorations
    def logo(self, x, y, s):
        c = self.c
        c.setFillColor(white)
        c.circle(x + s * 0.55, y + s * 0.55, s * 0.42, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.circle(x + s * 0.55, y + s * 0.55, s * 0.16, fill=1, stroke=0)
        for i, hh in enumerate((0.25, 0.4, 0.58)):
            c.setFillColor(GREEN)
            c.rect(x + s * (0.02 + i * 0.13), y + s * 0.02, s * 0.1, s * hh, fill=1, stroke=0)

    def header(self):
        c, s = self.c, self.snap
        c.setFillColor(NAVY)
        c.rect(0, H - HEAD, W, HEAD, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.rect(0, H - HEAD - 2.5, W, 2.5, fill=1, stroke=0)
        self.logo(M, H - HEAD + 12, 48)
        c.setFillColor(white)
        c.setFont(FONT_B, 15)
        c.drawString(M + 56, H - 28, "FOOTBALL")
        c.setFont(FONT_B, 7.6)
        c.drawString(M + 56, H - 40, "DATA AND PERFORMANCE")
        c.drawString(M + 56, H - 50, "ANALYSIS COMPANY")
        c.setFont(FONT_I, 7)
        c.drawString(M + 56, H - 62, S(s["tagline"]))
        c.setFont(FONT_B, 14)
        c.drawCentredString(W / 2 + 20, H - 27, S(s["header_title"]).upper())
        c.setFont(FONT_B, 12)
        c.drawCentredString(W / 2 + 20, H - 45, S(s["header_main"]))
        c.setFont(FONT, 8.5)
        c.drawCentredString(W / 2 + 20, H - 60, S(s["header_sub"]))
        c.setFont(FONT, 7.5)
        yy = H - 20
        for k, v in s["header_meta"]:
            c.setFillColor(HexColor("#9fb3d1"))
            c.drawString(W - 215, yy, S(k))
            c.setFillColor(white)
            c.drawString(W - 165, yy, S(v)[:36])
            yy -= 11

    def footer(self):
        c, s = self.c, self.snap
        c.setFillColor(NAVY)
        c.rect(0, 0, W, FOOT, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT, 6.5)
        c.drawString(M, 9, S(f"{s['company']} | {s['report_kind']} | v{s.get('version', 'draft')}"))
        c.drawCentredString(W * 0.68, 9, S(s.get("confidential_short", "Confidential")))
        c.drawRightString(W - M, 9, f"Page {self.page}")

    def watermark(self):
        if not self.wm:
            return
        c = self.c
        c.saveState()
        c.setFillColor(HexColor("#d64545"))
        c.setFillAlpha(0.10)
        c.setFont(FONT_B, 90)
        c.translate(W / 2, H / 2 - 20)
        c.rotate(25)
        c.drawCentredString(0, 0, S(self.wm))
        c.restoreState()

    def new_page(self):
        if self.page:
            self.watermark()
            self.footer()
            self.c.showPage()
        self.page += 1
        self.header()
        self.y = H - HEAD - 8
        if self.snap.get("data_status") == "provisional":
            self.c.setFillColor(AMBER)
            self.c.rect(M, self.y - 14, W - 2 * M, 14, fill=1, stroke=0)
            self.c.setFillColor(white)
            self.c.setFont(FONT_B, 8)
            self.c.drawCentredString(W / 2, self.y - 10, "PROVISIONAL DATA - this report uses match data that has not been fully validated")
            self.y -= 20

    # ---- panels
    def row(self, panels, min_h=0):
        """panels: list of (frac, title, [blocks])."""
        gap = 7
        usable = W - 2 * M - gap * (len(panels) - 1)
        tot = sum(p[0] for p in panels)
        widths = [usable * p[0] / tot for p in panels]
        heights = []
        for (f, title, blocks), w in zip(panels, widths):
            heights.append(18 + 6 + sum(b.height(w - 12) + 3 for b in blocks) + 4)
        rh = max(max(heights), min_h)
        if self.y - rh < FOOT + 6:
            self.new_page()
        x = M
        c = self.c
        for (f, title, blocks), w in zip(panels, widths):
            c.setFillColor(white)
            c.setStrokeColor(NAVY)
            c.setLineWidth(0.8)
            c.rect(x, self.y - rh, w, rh, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.rect(x, self.y - 15, w, 15, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont(FONT_B, 8.5)
            c.drawString(x + 6, self.y - 11, S(title).upper())
            yy = self.y - 21
            for b in blocks:
                b.draw(c, x + 6, yy, w - 12)
                yy -= b.height(w - 12) + 3
            x += w + gap
        self.y -= rh + 7

    def finish(self):
        self.watermark()
        self.footer()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


# ------------------------------------------------------------------------------- report builders
def _v(d, key, suffix=""):
    """Format a stored metric dict from the snapshot."""
    m = d.get(key)
    if m is None:
        return "N/A"
    if m["status"] == "not_collected":
        return "Not collected"
    if m["status"] == "na" or m["value"] is None:
        return "N/A"
    x = m["value"]
    s = f"{x:.1f}" if isinstance(x, float) else str(int(x))
    return s + suffix + ("*" if m["status"] == "partial" else "")


def _num(d, key):
    m = d.get(key)
    return m["value"] if m and m["status"] in ("ok", "partial") and m["value"] is not None else None


def _sources_panel(s):
    rows = [("Event source", s.get("source_name", "Not recorded")), ("Data status", s["data_status"].capitalize()),
            ("Confidence", s.get("confidence", "-"))]
    blocks = [KV(rows)]
    if s.get("quality"):
        blocks.append(Bullets(s["quality"], 7.8, GREY))
    blocks.append(Note("* partial: collected in only some matches. 'Not collected' = event category was not recorded for this match."))
    return (1, "Data sources and confidence", blocks)


def build_player(doc, s):
    p, st, t = s["player"], s["stats"], s["team_stats"]
    a = s["appearance"]
    mins = _v(st, "minutes")
    min_sub = ""
    if a.get("role") == "substitute" and a.get("sub_on_minute") is not None:
        min_sub = f"(from {a['sub_on_minute']}')"
    elif a.get("sub_off_minute") is not None:
        min_sub = f"(off at {a['sub_off_minute']}')"
    rating = s["input"].get("rating")
    tiles = [("Minutes played", mins, min_sub), ("Goals", _v(st, "goals"), ""), ("Assists", _v(st, "assists"), ""),
             ("Goals per 90", _v(st, "goals_per90"), "N/A if minutes unknown")]
    contrib = [Tiles(tiles)]
    if rating is not None:
        contrib.append(Text(f"Analyst assessment: {rating:.1f} / 10  (analyst opinion - see rating method)", 9, FONT_B, GREEN))
        if s["input"].get("rating_justification"):
            contrib.append(Text(s["input"]["rating_justification"], 7.8))
    else:
        contrib.append(Text("No analyst rating has been given for this match.", 8, FONT_I, GREY))
    prof = [("Name", p["name"]), ("Position", p["position"] or "Not recorded"), ("Club / team", p["team"] or "Not recorded"),
            ("Shirt number", str(a.get("shirt") or p.get("shirt") or "Not recorded")), ("Nationality", p["nationality"] or "Not recorded")]
    if p.get("dob"):
        prof.append(("Date of birth", p["dob"]))
    prof += [("Profile status", (p["verification"] or "").replace("_", " ").capitalize()),
             ("Source", p["source"] or "Not recorded"), ("Last verified", p["last_verified"] or "Not recorded")]
    key_ev = [f"{e['minute']}'  {e['text']}" for e in s["player_events"] if e["kind"] in ("goal", "penalty", "sub", "card_y", "card_r", "own_goal")]
    mt = s["match"]
    doc.row([(0.9, "Player profile", [KV(prof)]), (1.35, "Match contribution", contrib),
             (1.0, "Key match events", [Bullets(key_ev or ["No key events recorded for this player."])])])
    overview = [("Final score", f"{mt['home']} {mt['home_score']} - {mt['away_score']} {mt['away']}" if mt["home_score"] is not None else "Not recorded"),
                ("Competition", mt["competition"] or "-"), ("Venue", mt["venue"] or "-"),
                ("Possession", f"{_v(t['home'], 'possession', '%')} - {_v(t['away'], 'possession', '%')}"),
                ("Total shots", f"{_v(t['home'], 'shots')} - {_v(t['away'], 'shots')}"),
                ("Shots on target", f"{_v(t['home'], 'shots_on_target')} - {_v(t['away'], 'shots_on_target')}"),
                ("Corners", f"{_v(t['home'], 'corners')} - {_v(t['away'], 'corners')}"),
                ("Fouls", f"{_v(t['home'], 'fouls')} - {_v(t['away'], 'fouls')}")]
    att = Table(["Attacking and passing", "Value", "Per 90"], [
        ["Shots", _v(st, "shots"), _v(st, "shots_per90")], ["Shots on target", _v(st, "shots_on_target"), _v(st, "shots_on_target_per90")],
        ["Shot accuracy", _v(st, "shot_accuracy", "%"), "-"], ["Passes attempted", _v(st, "passes_attempted"), _v(st, "passes_attempted_per90")],
        ["Passes completed", _v(st, "passes_completed"), "-"], ["Pass completion", _v(st, "pass_completion", "%"), "-"],
        ["Key passes", _v(st, "key_passes"), _v(st, "key_passes_per90")], ["Crosses", _v(st, "crosses"), "-"],
        ["Dribbles / carries", _v(st, "dribbles"), "-"]], [0.5, 0.25, 0.25])
    dfn = Table(["Defensive contribution", "Value", "Per 90"], [
        ["Tackles", _v(st, "tackles"), _v(st, "tackles_per90")], ["Interceptions", _v(st, "interceptions"), _v(st, "interceptions_per90")],
        ["Clearances", _v(st, "clearances"), _v(st, "clearances_per90")], ["Blocks", _v(st, "blocks"), _v(st, "blocks_per90")],
        ["Recoveries", _v(st, "recoveries"), _v(st, "recoveries_per90")], ["Duels won", _v(st, "duels_won"), "-"],
        ["Aerial duels won", _v(st, "aerial_duels_won"), "-"], ["Fouls committed", _v(st, "fouls"), "-"],
        ["Yellow / red cards", f"{_v(st, 'yellow_cards')} / {_v(st, 'red_cards')}", "-"]], [0.5, 0.25, 0.25])
    doc.row([(0.9, "Match overview (team)", [KV(overview)]), (1.2, "Attacking and passing statistics", [att]),
             (1.2, "Defensive contribution", [dfn])])
    sp = KV([("Set pieces taken", _v(st, "set_pieces_taken")), ("Corners taken", _v(st, "corners")),
             ("Free kicks taken", _v(st, "free_kicks")), ("Goals from set pieces", _v(st, "goals_from_set_pieces")),
             ("Assists from set pieces", _v(st, "assists_from_set_pieces")), ("Penalties scored", _v(st, "penalties_scored"))])
    tl = [Timeline(s["timeline"], s["match"]["duration"]), Note("Green = goal, amber/red = card, blue = substitution.")]
    row2 = [(1.0, "Set-piece contribution", [sp]), (1.9, "Match timeline", tl)]
    if s.get("shot_map_png"):
        row2.append((1.0, "Shot map", [Img(s["shot_map_png"], 120)]))
    doc.row(row2)
    if s.get("heat_png"):
        doc.row([(1, "Heat map (located actions)", [Img(s["heat_png"], 150), Note("Density of this player's recorded, located actions - not tracking data.")])])
    video = s.get("video", [])
    vblocks = [Bullets([f"{v['title']} - {v['start']}s" + (f" ({v['category']})" if v['category'] else "") + (f": {v['notes']}" if v['notes'] else "") for v in video])] \
        if video else [Text("No permitted video evidence is attached to this report.", 8, FONT_I, GREY)]
    inp = s["input"]
    doc.row([(1.3, "Analyst observations (opinion)", [Bullets(inp.get("observations", []))]),
             (1, "Strengths demonstrated", [Bullets(inp.get("strengths", []))]),
             (1, "Development areas", [Bullets(inp.get("development", []))])])
    doc.row([(1, "Training priorities", [Bullets(inp.get("training", []))]),
             (1, "Recommendations for the next match", [Bullets(inp.get("next_match", []))]),
             (1, "Video evidence", vblocks)])
    doc.row([_sources_panel(s),
             (1.4, "Report details", [KV([("Analyst", s["analyst"]), ("Report date", s["report_date"]), ("Client", s["client"] or "Not assigned"),
                                          ("Rating method", "Documented rubric - analyst judgement")]),
                                      Text(s["confidentiality"], 7.5, FONT_I, GREY)])])


def _team_table(s, side_keys):
    t = s["team_stats"]
    rows = []
    spec = [("Possession", "possession", "%"), ("Total shots", "shots", ""), ("Shots on target", "shots_on_target", ""),
            ("Shot accuracy", "shot_accuracy", "%"), ("Corners", "corners", ""), ("Fouls", "fouls", ""),
            ("Yellow cards", "yellow_cards", ""), ("Red cards", "red_cards", ""), ("Passes attempted", "passes_attempted", ""),
            ("Pass completion", "pass_completion", "%"), ("Key passes", "key_passes", ""), ("Crosses", "crosses", ""),
            ("Tackles", "tackles", ""), ("Interceptions", "interceptions", ""), ("Clearances", "clearances", ""), ("Recoveries", "recoveries", "")]
    for label, key, suf in spec:
        rows.append((label, [_v(t[sk], key, suf) for sk in side_keys], [_num(t[sk], key) for sk in side_keys]))
    return rows


def build_match(doc, s, focus=None):
    mt, t = s["match"], s["team_stats"]
    inp = s["input"]
    both = focus is None
    score = f"{mt['home_score']} - {mt['away_score']}" if mt["home_score"] is not None else "Score not recorded"
    ov = [Text(f"{mt['home']}   {score}   {mt['away']}", 12, FONT_B),
          KV([("Competition", mt["competition"] or "-"), ("Date", mt["date"]), ("Venue", mt["venue"] or "-"),
              ("Attendance", str(mt["attendance"]) if mt["attendance"] else "Not recorded"), ("Match length", f"{mt['duration']} min")])]
    if both:
        stats_block = Bars([(l, v[0], v[1], n[0], n[1]) for l, v, n in _team_table(s, ["home", "away"])], mt["home"], mt["away"])
    else:
        key = "home" if focus == mt["home_id"] else "away"
        name = mt["home"] if key == "home" else mt["away"]
        stats_block = Table(["Statistic", name], [[l, v[0]] for l, v, n in _team_table(s, [key])], [0.6, 0.4])
    ev_lines = [f"{e['minute']}'  {e['text']}" for e in s["match_events"] if (both or e.get("team_id") == focus or e["kind"] == "goal")]
    doc.row([(1, "Match overview", ov), (1.5, "Match statistics" if both else "Team statistics", [stats_block]),
             (1.1, "Match events", [Bullets(ev_lines or ["No goals, cards or substitutions recorded."], 8)])])
    plist = [r for r in s["player_table"] if both or r["team_id"] == focus]
    hdr = ["Player", "Team", "Min", "G", "A", "Sh", "Pass", "Pass %", "KP", "Tkl", "Int"]
    prow = [[r["name"], r["team"][:14], r["min"], r["g"], r["a"], r["sh"], r["pass"], r["passpct"], r["kp"], r["tkl"], r["int"]] for r in plist]
    doc.row([(1.6, "Player contributions", [Table(hdr, prow[:30], [0.26, 0.17, 0.07, 0.05, 0.05, 0.06, 0.07, 0.09, 0.06, 0.06, 0.06], 7.2)]),
             (1, "Timeline", [Timeline(s["timeline"], mt["duration"]), Note("Green = goal, amber/red = card, blue = substitution.")])])
    adv = []
    if s.get("shot_map_png"):
        adv.append((1, "Shot map", [Img(s["shot_map_png"], 150)]))
    else:
        adv.append((1, "Shot map", [Note("Not available: shot coordinates were not collected.")]))
    if s.get("heat_png"):
        adv.append((1, "Heat maps (located actions)", [Img(s["heat_png"], 140), Note("Density of recorded, located actions - not tracking data.")]))
    if s.get("net_png"):
        adv.append((1, "Passing networks", [Img(s["net_png"], 140), Note("Completed passes with a recorded receiver; line width = number of passes.")]))
    if adv:
        doc.row(adv)
    doc.row([(1, "Key insights (analyst)", [Bullets(inp.get("insights", []))]),
             (1, "Tactical observations", [Bullets(inp.get("tactical", []))]),
             (1, "Strengths", [Bullets(inp.get("strengths", []))]),
             (1, "Weaknesses", [Bullets(inp.get("weaknesses", []))])])
    doc.row([(1, "Training priorities", [Bullets(inp.get("training", []))]),
             (1, "Recommendations for future matches", [Bullets(inp.get("next_match", []))]),
             (1, "Set pieces and key incidents", [Bullets(inp.get("incidents", []))])])
    doc.row([_sources_panel(s),
             (1.4, "Report details", [KV([("Analyst", s["analyst"]), ("Report date", s["report_date"]), ("Client", s["client"] or "Not assigned")]),
                                      Text(s["confidentiality"], 7.5, FONT_I, GREY)])])


def build_scouting(doc, s):
    sc, p = s["scouting"], s["player"]
    prof = [("Name", p["name"]), ("Position / role", sc["position_role"] or p["position"] or "Not recorded"), ("Club / team", p["team"] or "Not recorded"),
            ("Nationality", p["nationality"] or "Not recorded"), ("Profile status", (p["verification"] or "").replace("_", " ").capitalize()),
            ("Source", p["source"] or "Not recorded")]
    basis = [("Observation date", sc["date"] or "Not recorded"), ("Matches observed", str(len(sc["matches"]))),
             ("Sample size", f"{len(sc['matches'])} match(es)"), ("Confidence", sc["confidence"].capitalize())]
    doc.row([(1, "Player profile", [KV(prof)]), (1, "Basis of assessment", [KV(basis), Bullets(sc["matches"], 8)]),
             (1.2, "Recorded facts", [Text(sc["facts"] or "No factual evidence recorded.", 8.3), Note("Facts are observations that can be checked against the match record or video.")])])
    doc.row([(1, "Technical strengths (opinion)", [Text(sc["technical"] or "-", 8.3)]),
             (1, "Tactical strengths (opinion)", [Text(sc["tactical"] or "-", 8.3)]),
             (1, "Development areas (opinion)", [Text(sc["development"] or "-", 8.3)]),
             (1, "Decision-making (opinion)", [Text(sc["decision"] or "-", 8.3)])])
    vid = [Bullets(s.get("video_lines", []))] if s.get("video_lines") else [Text("No permitted video references.", 8, FONT_I, GREY)]
    doc.row([(1.4, "Recommendation (opinion)", [Text(sc["recommendation"] or "-", 8.5, FONT_B)]), (1, "Video references", vid)])
    doc.row([(1, "Data sources and confidence", [KV([("Confidence level", sc["confidence"].capitalize()), ("Sample", f"{len(sc['matches'])} match(es)")]),
                                                  Note("Scouting assessments are analyst opinion. Small samples carry low confidence.")]),
             (1.4, "Report details", [KV([("Analyst", s["analyst"]), ("Report date", s["report_date"]), ("Client", s["client"] or "Not assigned")]),
                                      Text(s["confidentiality"], 7.5, FONT_I, GREY)])])


def render(snap, watermark=None):
    """Return PDF bytes for a snapshot."""
    snap = dict(snap)          # never mutate the stored snapshot
    import base64
    for src, dst in (("shot_map_b64", "shot_map_png"), ("heat_b64", "heat_png"), ("net_b64", "net_png")):
        if snap.get(src) and not snap.get(dst):
            snap[dst] = base64.b64decode(snap[src])
    doc = Doc(snap, watermark)
    kind = snap["report_type"]
    if kind == "player":
        build_player(doc, snap)
    elif kind == "match":
        build_match(doc, snap, None)
    elif kind == "team":
        build_match(doc, snap, snap["match"]["focus_team_id"])
    elif kind == "scouting":
        build_scouting(doc, snap)
    else:
        raise ValueError("unknown report type")
    return doc.finish()
