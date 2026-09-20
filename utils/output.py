import json
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .config import Internship, OUTPUT_DIR, STALE_AFTER_DAYS


def save_json(jobs: list[Internship], filename: str = "") -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = filename or now.strftime("internships_%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{ts}.json"
    data = {
        "generated_at": now.isoformat(),
        "total": len(jobs),
        "internships": [j.to_dict() for j in jobs],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return str(path)


def save_html(jobs: list[Internship], filename: str = "") -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = filename or now.strftime("internships_%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{ts}.html"
    path.write_text(_build_html(jobs, now))
    return str(path)


def _badge(source: str) -> str:
    return f'<span class="s-badge">{source}</span>'


def _clean_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _build_html(jobs: list[Internship], now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now()

    by_source = {}
    for j in jobs:
        by_source.setdefault(j.source, []).append(j)

    sources = sorted(by_source.keys())
    chips = "".join(
        f'<button class="ch" data-s="{escape(s)}" onclick="fs(this,\'{escape(s)}\')">{escape(s)}</button>'
        for s in sources
    )

    rows = ""
    for j in sorted(jobs, key=lambda x: x.title.lower()):
        url = escape(_clean_url(j.url))
        stale_attr = ' data-stale="1"' if j.is_stale else ''
        stale_badge = ' <span class="stale-badge">stale</span>' if j.is_stale else ''
        date_cell = escape(j.date_posted) if j.date_posted else "—"
        rows += (
            f'<tr data-s="{escape(j.source)}"{stale_attr}>'
            f'<td class="t"><a href="{url}" target="_blank" rel="noopener">{escape(j.title)}</a>{stale_badge}</td>'
            f'<td class="co">{escape(j.company) if j.company else "—"}</td>'
            f'<td class="lo">{escape(j.location) if j.location else "—"}</td>'
            f'<td class="dt">{date_cell}</td>'
            f'<td class="src-cell">{_badge(escape(j.source))}</td>'
            f'</tr>'
        )

    stale_count = sum(1 for j in jobs if j.is_stale)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Egypt Internships</title>
<style>
:root{{
  --bg:#09090b;
  --surface:#18181b;
  --surface-inset:#111113;
  --border:rgba(255,255,255,0.07);
  --border-sep:rgba(255,255,255,0.06);
  --text:#fafafa;
  --text-2:#a1a1aa;
  --text-3:#52525b;
  --tr:0.2s ease;
}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1200px;margin:0 auto;padding:40px 24px}}
h1{{font-size:1.35rem;font-weight:700;letter-spacing:-.01em;margin:0}}
.sub{{color:var(--text-3);font-size:.85rem;margin-top:3px}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
.st{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px;font-size:.83rem;color:var(--text-3)}}
.st b{{color:var(--text);font-weight:600}}
.bar{{display:flex;flex-direction:column;gap:10px;margin-bottom:16px}}
.srch input{{width:100%;padding:10px 14px;font-size:.88rem;background:var(--surface-inset);color:var(--text);border:1px solid var(--border);border-radius:8px;outline:none;transition:all var(--tr)}}
.srch input:focus{{border-color:rgba(255,255,255,0.16)}}
.srch input::placeholder{{color:var(--text-3)}}
.chips{{display:flex;gap:6px;flex-wrap:wrap}}
.ch{{padding:6px 14px;border:1px solid var(--border);border-radius:100px;background:transparent;cursor:pointer;font-size:.79rem;color:var(--text-3);transition:all var(--tr);font-family:inherit}}
.ch:hover{{color:var(--text-2);border-color:rgba(255,255,255,0.14)}}
.ch.on{{color:var(--bg);background:var(--text);border-color:var(--text);font-weight:500}}
.ch.stale-toggle{{border-color:rgba(234,179,8,0.4);color:rgba(234,179,8,0.7)}}
.ch.stale-toggle.on{{background:rgba(234,179,8,0.15);color:rgb(234,179,8);border-color:rgba(234,179,8,0.6)}}
.cnt{{font-size:.79rem;color:var(--text-3);margin-top:2px}}
.tbl{{width:100%;border-collapse:collapse;margin-top:8px}}
.tbl th{{text-align:left;font-size:.68rem;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:.07em;padding:10px 10px 12px;border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap;transition:color var(--tr)}}
.tbl th:hover{{color:var(--text-2)}}
.tbl td{{padding:14px 10px;border-bottom:1px solid var(--border-sep);vertical-align:middle}}
.tbl tr.hide{{display:none}}
.tbl tbody tr{{transition:background var(--tr)}}
.tbl tbody tr:hover td{{background:rgba(255,255,255,0.025)}}
.t a{{color:var(--text);text-decoration:none;font-size:.93rem;font-weight:600;transition:color var(--tr)}}
.t a:hover{{color:var(--text-2)}}
.co,.lo,.dt{{color:var(--text-3);font-size:.82rem;white-space:nowrap}}
.s-badge{{display:inline-block;padding:3px 9px;border-radius:100px;font-size:.7rem;font-weight:500;background:rgba(255,255,255,0.06);border:1px solid var(--border);color:var(--text-3);text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
.stale-badge{{display:inline-block;margin-left:6px;padding:2px 7px;border-radius:100px;font-size:.65rem;font-weight:500;background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);color:rgba(234,179,8,0.8);text-transform:uppercase;letter-spacing:.04em;vertical-align:middle}}
.src-cell{{white-space:nowrap}}
.emp{{text-align:center;padding:56px 16px;color:var(--text-3);display:none;font-size:.88rem}}
.ftr{{margin-top:48px;padding-top:20px;border-top:1px solid var(--border);text-align:center;font-size:.8rem;color:var(--text-3)}}
.ftr a{{color:var(--text-2);text-decoration:none;transition:color var(--tr)}}
.ftr a:hover{{color:var(--text)}}
@media(max-width:700px){{
.wrap{{padding:24px 16px}}
.tbl,.tbl thead,.tbl tbody,.tbl tr,.tbl th,.tbl td{{display:block}}
.tbl th{{display:none}}
.tbl tr{{padding:14px 0;border-bottom:1px solid rgba(255,255,255,0.06)}}
.tbl td{{padding:2px 0;border:none}}
.tbl tbody tr:hover td{{background:transparent}}
.co,.lo,.dt{{white-space:normal}}
.st{{font-size:.8rem;gap:12px}}
}}
</style>
</head>
<body>
<div class="wrap">
<div class="top">
<div>
<h1>Egypt Internships</h1>
<div class="sub">{now.strftime('%B %d, %Y')} &middot; {len(jobs)} results</div>
</div>
</div>
<div class="st">
<span><b>{len(jobs)}</b> internships</span>
<span><b>{len(sources)}</b> sources</span>
{f'<span><b>{stale_count}</b> stale (&gt;{STALE_AFTER_DAYS}d)</span>' if stale_count else ''}
</div>
<div class="bar">
<div class="srch">
<input type="text" id="q" placeholder="Search title, company, location…" oninput="fl()">
</div>
<div class="chips">
<button class="ch on" data-s="all" onclick="fs(this,'all')">all</button>
{chips}
{f'<button class="ch stale-toggle" id="stale-toggle" onclick="toggleStale(this)">hide stale</button>' if stale_count else ''}
</div>
</div>
<div class="cnt" id="cnt">Showing {len(jobs)} of {len(jobs)}</div>
<table class="tbl">
<thead>
<tr>
<th onclick="st(0)">Title</th>
<th onclick="st(1)">Company</th>
<th onclick="st(2)">Location</th>
<th onclick="st(3)">Date Posted</th>
<th onclick="st(4)">Source</th>
</tr>
</thead>
<tbody id="b">{rows}</tbody>
</table>
<div class="emp" id="emp">No results match your search.</div>
<div class="ftr">
Built by <a href="https://mezoinnit.github.io" target="_blank" rel="noopener">Moataz Ahmed</a>
&middot; <a href="https://github.com/Mezoinnit/internship-Scraper" target="_blank" rel="noopener">Source code - GitHub</a>
&middot; &copy; {now.year} All rights reserved
</div>
</div>
<script>
var hideStale=false;
function fl(){{
var q=document.getElementById('q').value.toLowerCase()
var a=document.querySelector('.ch.on[data-s]')
var s=a?a.dataset.s:'all'
var r=document.querySelectorAll('#b tr')
var v=0
r.forEach(function(x){{
var matchSrc=(s==='all'||x.dataset.s===s)
var matchQ=x.textContent.toLowerCase().includes(q)
var matchStale=!(hideStale&&x.dataset.stale==='1')
var ok=matchSrc&&matchQ&&matchStale
x.classList.toggle('hide',!ok)
if(ok)v++
}})
document.getElementById('cnt').textContent='Showing '+v+' of '+r.length
document.getElementById('emp').style.display=v?'none':'block'
}}
function fs(b,s){{
document.querySelectorAll('.ch[data-s]').forEach(function(x){{x.classList.remove('on')}})
b.classList.add('on')
fl()
}}
function toggleStale(b){{
hideStale=!hideStale
b.classList.toggle('on',hideStale)
fl()
}}
function st(n){{
var tbody=document.getElementById('b')
var r=Array.from(tbody.querySelectorAll('tr'))
var d=tbody.dataset.dir==='a'?'d':'a'
tbody.dataset.dir=d
r.sort(function(rowA,rowB){{
var x=(rowA.children[n]?.textContent||'').trim().toLowerCase()
var y=(rowB.children[n]?.textContent||'').trim().toLowerCase()
return d==='a'?x.localeCompare(y):y.localeCompare(x)
}})
r.forEach(function(x){{tbody.appendChild(x)}})
fl()
}}
</script>
</body>
</html>"""
