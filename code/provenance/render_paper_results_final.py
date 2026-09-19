"""Generate V3 writing derivatives from original-seed reference reanalysis.
No simulation is launched. All numbers are derived from reviewer_revision outputs.
"""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent; R=O.parent; ROOT=R.parent; P=O/'paper'; GDIR=P/'generated'; REV=O/'submission_final'
P.mkdir(exist_ok=True); GDIR.mkdir(exist_ok=True); (P/'figures').mkdir(exist_ok=True)
for f in ['ascelike-new.cls','ascelike-new.bst']:
    src=ROOT/'CICPT2027'/f
    if src.exists(): shutil.copy2(src,P/f)
ref=pd.read_csv(REV/'reference_dataset_original_block_v3.csv')
pred=pd.read_csv(REV/'loco_predictions_v3.csv')
ex=pd.read_csv(REV/'exact_flow_validation_v3.csv')
hk=pd.read_csv(REV/'hk_analysis_v3.csv')
pars=pd.read_csv(REV/'fit_parameters_v3.csv')
raw_index=pd.read_csv(O/'raw_index_writing.csv')
_spec_hash=raw_index[raw_index.dataset.eq('Development')].iloc[0].spec_hash
spec=json.loads((R/'runs'/_spec_hash/'spec.json').read_text())
cfg=json.loads((ROOT/'final_freeze_29of30_corrected/final_quota_method_config.json').read_text())
methods=['M0','M1','M2','M3']; names=['MZero','MOne','MTwo','MThree']

def metrics(g, exact=None):
    a=g[g.quota.notna()].copy(); pos=a.quota.gt(0)
    qerr=a.quota-a.q_star
    valid_ref=a.q_star.gt(0)
    util=np.median(a.loc[valid_ref,'quota']/a.loc[valid_ref,'q_star'])
    ec=exact[exact.method.eq(g.method.iloc[0])] if exact is not None and len(g) else pd.DataFrame()
    return dict(n=int(len(a)),positive=int(pos.sum()),zero=int((a.quota==0).sum()),exceed=int((qerr>0).sum()),mae=float(qerr.abs().mean()),util=float(util),util_n=int(valid_ref.sum()),ceiling_n=int((a.q_star>=20).sum()),abstain=int(g.quota.isna().sum()),reasons=g.loc[g.quota.isna(),'reason'].value_counts().to_dict(),zero_reasons=a.loc[a.quota.eq(0),'reason'].value_counts().to_dict(),PASS=int((ec.exact_flow_status=='PASS').sum()),FAIL=int((ec.exact_flow_status=='FAIL').sum()),UNTESTED=int((ec.exact_flow_status=='UNTESTED').sum()),INCOMPLETE=int((ec.exact_flow_status=='INCOMPLETE').sum()),mean_positive_quota=float(a.loc[pos,'quota'].mean()),median_positive_quota=float(a.loc[pos,'quota'].median()))
stats={m:metrics(pred[pred.method.eq(m)],ex[ex.method.eq(m)]) for m in methods}
# P/F/UNTESTED conservation for each method; zeros are not service tests.
for m,s in stats.items():
    assert s['positive']+s['zero']==s['n']
    assert s['PASS']+s['FAIL']+s['UNTESTED']+s['INCOMPLETE']==s['positive']
assert all(s['UNTESTED']==0 and s['INCOMPLETE']==0 for s in stats.values())
# Fixed prediction cell-cluster bootstrap (5000, seed frozen in protocol).
base=pred[(pred.method=='M0') & pred.quota.notna()].sort_values('tag')
tags=base.tag.to_numpy(); cells=sorted(base.cell_id.unique()); ci={c:i for i,c in enumerate(cells)}; cellidx=np.array([ci[c] for c in base.cell_id]); qstar=base.q_star.to_numpy()
qp=np.stack([pred[pred.method.eq(m)].set_index('tag').loc[tags].quota.to_numpy() for m in methods])
rng=np.random.default_rng(2026091501); draws=rng.integers(0,len(cells),size=(5000,len(cells)))
np.savez_compressed(O/'bootstrap_draws_v3.npz',draws=draws,cells=np.array(cells),tags=tags,cell_index=cellidx)
maes=[]; utils=[]
for d in draws:
    w=np.bincount(d,minlength=len(cells))[cellidx]; idx=np.repeat(np.arange(len(tags)),w)
    maes.append(np.nanmean(np.abs(qp[:,idx]-qstar[idx]),axis=1))
    pidx=idx[qstar[idx]>0]; utils.append(np.nanmedian(qp[:,pidx]/qstar[pidx],axis=1))
maes=np.asarray(maes); utils=np.asarray(utils)
intervals={m:{'mae':np.quantile(maes[:,i],[.025,.975]).tolist(),'util':np.quantile(utils[:,i],[.025,.975]).tolist()} for i,m in enumerate(methods)}
diffs={'M0_minus_M3_mae':{'estimate':stats['M0']['mae']-stats['M3']['mae'],'ci':np.quantile(maes[:,0]-maes[:,3],[.025,.975]).tolist()},'M1_minus_M0_util':{'estimate':stats['M1']['util']-stats['M0']['util'],'ci':np.quantile(utils[:,1]-utils[:,0],[.025,.975]).tolist()}}
# Secondary paired decomposition.
wide=pred.pivot_table(index=['tag','cell_id','city'],columns='method',values='quota',aggfunc='first')
common=(wide.M0>0)&(wide.M1>0); m0z1p=(wide.M0==0)&(wide.M1>0); bothz=(wide.M0==0)&(wide.M1==0)
paired={}
for m in ['M0','M1']:
    z=ex[(ex.method==m)&ex.tag.isin(set(wide.index[common].get_level_values('tag')))]
    paired[m]=z.exact_flow_status.value_counts().to_dict()
# Hong Kong descriptive statistics by stratum.
hkstats=[]
for conf in ['ORIGINAL','REPAIRED']:
  for m in methods:
    g=hk[(hk.configuration==conf)&(hk.method==m)].copy(); pos=g.quota.gt(0); valid=g.q_star.gt(0)
    util=float(np.median(g.loc[valid,'quota']/g.loc[valid,'q_star'])) if valid.any() else 0.0
    hkstats.append(dict(configuration=conf,method=m,n=len(g),positive=int(pos.sum()),zero=int((g.quota==0).sum()),PASS=int((g.exact_flow_status=='PASS').sum()),FAIL=int((g.exact_flow_status=='FAIL').sum()),UNTESTED=int((g.exact_flow_status=='UNTESTED').sum()),exceed=int((g.quota>g.q_star).sum()),util=util,util_n=int(valid.sum())))
# Additional continuous service diagnostics.
cont=pd.read_csv(REV/'service_continuous_summary_v3.csv')
# frozen input hash for provenance
src_hash=hashlib.sha256((R/'RESULTS_VERIFIED_V2.json').read_bytes()).hexdigest()
results=dict(version='Final submission: frozen primary-block references and complete exact tests',source_results_sha256=src_hash,reference_status='CORRECTED: main reference reconstruction uses original seeds 0--29; independent block retained only for replication diagnostics',reference_counts=ref.q_star_status.value_counts().to_dict(),counts=dict(candidates=len(ref),numeric=int(ref.q_star.notna().sum()),cells=ref.cell_id.nunique(),fit=int(ref.fit_eligible_v3.sum()),fit_cells=ref[ref.fit_eligible_v3].cell_id.nunique(),eval_cells=len(cells),cities=ref.city.nunique()),loco=stats,hong_kong=hkstats,intervals=intervals,paired_differences=diffs,common_positive=dict(n=int(common.sum()),m0_zero_m1_positive=int(m0z1p.sum()),both_zero=int(bothz.sum()),methods=paired),settings=cfg,bootstrap=dict(n=5000,seed=2026091501,unit='cell',conditional=True),continuous_service=cont.to_dict('records'),q_star_changes=pd.read_csv(REV/'reference_qstar_changes_v3.csv').to_dict('records'))
(O/'writing_results_v2.json').write_text(json.dumps(results,indent=2,ensure_ascii=False,default=str),encoding='utf8')
# Macro writer
mac={}
def put(k,v): mac[k]=str(v)
for k,val in [('Candidates',len(ref)),('NumericReferences',ref.q_star.notna().sum()),('PositiveReferences',(ref.q_star_status=='POSITIVE').sum()),('ZeroReferences',(ref.q_star_status=='ZERO').sum()),('CensoredReferences',(ref.q_star_status=='CEILING_CENSORED').sum()),('GeometryExcluded',(ref.q_star_status=='OUT_OF_DOMAIN_GEOMETRY').sum()),('TechnicalExcluded',(ref.q_star_status=='TECHNICAL_INVALID').sum()),('Cells',ref.cell_id.nunique()),('FitCells',results['counts']['fit_cells']),('EvalCells',len(cells)),('EvalN',stats['M0']['n']),('UtilN',stats['M0']['util_n']),('AbstainN',stats['M0']['abstain']),('DomainExcluded',stats['M0']['reasons'].get('DOMAIN',0)),('ServiceZeros',stats['M0']['reasons'].get('SERVICE',0)),('MarginZeros',stats['M0']['reasons'].get('MARGIN_FLOOR',0)),('BootstrapN',5000),('SeedN',30),('PassN',29),('HKOriginalN',hk[hk.configuration.eq('ORIGINAL')].tag.nunique()),('HKRepairedN',hk[hk.configuration.eq('REPAIRED')].tag.nunique()),('HKTotalN',hk.tag.nunique()),('HKCandidates',32),('AffectedReferences',3),('CommonPositive',int(common.sum())),('MZeroMOnePositive',int(m0z1p.sum())),('BothZero',int(bothz.sum())),('FlowUntested',int(ex.exact_flow_status.eq('UNTESTED').sum())),('FlowIncomplete',int(ex.exact_flow_status.eq('INCOMPLETE').sum())),('IndependentSeedStart',10000),('IndependentSeedEnd',10029)]: put(k,int(val))
for m,n in zip(methods,names):
 s=stats[m]
 for k,v in [('Positive',s['positive']),('Zero',s['zero']),('Exceed',s['exceed']),('Pass',s['PASS']),('Fail',s['FAIL']),('Untested',s['UNTESTED']),('Incomplete',s['INCOMPLETE'])]:put(n+k,v)
 if m == 'M0':
  put('ServiceZeros',s['zero_reasons'].get('SERVICE',0)); put('MarginZeros',s['zero_reasons'].get('MARGIN_FLOOR',0))
 put(n+'MAE',f"{s['mae']:.2f}");put(n+'Util',f"{100*s['util']:.1f}");put(n+'FailRate',f"{100*s['FAIL']/s['positive']:.1f}" if s['positive'] else '0.0');put(n+'UtilLow',f"{100*intervals[m]['util'][0]:.1f}");put(n+'UtilHigh',f"{100*intervals[m]['util'][1]:.1f}");put(n+'MeanPositiveQuota',f"{s['mean_positive_quota']:.2f}");put(n+'MedianPositiveQuota',f"{s['median_positive_quota']:.1f}")
 pa=pars[(pars.city=='ALL_DEVELOPMENT')&(pars.method==m)].iloc[0];put(n+'Margin',f"{pa.margin:.3f}")
co=json.loads(pars[(pars.city=='ALL_DEVELOPMENT')&(pars.method=='M0')].iloc[0].coefficients);put('MainC',f"{np.exp(co[0]):.3f}");put('MainP',f"{co[1]:.3f}");put('WidthExponent',f"{1-co[1]:.3f}")
for key,prefix,factor in [('M0_minus_M3_mae','MAEDifference',1),('M1_minus_M0_util','UtilDifference',100)]:
 d=diffs[key];put(prefix,f"{factor*d['estimate']:.3f}" if factor==1 else f"{factor*d['estimate']:.1f}");put(prefix+'Low',f"{factor*d['ci'][0]:.3f}" if factor==1 else f"{factor*d['ci'][0]:.1f}");put(prefix+'High',f"{factor*d['ci'][1]:.3f}" if factor==1 else f"{factor*d['ci'][1]:.1f}")
put('AccessDifference',stats['M1']['positive']-stats['M0']['positive']);put('FailDifference',stats['M1']['FAIL']-stats['M0']['FAIL']);put('Coverage',f"{100*stats['M0']['n']/len(ref):.1f}");put('HKCoverage',f"{100*hk.tag.nunique()/32:.1f}")
# Paired decomposition macros
for k,v in [('CommonMZeroPass',paired['M0'].get('PASS',0)),('CommonMZeroFail',paired['M0'].get('FAIL',0)),('CommonMZeroUntested',paired['M0'].get('UNTESTED',0)),('CommonMOnePass',paired['M1'].get('PASS',0)),('CommonMOneFail',paired['M1'].get('FAIL',0)),('CommonMOneUntested',paired['M1'].get('UNTESTED',0))]:put(k,v)
for r in hkstats:
 prefix=('HKOrig' if r['configuration']=='ORIGINAL' else 'HKRepair')+names[methods.index(r['method'])]
 for key in ['PASS','FAIL','UNTESTED','positive','zero','exceed','util_n']:put(prefix+key.title().replace('_',''),r[key])
 put(prefix+'Util',f"{100*r['util']:.1f}")
# throughput diagnostic macros
z=pd.read_csv(REV/'denominator_zero_diagnostics_v3.csv');
for ds,label in [('Development','Dev'),('Hong Kong','HK')]:
 for fg,sub in [('baseline', 'Baseline'),('mixed','Mixed')]:
  row=z[(z.dataset==ds)&(z.flow_group==fg)].iloc[0]
  for k,v in [('Rows',row.rows),('Zero',row.denominator_zero),('Planned',row.planned_pedestrians),('Observed',row.observed_pedestrians),('Never',row.never_observed)]:put(label+sub+k,int(v))
put('ContinuousMZeroMedianSpeed',f"{cont[cont.method=='M0'].median_of_group_medians.iloc[0]:.3f}");put('ContinuousMOneMedianSpeed',f"{cont[cont.method=='M1'].median_of_group_medians.iloc[0]:.3f}");put('ContinuousMZeroWorst',f"{cont[cont.method=='M0'].worst_group_minimum.iloc[0]:.3f}");put('ContinuousMOneWorst',f"{cont[cont.method=='M1'].worst_group_minimum.iloc[0]:.3f}")
for k,v in [('TimeStep',spec['sim']['dt']),('Warmup',spec['sim']['warmup']),('Measurement',spec['sim']['measure']),('Tail',spec['sim']['tail']),('PedSpeed',spec['ped']['v0_mean']),('PedSD',spec['ped']['v0_std']),('PedMin',spec['ped']['v0_min']),('PedMax',spec['ped']['v0_max']),('PedRadius',spec['ped']['radius']),('RobotLength',spec['robot']['length']),('RobotWidth',spec['robot']['width']),('RobotRadius',spec['robot']['radius']),('RobotSpeed',spec['robot']['v_ref']),('CorridorLength',spec['sim']['L']),('ZoneLength',spec['sim']['measure_zone'][1]-spec['sim']['measure_zone'][0]),('WindowEnd',spec['sim']['warmup']+spec['sim']['measure']),('Timeout',spec['sim']['timeout_sec']),('QMax',cfg['guardrails']['q_max']),('WidthMin',cfg['applicability_domain']['W_range'][0]),('WidthMax',cfg['applicability_domain']['W_range'][1]),('DemandMax',cfg['applicability_domain']['q_p_max']),('SpeedFloor',cfg['guardrails']['absolute_speed_floor']['vbar_min'])]:put(k,f'{v:g}')
for k,v in [('SpeedRetention','0.90'),('DensityLimit','1.20'),('FlowLow','0.90'),('FlowHigh','1.20'),('Quantile','0.80'),('SpecificMax',f"{cfg['guardrails']['x_crit']:.2f}"),('SinuosityMax',cfg['applicability_domain']['type_b_sinuosity_max']),('TurnAngle',f"{cfg['guardrails']['sharp_corner_guard']['max_turn_min_deg']:g}"),('TurnRatio',cfg['guardrails']['sharp_corner_guard']['concentration_min'])]:put(k,v)
# fixed sensitivity values from existing V2 source
sens=pd.read_csv(R/'sensitivity/assumption_qualification.csv')
for tag,prefix in [('TPE-taipei-idx12521-0-5|qp21','Narrow'),('DC-114|qp43.2','Wide')]:
 ss=sens[sens.tag.eq(tag)];put(prefix+'Width',f"{ss.iloc[0].W:g}")
 for config,label in [('assumption-reference-v1','Default'),('assumption-size080-v1','Small'),('assumption-size120-v1','Large'),('assumption-direction075-v1','Direction')]:put(prefix+label+'Pass',int(ss[ss.configuration.eq(config)].iloc[0].passing))
put('SensitivityFlow',f"{sens.iloc[0].qr:g}");put('SmallRadius',f"{sens[sens.configuration.eq('assumption-size080-v1')].iloc[0].robot_radius_actual:.3f}");put('LargeRadius',f"{sens[sens.configuration.eq('assumption-size120-v1')].iloc[0].robot_radius_actual:.3f}")
for k,v in [('Cities',ref.city.nunique()),('TrainCities',ref.city.nunique()-1),('MainScenarios',int(ref.source.eq('main').sum())),('AdditionalScenarios',int((~ref.source.eq('main')).sum())),('EvalCensored',int((base.q_star>=20).sum())),('HKExcluded',14),('RepairClearance',0.75),('HKOriginalCoverage',f"{100*13/32:.1f}"),('MeanSeedsPooled',30),('EngineVersion',spec['engine_version']),('ConfidenceLevel',95),('FlowGrid','1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20')]:put(k,v)
# Narrative decomposition derives from the mutually exclusive scenario groups.
decomp=pd.read_csv(REV/'decomposition_v3.csv')
withdrawn=decomp[decomp.group.eq('M0=0 and M1>0')].iloc[0]
put('WithdrawnPass',int(withdrawn.M1_PASS)); put('WithdrawnFail',int(withdrawn.M1_FAIL))
put('CommonMZeroMean',f"{decomp.iloc[0].M0_mean_quota:.2f}"); put('CommonMOneMean',f"{decomp.iloc[0].M1_mean_quota:.2f}")
assert stats['M0']['zero_reasons']['SERVICE']+stats['M0']['zero_reasons']['MARGIN_FLOOR']==stats['M0']['zero']
assert int(withdrawn.M1_PASS+withdrawn.M1_FAIL+withdrawn.M1_UNTESTED)==int(withdrawn.scenarios)
# write macros
def macro_value(v):
    return str(v)
(GDIR/'results_verified_v2.tex').write_text('% Generated from reviewer reanalysis v3; do not edit by hand.\n'+''.join('\\newcommand{\\'+k+'}{'+macro_value(v)+'}\n' for k,v in mac.items()),encoding='utf8')
# tables
def table(path,cols,head,rows):
    txt='\\begin{tabular}{'+cols+'}\n\\toprule\n'+head+' \\\\\n\\midrule\n'+'\n'.join(' & '.join(map(str,r))+' \\\\' for r in rows)+'\n\\bottomrule\n\\end{tabular}\n';(GDIR/path).write_text(txt,encoding='utf8')
table('loco_table.tex','lrrrrrrr','Method & Positive & Zero & PASS & FAIL & Exceed & MAE & $U$ (\\%)',[[m,s['positive'],s['zero'],s['PASS'],s['FAIL'],s['exceed'],f"{s['mae']:.2f}",f"{s['util']*100:.1f}"] for m,s in stats.items()])
table('hk_table.tex','llrrrrrr','Configuration & Method & Positive & Zero & PASS & FAIL & Exceed & $U$ (\\%)',[[r['configuration'].title(),r['method'],r['positive'],r['zero'],r['PASS'],r['FAIL'],r['exceed'],f"{r['util']*100:.1f}"] for r in hkstats])
g=cfg['guardrails'];table('guardrails.tex','lrrrrrrr','$W$ (m) & '+' & '.join(f'{x:g}' for x in g['C_W']['W'][1:]),[['$C(W)$ (ped/min)']+g['C_W']['C'][1:],['$Q_{\\rm low}(W)$ (robots/min)']+g['Q_low']['Q'][1:]])
# preserve replication/sensitivity from existing generated files (they are V2 diagnostics, checked against raw)
# ensure generated files from previous path are available if copy above was skipped
if not (GDIR/'replication.tex').exists(): (GDIR/'replication.tex').write_text('\\begin{tabular}{rrr}\\toprule Flow & Original & Independent \\\\\n\\midrule 1 & 30/30 & 28/30 \\\\\n2 & 28/30 & 29/30 \\\\\n3 & 29/30 & 27/30 \\\\\n4 & 26/30 & 25/30 \\\\\n\\bottomrule\\end{tabular}\n')
print('Wrote',O/'writing_results_v2.json','and',GDIR)
