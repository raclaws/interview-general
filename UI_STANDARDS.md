# UI Standards — Interview Form Summarizer

Benchmark: Linear. Monochrome + teal accent.

---

## Button Hierarchy

| Level | Style | Usage | Example |
|-------|-------|-------|---------|
| Primary | Teal bg, white text, rounded | One per page — the main action | "Create Session", "Submit Assessment", "Generate Summary" |
| Secondary | Gray border, no fill, dark text | Supporting actions | "Edit", "Regenerate", "Copy as Markdown" |
| Danger | Red bg, white text | Destructive, always behind confirm | "Cancel Session" |
| Ghost | No bg/border, teal text, underline on hover | Navigation-like | "← Back to Dashboard", "View" |

### Rules
- Maximum ONE primary button visible per page section
- Never place danger next to primary
- Secondary buttons group horizontally with 8px gap
- Ghost buttons are inline text, not boxed

---

## Button Placement

| Context | Placement |
|---------|-----------|
| Page-level action (New Session) | Top-right, aligned with page title (h1 and button in a flex row) |
| Form submit (Create, Save, Submit) | Right-aligned below form on desktop. Full-width on mobile. |
| Detail page actions (Edit, Cancel) | Below the info section, left-aligned, horizontal group |
| Summary actions (Generate, Copy) | Inside the summary block, left-aligned |
| Table row actions (View, Copy link) | Right column of table, ghost style |
| Back navigation | Bottom of page, ghost style, left-aligned |

---

## Spacing

| Between | Gap |
|---------|-----|
| Label → input | 4px |
| Input → next label | 16px |
| Section → section (within card) | 24px |
| Buttons in a group | 8px |
| Content → action buttons below | 16px |
| Page title → first content | 24px |
| Cards in a grid | 16px |

---

## Layout Patterns

### Page Header (Dashboard, Templates)
```
[h1: Page Title]                    [Primary Button]
```
Flex row, `justify-content: space-between`, `align-items: center`.

### Detail Page Actions
```
[Info Card]
[Edit (secondary)] [Cancel (danger)]    ← horizontal row below card, 8px gap
```

### Form Actions (Desktop)
```
                              [Submit (primary)]
```
Right-aligned. `text-align: right` or flex with `justify-content: flex-end`.

### Form Actions (Mobile)
```
[Submit (primary, full-width)]
```

---

## Components

### Cards
- White bg, 8px radius, subtle shadow
- 24px padding
- No visible border (shadow provides depth)

### Tables
- Inside a card wrapper (shadow + radius)
- Uppercase 0.7rem headers, muted color
- Row hover: barely-there gray tint
- Actions in last column, ghost style

### Badges
- Pill-shaped (20px radius)
- Soft bg color + dark text of same hue
- Pending: amber. Completed: green. Cancelled: red.

### Inputs
- 1px border, 4px radius
- 12px vertical padding, 14px horizontal
- Focus: teal border + teal shadow ring (3px, 10% opacity)
- No outline

### Nav
- Charcoal bg (#1f2937)
- Links: light gray, teal on active/hover
- Logout: ghost style, right-aligned via `margin-left: auto`

---

## Typography

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| h1 | 1.5rem | 700 | text-primary |
| h2 | 1.15rem | 600 | text-primary |
| h3 | 1rem | 600 | text-primary |
| Body text | 0.875rem | 400 | text-secondary |
| Labels | 0.85rem | 500 | text-primary |
| Hints | 0.75rem | 400 | text-muted |
| Table headers | 0.7rem | 600 | text-muted, uppercase |
| Badges | 0.7rem | 600 | — |
| Buttons | 0.85rem | 500 | — |

---

## Pages to Update

### Dashboard (`dashboard.html`)
- [ ] h1 + "New Session" button in flex row (space-between)
- [ ] "View" link in table → ghost style

### Session Detail (`session_detail.html`)
- [ ] "Edit" + "Cancel" → horizontal row below info card (not inside it)
- [ ] "Generate Summary" stays primary inside summary block
- [ ] "Regenerate" + "Copy" → secondary, horizontal group
- [ ] "← Back to Dashboard" → ghost at page bottom

### Session New (`session_new.html`)
- [ ] "Create Session" → right-aligned on desktop, full-width mobile
- [ ] Remove previous loading-state JS override of button width

### Session Edit (`session_edit.html`)
- [ ] "Save Changes" → right-aligned
- [ ] "← Back to Session" → ghost at bottom

### Interview Form (`interview_form.html`)
- [ ] "Submit Assessment" → full-width always (interviewer is likely on mobile)

### Templates List (`templates_list.html`)
- [ ] Table actions → ghost "View" link

### Login (`login.html`)
- [ ] Submit → full-width (already is), confirm it stays primary

---

## Implementation Plan

1. Update CSS: add `.btn-ghost`, `.btn-outline` classes. Adjust `.btn` sizing. Add `.page-header` flex utility.
2. Update `dashboard.html` — page header layout
3. Update `session_detail.html` — move actions, fix hierarchy
4. Update `session_new.html` — right-align submit
5. Update `session_edit.html` — right-align submit
6. Update `templates_list.html` — ghost view links
7. Responsive check — mobile still works

Estimated: ~45 min total.
