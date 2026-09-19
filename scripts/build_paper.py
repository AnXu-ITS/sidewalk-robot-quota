"""Compile the committed submission source in an isolated output directory."""
from pathlib import Path
import shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'outputs/paper';out.mkdir(parents=True,exist_ok=True)
for p in (ROOT/'paper').iterdir():
    if p.is_dir():shutil.copytree(p,out/p.name,dirs_exist_ok=True)
    elif p.suffix in ['.tex','.bib','.cls','.bst']:shutil.copy2(p,out/p.name)
for cmd in [['pdflatex','-interaction=nonstopmode','-halt-on-error','ascexmpl-new.tex'],['bibtex','ascexmpl-new'],['pdflatex','-interaction=nonstopmode','-halt-on-error','ascexmpl-new.tex'],['pdflatex','-interaction=nonstopmode','-halt-on-error','ascexmpl-new.tex']]:
    subprocess.run(cmd,cwd=out,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
log=(out/'ascexmpl-new.log').read_text(errors='replace')
assert 'Overfull' not in log and 'undefined' not in log
print(out/'ascexmpl-new.pdf')
