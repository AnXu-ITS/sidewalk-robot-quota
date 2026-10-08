"""Build a CC0 scene with vector labels and geometry-only Hong Kong selections.

Preserve input photo pixels, all frozen flows and all 18 configurations.
No simulation, fitting or scientific retuning occurs.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, sys
import numpy as np
import pandas as pd
import pymupdf as fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/figure_qa'))
from audit_panel_alignment import require_matplotlib_panel_alignment

COMMONS_URL='https://commons.wikimedia.org/wiki/File:Moscow,_Yandex_employee_walking_his_pet_A-505_robot,_Aug_2025_04.jpg'

def draw_scene(photo, out, qa):
    supplied=photo.read_bytes(); pix=fitz.Pixmap(supplied)
    assert pix.width==pix.height and pix.width>=1280
    doc=fitz.open(); page=doc.new_page(width=414,height=264)
    # Embed the original JPEG stream. Text, boxes, leaders and target rings
    # are separate native PDF vector objects; no photo pixels are edited.
    rect=fitz.Rect(81,6,333,258)
    page.insert_image(rect,stream=supplied)
    for box in [fitz.Rect(3,135,79,161),fitz.Rect(340,79,412,165)]:
        page.draw_rect(box,color=(.18,.20,.22),fill=(1,1,1),width=.65,radius=3/box.height)
    page.insert_text((8,151.3),'Delivery robot',fontname='helv',fontsize=10)
    for x,y,t,size in [(347,94,'Shared',10),(347,106,'sidewalk space',9.1),
                       (347,128,'Pedestrians',8.4),(347,149,'Delivery robots',8.4)]:
        page.insert_text((x,y),t,fontname='helv',fontsize=size)
    for y in [125,146]:page.draw_circle((343.7,y),radius=.8,color=(.1,.1,.1),fill=(.1,.1,.1))
    for a,b in [((79,157),(195,181)),((340,158),(307,225))]:
        page.draw_line(a,b,color=(.12,.12,.12),width=.7)
        page.draw_circle(b,radius=2.6,color=(.12,.12,.12),fill=(1,1,1),width=.75)
    doc.save(out/'figure1_scene.pdf',deflate=True)
    page.get_pixmap(matrix=fitz.Matrix(3,3)).save(out/'figure1_scene.png')
    (out/'figure1_scene.svg').write_text(page.get_svg_image(text_as_path=False),encoding='utf-8')
    photo_manifest=dict(source=COMMONS_URL,author='Retired electrician',license='CC0 1.0 Universal',
        license_url='https://creativecommons.org/publicdomain/zero/1.0/',verified_date='2026-10-08',
        original_file_name='Moscow, Yandex employee walking his pet A-505 robot, Aug 2025 04.jpg',
        source_page_revision=1278797906,local_resolution=[pix.width,pix.height],
        photo_sha256=hashlib.sha256(supplied).hexdigest(),photo_pixels_modified=False,
        annotations='Separate editable PDF text and vector callouts; added by authors',
        evidentiary_role='Illustrative scene only; no measurement or robot-model validation')
    (qa/'scene_provenance.json').write_text(json.dumps(photo_manifest,indent=2),encoding='utf-8')

def select_representatives(cases, meta, geo, specs):
    """Four original and four repaired examples; no q*, quota or service inputs."""
    groups={c:list(z.tag) for c,z in cases.groupby('configuration')}
    chosen=[]; records=[]
    def choose(group,reason,key,reverse=False):
        options=[t for t in groups[group] if t not in chosen]
        # Stable lexical tie-break followed by stable numeric ordering.
        tag=sorted(sorted(options),key=key,reverse=reverse)[0]
        chosen.append(tag); records.append(dict(tag=tag,configuration=group,selection_reason=reason,
            W_m=float(meta.loc[tag,'W']),sinuosity=float(meta.loc[tag,'sinuosity']),rect_fill=float(meta.loc[tag,'rect_fill']),
            selection_uses_service_outcomes=False))
    def displacement(tag):
        rs=next(v['spec'] for v in specs if v['spec']['tag']==tag and v['configuration']=='nearest-safe-anchor-v1')
        return float(np.linalg.norm(np.array(rs['entrance_anchors'])-np.array(geo[tag]['centerline_local'])[[0,-1]],axis=1).sum())
    choose('ORIGINAL','Narrowest original representative input width',lambda t:meta.loc[t,'W'])
    choose('ORIGINAL','Straightest remaining original centreline',lambda t:meta.loc[t,'sinuosity'])
    choose('ORIGINAL','Widest remaining original representative input width',lambda t:meta.loc[t,'W'],True)
    choose('ORIGINAL','Lowest remaining original polygon rectangular fill',lambda t:meta.loc[t,'rect_fill'])
    choose('REPAIRED','Narrowest repaired representative input width',lambda t:meta.loc[t,'W'])
    choose('REPAIRED','Highest remaining repaired centreline sinuosity',lambda t:meta.loc[t,'sinuosity'],True)
    choose('REPAIRED','Lowest remaining repaired polygon rectangular fill',lambda t:meta.loc[t,'rect_fill'])
    choose('REPAIRED','Largest remaining sum of endpoint-to-anchor displacements',displacement,True)
    assert chosen==['HK-ST-06','HK-ST-15','HK-ST-25','HK-ST-28','HK-ST-05','HK-ST-16','HK-ST-22','HK-ST-24']
    return chosen,records

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scene', type=Path, default=ROOT/'manuscript/visual_revision_20261008/sources/yandex_moscow_cc0.jpg')
    ap.add_argument('--output', type=Path, default=ROOT/'outputs/visual_revision')
    args = ap.parse_args()
    out=args.output/'figures'; qa=args.output/'qa'
    out.mkdir(parents=True,exist_ok=True);qa.mkdir(exist_ok=True)
    draw_scene(args.scene,out,qa)
    for old, new in [('figure1','figure2_framework'), ('figure2','figure3_tradeoff')]:
        for ext in ['pdf','svg','png']:
            shutil.copyfile(ROOT/f'manuscript/refinement_20261008/figures/{old}.{ext}', out/f'{new}.{ext}')

    inputs = {'flows': ROOT/'data/hong_kong/hk_analysis_v3.csv',
              'geometry': ROOT/'data/scenarios/hk_formal_local_geometry.json',
              'widths': ROOT/'data/scenarios/HONG_KONG_FORMAL_SAMPLE_FREEZE.csv',
              'specs': ROOT/'configs/run_specs.json'}
    h = pd.read_csv(inputs['flows'])
    geo = json.loads(inputs['geometry'].read_text(encoding='utf-8'))
    meta = pd.read_csv(inputs['widths']).set_index('cell_id')
    specs = json.loads(inputs['specs'].read_text(encoding='utf-8'))
    cases = h[h.method.eq('M0')][['tag','configuration']]
    assert len(cases) == 18 and not cases.tag.duplicated().any()
    assert len(h) == 72 and not h.duplicated(['tag','method']).any()
    assert h.quota.notna().all() and h.q_star.notna().all()
    selected,selection=select_representatives(cases,meta,geo,specs)
    assert len(selected)==8 and len(set(selected))==8
    pd.DataFrame(selection).to_csv(qa/'HK_REPRESENTATIVE_SELECTION.csv',index=False)
    draw_hk(cases, h, geo, meta, specs, inputs, out, qa, 'hong_kong_all18_metric')
    chosen=cases.set_index('tag').loc[selected].reset_index()
    draw_hk(chosen, h, geo, meta, specs, inputs, out, qa, 'figure4_hk_representative')
    print('Created CC0 scene with vector annotations, eight examples and complete 18-case metric figure.')


def draw_hk(cases, h, geo, meta, specs, inputs, out, qa, stem):
    n=len(cases);top=(n-1)*7+1
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],
                         'font.size':8.5, 'pdf.fonttype':42, 'svg.fonttype':'none'})
    # One common data axis is also one common physical metres-per-point scale.
    # Each shape receives a vertical row translation only; no rotation or scaling.
    fig, ax = plt.subplots(figsize=(5.75, 6.85 if n==18 else 3.65))
    fig.subplots_adjust(left=.025, right=.99, bottom=.025, top=.985)
    ax.set(xlim=(-30,88), ylim=(-9,top+16), aspect='equal')
    ax.axis('off')
    xs = {'tag':-29, 'W':-9, 'q_star':57, 'M0':69, 'M1':81}
    for x, text, align in [(-29,'Site','left'),(-9,'W (m)','center'),
                           (24,'Local metric plan','center'),(57,'q*','center'),(69,'M0','center'),(81,'M1','center')]:
        ax.text(x,top+12,text,ha=align,va='center',fontweight='bold')
    ax.plot([-29,86],[top+8,top+8], color='#7A858D', lw=.6)
    # A shared scale bar applies to both longitudinal and transverse dimensions.
    ax.plot([12,22],[top+6,top+6], color='#303A41', lw=1)
    ax.plot([12,12],[top+5.4,top+6.6], color='#303A41', lw=.7)
    ax.plot([22,22],[top+5.4,top+6.6], color='#303A41', lw=.7)
    ax.text(24,top+6,'10 m',ha='left',va='center',fontsize=7.5)
    manifest=[]
    for i, row in enumerate(cases.itertuples(index=False)):
        tag, configuration = row.tag, row.configuration
        y=top-i*7
        pts=np.array(geo[tag]['walkable_polygon_local']['coordinates'][0],float)
        assert pts[:,0].min()>-.02 and pts[:,0].max()<50.02 and np.abs(pts[:,1]).max()<3.4
        cl=np.array(geo[tag]['centerline_local'],float)
        repaired=configuration=='REPAIRED'
        if repaired:
            rs=[v['spec'] for v in specs if v['spec']['tag']==tag and v['configuration']=='nearest-safe-anchor-v1']
            assert rs and all(v['entrance_anchors']==rs[0]['entrance_anchors'] for v in rs)
            anchors=np.array(rs[0]['entrance_anchors'],float)
            assert np.allclose(np.array(rs[0]['polygon'][0]),pts)
        else:
            anchors=cl[[0,-1]]
        shifted=pts+np.array([0,y])
        ax.add_patch(Polygon(shifted, facecolor='#E0ECF4', edgecolor='#607583', lw=.55))
        ax.plot(cl[:,0], cl[:,1]+y, color='#96A7B2', lw=.4, linestyle=(0,(2,2)))
        marker='>' if repaired else 'o'
        ax.scatter(anchors[:,0],anchors[:,1]+y,marker=marker,s=14 if repaired else 10,
                   facecolors='#A65D32' if repaired else 'white',edgecolors='#A65D32' if repaired else '#356C89',linewidths=.65,zorder=5)
        # Direction is taken from the recorded source-to-exit ordering.
        start=anchors[0]; end=anchors[1]; mid=(start+end)/2
        direction=(end-start)/np.linalg.norm(end-start)
        ax.annotate('',xy=mid+3*direction+[0,y],xytext=mid-3*direction+[0,y],
                    arrowprops={'arrowstyle':'->','color':'#356C89','lw':.65,'mutation_scale':6})
        label=tag.replace('HK-ST-','')+(' R' if repaired else '')
        ax.text(xs['tag'],y,'HK-ST-'+label,ha='left',va='center',fontsize=8.2)
        ax.text(xs['W'],y,f'{meta.loc[tag,"W"]:.3f}',ha='center',va='center')
        rows=h[h.tag.eq(tag)].set_index('method')
        assert rows.q_star.nunique()==1
        ax.text(xs['q_star'],y,f'{rows.q_star.iloc[0]:g}',ha='center',va='center')
        for method in ['M0','M1']:
            z=rows.loc[method];positive=z.quota>0
            assert not positive or z.exact_flow_status in ['PASS','FAIL']
            label=f'{z.quota:g}'+(' F' if z.exact_flow_status=='FAIL' else '')
            ax.text(xs[method],y,label,ha='center',va='center',color='#A64234' if z.exact_flow_status=='FAIL' else '#1F333F',
                    fontweight='bold' if method=='M0' and positive else 'normal')
        if i+1<len(cases) and cases.iloc[i+1].configuration!=configuration:ax.plot([-29,86],[y-3.5,y-3.5],color='#AAB5BC',lw=.6)
        manifest.append(dict(tag=tag,configuration=configuration,W_m=float(meta.loc[tag,'W']),
                             polygon_local_m=pts.tolist(),display_rotation_deg=0,display_scale=1,
                             display_translation_m=[0,y],marker_coordinates_m=anchors.tolist(),
                             marker_meaning='repaired entrance anchors' if repaired else 'original centreline endpoints'))
    # Legends live in their own rows below all 18 data cases.
    ax.scatter([-28],[ -3],marker='o',s=10,facecolors='white',edgecolors='#356C89',linewidths=.65)
    ax.text(-25,-3,'Original endpoints',va='center',fontsize=7.5)
    ax.scatter([6],[-3],marker='>',s=14,color='#A65D32')
    ax.text(9,-3,'R: repaired anchors',va='center',fontsize=7.5)
    if n==18:ax.text(48,-3,'F: failed direct test',va='center',fontsize=7.5)
    ax.text(-29,-7,'All plans: equal x/y scale. Flows: robots/min; 0 denotes zero admission.',va='center',fontsize=7.5)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=qa/f'{stem}.alignment.json',strict=True)
    fig.savefig(out/f'{stem}.pdf')
    fig.savefig(out/f'{stem}.svg')
    fig.savefig(out/f'{stem}.png',dpi=300)
    fig.savefig(out/f'{stem}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    # Validate rendered equality of a metre along both axes.
    origin=ax.transData.transform((0,0)); unitx=ax.transData.transform((1,0));unity=ax.transData.transform((0,1))
    assert np.isclose(np.linalg.norm(unitx-origin),np.linalg.norm(unity-origin),atol=1e-6)
    provenance=dict(inputs={k:dict(file=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for k,p in inputs.items()},
                    cases=manifest,case_count=n,total_evaluated_cases=18,flow_rows=len(h),independent_rescaling=False,
                    geographic_north_shown=False,coordinates='Existing local metric frame; original GIS preprocessing retained',
                    markers_are_insertion_observations=False,new_simulations=0,
                    metres_per_point=1/(np.linalg.norm(unitx-origin)*72/fig.dpi),
                    selection_uses_service_outcomes=False)
    (qa/f'{stem}.provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    pd.DataFrame([{k:v for k,v in x.items() if k not in ['polygon_local_m','marker_coordinates_m']} for x in manifest]).to_csv(qa/f'{stem}.display_geometry.csv',index=False)
    plt.close(fig)

if __name__=='__main__':main()
