"""
Visual knockout bracket renderer -> self-contained HTML for st.components.

The 2026 bracket is not a match-number-ordered binary tree, so matches are laid
out in recursive display order (derived from the FINAL backwards) where each
round's consecutive pairs feed the next round's matches in order. With matches
distributed evenly over a fixed canvas height, every parent box sits exactly at
the midpoint of its two children, so connector lines never cross.
"""

from flags import flag

# Display order per round (top -> bottom). Consecutive pairs feed the next
# round's match at the same index, matching the official 73..104 linkage.
ORDERS = [
    [73, 75, 74, 77, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87],  # R32
    [89, 90, 93, 94, 91, 92, 95, 96],                                  # R16
    [97, 98, 99, 100],                                                 # QF
    [101, 102],                                                        # SF
    [104],                                                             # Final
]
TITLES = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals",
          "Final"]

BW, BH, COLGAP, SLOT0 = 172, 46, 46, 58


def _team_line(name, top):
    radius = "5px 5px 0 0" if top else "0 0 5px 5px"
    if not name or name == "TBD":
        return (f"<div style='height:22px;display:flex;align-items:center;"
                f"padding:0 8px;color:#5b6477;font-size:12px;font-style:italic;"
                f"border-radius:{radius};'>TBD</div>")
    return (f"<div style='height:22px;display:flex;align-items:center;gap:6px;"
            f"padding:0 8px;font-size:13px;color:#e6ebf5;border-radius:{radius};'>"
            f"<span>{flag(name)}</span>"
            f"<span style='overflow:hidden;text-overflow:ellipsis;"
            f"white-space:nowrap;'>{name}</span></div>")


def _feeder_line(match_no, top):
    radius = "5px 5px 0 0" if top else "0 0 5px 5px"
    return (f"<div style='height:22px;display:flex;align-items:center;"
            f"padding:0 8px;font-size:11px;color:#727c91;"
            f"border-radius:{radius};'>Winner M{match_no}</div>")


def _box(x, y, t1, t2, highlight=False):
    border = "#3a7d4a" if highlight else "#2c3445"
    return (f"<div style='position:absolute;left:{x}px;top:{y:.1f}px;"
            f"width:{BW}px;height:{BH}px;background:#1b2230;border:1px solid "
            f"{border};border-radius:6px;box-sizing:border-box;'>{t1}"
            f"<div style='height:1px;background:#2c3445;'></div>{t2}</div>")


def _line(x, y, w, h):
    return (f"<div style='position:absolute;left:{x:.1f}px;top:{y:.1f}px;"
            f"width:{w:.1f}px;height:{h:.1f}px;background:#39414f;'></div>")


def build_bracket_html(r32_matches):
    """r32_matches: list of {match, home, away}. Returns (html, canvas_height)."""
    r32 = {m["match"]: (m["home"], m["away"]) for m in r32_matches}
    n0 = len(ORDERS[0])
    H = n0 * SLOT0
    nr = len(ORDERS)

    def cx(r):
        return r * (BW + COLGAP)

    def cy(r, j):
        return (j + 0.5) * H / len(ORDERS[r])

    parts = []
    # Connectors (drawn under the boxes).
    for r in range(1, nr):
        for j in range(len(ORDERS[r])):
            c1, c2 = cy(r - 1, 2 * j), cy(r - 1, 2 * j + 1)
            pc = cy(r, j)
            x_child = cx(r - 1) + BW
            x_parent = cx(r)
            mid = (x_child + x_parent) / 2
            parts.append(_line(x_child, c1 - 1, mid - x_child, 2))
            parts.append(_line(x_child, c2 - 1, mid - x_child, 2))
            parts.append(_line(mid - 1, min(c1, c2), 2, abs(c2 - c1)))
            parts.append(_line(mid, pc - 1, x_parent - mid, 2))

    # Boxes.
    for r in range(nr):
        for j, mn in enumerate(ORDERS[r]):
            x, y = cx(r), cy(r, j) - BH / 2
            if r == 0:
                home, away = r32.get(mn, ("TBD", "TBD"))
                t1, t2 = _team_line(home, True), _team_line(away, False)
            else:
                a, b = ORDERS[r - 1][2 * j], ORDERS[r - 1][2 * j + 1]
                t1, t2 = _feeder_line(a, True), _feeder_line(b, False)
            parts.append(_box(x, y, t1, t2, highlight=(r == nr - 1)))

    headers = "".join(
        f"<div style='position:absolute;left:{cx(r)}px;top:-26px;width:{BW}px;"
        f"text-align:center;color:#7fd99a;font-size:12px;font-weight:600;'>"
        f"{TITLES[r]}</div>" for r in range(nr))

    W = nr * (BW + COLGAP)
    html = (f"<div style='font-family:system-ui,-apple-system,sans-serif;"
            f"padding:34px 8px 8px;overflow:auto;'>"
            f"<div style='position:relative;width:{W}px;height:{H}px;'>"
            f"{headers}{''.join(parts)}</div></div>")
    return html, H + 90
