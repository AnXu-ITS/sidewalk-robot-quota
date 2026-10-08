"""Compile the portable ASCE project without changing the archived manuscript."""
from pathlib import Path
import argparse,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'outputs/manuscript');args=ap.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    latex=shutil.which('pdflatex');bib=shutil.which('bibtex')
    assert latex and bib,'Install pdfLaTeX/BibTeX or use the supplied Overleaf-ready project'
    cmd=[latex,'-interaction=nonstopmode','-halt-on-error','-file-line-error','-output-directory='+str(output),'ascexmpl-new.tex']
    logs=[]
    def execute(c,cwd):
        r=subprocess.run(c,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        logs.append(r.stdout+r.stderr)
        (output/'build.log').write_text('\n'.join(logs),encoding='utf-8')
        assert r.returncode==0,'Build failed; inspect '+str(output/'build.log')
    execute(cmd,ROOT/'manuscript')
    # BibTeX resolves inputs relative to cwd; copy only the bibliography/style.
    shutil.copyfile(ROOT/'manuscript/ascexmpl-new.bib',output/'ascexmpl-new.bib')
    shutil.copyfile(ROOT/'manuscript/ascelike-new.bst',output/'ascelike-new.bst')
    execute([bib,'ascexmpl-new'],output)
    execute(cmd,ROOT/'manuscript');execute(cmd,ROOT/'manuscript')
    print(output/'ascexmpl-new.pdf')

if __name__=='__main__':main()
