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
    assert source.count(r'\begin{figure}')==3 and source.count(r'\begin{table}')==3
    release='https://github.com/AnXu-ITS/sidewalk-robot-quota/releases/tag/cictp2027-v1.0.0'
    assert release in source
    d=fitz.open(ROOT/'manuscript/ascexmpl-new.pdf');assert len(d)<=12
    uris=[l.get('uri') for p in d for l in p.get_links() if l.get('uri')]
    assert release in uris
    text='\n'.join(p.get_text() for p in d)
    assert 'Jin et al. 2026' in text
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
    result=dict(status='PASS',pages=len(d),figures=3,tables=3,abstract_words=len(abstract.split()),keywords=len(keywords),
                public_files=len(files),largest_file_bytes=largest,private_paths_found=0,credentials_found=0,off_page_text=0,
                release_url=release,reproduced_main_results=True,separated_scientific_versions=True)
    output=ROOT/'outputs/package_validation.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
