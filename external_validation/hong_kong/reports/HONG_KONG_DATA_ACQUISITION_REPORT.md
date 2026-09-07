# Hong Kong External Test — Data Acquisition Report (Q1)

**Round scope:** official data download → data quality review → small-area selection →
real geometry → SUMO–JuPedSim smoke test → READY / NOT READY.
**Discipline:** read-only on frozen D2 assets. This report covers Q1 (sources & acquisition).

## 1. Independence check

The frozen reference dataset (`final_freeze/final_quota_method_config.json`
→ `dataset.cities`) contains exactly 7 cities:

`amsterdam, melbourne, newtaipei, nyc, seattle, taipei, taoyuan`

**Hong Kong is absent.** The frozen city list also appears in
`data/final/full_reference_dataset.csv` (D2, 400 rows, 7 cities only).
Therefore Hong Kong is a genuinely **independent external test city**; no
re-fitting or parameter tuning was (or will be) done on HK data.

## 2. Official data sources (CSDI — Hong Kong CSDI Portal)

Both sources are the **official CSDI datasets** (NOT third-party mirrors).

### Source A — Pavement Polygon (Highways Department)

| field | value |
|---|---|
| Provider | Highways Department (路政署) |
| Dataset | Pavement Polygon (行人路/行车道多边形) |
| CSDI dataset id | `hyd_rcd_1632210918434_60749` |
| Layer | `INV_PG` |
| Portal | `https://portal.csdi.gov.hk` (ArcGIS Geoportal Server SPA) |
| Download endpoint | `/csdi-webpage/file-api` |
| Full request URL | `https://portal.csdi.gov.hk/csdi-webpage/file-api?dataset_id=hyd_rcd_1632210918434_60749&format=geojson&layer_name=INV_PG` |
| Service type | HTTP GET (GeoJSON export), TLS 1.3, resumable |
| Format delivered | GeoJSON (FeatureCollection), EPSG:4326 |
| Size | 332,747,464 bytes (≈332 MB) |
| SHA-256 | `EB978B50E6031B0E264318CEB5DA1F5F8446F1833F95CA10F94D945666A08B3E` |
| Download time (local) | 2026-09-07 12:24:31 |
| Tool | `curl.exe 8.21.0` (`--retry 5 --retry-all-errors -C -`) |

### Source B — Digital Topographic Map iB1000 (Lands Department)

| field | value |
|---|---|
| Provider | Lands Department (地政總署) |
| Dataset | Digital Topographic Map iB1000 |
| CSDI dataset id | `landsd_rcd_1637223748322_25497` |
| Layer exposed on CSDI | `TileIndex` (3333 tile polygons with per-sheet download links) |
| Full request URL (index) | `https://portal.csdi.gov.hk/csdi-webpage/file-api?dataset_id=landsd_rcd_1637223748322_25497&format=geojson&layer_name=TileIndex` |
| Index size | 3,876,132 bytes (≈3.9 MB) |
| Index SHA-256 | `257AC0109A785CDA5F645B37E7416F56ACD6BCCBDBB2CF2B9BE45136820B8D0F` |
| Download time (local) | 2026-09-07 12:23:29 |

The CSDI `iB1000` dataset exposes the **tile index**; the actual topographic
sheets (buildings / roads / obstacles) are served by the official HK Map Service
(`open.hkmapservice.gov.hk`). One sheet covering the study cells was downloaded
as the auxiliary cross-check:

| field | value |
|---|---|
| Sheet | `7-SE-11C` (covers HK-ST-01 / HK-ST-02) |
| Request URL | `https://open.hkmapservice.gov.hk/OpenData/directDownload?productName=iB1000&sheetName=T7-SE-11C&productFormat=FGDB` |
| Format | File Geodatabase (`.gdb` inside ZIP) |
| Size | 42,275,847 bytes (≈42 MB) |
| SHA-256 | `7B72CD791423D71384748050F654DC45E8273DBDA33C3F2717F384480D691002` |
| Download time (local) | 2026-09-07 12:36:25 |

Full seamless iB1000 is also available via
`directDownload?productName=iB1000&sheetName=Fullset_Seamless&productFormat=FGDB`
(very large); not needed for the smoke round.

## 3. Acquisition method notes

- The CSDI "download common" links (`/csdi-webpage/download/common/<hash>`) return
  **403 (Azure Front Door WAF)** even with browser headers; the working official
  route is the `/csdi-webpage/file-api` export endpoint above (HTTP 200).
- A first attempt with Python `urllib` failed with `ssl.SSLEOFError` on the 332 MB
  stream; switched to `curl.exe` with retries + resume, both completed cleanly.
- No third-party mirror was used for any authoritative download.

## 4. Raw-file manifest

| file | bytes | SHA-256 |
|---|---|---|
| `data/raw/INV_PG_CSDI_INV_PG_converted.geojson` | 332,747,464 | `EB978B50…A08B3E` |
| `data/raw/iB1000_Index_2026_08_13_TileIndex_converted.geojson` | 3,876,132 | `257AC010…20B8D0F` |
| `data/raw/iB1000_7-SE-11C_FGDB.zip` | 42,275,847 | `7B72CD79…D691002` |

(SHA-256 full digests recorded in `manifests/hk_raw_manifest.txt`.)
