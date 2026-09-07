# -*- coding: utf-8 -*-
"""Section 8 — SHA-256 manifest of every HK formal-external-test output.

Produces HONG_KONG_SHA256_MANIFEST.txt with one "<hex>  <path>" line per file,
sorted by path, covering reports/, sites/, runs/, figures/ outputs and the
scripts that produced them.
"""
import hashlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = ["reports", "sites", "runs", "figures", "scenarios"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = []
    for root in ROOTS:
        rp = os.path.join(_HERE, root)
        if not os.path.isdir(rp):
            continue
        for dirpath, dirnames, filenames in os.walk(rp):
            # skip transient scenario dirs (per-run artefacts, not deliverables)
            if os.path.basename(dirpath).startswith("HK-ST-") and root == "scenarios":
                continue
            for fn in sorted(filenames):
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, _HERE).replace(os.sep, "/")
                entries.append((rel, sha256(fp)))
    # scripts too (reproducibility)
    for fn in sorted(os.listdir(_HERE)):
        if fn.endswith(".py") and fn.startswith("section"):
            entries.append((fn, sha256(os.path.join(_HERE, fn))))
    entries.sort()
    out = os.path.join(_HERE, "HONG_KONG_SHA256_MANIFEST.txt")
    with open(out, "w", encoding="utf-8") as f:
        for rel, hx in entries:
            f.write(f"{hx}  {rel}\n")
    print(f"wrote {out} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
