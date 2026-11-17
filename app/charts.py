"""Charts drawn only from collected data. Missing categories are omitted, never plotted as zero."""
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle

NAVY, GREEN, BLUE, RED, GREY = "#0b2a55", "#1f9d3a", "#2f6fd0", "#d64545", "#c9d2de"


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def team_comparison(rows, home_name, away_name, title=None):
    """rows: [(label, home_value, away_value)] with only available numeric values."""
    rows = [r for r in rows if r[1] is not None and r[2] is not None]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 0.42 * len(rows) + 0.9))
    ys = list(range(len(rows)))[::-1]
    for y, (label, h, a) in zip(ys, rows):
        tot = (h + a) or 1
        ax.barh(y, -h / tot, color=GREEN, height=0.55)
        ax.barh(y, a / tot, color=BLUE, height=0.55)
        ax.text(-1.04, y, f"{h:g}", ha="right", va="center", fontsize=9, color=NAVY, fontweight="bold")
        ax.text(1.04, y, f"{a:g}", ha="left", va="center", fontsize=9, color=NAVY, fontweight="bold")
        ax.text(0, y + 0.42, label, ha="center", va="center", fontsize=8, color="#444")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.axis("off")
    ax.set_title(f"{home_name}   vs   {away_name}" if not title else title, fontsize=10, color=NAVY, fontweight="bold")
    return _png(fig)


def draw_pitch(ax):
    ax.add_patch(Rectangle((-2, -2), 104, 104, fc="#2e8b45", ec="none", zorder=0))       # grass (axis is off, so draw it)
    ax.add_patch(Rectangle((0, 0), 100, 100, fill=False, ec="white", lw=1.2))
    ax.plot([50, 50], [0, 100], color="white", lw=1)
    ax.add_patch(plt.Circle((50, 50), 9, fill=False, ec="white", lw=1))
    for x0 in (0, 83):
        ax.add_patch(Rectangle((x0, 21), 17, 58, fill=False, ec="white", lw=1))
    for x0 in (0, 94):
        ax.add_patch(Rectangle((x0, 37), 6, 26, fill=False, ec="white", lw=1))
    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    ax.set_aspect("auto")
    ax.set_facecolor("#2e8b45")
    ax.axis("off")


def shot_map(events, team_id, title):
    """events: dicts with code, outcome, x_start, y_start. Returns None if no coordinates were collected."""
    pts = [e for e in events if e["team_id"] == team_id and e["code"] in ("shot", "goal", "penalty")
           and e["x_start"] is not None and e["y_start"] is not None]
    if not pts:
        return None
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    draw_pitch(ax)
    for e in pts:
        if e["code"] == "goal" or (e["code"] == "penalty" and e["outcome"] == "scored"):
            ax.scatter(e["x_start"], e["y_start"], s=70, c=RED, edgecolors="white", zorder=3)
        elif e["outcome"] == "on_target" or e["outcome"] == "saved":
            ax.scatter(e["x_start"], e["y_start"], s=55, c="#4aa3ff", edgecolors="white", zorder=3)
        elif e["outcome"] == "blocked":
            ax.scatter(e["x_start"], e["y_start"], s=45, c="#888", edgecolors="white", zorder=3)
        else:
            ax.scatter(e["x_start"], e["y_start"], s=45, c="#f0f0f0", edgecolors="#333", zorder=3)
    ax.set_title(title, fontsize=8, color=NAVY)
    return _png(fig)


def trend(labels, values, title, ylabel=""):
    pts = [(l, v) for l, v in zip(labels, values) if v is not None]
    if len(pts) < 2:
        return None
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color=GREEN, lw=2)
    ax.set_title(title, fontsize=9, color=NAVY)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return _png(fig)


def shot_map_pair(events, home_id, away_id, home_name, away_name):
    """Both teams' shot maps in one image; None if no coordinates were collected for either team."""
    def pts(tid):
        return [e for e in events if e["team_id"] == tid and e["code"] in ("shot", "goal", "penalty")
                and e["x_start"] is not None and e["y_start"] is not None]
    if not pts(home_id) and not pts(away_id):
        return None
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 2.9))
    for ax, tid, name in ((axes[0], home_id, home_name), (axes[1], away_id, away_name)):
        draw_pitch(ax)
        for e in pts(tid):
            if e["code"] == "goal" or (e["code"] == "penalty" and e["outcome"] == "scored"):
                ax.scatter(e["x_start"], e["y_start"], s=60, c=RED, edgecolors="white", zorder=3)
            elif e["outcome"] in ("on_target", "saved"):
                ax.scatter(e["x_start"], e["y_start"], s=48, c="#4aa3ff", edgecolors="white", zorder=3)
            elif e["outcome"] == "blocked":
                ax.scatter(e["x_start"], e["y_start"], s=40, c="#888", edgecolors="white", zorder=3)
            else:
                ax.scatter(e["x_start"], e["y_start"], s=40, c="#f0f0f0", edgecolors="#333", zorder=3)
        ax.set_title(name + " (red goal, blue on target, grey blocked, white off target)", fontsize=6.5, color=NAVY)
    return _png(fig)


# ----------------------------------------------------------------------------- Phase 8: coordinate-based advanced charts
import numpy as np

HEAT_MIN_POINTS = 15
NET_MIN_PASSES = 10


def heat_points(events, team_id, player_id=None):
    out = []
    for e in events:
        if e["team_id"] != team_id or e["x_start"] is None or e["y_start"] is None:
            continue
        if player_id is not None and e["player_id"] != player_id:
            continue
        if e["code"] in ("period_start", "period_end", "substitution", "other"):
            continue
        out.append((e["x_start"], e["y_start"]))
    return out


def _heat_on(ax, pts, title):
    draw_pitch(ax)
    grid = np.zeros((20, 32))
    for x, y in pts:
        grid[min(19, int(y / 5.0001)), min(31, int(x / 3.1251))] += 1
    k = np.array([1, 4, 6, 4, 1], float)
    k /= k.sum()
    for axis in (0, 1):                      # separable smoothing (no SciPy needed)
        grid = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis, grid)
    ax.imshow(grid, extent=(0, 100, 100, 0), cmap="YlOrRd", alpha=0.62, aspect="auto", zorder=2, interpolation="bilinear")
    ax.set_title(f"{title} ({len(pts)} located actions)", fontsize=7, color=NAVY)


def heatmap(events, team_id, title, player_id=None):
    """Density of located actions. Returns None when fewer than HEAT_MIN_POINTS were collected (never invents a map)."""
    pts = heat_points(events, team_id, player_id)
    if len(pts) < (8 if player_id is not None else HEAT_MIN_POINTS):
        return None
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    _heat_on(ax, pts, title)
    return _png(fig)


def heatmap_pair(events, home_id, away_id, home_name, away_name):
    h, a = heat_points(events, home_id), heat_points(events, away_id)
    if len(h) < HEAT_MIN_POINTS and len(a) < HEAT_MIN_POINTS:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.0))
    for ax, pts, name in ((axes[0], h, home_name), (axes[1], a, away_name)):
        if len(pts) >= HEAT_MIN_POINTS:
            _heat_on(ax, pts, name)
        else:
            draw_pitch(ax)
            ax.set_title(f"{name}: not enough located actions", fontsize=7, color=NAVY)
    return _png(fig)


def network_data(events, team_id, names):
    """Passing network from completed passes with a start location AND a recorded receiver.
    Returns (nodes{pid:(x,y,name,n)}, edges{(a,b):count}) or None if too little data."""
    pos, cnt, edges = {}, {}, {}
    n_used = 0
    for e in events:
        if e["team_id"] != team_id or e["code"] not in ("pass", "key_pass") or e["outcome"] not in ("completed", None):
            continue
        a, b = e["player_id"], e["related_player_id"]
        if not a or not b or a == b or e["x_start"] is None or e["y_start"] is None:
            continue
        n_used += 1
        pos.setdefault(a, []).append((e["x_start"], e["y_start"]))
        if e["x_end"] is not None:
            pos.setdefault(b, []).append((e["x_end"], e["y_end"]))
        key = tuple(sorted((a, b)))
        edges[key] = edges.get(key, 0) + 1
        cnt[a] = cnt.get(a, 0) + 1
    if n_used < NET_MIN_PASSES:
        return None
    nodes = {p: (float(np.mean([q_[0] for q_ in v])), float(np.mean([q_[1] for q_ in v])), names.get(p, str(p)), cnt.get(p, 0)) for p, v in pos.items()}
    return nodes, edges


def _net_on(ax, nd, title, min_edge=3):
    nodes, edges = nd
    draw_pitch(ax)
    mx = max(edges.values())
    for (a, b), n in edges.items():
        if n >= min_edge and a in nodes and b in nodes:
            ax.plot([nodes[a][0], nodes[b][0]], [nodes[a][1], nodes[b][1]], color="white", lw=0.6 + 3.2 * n / mx, alpha=0.7, zorder=2)
    for p, (x, y, name, n) in nodes.items():
        ax.scatter(x, y, s=60 + 12 * n, c="#0b2a55", edgecolors="white", zorder=3)
        ax.text(x, y + 6, name.split()[-1], color="white", fontsize=6, ha="center", zorder=4)
    ax.set_title(title + " - passing network (lines = passes between pairs, min 3)", fontsize=6.5, color=NAVY)


def passing_network(events, team_id, names, title):
    nd = network_data(events, team_id, names)
    if not nd:
        return None
    fig, ax = plt.subplots(figsize=(4.6, 3.1))
    _net_on(ax, nd, title)
    return _png(fig)


def network_pair(events, home_id, away_id, home_name, away_name, names):
    h, a = network_data(events, home_id, names), network_data(events, away_id, names)
    if not h and not a:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.1))
    for ax, nd, name in ((axes[0], h, home_name), (axes[1], a, away_name)):
        if nd:
            _net_on(ax, nd, name)
        else:
            draw_pitch(ax)
            ax.set_title(f"{name}: not enough passes with a recorded receiver", fontsize=7, color=NAVY)
    return _png(fig)
