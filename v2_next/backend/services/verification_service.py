from __future__ import annotations

import csv
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..models.data_model import FactoryData
from .. import constants
from .plc_service import plc_service




def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _iter_csv_rows(path: Path) -> tuple[list[str], Iterable[list[str]]]:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            handle = path.open("r", encoding=enc, newline="")
        except Exception:
            continue
        with handle:
            reader = csv.reader(handle)
            rows = list(reader)
        if not rows:
            return [], []
        header = rows[0]
        body = rows[1:]
        return header, body
    return [], []


def _build_header_map(header: list[str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for idx, name in enumerate(header):
        normalized = _normalize_header(name)
        if not normalized:
            continue
        key = constants.HEADER_ALIASES.get(normalized)
        if key:
            mapping[idx] = key
    return mapping


def load_reference_csv(path: str) -> list[Dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(path)
    header, rows = _iter_csv_rows(csv_path)
    if not header:
        return []
    mapping = _build_header_map(header)
    if not mapping:
        return []
    parsed: list[Dict[str, float]] = []
    for row in rows:
        row_map: Dict[str, float] = {}
        for idx, key in mapping.items():
            if idx >= len(row):
                continue
            value = _parse_float(row[idx])
            if value is None or not math.isfinite(value):
                continue
            row_map[key] = float(value)
        if row_map:
            parsed.append(row_map)
    return parsed


def _collect_live_samples(sample_count: int, interval_sec: float) -> list[Dict[str, float]]:
    samples: list[Dict[str, float]] = []
    for _ in range(sample_count):
        snapshot = plc_service.get_latest_data()
        row: Dict[str, float] = {}
        for key in constants.FIELD_KEYS:
            value = getattr(snapshot, key, None)
            value = _parse_float(value)
            if value is None or not math.isfinite(value):
                continue
            row[key] = float(value)
        if row:
            samples.append(row)
        time.sleep(interval_sec)
    return samples


def _calc_stats(rows: Iterable[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    buckets: Dict[str, List[float]] = {key: [] for key in constants.FIELD_KEYS}
    for row in rows:
        for key, value in row.items():
            if key not in buckets:
                continue
            if math.isfinite(value):
                buckets[key].append(float(value))
    for key, values in buckets.items():
        if not values:
            continue
        total = sum(values)
        count = float(len(values))
        stats[key] = {
            "count": count,
            "mean": total / count,
            "min": min(values),
            "max": max(values),
        }
    return stats


def compare_with_reference(
    reference_csv_path: str,
    sample_count: int,
    interval_sec: float,
    tolerance_abs: Optional[Dict[str, float]] = None,
    tolerance_pct: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    reference_rows = load_reference_csv(reference_csv_path)
    live_rows = _collect_live_samples(sample_count, interval_sec)
    ref_stats = _calc_stats(reference_rows)
    live_stats = _calc_stats(live_rows)

    abs_tol = constants.DEFAULT_ABS_TOLERANCE.copy()
    if tolerance_abs:
        abs_tol.update({k: float(v) for k, v in tolerance_abs.items()})
    pct_tol = {key: constants.DEFAULT_PCT_TOLERANCE for key in constants.FIELD_KEYS}
    if tolerance_pct:
        pct_tol.update({k: float(v) for k, v in tolerance_pct.items()})

    results: Dict[str, Any] = {}
    pass_count = 0
    fail_count = 0
    for key in constants.FIELD_KEYS:
        ref = ref_stats.get(key)
        live = live_stats.get(key)
        if not ref or not live:
            results[key] = {
                "status": "INSUFFICIENT",
                "ref_count": ref.get("count", 0) if ref else 0,
                "live_count": live.get("count", 0) if live else 0,
            }
            continue
        diff = abs(live["mean"] - ref["mean"])
        tol_abs = abs_tol.get(key, 0.0)
        tol_pct = pct_tol.get(key, 0.0)
        tol = max(tol_abs, abs(ref["mean"]) * tol_pct)
        ok = diff <= tol
        if ok:
            pass_count += 1
            status = "PASS"
        else:
            fail_count += 1
            status = "FAIL"
        results[key] = {
            "status": status,
            "ref_mean": ref["mean"],
            "live_mean": live["mean"],
            "diff": diff,
            "tolerance": tol,
            "ref_count": ref["count"],
            "live_count": live["count"],
        }

    return {
        "reference_csv": reference_csv_path,
        "reference_rows": len(reference_rows),
        "sample_count": sample_count,
        "interval_sec": interval_sec,
        "summary": {"pass": pass_count, "fail": fail_count},
        "results": results,
    }
