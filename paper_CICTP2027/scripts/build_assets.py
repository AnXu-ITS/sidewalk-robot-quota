"""Rebuild the paper's compact tables and margin figure from verified evidence."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/figure_qa'))
from audit_panel_alignment import require_matplotlib_panel_alignment

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=ROOT/'outputs/reproduced')
    ap.add_argument('--output',type=Path,default=ROOT/'outputs/assets')
    args=ap.parse_args();out=args.output.resolve();(out/'tables').mkdir(parents=True,exist_ok=True);(out/'figures').mkdir(exist_ok=True)
    main=pd.read_csv(args.results/'main_comparison.csv').set_index('method')
    sweep=pd.read_csv(args.results/'margin_sweep.csv').sort_values('tau')
    ref=pd.read_csv(ROOT/'data/reference_flows/reference_dataset_original_block_v3.csv')
    pred=pd.read_csv(ROOT/'data/admission_results/loco_predictions_v3.csv')
    cfg=json.loads((ROOT/'configs/admission.json').read_text(encoding='utf-8'))
    specs=json.loads((ROOT/'configs/run_specs.json').read_text(encoding='utf-8'))
    s=next(r['spec'] for r in specs if r['spec']['dataset']=='Development' and r['spec']['qr']==0)
    pars=pd.read_csv(ROOT/'data/admission_results/fit_parameters_v3.csv')
    p=pars[pars.city.eq('ALL_DEVELOPMENT')&pars.method.eq('M0')].iloc[0];coef=json.loads(p.coefficients)
    values=dict(Candidates=len(ref),Cells=ref.cell_id.nunique(),MainScenarios=int(ref.source.eq('main').sum()),AdditionalScenarios=int(ref.source.eq('decoupled').sum()),
                CorridorLength=f"{s['L']:g}",EngineVersion='SUMO 1.27.1',PedRadius=f"{s['ped']['radius']:g}",PedSpeed=f"{s['ped']['v0_mean']:g}",
                PedSD=f"{s['ped']['v0_std']:g}",PedMin=f"{s['ped']['v0_min']:g}",PedMax=f"{s['ped']['v0_max']:g}",
                RobotLength=f"{s['robot']['length']:g}",RobotWidth=f"{s['robot']['width']:g}",RobotRadius=f"{s['robot']['radius']:g}",RobotSpeed=f"{s['robot']['v_ref']:g}",
                TimeStep=f"{s['sim']['dt']:g}",Warmup=f"{s['sim']['warmup']:g}",Measurement=f"{s['sim']['measure']:g}",Tail=f"{s['sim']['tail']:g}",
                ZoneLength=f"{s['sim']['measure_zone'][1]-s['sim']['measure_zone'][0]:g}",Timeout=f"{s['sim']['timeout_sec']:g}",
                SpeedRetention=f"{cfg['service']['speed_retention']:.2f}",DensityLimit=f"{cfg['service']['density_limit']:.2f}",
                FlowLow=f"{cfg['service']['throughput_low']:.2f}",FlowHigh=f"{cfg['service']['throughput_high']:.2f}",PassN=cfg['service']['passing_seeds'],SeedN=30,
                QMax=f"{cfg['guardrails']['q_max']:g}",WidthMin=f"{cfg['applicability_domain']['W_range'][0]:g}",WidthMax=f"{cfg['applicability_domain']['W_range'][1]:.1f}",
                DemandMax=f"{cfg['applicability_domain']['q_p_max']:g}",SpecificMax=r'\frac{100}{3}',SinuosityMax=f"{cfg['applicability_domain']['type_b_sinuosity_max']:g}",
                TurnAngle=f"{cfg['guardrails']['sharp_corner_guard']['max_turn_min_deg']:g}",TurnRatio=f"{cfg['guardrails']['sharp_corner_guard']['concentration_min']:g}",
                SpeedFloor=f"{cfg['guardrails']['absolute_speed_floor']['vbar_min']:g}",MainC=f"{np.exp(coef[0]):.3f}",MainP=f"{coef[1]:.3f}",MZeroMargin=f"{p.margin:.3f}")
    eligible=pred[pred.method.eq('M0')&pred.quota.notna()]
    values.update(EvalN=len(eligible),EvalCells=eligible.cell_id.nunique(),UtilN=int(eligible.q_star.gt(0).sum()),
                  EvalCensored=int(eligible.q_star_status.eq('CEILING_CENSORED').sum()))
    assert values['EvalN']==164 and values['EvalCells']==64 and values['UtilN']==139
    (out/'tables/results_values.tex').write_text('% Generated from verified CICTP inputs.\n'+''.join(f'\\newcommand{{\\{k}}}{{{v}}}\n' for k,v in values.items()),encoding='utf-8')
    g=cfg['guardrails'];indices=[i for i,w in enumerate(g['C_W']['W']) if w>=cfg['applicability_domain']['W_range'][0]]
    widths=[g['C_W']['W'][i] for i in indices]
    rows=[r'$W$ (m) & '+' & '.join(f'{w:g}' for w in widths)+r' \\',
          r'$C(W)$ (ped/min) & '+' & '.join(f"{g['C_W']['C'][i]:g}" for i in indices)+r' \\',
          r'$Q_{\rm low}(W)$ (robots/min) & '+' & '.join(f"{g['Q_low']['Q'][i]:g}" for i in indices)+r' \\']
    (out/'tables/guardrails.tex').write_text(r'\begin{tabular}{lrrrrrrr}'+'\n'+r'\toprule'+'\n'+rows[0]+'\n'+r'\midrule'+'\n'+'\n'.join(rows[1:])+'\n'+r'\bottomrule'+'\n'+r'\end{tabular}'+'\n',encoding='utf-8')
    table=r'\begin{tabular}{lrrrrr}'+'\n'+r'\toprule'+'\n'+r'Rule & Positive & Zero & PASS & FAIL & $U$ (\%) \\'+'\n'+r'\midrule'+'\n'
    labels={'M0':'M0: width--demand + margin','M1':'M1: no margin','M2':'M2: width only','M3':'M3: free exponents'}
    for method in ['M0','M1','M2','M3']:
        r=main.loc[method]
        if method=='M0':table+=r'\rowcolor{tableblue}'+'\n'
        table+=' & '.join([labels[method]]+[str(int(r[k])) for k in ['positive','zero','PASS','FAIL']]+[f'{100*r.util:.1f}'])+r' \\'+'\n'
    table+=r'\bottomrule'+'\n'+r'\end{tabular}'+'\n';(out/'tables/main_comparison.tex').write_text(table,encoding='utf-8')
    assumptions=pd.read_csv(ROOT/'data/operating_conditions/assumption_qualification.csv')
    settings=['assumption-size080-v1','assumption-reference-v1','assumption-size120-v1','assumption-direction075-v1']
    table=r'\begin{tabular}{rrrr}'+'\n'+r'\toprule'+'\n'+r'Robot radius (m) & Opposing pedestrians (\%) & Narrow & Wide \\'+'\n'+r'\midrule'+'\n'
    for setting in settings:
        z=assumptions[assumptions.configuration.eq(setting)].sort_values('W');assert len(z)==2 and z.complete.all()
        cells=[f'{z.robot_radius_actual.iloc[0]:.3f}',f'{100*z.direction_larger_share.iloc[0]:.0f}',str(int(z.passing.iloc[0])),str(int(z.passing.iloc[1]))]
        if setting=='assumption-size120-v1':cells[2]=r'\cellcolor{tableblue}0'
        table+=' & '.join(cells)+r' \\'+'\n'
    table+=r'\bottomrule'+'\n'+r'\end{tabular}'+'\n';(out/'tables/operating_conditions.tex').write_text(table,encoding='utf-8')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],'font.size':9.5,
                         'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(5.75,2.90))
    fig.subplots_adjust(left=.14,right=.97,bottom=.22,top=.95)
    x=sweep.positive_recommendations.to_numpy();y=sweep.FAIL.to_numpy()
    ax.plot(x,y,color='#626E77',lw=1.3,zorder=1)
    for i,(xx,yy) in enumerate(zip(x,y)):
        ax.scatter([xx],[yy],s=34,color='#356C89' if i==3 else 'white' if i==4 else '#707B84',edgecolors='#356C89' if i in [3,4] else '#707B84',zorder=3)
    labels=[('No margin (M1)',(-8,11),'right'),('0.50',(-9,9),'right'),('0.65',(11,-17),'left'),('0.80 (M0)',(0,11),'center'),('0.90',(0,11),'center')]
    for (xx,yy),(label,offset,ha) in zip(zip(x,y),labels):ax.annotate(label,(xx,yy),xytext=offset,textcoords='offset points',ha=ha,va='bottom',fontsize=9.5)
    ax.set(xlim=(49,146),ylim=(-2.2,22),xlabel='Scenarios receiving robot access (of 164)',ylabel='Failed direct service tests')
    ax.set_xticks([60,80,100,120,140]);ax.set_yticks([0,5,10,15,20]);ax.tick_params(direction='out',length=3)
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=str(out/'figures/figure2.alignment.json'),strict=True)
    fig.savefig(out/'figures/figure2.pdf')
    fig.savefig(out/'figures/figure2.svg')
    fig.savefig(out/'figures/figure2.png',dpi=300)
    plt.close(fig)
    (out/'BUILD_INPUTS.json').write_text(json.dumps(dict(results=str(args.results.name),margin_csv_sha256=__import__('hashlib').sha256((args.results/'margin_sweep.csv').read_bytes()).hexdigest(),
                                                    direct_labels='Prespecified residual quantile; no-margin condition explicit',intervals='Descriptive complete evaluated-sample counts; no population risk interval inferred'),indent=2),encoding='utf-8')
    print('Generated compact tables, exact macros and Figure2 from verified CICTP evidence.')

if __name__=='__main__':main()
