from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz
from src.paths import products_db_path


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def ob_match_identity(drug_name: str, strength: str = "", limit: int = 50) -> Dict[str, Any]:
    """
    Tool: Given a drug name (brand or generic-ish string) and optional strength,
    return the best Orange Book identity match + a few alternates.

    Uses products.db (table: ob_products_slim).
    """
    q = _norm(drug_name)
    if not q:
        return {"ok": False, "error": "drug_name is empty"}

    con = sqlite3.connect(products_db_path())
    cur = con.cursor()

    # exact normalized match first
    cur.execute(
        """
        SELECT appl_type, appl_no, product_no, trade_name, ingredient, strength, dosage_form, route, te_code
        FROM ob_products_slim
        WHERE trade_name_n = ?
        LIMIT ?
        """,
        (q, 2000),
    )
    rows = cur.fetchall()

    # prefix fallback (index friendly)
    if not rows and len(q) >= 4:
        like = q[:8] + "%"
        cur.execute(
            """
            SELECT appl_type, appl_no, product_no, trade_name, ingredient, strength, dosage_form, route, te_code
            FROM ob_products_slim
            WHERE trade_name_n LIKE ?
            LIMIT ?
            """,
            (like, 2000),
        )
        rows = cur.fetchall()

    con.close()

    if not rows:
        return {"ok": False, "error": "No Orange Book match found"}

    qs = _norm(strength)

    scored = []
    for r in rows:
        appl_type, appl_no, product_no, trade_name, ingredient, st, form, route, te = r
        score = fuzz.partial_ratio(q, _norm(trade_name))
        if qs:
            score += 20 if _norm(st) == qs else 0
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    def pack(row):
        appl_type, appl_no, product_no, trade_name, ingredient, st, form, route, te = row
        return {
            "appl_type": appl_type,
            "appl_no": appl_no,
            "product_no": product_no,
            "trade_name": trade_name,
            "ingredient": ingredient,
            "strength": st,
            "dosage_form": form,
            "route": route,
            "te_code": te,
            "classification": ("brand" if appl_type == "N" else ("generic" if appl_type == "A" else "unknown")),
        }

    best = pack(scored[0][1])
    alts = [pack(r) for _, r in scored[1 : 1 + max(0, limit - 1)]]

    return {"ok": True, "best": best, "alternates": alts}


def ob_find_equivalents(
    ingredient: str,
    strength: str,
    dosage_form: str,
    route: str,
    te_a_only: bool = True,
    limit: int = 200,
) -> Dict[str, Any]:
    """
    Tool: Find Orange Book equivalents for a canonical product description.
    """
    con = sqlite3.connect(products_db_path())
    cur = con.cursor()

    cur.execute(
        """
        SELECT appl_type, appl_no, product_no, trade_name, ingredient, strength, dosage_form, route, te_code
        FROM ob_products_slim
        WHERE ingredient_n = ?
          AND strength_n = ?
          AND dosage_form_n = ?
          AND route_n = ?
        LIMIT ?
        """,
        (_norm(ingredient), _norm(strength), _norm(dosage_form), _norm(route), 5000),
    )
    rows = cur.fetchall()
    con.close()

    if te_a_only:
        rows = [r for r in rows if (r[8] or "").strip().upper().startswith("A")]

    def pack(r):
        appl_type, appl_no, product_no, trade_name, ing, st, form, rt, te = r
        return {
            "trade_name": trade_name,
            "is_generic": (appl_type == "A"),
            "appl_type": appl_type,
            "appl_no": appl_no,
            "product_no": product_no,
            "ingredient": ing,
            "strength": st,
            "dosage_form": form,
            "route": rt,
            "te_code": te,
        }

    return {"ok": True, "count": len(rows), "items": [pack(r) for r in rows[:limit]]}


def ob_ingredient_to_generic_candidates(ingredient: str) -> Dict[str, Any]:
    """
    Tool: Return heuristic generic-name candidates from an Orange Book ingredient string.
    This is a *tool* so the LLM can decide whether/when to use it.
    """
    salts = {
        "HYDROCHLORIDE", "HCL", "SODIUM", "POTASSIUM", "CALCIUM", "MAGNESIUM",
        "PHOSPHATE", "SULFATE", "NITRATE", "ACETATE", "BESYLATE", "MESYLATE",
        "TARTRATE", "CITRATE", "FUMARATE", "SUCCINATE", "MALEATE", "LACTATE",
        "CHLORIDE", "BROMIDE", "IODIDE", "OXALATE",
    }

    ing = _norm(ingredient)
    if not ing:
        return {"ok": False, "error": "ingredient is empty"}

    # split multi-ingredient on ; or /
    parts = [p.strip() for p in ing.replace("/", ";").split(";") if p.strip()]

    cleaned = []
    for p in parts:
        words = [w for w in p.split() if w and w not in salts]
        if words:
            cleaned.append(" ".join(words))

    cands: List[str] = []
    cands.extend(cleaned)
    if len(cleaned) > 1:
        cands.append(" ".join(cleaned))

    # de-dupe
    out = []
    seen = set()
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)

    return {"ok": True, "candidates": out}
