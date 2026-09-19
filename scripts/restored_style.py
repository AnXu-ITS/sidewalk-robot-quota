"""
Exact visual style from DynaDreamer PDF:
- Black outlines (lw=0.7 to 1.0) for all boxes and arrows
- Very pale pastel fill colors (pale green, pale blue, pale yellow)
- Black sans-serif text inside diagrams
- Matplotlib default-like strong colors for data plots (navy, orange/red, green)
"""
from pathlib import Path
import sys, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, PathPatch, Polygon
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'revision_20260914' / 'source_data'
ASSETS = ROOT / 'assets'
OUT = ROOT / 'paper' / 'figures'

# ── Exact PDF Palette ──────────────────────────────────────────────────────
BLACK       = '#000000'
DARK_GRAY   = '#333333'

# Fills (from PDF Fig 1 & Fig 2)
PALE_BLUE   = '#DEEBF7'   # Predictor/Encoder blocks
PALE_GREEN  = '#E2F0D9'   # Transformer/Env blocks
PALE_YELLOW = '#FFF2CC'   # Actor/Critic blocks
PALE_GRAY   = '#F2F2F2'   # Background grouping blocks

# Data colors (from PDF Fig 5, 14, etc.)
NAVY_BLUE   = '#1A3B5C'   # Strong data line / ground truth
STD_BLUE    = '#1F77B4'   # Main scatter/bars
STD_ORANGE  = '#FF7F0E'   # Comparisons / Zero margin
STD_GREEN   = '#2CA02C'   # Conservative policy
STD_RED     = '#D62728'   # Failures / Highlights
LIGHT_BAND  = '#D0E3F0'   # GT band in Fig 14
GRID_COLOR  = '#E0E0E0'

# Semantic mapping for our paper
TEXT = BLACK
EDGE = BLACK
IVORY = PALE_GRAY

WIDTH = 414.0

plt.rcParams.update({
    'font.family': 'Arial',
    'font.size': 9.5,
    'axes.labelsize': 9.5,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'mathtext.fontset': 'dejavusans',
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
    'text.color': BLACK,
    'axes.edgecolor': BLACK,
    'axes.labelcolor': BLACK,
    'xtick.color': BLACK,
    'ytick.color': BLACK,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.8,
    'legend.frameon': False,
    'savefig.facecolor': '#FFFFFF',
})

def canvas(height):
    return plt.figure(figsize=(WIDTH / 72, height / 72))

def axes(f, rect, name):
    w, h = f.get_size_inches() * 72
    a = f.add_axes([rect[0]/w, rect[1]/h, rect[2]/w, rect[3]/h])
    a.set_gid(name)
    return a

def schematic(f, height, name='schematic'):
    a = axes(f, [0, 0, WIDTH, height], name)
    a.set(xlim=(0, WIDTH), ylim=(0, height))
    a.axis('off')
    return a

def txt(a, x, y, s, size=9.5, **kw):
    return a.text(x, y, s, fontsize=size, va=kw.pop('va', 'center'), color=kw.pop('color', BLACK), **kw)

def arrow(a, start, end, color=BLACK, style='-|>', **kw):
    a.add_patch(FancyArrowPatch(
        start, end, arrowstyle=style, mutation_scale=10,
        lw=0.9, color=color, shrinkA=0, shrinkB=0, **kw))

def route(a, points, color=BLACK):
    a.add_patch(FancyArrowPatch(
        path=MPath(points, [MPath.MOVETO] + [MPath.LINETO]*(len(points)-1)),
        arrowstyle='-|>', mutation_scale=10, lw=0.9, color=color))

def rounded_box(a, x, y, w, h, s, fc=PALE_GRAY, ec=BLACK, size=9.5, pad=0.0):
    """Exact PDF style: black border, pale fill, slight rounding."""
    a.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f'round,pad={pad},rounding_size=3',
        facecolor=fc, edgecolor=ec, linewidth=0.8,
        zorder=2))
    txt(a, x + w/2, y + h/2, s, size, ha='center', linespacing=1.25, zorder=3)

def box(a, x, y, w, h, s, fc=PALE_GRAY, size=9.5):
    rounded_box(a, x, y, w, h, s, fc=fc, ec=BLACK, size=size)

def heading(a, s):
    a.text(0, 1.04, s, transform=a.transAxes, fontsize=10,
           weight='bold', va='bottom', color=BLACK)

def export(f, name):
    f.savefig(OUT / f'{name}.pdf')
    f.savefig(OUT / f'{name}.png', dpi=300)
    plt.close(f)

def icon(a, name, x, y, height, color=BLACK, flip=False):
    import re, xml.etree.ElementTree as ET
    svg_file = ASSETS / f'{name}.svg'
    if not svg_file.exists():
        a.plot(x, y, 'o', ms=height*0.3, color=color)
        return
    root = ET.parse(svg_file).getroot()
    _, _, w, h = map(float, root.attrib['viewBox'].split())
    sc = height / h
    for el in root.iter('{http://www.w3.org/2000/svg}path'):
        tokens = re.findall(r'[MLZ]|-?\d+(?:\.\d+)?', el.attrib['d'])
        verts = []; codes = []; i = 0; first = None
        while i < len(tokens):
            cmd = tokens[i]; i += 1
            if cmd == 'Z':
                verts.append(first); codes.append(MPath.CLOSEPOLY); continue
            xx, yy = map(float, tokens[i:i+2]); i += 2
            v = (x + (w - xx if flip else xx) * sc, y + (h - yy) * sc)
            if cmd == 'M': first = v
            verts.append(v)
            codes.append(MPath.MOVETO if cmd == 'M' else MPath.LINETO)
        a.add_patch(PathPatch(MPath(verts, codes), fc=color, ec='none'))

def corridor(a, x, y, w=120, h=65, robot=True, labels=True):
    a.add_patch(Polygon(
        [(x, y), (x+w-13, y), (x+w, y+h), (x+13, y+h)],
        fc=PALE_GRAY, ec=BLACK, lw=0.8, alpha=1.0))
    a.plot([x+7, x+w-7], [y+h*0.49]*2, color=DARK_GRAY, lw=0.6, ls=(0, (4, 4)))
    for dx, dy, flip in [(.25, .48, False), (.55, .56, False), (.77, .08, True)]:
        icon(a, 'pedestrian', x + w*dx, y + h*dy, h*0.36, DARK_GRAY, flip)
    if robot:
        icon(a, 'robot', x+8, y+h*0.05, h*0.51, BLACK)
    arrow(a, (x+w*0.25, y+h*0.9), (x+w*0.74, y+h*0.9), color=BLACK)
    arrow(a, (x+w*0.85, y+h*0.08), (x+w*0.54, y+h*0.08), color=BLACK)
    if labels:
        arrow(a, (x-7, y+2), (x+6, y+h-2), style='<->')
        txt(a, x-13, y+h/2, '$W$', 10, ha='center')
        txt(a, x+w*0.54, y+h+10, 'Bidirectional $q_p$', 9, ha='center')
        arrow(a, (x-16, y+13), (x+8, y+13), color=BLACK)
        txt(a, x+w/2, y-12, 'Robot entry →', 9, ha='center')
