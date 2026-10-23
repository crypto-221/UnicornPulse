"""Data loading, cleaning, and every number the pages need."""
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "unicorns.csv"

PALETTE = ["#9179ff", "#e8b95e", "#4fd8a0", "#f0715c", "#5eb3e8"]
PAGE_SIZE = 25
# column -> default sort direction on first click
SORTABLE = {
    "Company": "asc", "Industry": "asc", "Country": "asc",
    "Year Founded": "desc", "Year Joined": "desc",
    "Funding_B": "desc", "Valuation_B": "desc",
}

_df_cache = None


# ------------------------------------------------------------------ cleaning
def clean_money(val):
    """'$8B' -> 8.0, '$150M' -> 0.15, 'Unknown' -> NaN (values in $ billions)."""
    if pd.isna(val):
        return np.nan
    val = str(val).replace("$", "").replace(",", "").strip()
    if val == "" or val.lower() == "unknown":
        return np.nan
    try:
        if val.endswith("B"):
            return float(val[:-1])
        if val.endswith("M"):
            return float(val[:-1]) / 1000
        if val.endswith("K"):
            return float(val[:-1]) / 1_000_000
        return float(val)
    except ValueError:
        return np.nan


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-") or "company"


def load_data() -> pd.DataFrame:
    """Load + clean the CSV once, cache it for the app's lifetime."""
    global _df_cache
    if _df_cache is not None:
        return _df_cache.copy()

    df = pd.read_csv(CSV_PATH)

    df["Valuation_B"] = df["Valuation"].apply(clean_money)
    df["Funding_B"] = df["Funding"].apply(clean_money)

    df["Date Joined"] = pd.to_datetime(df["Date Joined"], errors="coerce")
    df["Year Joined"] = df["Date Joined"].dt.year
    df["Quarter"] = df["Date Joined"].dt.to_period("Q").astype(str)
    df.loc[df["Date Joined"].isna(), "Quarter"] = np.nan

    # Industry: merge spellings that differ only by case
    # ("Artificial intelligence" / "Artificial Intelligence") + one known alias.
    ind = df["Industry"].astype(str).str.strip().replace(
        {"Data & analytics": "Data management & analytics"}
    )
    key = ind.str.lower()
    canon = ind.groupby(key).agg(lambda s: s.value_counts().idxmax())
    df["Industry"] = key.map(canon)

    for col in ("Country", "City", "Continent"):
        df[col] = df[col].str.strip()

    # Derived fields
    ytu = df["Year Joined"] - df["Year Founded"]
    df["Years To Unicorn"] = ytu.where(ytu >= 0)  # negative = bad source data
    df["Efficiency"] = (df["Valuation_B"] / df["Funding_B"]).replace([np.inf, -np.inf], np.nan)
    df["Top Investor"] = df["Select Investors"].fillna("").str.split(",").str[0].str.strip()

    # Unique slugs (the CSV has repeated names, e.g. Bolt, OpenAI, Databricks)
    base = df["Company"].apply(slugify)
    n = base.groupby(base).cumcount()
    df["Slug"] = base.where(n == 0, base + "-" + (n + 1).astype(str))

    _df_cache = df
    return df.copy()


def to_records(df: pd.DataFrame) -> list:
    """DataFrame -> list of plain dicts, NaN/NaT -> None."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def get_company(slug: str):
    df = load_data()
    row = df[df["Slug"] == slug]
    if row.empty:
        return None
    rec = to_records(row.head(1))[0]
    if rec.get("Date Joined") is not None:
        rec["Date Joined"] = rec["Date Joined"].strftime("%b %d, %Y")
    return rec


def site_meta() -> dict:
    df = load_data()
    return {"total": len(df), "first_year": int(df["Year Joined"].min()),
            "last_year": int(df["Year Joined"].max())}


def available_years() -> list:
    return sorted(int(y) for y in load_data()["Year Joined"].dropna().unique())


# ------------------------------------------------------------------ overview
def overview_stats() -> dict:
    df = load_data()
    newest = int(df["Year Joined"].max())
    return {
        "total_unicorns": len(df),
        "combined_valuation": float(df["Valuation_B"].sum()),
        "avg_years_to_unicorn": round(float(df["Years To Unicorn"].mean()), 1),
        "countries": int(df["Country"].nunique()),
        "newest_year": newest,
        "new_this_year": int((df["Year Joined"] == newest).sum()),
    }


def top_by_valuation(limit=5) -> list:
    df = load_data().sort_values("Valuation_B", ascending=False).head(limit)
    return to_records(df[["Company", "Valuation_B", "Country", "Industry", "Slug"]])


def timeline():
    df = load_data().dropna(subset=["Year Joined"])
    counts = df.groupby(df["Year Joined"].astype(int)).size()
    years = list(range(int(counts.index.min()), int(counts.index.max()) + 1))
    return years, [int(counts.get(y, 0)) for y in years]


def valuation_bands() -> list:
    v = load_data()["Valuation_B"].dropna()
    labels = ["$1–2B", "$2–5B", "$5–10B", "$10–30B", "$30B+"]
    cats = pd.cut(v, bins=[0, 2, 5, 10, 30, np.inf], labels=labels, right=True)
    counts = cats.value_counts().reindex(labels).fillna(0).astype(int)
    total = int(counts.sum()) or 1
    out = []
    for i, lab in enumerate(labels):
        out.append({"label": lab, "count": int(counts[lab]),
                    "pct": counts[lab] / total * 100, "color": PALETTE[i]})
    return out


def donut_gradient(bands) -> str:
    stops, acc = [], 0.0
    for b in bands:
        stops.append(f"{b['color']} {acc:.2f}% {acc + b['pct']:.2f}%")
        acc += b["pct"]
    return ", ".join(stops)


# ------------------------------------------------------------------ analytics
def top_countries(by="count", limit=8) -> list:
    df = load_data()
    g = df.groupby("Country").agg(count=("Company", "size"), valuation=("Valuation_B", "sum"))
    g = g.sort_values("count" if by == "count" else "valuation", ascending=False).head(limit)
    return [{"label": k, "value": float(r["count" if by == "count" else "valuation"])}
            for k, r in g.iterrows()]


def top_industries(limit=8) -> list:
    s = load_data()["Industry"].value_counts().head(limit)
    return [{"label": k, "value": int(v)} for k, v in s.items()]


def top_industries_by_avg(limit=8, min_count=5) -> list:
    g = load_data().groupby("Industry").agg(n=("Company", "size"), avg=("Valuation_B", "mean"))
    g = g[g["n"] >= min_count].sort_values("avg", ascending=False).head(limit)
    return [{"label": k, "value": float(r["avg"])} for k, r in g.iterrows()]


def sector_shift(y1: int, y2: int, limit=7) -> dict:
    df = load_data()
    a = df[df["Year Joined"] == y1]["Industry"].value_counts()
    b = df[df["Year Joined"] == y2]["Industry"].value_counts()
    top = pd.concat([a, b], axis=1).fillna(0).sum(axis=1).sort_values(ascending=False).head(limit).index
    return {"sectors": list(top), "a": [int(a.get(s, 0)) for s in top],
            "b": [int(b.get(s, 0)) for s in top], "na": int(a.sum()), "nb": int(b.sum())}


def scatter_points() -> list:
    df = load_data().dropna(subset=["Valuation_B", "Funding_B"])
    return to_records(df[["Company", "Valuation_B", "Funding_B"]])


def efficiency_leaders(limit=10) -> list:
    df = load_data().dropna(subset=["Efficiency"])
    top = df.sort_values("Efficiency", ascending=False).head(limit)
    return to_records(top[["Company", "Valuation_B", "Funding_B", "Efficiency", "Slug"]])


def quarterly(year: int) -> dict:
    df = load_data()
    q = df[df["Quarter"].astype(str).str.startswith(str(year))]
    g = q.groupby("Quarter")["Valuation_B"].sum().sort_index()
    return {"quarters": list(g.index), "vals": [round(float(v), 1) for v in g.values]}


def top_investors(limit=10) -> list:
    df = load_data()
    s = df[df["Top Investor"] != ""]["Top Investor"].value_counts().head(limit)
    return [{"label": k, "value": int(v)} for k, v in s.items()]


# ------------------------------------------------------------------ explore
def filter_options() -> tuple:
    df = load_data()
    return (sorted(df["Industry"].dropna().unique().tolist()),
            sorted(df["Country"].dropna().unique().tolist()))


def query_companies(search="", industry="", country="", min_val=None,
                    sort_by="Valuation_B", order=None, page=1) -> dict:
    df = load_data()
    if search:
        df = df[df["Company"].str.contains(search, case=False, regex=False, na=False)]
    if industry:
        df = df[df["Industry"] == industry]
    if country:
        df = df[df["Country"] == country]
    if min_val is not None:
        df = df[df["Valuation_B"] >= min_val]

    if sort_by not in SORTABLE:
        sort_by = "Valuation_B"
    if order not in ("asc", "desc"):
        order = SORTABLE[sort_by]
    asc = order == "asc"
    if SORTABLE[sort_by] == "asc":  # text column -> case-insensitive
        df = df.sort_values(sort_by, ascending=asc, na_position="last", key=lambda s: s.str.lower())
    else:
        df = df.sort_values(sort_by, ascending=asc, na_position="last")

    total = len(df)
    pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(max(page, 1), pages)
    start = (page - 1) * PAGE_SIZE
    cols = ["Company", "Valuation_B", "Industry", "Country", "City",
            "Year Founded", "Year Joined", "Funding_B", "Slug"]
    rows = to_records(df.iloc[start:start + PAGE_SIZE][cols])

    next_order = {k: (("asc" if order == "desc" else "desc") if k == sort_by else d)
                  for k, d in SORTABLE.items()}
    return {"rows": rows, "total": total, "page": page, "pages": pages,
            "start": start + 1 if total else 0, "end": min(start + PAGE_SIZE, total),
            "sort_by": sort_by, "order": order, "next_order": next_order}


def compare_options() -> list:
    df = load_data().sort_values("Company", key=lambda s: s.str.lower())
    return [{"slug": r.Slug, "label": f"{r.Company} — ${r.Valuation_B:g}B · {r.Country}"}
            for r in df.itertuples()]


# ------------------------------------------------------------------ insights
def insights_story() -> dict:
    df = load_data()
    top = df.loc[df["Valuation_B"].idxmax()]

    cg = df.groupby("Country")["Valuation_B"].sum().sort_values(ascending=False)
    qg = df.groupby("Quarter")["Valuation_B"].agg(["sum", "size"])
    pq = qg["sum"].idxmax()

    ind_counts = df["Industry"].value_counts()

    eff = efficiency_leaders(1)
    fast = (df.dropna(subset=["Years To Unicorn"])
              .sort_values(["Years To Unicorn", "Valuation_B"], ascending=[True, False]))
    fastest = fast.iloc[0]

    return {
        "total_unicorns": len(df),
        "combined_valuation": float(df["Valuation_B"].sum()),
        "avg_years": round(float(df["Years To Unicorn"].mean()), 1),
        "top_company": top["Company"], "top_company_val": float(top["Valuation_B"]),
        "top_company_slug": top["Slug"], "top_company_country": top["Country"],
        "peak_country": cg.index[0], "peak_country_val": float(cg.iloc[0]),
        "peak_country_share": float(cg.iloc[0] / cg.sum() * 100),
        "runner_up": cg.index[1], "runner_up_val": float(cg.iloc[1]),
        "peak_quarter": pq, "peak_quarter_val": float(qg.loc[pq, "sum"]),
        "peak_quarter_n": int(qg.loc[pq, "size"]),
        "top_industry": ind_counts.index[0], "top_industry_count": int(ind_counts.iloc[0]),
        "eff": eff[0] if eff else None,
        "fastest_name": fastest["Company"], "fastest_slug": fastest["Slug"],
        "fastest_years": int(fastest["Years To Unicorn"]),
        "fastest_ties": int((fast["Years To Unicorn"] == fastest["Years To Unicorn"]).sum()),
    }
