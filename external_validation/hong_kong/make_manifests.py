# -*- coding: utf-8 -*-
"""Generate SHA-256 manifests for all HK external-test deliverables."""
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MAN = os.path.join(HERE, "manifests")
os.makedirs(MAN, exist_ok=True)

GROUPS = [
    ("hk_raw_manifest.txt", ["data/raw"]),
    ("hk_processed_manifest.txt", ["data/processed", "data/metadata"]),
    ("hk_sites_manifest.txt", ["sites"]),
    ("hk_reports_manifest.txt", ["reports"]),
    ("hk_figures_manifest.txt", ["figures"]),
    ("hk_smoke_runs_manifest.txt", ["runs/smoke"]),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def files_under(rel):
    root = os.path.join(HERE, rel)
    out = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            out.append(os.path.join(dp, fn))
    return out


for name, roots in GROUPS:
    lines = ["# SHA-256 manifest (external_validation/hong_kong)", ""]
    total = 0
    for rel in roots:
        for fp in sorted(files_under(rel)):
            if fp.endswith(".zip") and rel == "data/raw":
                continue  # raw zips already in raw manifest via files_under
            relp = os.path.relpath(fp, HERE)
            lines.append(f"{sha256(fp)}  {relp}")
            total += 1
    with open(os.path.join(MAN, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{name}: {total} files")

# also a single combined manifest
allfiles = []
for _, roots in GROUPS:
    for rel in roots:
        allfiles.extend(files_under(rel))
lines = ["# Combined SHA-256 manifest (external_validation/hong_kong)", ""]
for fp in sorted(allfiles):
    relp = os.path.relpath(fp, HERE)
    lines.append(f"{sha256(fp)}  {relp}")
with open(os.path.join(MAN, "hk_all_manifest.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("hk_all_manifest.txt:", len(allfiles), "files")
