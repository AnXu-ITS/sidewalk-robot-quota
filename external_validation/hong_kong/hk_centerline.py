# -*- coding: utf-8 -*-
"""Centerline + width extraction for real HK footway polygons.

Approach (no raster skeleton needed):
  1. oriented bbox -> long axis u (a stable slicing direction).
  2. cast parallel cross-sections perpendicular to u; for each, keep the longest
     connected chord; its MIDPOINT is a centerline sample, its length an
     approximate width (perpendicular to u).
  3. the midpoint sequence is the centerline (follows gentle curves); resample +
     smooth; then re-measure width perpendicular to the LOCAL centerline tangent
     (true centerline-normal width).
  4. sinuosity = centerline arc-length / end-to-end chord.
"""
import numpy as np
from shapely.geometry import LineString, Point


def obb_axis(geom):
    r = geom.minimum_rotated_rectangle
    c = np.array(list(r.exterior.coords)[:4])
    v1, v2 = c[1] - c[0], c[2] - c[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    if l1 >= l2:
        return l1, l2, v1 / l1, v2 / l2, c[0] + 0.5 * (v1 + v2)
    return l2, l1, v2 / l2, v1 / l1, c[0] + 0.5 * (v1 + v2)


def _longest_line(inter):
    if inter.is_empty:
        return None
    gt = inter.geom_type
    if gt == "LineString":
        return inter
    if gt in ("Point", "MultiPoint", "Polygon", "MultiPolygon"):
        return None
    # MultiLineString or GeometryCollection
    lines = [g for g in inter.geoms if g.geom_type == "LineString"]
    return max(lines, key=lambda g: g.length) if lines else None


def extract_centerline(geom, step=1.0, smooth=3):
    """Return (centerline_pts, arc_len, chord_len) in source CRS units."""
    length, width, u, v, center = obb_axis(geom)
    big = width + 5.0
    mid = []
    s = -length / 2.0
    while s <= length / 2.0 + 1e-6:
        p = center + s * u
        seg = LineString([p - big * v, p + big * v])
        line = _longest_line(geom.intersection(seg))
        if line is not None and line.length > 0.05:
            mid.append((s, np.array([line.interpolate(0.5, normalized=True).x,
                                     line.interpolate(0.5, normalized=True).y])))
        s += step
    if len(mid) < 3:
        # degenerate: fall back to the OBB axis
        pts = [center - (length / 2) * u, center + (length / 2) * u]
        arc = float(np.hypot(*(pts[1] - pts[0])))
        return [np.array(p) for p in pts], arc, arc
    pts = np.array([m for _, m in mid])
    # light smoothing along the sequence
    if smooth > 1 and len(pts) > smooth:
        k = np.ones(smooth) / smooth
        xs = np.convolve(pts[:, 0], k, mode="same")
        ys = np.convolve(pts[:, 1], k, mode="same")
        pts = np.column_stack([xs, ys])
        # pin ends
        pts[0] = mid[0][1]; pts[-1] = mid[-1][1]
    arc = float(np.sum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))))
    chord = float(np.hypot(*(pts[-1] - pts[0])))
    return [np.array(p) for p in pts], arc, chord


def centerline_widths(geom, cl_pts):
    """Width profile perpendicular to the LOCAL centerline tangent."""
    n = len(cl_pts)
    widths = []
    for i in range(n):
        if i == 0:
            t = cl_pts[1] - cl_pts[0]
        elif i == n - 1:
            t = cl_pts[-1] - cl_pts[-2]
        else:
            t = cl_pts[i + 1] - cl_pts[i - 1]
        tn = np.hypot(*t)
        if tn < 1e-9:
            continue
        nrm = np.array([-t[1] / tn, t[0] / tn])
        seg = LineString([cl_pts[i] - 4.0 * nrm, cl_pts[i] + 4.0 * nrm])
        line = _longest_line(geom.intersection(seg))
        if line is not None:
            widths.append(line.length)
    return widths


def cumulative(pts):
    d = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        d.append(d[-1] + float(np.hypot(*(b - a))))
    return d


def obb_cross_widths(geom, step=0.5):
    """Width profile perpendicular to the OBB long axis (straight slicing).

    Returns (s_values, widths) with s measured from the OBB centre along u."""
    length, width, u, v, center = obb_axis(geom)
    prof_s, prof_w = [], []
    s = -length / 2.0
    while s <= length / 2.0 + 1e-6:
        p = center + s * u
        seg = LineString([p - (width + 1.0) * v, p + (width + 1.0) * v])
        line = _longest_line(geom.intersection(seg))
        if line is not None and line.length > 0.05:
            prof_s.append(s)
            prof_w.append(line.length)
        s += step
    return prof_s, prof_w


def point_at(pts, cum, s):
    """Interpolate point at arclength s along polyline."""
    if s <= cum[0]:
        return np.array(pts[0])
    if s >= cum[-1]:
        return np.array(pts[-1])
    for i in range(len(cum) - 1):
        if cum[i] <= s <= cum[i + 1]:
            f = (s - cum[i]) / (cum[i + 1] - cum[i] + 1e-12)
            return np.array(pts[i]) + f * (np.array(pts[i + 1]) - np.array(pts[i]))
    return np.array(pts[-1])
