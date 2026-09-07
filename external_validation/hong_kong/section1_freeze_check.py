# -*- coding: utf-8 -*-
"""Section 1 — freeze & isolation verification for the HK formal external test.

Verifies (read-only):
  * D2 7-city list (HK absent)
  * D2 reference dataset SHA-256 vs frozen config claim
  * frozen config / runtime / docs SHA-256 vs repository SHA256SUMS.txt
  * frozen constants (c, p, delta) + execution order + baseline qualification
  * code version (method_version, git_commit)
Writes results to reports/hk_freeze_verification.json (NO frozen file modified).
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FREEZE = os.path.join(REPO, "final_freeze")

FROZEN_C = 24.374155890965095
FROZEN_P = -0.9454494315945483
FROZEN_DELTA = 3.1068


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().lower()


def main():
    cfg = json.load(open(os.path.join(FREEZE, "final_quota_method_config.json"),
                         encoding="utf-8"))
    out = {}

    # 1. city list
    cities = cfg["dataset"]["cities"]
    out["d2_cities"] = cities
    out["hongkong_absent"] = "hongkong" not in [c.lower() for c in cities]

    # 2. D2 dataset SHA-256
    d2_path = os.path.join(REPO, *cfg["dataset"]["path"].split("/"))
    d2_sha = sha256_file(d2_path) if os.path.exists(d2_path) else None
    out["d2_dataset"] = dict(
        path=cfg["dataset"]["path"], claimed_sha=cfg["dataset"]["sha256"],
        actual_sha=d2_sha, sha_match=(d2_sha == cfg["dataset"]["sha256"].lower()),
        rows=cfg["dataset"]["rows"])

    # 3. frozen constants + rule
    out["constants"] = dict(
        c=float(cfg["nominal_model"]["c"]), p=float(cfg["nominal_model"]["p"]),
        delta=float(cfg["safety_margin"]["delta"]),
        c_match=abs(float(cfg["nominal_model"]["c"]) - FROZEN_C) < 1e-12,
        p_match=abs(float(cfg["nominal_model"]["p"]) - FROZEN_P) < 1e-12,
        delta_match=abs(float(cfg["safety_margin"]["delta"]) - FROZEN_DELTA) < 1e-9)
    out["execution_order"] = cfg["execution_order"]
    out["baseline_qualification"] = cfg["baseline_qualification"]
    out["base_pass_note"] = cfg["baseline_qualification"].get("note")
    out["method_version"] = cfg["method_version"]
    out["git_commit"] = cfg["git_commit"]

    # 4. frozen file SHA-256 vs repository manifest
    manifest = {}
    sums_path = os.path.join(FREEZE, "SHA256SUMS.txt")
    if os.path.exists(sums_path):
        for line in open(sums_path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) == 2:
                manifest[parts[1]] = parts[0].lower()
    targets = ["final_quota_method_config.json",
               "final_quota_method_config.yaml",
               "src/operational_quota.py",
               "final_operational_rule.md",
               "base_pass_deployment_final.md"]
    out["frozen_file_sha"] = []
    for t in targets:
        p = os.path.join(FREEZE, t)
        actual = sha256_file(p) if os.path.exists(p) else None
        key = "final_freeze/" + t.replace(os.sep, "/")
        claimed = manifest.get(key)
        out["frozen_file_sha"].append(dict(
            file=t, actual=actual, claimed=claimed,
            match=(actual is not None and claimed is not None and actual == claimed)))
    all_match = all(r["match"] for r in out["frozen_file_sha"])

    # 5. runtime self-test (read-only import)
    import sys
    sys.path.insert(0, os.path.join(FREEZE, "src"))
    import operational_quota as oq
    m = oq.OperationalQuota()
    selftest = [
        (2.5, 12, 1, None, None, 10.0),
        (2.5, 12, 0, None, None, 0.0),
        (1.4, 12, 1, None, None, None),
    ]
    st_ok = all(m.quota(a[0], a[1], a[2], a[3], a[4]) == a[5] for a in selftest)
    out["runtime_selftest_ok"] = bool(st_ok)

    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    with open(os.path.join(HERE, "reports", "hk_freeze_verification.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)

    print(json.dumps(out, indent=2, default=str))
    print("\nALL_FROZEN_FILES_MATCH:", all_match,
          "| sha_match:", out["d2_dataset"]["sha_match"],
          "| hk_absent:", out["hongkong_absent"],
          "| selftest:", st_ok)


if __name__ == "__main__":
    main()
