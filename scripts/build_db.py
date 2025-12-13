from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd


# -------------------------
# Shared helpers
# -------------------------
def norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s).strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s


def split_df_route(df_route: str) -> tuple[str, str]:
    # Orange Book combined field like: 'TABLET;ORAL'
    if not df_route:
        return "", ""
    parts = [p.strip() for p in df_route.split(";", 1)]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


# -------------------------
# Orange Book -> products.db
# -------------------------
def build_ob(products_txt_path: str, products_db_path: str) -> None:
    os.makedirs(os.path.dirname(products_db_path), exist_ok=True)
    con = sqlite3.connect(products_db_path)
    cur = con.cursor()

    cur.execute("DROP TABLE IF EXISTS ob_products_slim;")
    cur.execute("""
        CREATE TABLE ob_products_slim (
            appl_type TEXT,
            appl_no TEXT,
            product_no TEXT,
            trade_name TEXT,
            ingredient TEXT,
            strength TEXT,
            dosage_form TEXT,
            route TEXT,
            te_code TEXT,
            rld TEXT,
            rs TEXT,
            product_type TEXT,

            trade_name_n TEXT,
            ingredient_n TEXT,
            strength_n TEXT,
            dosage_form_n TEXT,
            route_n TEXT,
            te_code_n TEXT
        );
    """)

    with open(products_txt_path, "r", encoding="latin-1", errors="replace") as f:
        header = f.readline().rstrip("\n")
        cols = header.split("~")
        idx = {c: i for i, c in enumerate(cols)}

        required = ["Ingredient", "DF;Route", "Trade_Name", "Strength", "Appl_Type", "Appl_No", "Product_No", "TE_Code"]
        missing = [c for c in required if c not in idx]
        if missing:
            raise ValueError(f"Missing expected Orange Book columns: {missing}\nFound: {cols}")

        opt = {"RLD": idx.get("RLD"), "RS": idx.get("RS"), "Type": idx.get("Type")}

        batch = []
        BATCH = 50_000

        for line in f:
            parts = line.rstrip("\n").split("~")

            ingredient = parts[idx["Ingredient"]].strip()
            df_route = parts[idx["DF;Route"]].strip()
            trade_name = parts[idx["Trade_Name"]].strip()
            strength = parts[idx["Strength"]].strip()
            appl_type = parts[idx["Appl_Type"]].strip()
            appl_no = parts[idx["Appl_No"]].strip()
            product_no = parts[idx["Product_No"]].strip()
            te_code = parts[idx["TE_Code"]].strip()

            dosage_form, route = split_df_route(df_route)

            rld = parts[opt["RLD"]].strip() if opt["RLD"] is not None and opt["RLD"] < len(parts) else ""
            rs = parts[opt["RS"]].strip() if opt["RS"] is not None and opt["RS"] < len(parts) else ""
            product_type = parts[opt["Type"]].strip() if opt["Type"] is not None and opt["Type"] < len(parts) else ""

            batch.append((
                appl_type, appl_no, product_no,
                trade_name, ingredient, strength,
                dosage_form, route, te_code,
                rld, rs, product_type,
                norm(trade_name), norm(ingredient), norm(strength),
                norm(dosage_form), norm(route), norm(te_code),
            ))

            if len(batch) >= BATCH:
                cur.executemany(
                    "INSERT INTO ob_products_slim VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch
                )
                con.commit()
                batch = []

        if batch:
            cur.executemany(
                "INSERT INTO ob_products_slim VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch
            )
            con.commit()

    cur.execute("CREATE INDEX IF NOT EXISTS idx_ob_trade_name_n ON ob_products_slim(trade_name_n);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ob_equiv_key ON ob_products_slim(ingredient_n, strength_n, dosage_form_n, route_n);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ob_app ON ob_products_slim(appl_type, appl_no, product_no);")
    con.commit()
    con.close()
    print("✅ Built Orange Book DB:", products_db_path)


# -------------------------
# CMS Part D -> medicare.db (long format)
# -------------------------
def build_cms_partd(partd_csv_path: str, medicare_db_path: str,
                    table_name: str = "cms_partd_costs_slim",
                    years: Sequence[int] = (2019, 2020, 2021, 2022, 2023),
                    chunksize: int = 200_000) -> None:
    """
    Creates a long-format table with one row per (drug, year).
    Requires CMS columns: Brnd_Name, Gnrc_Name, Tot_Mftr, Mftr_Name
    and yearly columns: Avg_Spnd_Per_Dsg_Unt_Wghtd_YYYY, Outlier_Flag_YYYY
    """
    os.makedirs(os.path.dirname(medicare_db_path), exist_ok=True)
    con = sqlite3.connect(medicare_db_path)
    cur = con.cursor()

    cur.execute(f"DROP TABLE IF EXISTS {table_name};")
    cur.execute(f"""
        CREATE TABLE {table_name} (
            brand_name TEXT,
            generic_name TEXT,
            manufacturer TEXT,
            tot_mftr INTEGER,

            year INTEGER,
            avg_spend_per_dose REAL,
            outlier_flag INTEGER,

            brand_name_n TEXT,
            generic_name_n TEXT
        );
    """)

    base_cols = ["Brnd_Name", "Gnrc_Name", "Tot_Mftr", "Mftr_Name"]
    spend_cols = [f"Avg_Spnd_Per_Dsg_Unt_Wghtd_{y}" for y in years]
    outlier_cols = [f"Outlier_Flag_{y}" for y in years]
    usecols = base_cols + spend_cols + outlier_cols

    for chunk in pd.read_csv(partd_csv_path, usecols=usecols, chunksize=chunksize):
        chunk["Tot_Mftr"] = pd.to_numeric(chunk["Tot_Mftr"], errors="coerce").fillna(0).astype(int)

        out_rows = []
        for y in years:
            spend_col = f"Avg_Spnd_Per_Dsg_Unt_Wghtd_{y}"
            out_col = f"Outlier_Flag_{y}"

            tmp = chunk[["Brnd_Name", "Gnrc_Name", "Tot_Mftr", "Mftr_Name", spend_col, out_col]].copy()
            tmp = tmp.rename(columns={
                "Brnd_Name": "brand_name",
                "Gnrc_Name": "generic_name",
                "Tot_Mftr": "tot_mftr",
                "Mftr_Name": "manufacturer",
                spend_col: "avg_spend_per_dose",
                out_col: "outlier_flag",
            })

            tmp["year"] = y
            tmp["avg_spend_per_dose"] = pd.to_numeric(tmp["avg_spend_per_dose"], errors="coerce")
            tmp["outlier_flag"] = pd.to_numeric(tmp["outlier_flag"], errors="coerce").fillna(0).astype(int)

            tmp = tmp[tmp["avg_spend_per_dose"].notna()]

            tmp["brand_name_n"] = tmp["brand_name"].map(norm)
            tmp["generic_name_n"] = tmp["generic_name"].map(norm)

            out_rows.extend(list(zip(
                tmp["brand_name"].astype(str).where(tmp["brand_name"].notna(), "").tolist(),
                tmp["generic_name"].astype(str).where(tmp["generic_name"].notna(), "").tolist(),
                tmp["manufacturer"].astype(str).where(tmp["manufacturer"].notna(), "").tolist(),
                tmp["tot_mftr"].tolist(),
                tmp["year"].tolist(),
                tmp["avg_spend_per_dose"].tolist(),
                tmp["outlier_flag"].tolist(),
                tmp["brand_name_n"].tolist(),
                tmp["generic_name_n"].tolist(),
            )))

        cur.executemany(
            f"INSERT INTO {table_name} VALUES (?,?,?,?,?,?,?,?,?)",
            out_rows
        )
        con.commit()

    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_brand_n_year ON {table_name}(brand_name_n, year);")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_generic_n_year ON {table_name}(generic_name_n, year);")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_year_cost ON {table_name}(year, avg_spend_per_dose);")
    con.commit()
    con.close()
    print("✅ Built Medicare DB:", medicare_db_path)


# -------------------------
# Main using your repo path
# -------------------------
if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "Data"

    products_txt = data_dir / "products.txt"
    partd_csv = data_dir / "DSD_PTD_RY25_P04_V10_DY23_BGM.csv"  # rename if your file differs

    products_db = data_dir / "products.db"
    medicare_db = data_dir / "medicare.db"

    if not products_txt.exists():
        raise FileNotFoundError(f"Missing: {products_txt}")
    if not partd_csv.exists():
        raise FileNotFoundError(f"Missing: {partd_csv} (rename in script if needed)")

    build_ob(str(products_txt), str(products_db))
    build_cms_partd(str(partd_csv), str(medicare_db), years=[2019, 2020, 2021, 2022, 2023])

    # quick sanity counts
    con1 = sqlite3.connect(str(products_db))
    c1 = con1.cursor()
    c1.execute("SELECT COUNT(*) FROM ob_products_slim")
    print("ob_products_slim rows:", c1.fetchone()[0])
    con1.close()

    con2 = sqlite3.connect(str(medicare_db))
    c2 = con2.cursor()
    c2.execute("SELECT COUNT(*) FROM cms_partd_costs_slim")
    print("cms_partd_costs_slim rows:", c2.fetchone()[0])
    con2.close()
