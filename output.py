import json
from datetime import datetime
from pathlib import Path

from config import Internship, OUTPUT_DIR


def save_json(jobs: list[Internship], filename: str = "") -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = filename or datetime.now().strftime("internships_%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{ts}.json"
    data = {
        "generated_at": datetime.now().isoformat(),
        "total": len(jobs),
        "internships": [j.to_dict() for j in jobs],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return str(path)


def save_html(jobs: list[Internship], filename: str = "") -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = filename or datetime.now().strftime("internships_%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{ts}.html"
    path.write_text(_build_html(jobs))
    return str(path)


def _badge(source: str) -> str:
    styles = {
        "linkedin": "font-weight:700;text-transform:uppercase;letter-spacing:.04em",
        "indeed": "font-weight:400;font-style:italic",
        "wuzzuf": "font-weight:300;text-transform:uppercase;letter-spacing:.06em",
        "company": "font-weight:500",
        "search": "font-weight:300;font-style:italic",
        "glassdoor": "font-weight:600;text-transform:uppercase;letter-spacing:.03em",
    }
    s = styles.get(source, "font-weight:400")
    return f'<span class="s" style="{s}">{source}</span>'


def _clean_url(url: str) -> str:
    return url.split("?")[0] if "?" in url else url


def _build_html(jobs: list[Internship]) -> str:
    by_source = {}
    for j in jobs:
        by_source.setdefault(j.source, []).append(j)

    sources = sorted(by_source.keys())
    chips = "".join(
        f'<button class="ch" data-s="{s}" onclick="fs(this,\'{s}\')">{_badge(s)}</button>'
        for s in sources
    )

    rows = ""
    for j in sorted(jobs, key=lambda x: x.title.lower()):
        url = _clean_url(j.url)
        rows += (
            f'<tr data-s="{j.source}">'
            f'<td class="t"><a href="{url}" target="_blank" rel="noopener">{j.title}</a></td>'
            f'<td class="co">{j.company or "—"}</td>'
            f'<td class="lo">{j.location or "—"}</td>'
            f'<td>{_badge(j.source)}</td>'
            f'</tr>'
        )

    now = datetime.now()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Egypt Internships</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;background:#000;color:#fff;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:40px 24px}}
h1{{font-size:1.35rem;font-weight:700;letter-spacing:-.01em;margin:0}}
.sub{{color:#666;font-size:.85rem;margin-top:2px}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}}
.st{{display:flex;gap:20px;flex-wrap:wrap;margin:24px 0;font-size:.85rem;color:#666}}
.st b{{color:#fff;font-weight:600}}
.srch input{{width:100%;padding:10px 14px;font-size:.88rem;background:#111;color:#fff;border:1px solid #222;border-radius:8px;outline:none;transition:.15s}}
.srch input:focus{{border-color:#555}}
.srch input::placeholder{{color:#444}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px}}
.ch{{padding:6px 12px;border:1px solid #222;border-radius:6px;background:transparent;cursor:pointer;font-size:.8rem;color:#555;transition:.15s}}
.ch:hover{{color:#aaa;border-color:#444}}
.ch.on{{color:#fff;border-color:#555;background:#111}}
.ch .s{{font-style:normal}}
.cnt{{font-size:.82rem;color:#444;margin-top:4px}}
.tbl{{width:100%;border-collapse:collapse;margin-top:12px}}
.tbl th{{text-align:left;font-size:.75rem;font-weight:600;color:#444;text-transform:uppercase;letter-spacing:.05em;padding:8px 8px 10px;border-bottom:1px solid #1a1a1a;cursor:pointer;user-select:none;white-space:nowrap}}
.tbl th:hover{{color:#fff}}
.tbl td{{padding:10px 8px;font-size:.88rem;border-bottom:1px solid #111;vertical-align:top}}
.tbl tr.hide{{display:none}}
.tbl tbody tr:hover td{{background:#0a0a0a}}
.t a{{color:#fff;text-decoration:none;font-weight:500}}
.t a:hover{{text-decoration:underline}}
.co,.lo{{color:#666;white-space:nowrap}}
.emp{{text-align:center;padding:48px 16px;color:#444;display:none}}
.ftr{{margin-top:48px;padding-top:20px;border-top:1px solid #141414;text-align:center;font-size:.8rem;color:#444}}
.ftr a{{color:#888;text-decoration:none}}
.ftr a:hover{{color:#fff}}
@media(max-width:700px){{
.wrap{{padding:24px 16px}}
.tbl,.tbl thead,.tbl tbody,.tbl tr,.tbl th,.tbl td{{display:block}}
.tbl th{{display:none}}
.tbl tr{{padding:14px 0;border-bottom:1px solid #141414}}
.tbl td{{padding:2px 0;border:none}}
.tbl tbody tr:hover td{{background:transparent}}
.co,.lo{{white-space:normal}}
.st{{font-size:.82rem;gap:12px}}
}}
</style>
</head>
<body>
<div class="wrap">
<div class="top">
<div>
<h1>Egypt Internships</h1>
<div class="sub">{now.strftime('%B %d, %Y')} · {len(jobs)} results</div>
</div>
</div>
<div class="st">
<span><b>{len(jobs)}</b> internships</span>
<span><b>{len(sources)}</b> sources</span>
</div>
<div class="srch">
<input type="text" id="q" placeholder="Search title, company, location…" oninput="fl()">
</div>
<div class="chips">
<button class="ch on" data-s="all" onclick="fs(this,'all')">all</button>
{chips}
</div>
<div class="cnt" id="cnt">Showing {len(jobs)} of {len(jobs)}</div>
<table class="tbl">
<thead>
<tr>
<th onclick="st(0)">Title</th>
<th onclick="st(1)">Company</th>
<th onclick="st(2)">Location</th>
<th onclick="st(3)">Source</th>
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
function fl(){{
var q=document.getElementById('q').value.toLowerCase()
var a=document.querySelector('.ch.on')
var s=a?a.dataset.s:'all'
var r=document.querySelectorAll('#b tr')
var v=0
r.forEach(function(x){{
var ok=(s==='all'||x.dataset.s===s)&&x.textContent.toLowerCase().includes(q)
x.classList.toggle('hide',!ok)
if(ok)v++
}})
document.getElementById('cnt').textContent='Showing '+v+' of '+r.length
document.getElementById('emp').style.display=v?'none':'block'
}}
function fs(b,s){{
document.querySelectorAll('.ch').forEach(function(x){{x.classList.remove('on')}})
b.classList.add('on')
fl()
}}
function st(n){{
var b=document.getElementById('b')
var r=Array.from(b.querySelectorAll('tr'))
var d=b.dataset.dir==='a'?'d':'a'
b.dataset.dir=d
r.sort(function(a,b){{
var x=(a.children[n]?.textContent||'').trim().toLowerCase()
var y=(b.children[n]?.textContent||'').trim().toLowerCase()
return d==='a'?x.localeCompare(y):y.localeCompare(x)
}})
r.forEach(function(x){{b.appendChild(x)}})
}}
</script>
</body>
</html>"""
