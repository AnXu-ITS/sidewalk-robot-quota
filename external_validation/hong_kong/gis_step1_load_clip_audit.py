# -*- coding: utf-8 -*-
"""
HK external test — GIS step 1: load, clip to Sha Tin, classify, audit.

The CSDI file-api GEOJSON is WGS84 (EPSG:4326) with FEAT_TYPE / LVL already
decoded to human-readable STRINGS (unlike the ArcGIS REST service which uses
coded integers). We clip with a WGS84 bbox around Sha Tin Town Centre, then
reproject the working clip to EPSG:2326 (HK1980 Grid) for metric geometry.

Only writes under external_validation/hong_kong/. Never touches D2 data.
"""
import json
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.validation import explain_validity

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
PROC = os.path.join(HERE, "data", "processed")
META = os.path.join(HERE, "data", "metadata")
os.makedirs(PROC, exist_ok=True)
os.makedirs(META, exist_ok=True)

# Sha Tin Town Centre WGS84 bbox (generous ~2.4 km x 2.6 km first clip)
SHA_TIN_WGS84 = (114.178, 22.368, 114.202, 22.392)  # minx, miny, maxx, maxy

# Ground-level public footway classification (string-coded in the GEOJSON)
FOOTWAY_LABELS = {"Footway", "PTI-Footway", "Carpark-Footway"}
GROUND_LABEL = "Ground level"


def _fmt(g):
    return "" if g.is_valid else explain_validity(g)


def main():
    src = os.path.join(RAW, "INV_PG_CSDI_INV_PG_converted.geojson")
    if not os.path.exists(src):
        print(f"[BLOCKED] raw file not found: {src}")
        sys.exit(3)
    print("Reading full Pavement-Polygon GEOJSON (WGS84 bbox-filtered) ...",
          flush=True)
    gdf = gpd.read_file(src, bbox=SHA_TIN_WGS84)
    print(f"clipped features in Sha Tin WGS84 envelope: {len(gdf)}", flush=True)
    print("file CRS:", gdf.crs, flush=True)

    # ensure a single active geometry column
    gdf = gdf.set_geometry("geometry")

    print("columns:", list(gdf.columns), flush=True)

    # ---- classification by decoded strings -------------------------------
    gdf["is_footway"] = gdf["FEAT_TYPE"].isin(FOOTWAY_LABELS)
    gdf["is_ground"] = (gdf["LVL"] == GROUND_LABEL)
    gdf["is_ground_public_footway"] = gdf["is_footway"] & gdf["is_ground"]

    print("\nFEAT_TYPE distribution (clip):")
    print(gdf["FEAT_TYPE"].value_counts(dropna=False).to_string())
    print("\nLVL distribution (clip):")
    print(gdf["LVL"].value_counts(dropna=False).to_string())
    print("\nground-level footway flags:")
    print("  footway(any lvl):", int(gdf["is_footway"].sum()),
          "| ground:", int(gdf["is_ground"].sum()),
          "| ground+footway:", int(gdf["is_ground_public_footway"].sum()))

    # ---- attribute audit ---------------------------------------------------
    key_fields = ["PG_UID", "FEAT_TYPE", "SUR_TYPE_1", "PAVER_TYPE", "LVL"]
    null_rate = {c: float(gdf[c].isna().mean()) for c in key_fields
                 if c in gdf.columns}
    print("\nnull rates (clip):", json.dumps(null_rate, indent=2))
    dup = int(gdf["PG_UID"].duplicated().sum())
    print("duplicate PG_UID in clip:", dup)

    # ---- geometry validity --------------------------------------------------
    n_invalid = int((~gdf.geometry.is_valid).sum())
    n_empty = int(gdf.geometry.is_empty.sum())
    print("invalid geometries:", n_invalid, "| empty:", n_empty)
    print("geometry types:", gdf.geom_type.value_counts(dropna=False).to_dict())

    # ---- write clip in both CRS -------------------------------------------
    gdf.to_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_wgs84.gpkg"),
                driver="GPKG", layer="inv_pg_clip")
    gdf_2326 = gdf.to_crs("EPSG:2326")
    gdf_2326.to_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"),
                     driver="GPKG", layer="inv_pg_clip")
    print("\nwrote clips (wgs84 + hk1980) to data/processed/", flush=True)

    # ---- schema/quality audit CSV -----------------------------------------
    audit_rows = []
    for c in list(gdf.columns):
        col = gdf[c]
        audit_rows.append(dict(
            layer="INV_PG", column=c,
            dtype=str(col.dtype),
            null_rate=float(col.isna().mean()),
            n_unique=int(col.nunique(dropna=True)),
            sample=repr(col.dropna().iloc[0]) if len(col.dropna()) else "",
        ))
    pd.DataFrame(audit_rows).to_csv(
        os.path.join(META, "layer_schema_audit.csv"), index=False)
    print("wrote metadata/layer_schema_audit.csv", flush=True)


if __name__ == "__main__":
    main()
