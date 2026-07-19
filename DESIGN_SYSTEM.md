# INS ATS — Design System

## Design Tokens

### Type Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--text-xs` | 0.7rem | Badge labels, helper text, overflow counts |
| `--text-sm` | 0.75rem | Form hints, meta text, table secondary |
| `--text-base` | 0.8rem | Table cells, buttons, nav items |
| `--text-md` | 0.85rem | Body text (default), form labels |
| `--text-lg` | 0.95rem | Section headings, emphasized text |

Font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif`

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 0.15rem | Tight padding (badge internal, checkbox) |
| `--space-sm` | 0.25rem | Small gaps, compact buttons |
| `--space-md` | 0.4rem | Standard element padding |
| `--space-lg` | 0.6rem | Nav item padding, form field gaps |
| `--space-xl` | 0.85rem | Button padding, section spacing |
| `--space-2xl` | 1.25rem | Large button padding, section margins |

### Colors — Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--accent` | #505050 | Links, active states, primary actions |
| `--accent-hover` | #1a1a1a | Hover state for accent elements |
| `--accent-light` | #f2f2f2 | Light accent background |
| `--text-primary` | #1a1a1a | Headings, primary text, button labels |
| `--text-secondary` | #555555 | Body text (default) |
| `--text-muted` | #999999 | Placeholder, disabled, meta labels |
| `--bg-page` | #f8f8f8 | Page background |
| `--bg-card` | #ffffff | Card/panel surfaces |
| `--bg-muted` | #f0f0f0 | Hover states, muted backgrounds |
| `--border` | #e5e5e5 | Dividers, card borders |
| `--border-focus` | #505050 | Input focus ring |

### Colors — Dark Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--accent` | #b0b0b0 | Links, active states |
| `--accent-hover` | #d0d0d0 | Hover state |
| `--text-primary` | #e8e8e8 | Headings, primary text |
| `--text-secondary` | #aaaaaa | Body text |
| `--text-muted` | #666666 | Meta, placeholder |
| `--bg-page` | #161616 | Page background |
| `--bg-card` | #1c1c1c | Card surfaces |
| `--bg-muted` | #262626 | Hover, group headers |
| `--border` | #333333 | Dividers |
| `--border-focus` | #a0aec0 | Focus ring |

### Semantic Colors

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--danger` | #dd4444 | #e06060 | Destructive actions, errors |
| `--danger-bg` | #fef2f2 | #2a1c1c | Error backgrounds, WELL_ABOVE band |
| `--warning` | #cc8800 | #dda030 | Warnings, ABOVE band |
| `--warning-bg` | #fefce8 | #2a2618 | Warning backgrounds |
| `--success` | #22aa55 | #55cc77 | Confirmations, WELL_BELOW band |
| `--success-bg` | #f0fdf4 | #1a2a1c | Success backgrounds, BELOW band |

### Elevation

| Token | Light | Dark |
|-------|-------|------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.04)` | `0 1px 2px rgba(0,0,0,0.3)` |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.06)` | `0 4px 6px rgba(0,0,0,0.4)` |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Buttons, badges, inputs |
| `--radius-md` | 8px | Cards, panels, images |
| `--radius-lg` | 12px | Modals, large containers |

---

## Components

### Button

4 tiers with 3 sizes.

| Class | Visual | Usage |
|-------|--------|-------|
| `.btn` | Outlined (border + transparent bg) | Primary actions (Save, Create, Submit) |
| `.btn-ghost` | No border, accent text | Secondary actions (Cancel, links) |
| `.btn-danger` | Muted text, red on hover | Destructive actions (Delete) |
| `.btn-icon` | Icon-only, no border | Toolbar actions (copy, filter, sort) |
| `.btn-pill` | Dashed border, rounded | Additive actions (+ Add tag) |

**Sizes:** `.btn--sm` / default / `.btn--lg`
**Modifiers:** `.btn--full` (full-width), `.btn--loading` (disabled + opacity)
**States:** `:hover` inverts (bg fills with text-primary), `:disabled` at 40% opacity

### Badge

Status indicators with optional dot prefix.

| Class | Visual | Usage |
|-------|--------|-------|
| `.badge` (default) | Grey bg, grey text | Generic labels |
| `.badge-pending` | Hollow dot `◌` | Not started |
| `.badge-screening` / `.badge-open` | Filled dot `●` | Active/open |
| `.badge-interview` / `.badge-offer` | Half dot `◐` | In progress |
| `.badge-completed` / `.badge-hired` | Check `✓`, green | Success |
| `.badge-cancelled` / `.badge-rejected` | Cross `✕`, red | Failure |
| `.badge-withdrawn` / `.badge-low` | Empty `○`, muted | Neutral/low |
| `.badge-muted` | No icon, low opacity | Skill tags, labels |

### Band Pill

Salary positioning indicator (signal engine).

| Class | Color | Meaning |
|-------|-------|---------|
| `.band-well-below` | success-bg/success | Strong below-market (P0-P10) |
| `.band-below` | success-bg/success, 75% opacity | Below market (P10-P25) |
| `.band-market` | bg-muted/text-muted | Normal range (P25-P75) |
| `.band-above` | warning-bg/warning | Above market (P75-P90) |
| `.band-well-above` | danger-bg/danger | Strong above-market (P90-P100) |
| `.band-none` | Dashed border | No data / insufficient |

### Form Inputs

| Element | Styling |
|---------|---------|
| `.form-input` | Full-width, border, bg-card, radius-sm, text-md |
| `.form-label` | text-sm, text-secondary, font-weight 500 |
| `.form-hint` | text-sm, text-muted |
| `.inline-select` | Transparent bg, no border, auto-submit on change |
| `input:focus` | border-color: border-focus, outline: none |

### Card

| Class | Usage |
|-------|-------|
| `.card` | Generic content container (bg-card, shadow-md, radius-md) |
| `.detail-section` | Detail page section (bg-card, border, radius-md, padding) |
| `.detail-section-label` | Section heading (text-sm, text-muted, uppercase, letter-spacing) |

### Table

| Class | Usage |
|-------|-------|
| `.table-clean` | Borderless table (no row borders, hover delineation) |
| `.clickable-row` | Cursor pointer, bg-muted on hover |
| `.row-focused` | Keyboard-selected row (bg-muted) |
| `.group-header` | Collapsible group divider (bg-muted, bold, clickable) |
| `.col-primary` | Primary cell text (font-weight 500, text-primary) |
| `.row-meta` | Secondary cell text (text-sm, text-muted) |

### Toast

| Pattern | Usage |
|---------|-------|
| `.toast` | Fixed-position notification (bottom-right) |
| `.toast.show` | Visible state (slide in) |
| `.toast.hide` | Exiting state (fade out) |
| `.toast-undo` | Toast with undo button (flex row) |

### Context Menu

| Class | Usage |
|-------|-------|
| `#ctx-menu` | Positioned popup (bg-card, shadow-md, border) |
| `.ctx-item` | Menu item (hover: bg-muted) |
| `.ctx-danger` | Destructive menu item (hover: danger color) |

### Confirm Dialog

| Pattern | Usage |
|---------|-------|
| `.confirm-backdrop` | Full-screen overlay (rgba black) |
| `.confirm-card` | Centered modal (bg-card, shadow, radius-lg) |
| Danger detection | Keywords "delete"/"cancel"/"remove" → red confirm button |

---

## Layout Patterns

### App Shell

```
┌─ sidebar (240px, fixed) ──────────────────┐
│ brand                                      │
│ nav links (active = border-left + bg-muted)│
│ groups (collapsible)                       │
│ footer (logout)                            │
├─ main-content (margin-left: 240px) ───────┤
│ topbar (theme toggle)                      │
│ breadcrumb                                 │
│ page-header                                │
│ content                                    │
└────────────────────────────────────────────┘
```

Collapsed sidebar: 56px rail, icons only, localStorage persisted.

### List Page

```
page-header (h1 + optional action)
table-controls (search input + filter btn + sort btn + add btn)
filter-pills (active filters, removable)
sync-table-wrap (scrollable tbody)
table-count
```

### Detail Page

```
page-header (h1)
detail-actions (4 clusters: nav | export | mutate | destruct)
detail-section × N (label + content)
comment-section (form + trail)
activity-section (capped trail + "show all")
```

### Settings Page

```
settings-shell (grid: 180px nav | content)
settings-tab × N (vertical nav, active state)
settings-content (HTMX-swapped tab body)
```

---

## Interaction Patterns

### Inline Edit (edit-commit protocol)

Two modes:
1. **Auto-submit select**: `onchange → opacity 0.5 → requestSubmit()` — no save button
2. **Text + save**: input field + explicit "Save" button — manual commit

Both use: `hx-post` + `hx-swap="none"` + `hx-select="unset"` + `hx-boost="false"`

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Next row |
| `k` / `↑` | Previous row |
| `Enter` | Navigate to focused row |
| `/` | Focus search input |
| `Escape` | Clear focus / blur input |
| `Home` / `End` | Jump to first/last |
| `Shift+click` | Range select (bulk) |
| `Backspace` | Browser back |

### Soft Delete + Undo

1. Delete → `HX-Trigger: undoable-delete` → toast with undo button
2. Undo → `POST /restore/{model}/{id}` → WS broadcast "insert"
3. 30-day auto-purge of soft-deleted records

### Theme Toggle

- `data-theme` attribute on `<html>` (dark/light)
- Flash prevention: inline `<script>` in `<head>` reads localStorage before paint
- localStorage key: `'theme'`, values: `'dark'` / `'light'`
- System default: `prefers-color-scheme` media query fallback

---

## Dark Mode Strategy

Monochrome-first. No semantic colors change meaning between themes — only luminance inverts. All colors defined as CSS custom properties on `:root`, overridden in `[data-theme="dark"]` and `@media (prefers-color-scheme: dark)` (both present for redundancy).

---

## Naming Conventions

| Pattern | Example | Rule |
|---------|---------|------|
| Component | `.btn`, `.badge`, `.card` | Single word, no prefix |
| Variant | `.btn-ghost`, `.badge-pending` | Component-variant |
| Tier (BEM-lite) | `.btn--sm`, `.btn--full` | Double-dash modifier |
| State | `.active`, `.show`, `.hide` | Generic class, scoped by parent |
| Layout | `.app-shell`, `.main-content` | Hyphenated compound |
| Cell type | `.col-primary`, `.row-meta`, `.cell-date` | Prefix by role |
| JS hook | `data-sync-table`, `data-href` | data-attribute, no class coupling |

---

## Motion

| Context | Duration | Easing |
|---------|----------|--------|
| Hover transitions | 0.15s | ease (default) |
| Sidebar collapse | 0.15s | ease |
| Toast enter | CSS class swap (instant) | — |
| Toast exit | 0.3s fade | ease-out |
| Theme thumb | 0.15s | ease |

No spring animations. No enter animations on page content. Motion is functional (state feedback), never decorative.
