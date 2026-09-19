"""Figure 2 for reviewer revision: compact reference construction plus V3 trade-off.
All labels and counts are read from reviewer reanalysis outputs.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from matplotlib.ticker import NullLocator
from restored_style import *
O=Path(__file__).resolve().parent
REV=O.parent/'data/submission'

def figure2(exporter):
    ref=pd.read_csv(REV/'reference_dataset_original_block_v3.csv')
    audit=pd.read_csv(REV/'reference_flow_audit_v3.csv')
    results=json.loads((REV/'FINAL_RESULTS.json').read_text(encoding='utf8'))
    assert all(v['UNTESTED']==0 and v['INCOMPLETE']==0 for v in results['loco'].values())
    eval_n=results['loco']['M0']['n']
    tag='AMS-amsterdam-chain-141619-0|qp10'
    z=pd.read_csv(REV/'matched_raw_primary.csv',low_memory=False)
    z=z[z.tag.eq(tag)&z.configuration.eq('historical')&z.seed.between(0,29)]
    base=z[z.qr.eq(0)];
    scan=audit[audit.tag.eq(tag)].sort_values('qr').copy()
    qstar=float(ref.loc[ref.tag.eq(tag),'q_star'].iloc[0])
    # The audit already applies the denominator-defined service rule.
    f=canvas(330); s=schematic(f,330)
    txt(s,8,322,'(a) Reference construction from configuration-matched service tests',10.5,weight='bold')
    corridor(s,14,256,78,36,robot=False,labels=False); corridor(s,116,256,78,36,robot=True,labels=False)
    txt(s,53,304,'No-robot baseline',8.8,ha='center'); txt(s,155,304,'Mixed-flow test',8.8,ha='center')
    arrow(s,(96,274),(112,274)); txt(s,104,246,'30 original seeds per flow',8.5,ha='center')
    box(s,10,184,202,45,'Speed retention ≥ 0.90\nDensity ≤ 1.20 ped/m²\nThroughput 0.90–1.20 when denominator > 0',fc=PALE_GREEN,size=8.5)
    a=axes(f,[250,211,150,90],'scan')
    a.plot(scan.qr,100*scan.passing/scan.n,color=DARK_GRAY,marker='o',ms=3,lw=.9)
    a.axhline(29/30*100,color=NAVY_BLUE,lw=.7,ls='--')
    a.set(xlim=(0,20),ylim=(25,103),xticks=[0,5,10,15,20],yticks=[40,70,100])
    a.set_xlabel('Robot flow (robots/min)',fontsize=8.5,labelpad=1); a.set_ylabel('Seeds passing (%)',fontsize=8.5,labelpad=1)
    a.annotate('29/30',(20,96.67),xytext=(-2,3),textcoords='offset points',ha='right',va='bottom',fontsize=8.3,color=NAVY_BLUE)
    a.annotate(f'$q^*={qstar:g}$',(qstar,100),xytext=(-28,-26),textcoords='offset points',fontsize=8.5,arrowprops={'arrowstyle':'->','lw':.7,'color':NAVY_BLUE},color=NAVY_BLUE)
    txt(s,8,161,'(b) Robot access and directly tested service',10.5,weight='bold')
    b=axes(f,[55,54,332,82],'tradeoff')
    labels=[]; y=np.arange(4)
    colors={'PASS':'#2CA02C','FAIL':'#D62728','ZERO':'#B7BDC2'}
    order=['PASS','FAIL','ZERO']
    for i,m in enumerate(['M0','M1','M2','M3']):
        s0=results['loco'][m]; left=0
        for key in order:
            val=int(s0.get('zero' if key=='ZERO' else key,0)); b.barh(i,val,left=left,height=.55,color=colors[key],edgecolor='white',linewidth=.4,label=key if i==0 else None); left+=val
        b.text(eval_n+.8,i,f"P {s0['positive']} · Z {s0['zero']}",va='center',ha='left',fontsize=8)
    b.set(xlim=(0,eval_n*1.25),ylim=(-.6,3.6),yticks=y,yticklabels=['M0','M1','M2','M3'],xlabel=f'Evaluated scenarios (n = {eval_n})',xticks=[0,40,80,120,160,200])
    b.invert_yaxis(); b.grid(axis='x',color=GRID_COLOR,lw=.5); b.set_axisbelow(True)
    b.legend(loc='upper center',bbox_to_anchor=(.52,1.25),ncol=3,fontsize=8,handlelength=1.0,columnspacing=1.0)
    txt(s,8,11,'All positive recommendations directly tested; zero admission is not a service PASS.',8.5,color=DARK_GRAY)
    exporter(f,'figure2')
