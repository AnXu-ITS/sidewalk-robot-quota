# -*- coding: utf-8 -*-
"""Section 2 — geometry execution check: confirm SUMO/JuPedSim actually loaded
the REAL CSDI footway polygon (not an equivalent-area rectangle), entry/exit and
boundaries are correct, and W/L/area/width profile match GIS."""
import json
import os
import re
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon, shape

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = json.load(open(os.path.join(HERE, "sites", "hk_cell_local_geometry.json"),
                     encoding="utf-8"))

# pick one scenario dir per cell (use existing smoke scenarios for HK-ST-01)
SCEN = os.path.join(HERE, "scenarios")


def load_sumo_polygon(add_xml):
    tree = ET.parse(add_xml)
    for poly in tree.getroot():
        if poly.tag == "poly" and poly.get("id") == "walkable":
            s = poly.get("shape")
            pts = [tuple(map(float, p.split(","))) for p in s.split()]
            return Polygon(pts)
    return None


def load_mini_edges(net_xml):
    tree = ET.parse(net_xml)
    edges = {}
    for e in tree.getroot():
        if e.tag != "edge":
            continue
        eid = e.get("id")
        lanes = e.findall("lane")
        if lanes:
            shape_s = lanes[0].get("shape")
            pts = [tuple(map(float, p.split(","))) for p in shape_s.split()]
            edges[eid] = pts
    return edges


def main():
    out = {}
    for cid in ["HK-ST-01", "HK-ST-02", "HK-ST-03"]:
        g = GEO[cid]
        gis_poly = shape({"type": "Polygon",
                          "coordinates": g["walkable_polygon_local"]["coordinates"]})
        cl = g["centerline_local"]
        L = cl[-1][0] - cl[0][0]

        # find a scenario dir for this cell (smoke ones exist for HK-ST-01)
        import glob
        dirs = sorted(glob.glob(os.path.join(SCEN, cid + "_*")))
        if not dirs:
            out[cid] = dict(note="no scenario dir found (not yet simulated)")
            continue
        d = dirs[0]
        sumo_poly = load_sumo_polygon(os.path.join(d, "cell.add.xml"))
        edges = load_mini_edges(os.path.join(d, "cell.net.xml"))

        # 1. polygon identity: area / bounds / perimeter / vertex count
        rec = dict(
            cell=cid, L=L,
            gis_area=round(gis_poly.area, 3),
            sumo_area=round(sumo_poly.area, 3),
            area_ratio=round(sumo_poly.area / gis_poly.area, 6),
            gis_bounds=[round(v, 3) for v in gis_poly.bounds],
            sumo_bounds=[round(v, 3) for v in sumo_poly.bounds],
            gis_n_vertices=len(gis_poly.exterior.coords),
            sumo_n_vertices=len(sumo_poly.exterior.coords),
            sumo_is_rectangle=sumo_poly.equals(sumo_poly.minimum_rotated_rectangle),
            sym_diff_area=round(gis_poly.symmetric_difference(sumo_poly).area, 4),
        )
        # 2. mini edges
        for eid, pts in sorted(edges.items()):
            rec[f"edge_{eid}"] = [[round(x, 3), round(y, 3)] for x, y in pts]
        # 3. symmetry-difference: how close is SUMO poly to GIS poly
        rec["sym_diff_ratio"] = round(
            gis_poly.symmetric_difference(sumo_poly).area / gis_poly.area, 6)
        out[cid] = rec

    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    with open(os.path.join(HERE, "reports", "hk_geometry_execution_check.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
