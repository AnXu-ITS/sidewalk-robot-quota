# -*- coding: utf-8 -*-
"""Recompute max_turn_deg / cum_turn_deg for all cells in cells.json with the
zero-length-segment guard, and write the corrected values back in place.

The SUMO/JuPedSim ground truth used the centerline (unchanged) — only the
turn-angle METRICS were corrupted by duplicate points, so no re-simulation is
needed.  Also verifies L/sinuosity are unaffected.
"""
import json
import math


def ang_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def fixed_geometry(sub):
    brgs = []
    path = 0.0
    for i in range(len(sub) - 1):
        dx, dy = sub[i + 1][0] - sub[i][0], sub[i + 1][1] - sub[i][1]
        d = math.hypot(dx, dy)
        path += d
        if d > 1e-6:
            brgs.append((math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0)
    max_turn = max((ang_diff(brgs[i], brgs[i + 1]) for i in range(len(brgs) - 1)),
                   default=0.0)
    cum_turn = sum(ang_diff(brgs[i], brgs[i + 1]) for i in range(len(brgs) - 1))
    chord = math.hypot(sub[-1][0] - sub[0][0], sub[-1][1] - sub[0][1])
    sinu = path / chord if chord > 0.05 else 1.0
    return path, max_turn, cum_turn, sinu


def main():
    path = r"sumo_jupedsim\data\cells.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    for c in data["cells"]:
        old_max, old_cum = c["max_turn_deg"], c["cum_turn_deg"]
        L, mt, ct, sinu = fixed_geometry(c["centerline"])
        c["max_turn_deg"] = round(mt, 1)
        c["cum_turn_deg"] = round(ct, 1)
        # keep stored L/sinuosity (should match; report if not)
        if abs(c["L"] - L) > 0.5 or abs(c["sinuosity"] - sinu) > 0.002:
            print(f"  !! {c['cell_id']}: L {c['L']}->{L:.1f} "
                  f"sin {c['sinuosity']}->{sinu:.3f}")
        if abs(old_max - mt) > 0.5 or abs(old_cum - ct) > 0.5:
            changed += 1
            if abs(old_max - mt) > 20:
                print(f"  {c['cell_id']}: max_turn {old_max}->{mt:.1f} "
                      f"cum {old_cum}->{ct:.1f} (type {c['type']})")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nupdated cells.json in place; {changed}/{len(data['cells'])} cells "
          f"had turn-angle correction")


if __name__ == "__main__":
    main()
