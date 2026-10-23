# UnicornPulse — Global Unicorn Ledger

A Flask dashboard for the unicorn-companies dataset. **Everything is rendered by
Flask (Jinja templates) — no JavaScript at all.** Charts are plain HTML/CSS/SVG
generated on the server; filters, sorting, pagination and compare use normal
GET forms and links.

| Page | Route | What it shows |
|---|---|---|
| Overview | `/` | Headline stats, unicorns per year, valuation bands, top 5 |
| Explore | `/explore` | Search / filter / sort / paginate all companies |
| Analytics | `/analytics` | Countries, sectors, 2-year sector comparison, valuation-vs-funding scatter, efficiency leaders, quarterly valuation |
| Compare | `/compare` | Pick up to 3 companies side by side |
| Insights | `/insights` | Plain-language highlights from the data |

## Run it

```bash
cd UnicornPulse
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Structure

- `app.py` — routes only
- `data_processing.py` — CSV loading/cleaning and all calculations
- `charts.py` — server-side SVG charts (timeline, scatter)
- `_macros.html` — CSS bar-chart macros
- `style.css` — the only static asset
