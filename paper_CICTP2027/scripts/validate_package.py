"""Check the publication package, scientific version and compiled manuscript."""
from pathlib import Path
import argparse,ast,hashlib,json,re
import numpy as np
import pandas as pd
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--results',type=Path,default=ROOT/'outputs/reproduced');args=ap.parse_args()
    integrity=json.loads((args.results/'integrity.json').read_text(encoding='utf-8'))
    assert integrity['status']=='PASS' and integrity['new_simulations_executed']==0
    v=pd.read_csv(ROOT/'configs/VERSION_PARAMETERS.csv').set_index('version')
    assert np.isclose(v.loc['D2_202609','c'],24.374155890965095)
    assert np.isclose(v.loc['CICTP2027_primary_plus_E1_E5','c'],23.841787076606813)
    assert v.c.nunique()==3 and v.p.nunique()==3
    source=(ROOT/'manuscript/ascexmpl-new.tex').read_text(encoding='utf-8')
    abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',source,re.S).group(1)
    keywords=re.search(r'\\KeyWords\{([^}]+)\}',source).group(1).split(';')
    assert len(abstract.split())<=300 and len(keywords)<=5
    assert source.count(r'\begin{figure}')==4 and source.count(r'\begin{table}')==3
    assert 'Source and permission statement pending' not in source
    assert 'CC0 1.0' in source and 'Retired electrician' in source
    selection=pd.read_csv(ROOT/'figures/HK_REPRESENTATIVE_SELECTION.csv')
    assert len(selection)==8 and selection.tag.nunique()==8
    assert selection.configuration.value_counts().to_dict()=={'ORIGINAL':4,'REPAIRED':4}
    assert selection.selection_uses_service_outcomes.eq(False).all()
    all18=json.loads((ROOT/'figures/hong_kong_all18_metric.provenance.json').read_text(encoding='utf-8'))
    assert all18['case_count']==18 and all18['total_evaluated_cases']==18
    assert all18['independent_rescaling']==False and all18['new_simulations']==0
    release='https://github.com/AnXu-ITS/sidewalk-robot-quota/releases/tag/cictp2027-v1.0.0'
    assert release in source
    d=fitz.open(ROOT/'manuscript/ascexmpl-new.pdf');assert len(d)<=12
    uris=[l.get('uri') for p in d for l in p.get_links() if l.get('uri')]
    assert release in uris
    text='\n'.join(p.get_text() for p in d)
    assert 'Jin et al. 2026' in text
    full_sentence='A zero denominator is undefined and fails the flow component.'
    service_pages=[i for i,p in enumerate(d) if full_sentence in ' '.join(p.get_text().split())]
    assert len(service_pages)==1,'The service sentence must remain continuous on one page'
    framework_pages=[i for i,p in enumerate(d) if 'Fig. 2.' in p.get_text()]
    assert len(framework_pages)==1 and service_pages[0]<=framework_pages[0]
    if service_pages[0]==framework_pages[0]:
        t=' '.join(d[service_pages[0]].get_text().split())
        assert t.index(full_sentence)<t.index('Fig. 2.')
    # Bounds check individual visible text spans. Content outside page is not accepted.
    clipped=[]
    for i,p in enumerate(d):
        for block in p.get_text('dict')['blocks']:
            if block['type']!=0:continue
            for line in block['lines']:
                for s in line['spans']:
                    b=fitz.Rect(s['bbox'])
                    if b.x0<-.5 or b.y0<-.5 or b.x1>p.rect.width+.5 or b.y1>p.rect.height+.5:clipped.append((i+1,s['text']))
    assert not clipped,clipped
    files=[p for p in ROOT.rglob('*') if p.is_file() and 'outputs' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts]
    private=[];secrets=[]
    for p in files:
        if p.suffix not in ['.py','.md','.json','.csv','.tsv','.tex','.bib','.yml','.cff','.txt']:continue
        t=p.read_text(encoding='utf-8',errors='replace')
        if re.search(r'[A-Za-z]:[/\\](?:Users|quota_experiment)',t):private.append(p.relative_to(ROOT).as_posix())
        if re.search(r'gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',t):secrets.append(p.relative_to(ROOT).as_posix())
    assert not private,('Developer paths',private)
    assert not secrets,('Potential credentials',secrets)
    for p in ROOT.glob('scripts/*.py'):ast.parse(p.read_text(encoding='utf-8'))
    largest=max(p.stat().st_size for p in files);assert largest<100*1024*1024
    # Every public scientific outcome must map to an archived complete group.
    s=pd.read_csv(ROOT/'experiments/E2_margin_sweep/E2_MARGIN_SWEEP_SCENARIOS.csv')
    assert s[s.quota.gt(0)].service_status.isin(['PASS','FAIL']).all()
    assert s[s.quota.gt(0)].reuse_valid.eq(True).all()
    result=dict(status='PASS',pages=len(d),figures=4,tables=3,abstract_words=len(abstract.split()),keywords=len(keywords),
                public_files=len(files),largest_file_bytes=largest,private_paths_found=0,credentials_found=0,off_page_text=0,
                release_url=release,reproduced_main_results=True,separated_scientific_versions=True,
                scene_license='CC0 1.0',main_hk_examples=8,repository_hk_configurations=18,
                service_sentence_continuous=True)
    output=ROOT/'outputs/package_validation.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
