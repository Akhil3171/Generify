from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from src.paths import medicare_db_path


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def medicare_latest_year() -> Dict[str, Any]:
    """
    Tool: Return the latest year available in cms_partd_costs_slim.
    """
    con = sqlite3.connect(medicare_db_path())
    cur = con.cursor()
    cur.execute("SELECT MAX(year) FROM cms_partd_costs_slim;")
    y = cur.fetchone()[0]
    con.close()
    return {"ok": True, "latest_year": int(y) if y is not None else None}


def medicare_lookup_costs(name: str, year: Optional[int] = None, limit: int = 50) -> Dict[str, Any]:
    """
    Tool: Lookup Medicare Part D cost-per-dose rows where:
      brand_name_n == name OR generic_name_n == name
    If year is None, uses latest year available.
    """
    q = _norm(name)
    if not q:
        return {"ok": False, "error": "name is empty"}

    con = sqlite3.connect(medicare_db_path())
    cur = con.cursor()

    if year is None:
        cur.execute("SELECT MAX(year) FROM cms_partd_costs_slim;")
        year = cur.fetchone()[0]

    if year is None:
        con.close()
        return {"ok": False, "error": "No year data found in medicare db"}

    cur.execute(
        """
        SELECT brand_name, generic_name, manufacturer, tot_mftr, year, avg_spend_per_dose, outlier_flag
        FROM cms_partd_costs_slim
        WHERE year = ?
          AND (brand_name_n = ? OR generic_name_n = ?)
          AND avg_spend_per_dose IS NOT NULL
        ORDER BY avg_spend_per_dose ASC
        LIMIT ?
        """,
        (int(year), q, q, int(limit)),
    )
    rows = cur.fetchall()
    con.close()

    items = []
    for r in rows:
        brand_name, generic_name, manufacturer, tot_mftr, yr, avg, outlier = r
        items.append({
            "brand_name": brand_name,
            "generic_name": generic_name,
            "manufacturer": manufacturer,
            "tot_mftr": int(tot_mftr) if tot_mftr is not None else None,
            "year": int(yr),
            "avg_spend_per_dose": float(avg),
            "outlier_flag": bool(outlier),
        })

    return {"ok": True, "year": int(year), "count": len(items), "items": items}
