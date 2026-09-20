# DESIGN_SYSTEM.md

UI conventions for the two rendered surfaces:
- `templates/index.html` — the dark control panel (run configuration + live log)
- `utils/output.py` `_build_html` — the generated, self-contained results report

Both are **dark-mode-only**, hand-written, dependency-free CSS using CSS custom
properties. There is no Tailwind, no build step, no theme switch. Styling lives inline
in a single `<style>` block per file. Keep new UI consistent with these tokens.

---

## Color tokens

Defined in `:root`. The two surfaces share most tokens; the control UI adds a few.

### Shared / report (`utils/output.py`)
| Token            | Value                    | Use                                  |
|------------------|--------------------------|--------------------------------------|
| `--bg`           | `#09090b`                | Page background (near-black)         |
| `--surface`      | `#18181b`                | Raised panels / result cards         |
| `--surface-inset`| `#111113`                | Inputs, log panel, inset fields      |
| `--border`       | `rgba(255,255,255,0.07)` | Default hairline borders             |
| `--border-sep`   | `rgba(255,255,255,0.06)` | Table row separators (report only)   |
| `--text`         | `#fafafa`                | Primary text / inverted button bg    |
| `--text-2`       | `#a1a1aa`                | Secondary text, links                |
| `--text-3`       | `#52525b`                | Muted: labels, meta, placeholders    |
| `--tr`           | `0.2s ease`              | Standard transition                  |

### Control UI extras (`templates/index.html`)
| Token             | Value                    | Use                                 |
|-------------------|--------------------------|-------------------------------------|
| `--surface-raised`| `#1d1d20`                | Dropdown / popover surface          |
| `--border-active` | `rgba(255,255,255,0.16)` | Hover/focus borders                 |
| `--green`         | `#34d399`                | Log success entries (`.ent.ok`)     |
| `--red`           | `#f87171`                | Log error entries (`.ent.err`)      |

### Yellow "stale" accent (report only)
Stale jobs (older than `STALE_AFTER_DAYS = 30`) use a yellow accent built from
`234,179,8` (amber) at varying alpha — there is no token; it's used literally:
- Stale badge: `bg rgba(234,179,8,0.1)`, `border rgba(234,179,8,0.3)`,
  `color rgba(234,179,8,0.8)`.
- Stale filter chip on/off states use the same amber at 0.15/0.4/0.6/0.7 alpha.

When extending the report, reuse this amber for any stale/aged state rather than
introducing a new warning color.

---

## Typography

- **Report (`output.py`):** system font stack —
  `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`. No web fonts (keeps the
  report fully portable/offline).
- **Control UI (`index.html`):** `'DM Sans'` first, falling back to the same system
  stack; monospace log uses `'DM Mono','JetBrains Mono','Fira Code','Courier New',monospace`.
- Scale (rem): `h1` 1.25–1.35rem / weight 700, body ~0.88rem, secondary ~0.82rem,
  meta/badges ~0.7–0.79rem. Uppercase labels: ~0.68–0.7rem, weight 600,
  `letter-spacing .07em`, color `--text-3`.
- `-webkit-font-smoothing: antialiased` on `body`. Negative tracking `-.01em` on headings.

---

## Spacing & layout

- Box model: `*{box-sizing:border-box}`.
- Container width: **report `max-width:1200px`**, **control UI `max-width:680px`**, both
  centered (`margin:0 auto`), padding `40–48px 24px` (tightening to `24px 16px` on mobile).
- Spacing rhythm is multiples of ~4px: gaps `6/10/16/20/24/28/36px`; cell padding
  `10–14px`; section `margin-bottom:24px`.
- Border radii: inputs/log `8–10px`, buttons `6–10px`, **pills/chips/badges `100px`**.

---

## Component patterns

- **Badge (`.s-badge`):** pill, `rgba(255,255,255,0.06)` bg, hairline border, uppercase
  `--text-3`. Used for the source column.
- **Chip / filter button (`.ch`, `.src`):** pill, transparent by default, `--text-3`;
  `.on` inverts (bg `--text`, text `--bg`). Stale chip variant uses the amber accent.
- **Table (`.tbl`):** full-width, `border-collapse:collapse`, uppercase th headers
  (clickable to sort), `--border-sep` row dividers, subtle hover
  `background rgba(255,255,255,0.025)`. **On screens ≤700px the table reflows to a stacked
  block layout** (`th` hidden, each `tr` becomes a card).
- **Inputs (`.inp`, `.srch input`):** `--surface-inset` bg, hairline border, focus raises
  the border to `--border-active`; placeholder is `--text-3`.
- **Primary button (`.btn-p`):** inverted (bg `--text`, text `--bg`), weight 600,
  radius 10px. **Ghost button (`.btn-ghost`):** transparent, hairline, `--text-3`.
- **Log entries (`.ent`):** monospace; `.ok` green, `.err` red, `.sk` muted italic —
  these map to the SSE event types in CONVENTIONS §7.

---

## Responsive

- **Report:** single breakpoint `@media (max-width:700px)` → table collapses to stacked cards.
- **Control UI:** single breakpoint `@media (max-width:550px)`.
- No other breakpoints; design mobile-down from these two.

---

## Accessibility

- Links use `rel="noopener"` with `target="_blank"`; user-supplied text is HTML-escaped
  (`html.escape` in `output.py`, `esc()` in the template) — keep this on any new injected
  content (no raw HTML insertion).
- Focusable controls in the UI define `:focus-visible` outlines (`.btn-p`, `.btn-ghost`,
  `.ms-trigger`) — keep visible focus rings on new interactive elements.
- Color is dark-only with `--text`/`--text-2`/`--text-3` providing the contrast tiers;
  don't rely on the amber stale accent alone to convey state (it's paired with the text
  "stale").
