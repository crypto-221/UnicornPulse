import math

from flask import Flask, abort, render_template, request, url_for

from utils import charts
from utils import data_processing as dp

app = Flask(__name__)


# ------------------------------------------------------------------ helpers
@app.template_filter("money")
def money(v):
    """Value in $B -> '$12.5B' (or '$150M' under a billion). None/NaN -> em dash."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if v < 1:
        return f"${v * 1000:,.0f}M"
    s = f"{v:,.1f}".rstrip("0").rstrip(".")
    return f"${s}B"


@app.template_filter("num")
def num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{int(v)}"


@app.template_filter("mult")
def mult(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.1f}×"


@app.context_processor
def inject_globals():
    def url_args(**changes):
        """Current URL with some query params changed (None/'' removes one)."""
        args = request.args.to_dict()
        for k, v in changes.items():
            if v is None or v == "":
                args.pop(k, None)
            else:
                args[k] = v
        return url_for(request.endpoint, **args)

    return {"url_args": url_args, "site": dp.site_meta()}


# ------------------------------------------------------------------ pages
@app.route("/")
def index():
    years, counts = dp.timeline()
    bands = dp.valuation_bands()
    return render_template(
        "index.html", active="home",
        stats=dp.overview_stats(), top5=dp.top_by_valuation(5),
        timeline_svg=charts.timeline_svg(years, counts),
        bands=bands, donut=dp.donut_gradient(bands),
    )


@app.route("/explore")
def explore():
    industries, countries = dp.filter_options()
    q = dp.query_companies(
        search=request.args.get("search", "").strip(),
        industry=request.args.get("industry", ""),
        country=request.args.get("country", ""),
        min_val=request.args.get("min_val", type=float),
        sort_by=request.args.get("sort_by", "Valuation_B"),
        order=request.args.get("order"),
        page=request.args.get("page", 1, type=int),
    )
    return render_template(
        "explore.html", active="explore", q=q,
        industries=industries, countries=countries,
        f={k: request.args.get(k, "") for k in ("search", "industry", "country", "min_val")},
    )


@app.route("/analytics")
def analytics():
    years = dp.available_years()
    y1 = request.args.get("y1", 2019, type=int)
    y2 = request.args.get("y2", 2025, type=int)
    year = request.args.get("year", 2021, type=int)
    y1 = y1 if y1 in years else 2019
    y2 = y2 if y2 in years else 2025
    year = year if year in years else 2021
    return render_template(
        "analytics.html", active="analytics",
        years=years, y1=y1, y2=y2, year=year,
        countries_count=dp.top_countries("count"),
        countries_val=dp.top_countries("valuation"),
        industries=dp.top_industries(),
        industries_avg=dp.top_industries_by_avg(),
        shift=dp.sector_shift(y1, y2),
        eff=dp.efficiency_leaders(10),
        scatter_svg=charts.scatter_svg(dp.scatter_points()),
        quarterly=dp.quarterly(year),
    )


COMPARE_ROWS = [
    ("Industry", "Industry", "text"), ("Country", "Country", "text"),
    ("Founded", "Year Founded", "int"), ("Joined unicorn club", "Year Joined", "int"),
    ("Years to unicorn", "Years To Unicorn", "int"),
    ("Funding raised", "Funding_B", "money"),
    ("Efficiency (valuation ÷ funding)", "Efficiency", "mult"),
    ("Top investor", "Top Investor", "text"),
]


@app.route("/compare")
def compare():
    slugs = [request.args.get(k, "") for k in ("c1", "c2", "c3")]
    chosen = []
    for s in slugs:
        c = dp.get_company(s) if s else None
        if c and all(c["Slug"] != x["Slug"] for x in chosen):
            chosen.append(c)
    return render_template(
        "compare.html", active="compare", slugs=slugs, chosen=chosen,
        options=dp.compare_options(), rows=COMPARE_ROWS,
    )


@app.route("/insights")
def insights():
    return render_template("insights.html", active="insights",
                           story=dp.insights_story(), investors=dp.top_investors(10))


@app.route("/company/<slug>")
def company_detail(slug):
    row = dp.get_company(slug)
    if row is None:
        abort(404)
    df = dp.load_data()
    similar = dp.to_records(
        df[(df["Industry"] == row["Industry"]) & (df["Slug"] != slug)]
        .sort_values("Valuation_B", ascending=False)
        .head(6)[["Company", "Valuation_B", "Country", "Slug"]]
    )
    return render_template("company.html", active="explore", c=row, similar=similar)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
