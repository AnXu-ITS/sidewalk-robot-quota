"""
Figure 1 - Compact Redesign v4: Admission Architecture
Matching the EXACT visual style of DynaDreamer PDF:
Black borders, pale pastel fills, standard black arrows.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from restored_style import *


def figure1_compact(exporter):
    H = 215
    f = canvas(H)
    s = schematic(f, H)

    # ════════════════════════════════════════════════════════════
    #  (a) Offline assessment - thin banner at top
    # ════════════════════════════════════════════════════════════
    banner_h = 44
    # Gray background group box like "Vanilla WM" in PDF Fig 1
    s.add_patch(FancyBboxPatch(
        (3, H - banner_h - 2), WIDTH - 35, banner_h,
        boxstyle='round,pad=2,rounding_size=5', fc=PALE_GRAY, ec='none', zorder=0))
    txt(s, 8, H - 8, '(a) Offline assessment', 10, weight='bold')

    bw, bh = 86, 26
    by = H - 40
    x1, x2, x3 = 10, 112, 214
    # Use PALE_BLUE and PALE_GREEN for these structural blocks, like Fig 2
    rounded_box(s, x1, by, bw, bh, 'Geometry &\ndemand design', fc='#FFFFFF', pad=0.05)
    rounded_box(s, x2, by, bw, bh, 'Service tests &\nreferences', fc='#FFFFFF', pad=0.05)
    bw3 = 96
    rounded_box(s, x3, by, bw3, bh, 'Frozen fit, margin\n& guardrails', fc='#FFFFFF', pad=0.05)

    arrow(s, (x1 + bw + 2, by + bh/2), (x2 - 2, by + bh/2))
    arrow(s, (x2 + bw + 2, by + bh/2), (x3 - 2, by + bh/2))

    # ════════════════════════════════════════════════════════════
    #  (b) Candidate admission decision
    # ════════════════════════════════════════════════════════════
    sec_top = H - banner_h - 10
    txt(s, 8, sec_top, '(b) Candidate admission decision', 10, weight='bold')

    # ── LEFT: Corridor scene ──
    cw, ch = 78, 40
    cx, cy = 18, sec_top - 56
    corridor(s, cx, cy, cw, ch, robot=True, labels=False)
    arrow(s, (cx - 4, cy + 3), (cx + 3, cy + ch - 3), style='<->')
    txt(s, cx - 8, cy + ch/2, '$W$', 8, ha='center')
    txt(s, cx + cw/2, cy + ch + 5, 'Bidir. $q_p$', 8.5, ha='center')
    arrow(s, (cx - 8, cy + 7), (cx + 3, cy + 7))
    txt(s, cx + cw/2, cy - 7, 'Robot entry →', 8.5, ha='center')
    # Input text
    txt(s, cx + cw/2, cy - 20, '$(W,q_p,g)$; $B,v_0$', 8.5, ha='center')

    # ── CENTER: Decision flow ──
    fw, fh = 130, 24
    fx = 120
    vgap = 12

    # Domain check -> PALE_BLUE like Predictor box in PDF
    dc_y = sec_top - 33
    rounded_box(s, fx, dc_y, fw, fh, 'Domain check\nWidth, demand & geometry', fc=PALE_BLUE, pad=0.05)
    arrow(s, (cx + cw + 2, cy + ch * 0.6), (fx - 2, dc_y + fh/2))

    # Service check -> PALE_GREEN like Env block in PDF
    sc_y = dc_y - fh - vgap
    rounded_box(s, fx, sc_y, fw, fh, 'Service check\nBaseline & demand gate', fc=PALE_GREEN, pad=0.05)
    arrow(s, (fx + fw/2, dc_y - 1), (fx + fw/2, sc_y + fh + 1))
    txt(s, fx + fw/2 + 8, (dc_y + sc_y + fh) / 2, 'pass', 8.5)

    # Candidate entry rate -> PALE_YELLOW like Actor box in PDF
    qc_h = 38
    qc_y = sc_y - qc_h - vgap
    rounded_box(s, fx - 3, qc_y, fw + 6, qc_h, '', fc=PALE_YELLOW, pad=0.05)
    txt(s, fx + 2, qc_y + qc_h - 4, 'Candidate entry rate', 9.5, weight='bold', va='top')
    txt(s, fx + 2, qc_y + qc_h - 16, 'Estimate − margin', 8.5, va='top')
    txt(s, fx + 2, qc_y + qc_h - 27, 'Clip → cap → floor', 8.5, va='top')
    arrow(s, (fx + fw/2, sc_y - 1), (fx + fw/2, qc_y + qc_h + 1))
    txt(s, fx + fw/2 + 8, (sc_y + qc_y + qc_h) / 2, 'pass', 8.5)

    # ── RIGHT: Fail outcomes (single column, tight) ──
    out_x = fx + fw + 8

    # Abstain
    arrow(s, (fx + fw + 1, dc_y + fh/2), (out_x + 25, dc_y + fh/2))
    txt(s, out_x + 8, dc_y + fh/2 + 8, 'fail', 8.5, ha='center', color=STD_RED)
    txt(s, out_x + 55, dc_y + fh/2, 'Abstain', 9, ha='center', weight='bold', color=STD_RED)

    # Zero admission
    arrow(s, (fx + fw + 1, sc_y + fh/2), (out_x + 25, sc_y + fh/2))
    txt(s, out_x + 8, sc_y + fh/2 + 8, 'fail', 8.5, ha='center', color=STD_RED)
    txt(s, out_x + 60, sc_y + fh/2, 'Zero admission', 9, ha='center', weight='bold', color=STD_RED)

    # ── Configure arrow: compact L-shape on right margin ──
    cfg_x = WIDTH - 22
    # From Parameters bottom-right, down the right margin, into Quota box
    route(s, [(x3 + bw3, by + bh/2),
              (cfg_x, by + bh/2),
              (cfg_x, qc_y + qc_h/2),
              (fx + fw + 6 + 1, qc_y + qc_h/2)], color=BLACK)
    txt(s, cfg_x - 20, by + bh/2 - 12, 'configure', 8.5, color=BLACK, ha='right')

    # ── Output: quota <- left ──
    arrow(s, (fx - 3 - 1, qc_y + qc_h/2), (cx + cw - 5, qc_y + qc_h/2))
    txt(s, 10, qc_y + qc_h/2, r'$q_{\mathrm{cand}}$', 9, weight='bold')
    txt(s, 10, qc_y + qc_h/2 - 12, 'zero or positive', 8.5)
    txt(s, 10, qc_y + qc_h/2 - 23, 'robots/min', 8.5)

    # Bottom note
    txt(s, 8, 17, 'Positive rate → configuration-matched service test → PASS or further assessment.', 8.5, color=DARK_GRAY)

    exporter(f, 'figure1')
    print("  Figure 1 (strict PDF style) saved.")
