"""Three vector figures, using the approved Figure 1 typography and V2 data."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,Polygon
O=Path(__file__).resolve().parent;ROOT=O.parent;P=ROOT/'outputs/figures';Q=ROOT/'outputs/figure_qa';P.mkdir(parents=True,exist_ok=True);Q.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(O/'figure_qa'))
from audit_panel_alignment import require_matplotlib_panel_alignment
d=json.loads((ROOT/'data/submission/FINAL_RESULTS.json').read_text(encoding='utf8'));ss=d['loco'];W=414
plt.rcParams.update({'font.family':'Arial','font.size':9.5,'axes.labelsize':9.5,'xtick.labelsize':9,'ytick.labelsize':9,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'legend.frameon':False,'text.color':'#333333','axes.labelcolor':'#333333'})
green='#27815D';orange='#D77824';blue='#1A3B5C';gray='#D8DEE2';ink='#333333'
def fig(h):return plt.figure(figsize=(W/72,h/72))
def ax(f,r,name):
 h=f.get_size_inches()[1]*72;a=f.add_axes([r[0]/W,r[1]/h,r[2]/W,r[3]/h]);a.set_gid(name);return a
def text(a,x,y,t,**kw):return a.text(x,y,t,va=kw.pop('va','center'),fontsize=kw.pop('fontsize',9.5),**kw)
def save(f,name,peers=None,rows=None):
 f.canvas.draw()
 if peers:
  require_matplotlib_panel_alignment(f,axes=peers,row_groups=rows,json_out=Q/(name+'.alignment.json'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 else:
  (Q/(name+'.alignment.json')).write_text(json.dumps({'status':'NOT APPLICABLE','reason':'Schematic or heterogeneous geometry/quantitative layout; no comparable plot-area peers'}))
 f.savefig(P/(name+'.pdf'))
 f.savefig(P/(name+'.svg'))
 f.savefig(P/(name+'.png'),dpi=300)
 plt.close(f)
from restored_architecture import figure1_compact
from reviewer_reference import figure2
figure1_compact(save)
figure2(save)
# Shape gallery: all final configurations, sorted by site ID, independently scaled.
hk=pd.read_csv(ROOT/'data/submission/hk_analysis_v3.csv');sites=sorted(hk.tag.unique());geom=json.loads((ROOT/'data/geometry/hk_formal_local_geometry.json').read_text(encoding='utf8'))
f=fig(380);a=ax(f,[0,165,414,215],'geometry');a.set(xlim=(0,414),ylim=(0,215));a.axis('off')
text(a,6,205,'(a) Original polygon shapes',fontsize=10.5,fontweight='bold')
text(a,6,187,'All final sites; individually scaled; R = repaired entrance',fontsize=9)
for j,tag in enumerate(sites):
 row,col=divmod(j,3);x=col*138+7;y=163-row*29
 g=geom[tag];poly=np.array(g['walkable_polygon_local']['coordinates'][0]);cl=np.array(g['centerline_local']);direction=cl[-1]-cl[0];theta=np.arctan2(direction[1],direction[0]);rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
 xy=poly@rot;xy-=xy.min(axis=0);extent=xy.max(axis=0);scale=min(123/max(extent[0],.1),13/max(extent[1],.1));xy=xy*scale+[x,y-5]
 config=hk[hk.tag.eq(tag)].iloc[0].configuration;label=tag.replace('HK-ST-','')+(' R' if config=='REPAIRED' else '')
 a.add_patch(Polygon(xy,fc='#DCE8EE',ec=blue,lw=.6));text(a,x,y+14,label,fontsize=9)
 bnds=xy.max(axis=0)
b=ax(f,[40,45,367,105],'quota');x=np.arange(len(sites));met=hk[hk.method.eq('M0')].set_index('tag').loc[sites]
b.scatter(x,met.q_star,marker='D',s=22,color=ink,label='Reference',zorder=3)
for m,shift,color,marker in [('M0',-.17,green,'o'),('M1',.17,orange,'^')]:
 vals=hk[hk.method.eq(m)].set_index('tag').loc[sites];b.scatter(x+shift,vals.quota,marker=marker,color=color,s=24,label=m,zorder=4)
b.set(xlim=(-.65,len(sites)-.35),ylim=(-1,22),yticks=[0,5,10,15,20],xticks=x,xticklabels=[t.replace('HK-ST-','')+('R' if hk[hk.tag.eq(t)].iloc[0].configuration=='REPAIRED' else '') for t in sites],ylabel='Robots/min')
b.tick_params(axis='x',rotation=90);b.grid(axis='y',lw=.4,color='#DDDDDD');b.set_axisbelow(True)
b.set_title('(b) Reference and recommended entry rates',loc='left',fontsize=10.5,fontweight='bold',pad=9)
f.legend(*b.get_legend_handles_labels(),loc='lower center',ncol=3,fontsize=9,bbox_to_anchor=(.55,-.01));save(f,'figure3')
