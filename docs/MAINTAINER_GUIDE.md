# Front-end maintainer guide

This guide describes the HTML and CSS architecture after refactoring A–E (October 2026). Update it when ownership or shared contracts change. The goal is code a CS university student can follow: explicit names, small responsibilities, useful section comments, and predictable behavior.

## Start here

- `templates/base.html` owns the document shell, shared assets and extension blocks.
- Feature pages compose list/detail panels and modal collections from their own `includes/` directories.
- `static/css/` contains authored styles. `static/vendor/` contains third-party assets; do not reformat those.
- `static/js/` contains progressively added browser behavior. The app remains server-rendered Django with Bootstrap; Dashboard also renders records from JSON.
- Local `build_docs/` contains audit reports, product decisions and evidence. It is ignored by Git and may not exist in a fresh checkout. This guide is intentionally versioned.

## What the HTML/CSS refactoring changed

| Stage | Result |
| --- | --- |
| A | Expanded compressed CSS/templates; introduced Prettier, Stylelint and djLint conventions. |
| B | Removed proved obsolete CSS and separated reusable Event form styles from the Event page. |
| C | Shared pagination, feature modal collections and page panel partials; removed obsolete Property record templates. |
| D | Replaced the large `site.css` with foundation, components, workspace and feature owners. |
| E1 | Reviewed section comments and made structural template markup easier to scan. |
| E2 | Corrected shared workspace ownership and gave Contacts' Notes component its own stylesheet. |
| E3 | Split 26 dialogs into feature-local files; shared Task deadline details and Contact form fields; clarified linked-Task metadata; merged four adjacent identical media blocks. |

E3 ends at commit `3c548ff`: 11 authored stylesheets and 99 runtime templates. More files and expanded lines are intentional where they make responsibilities clearer. Moves are not code deletions.

## CSS ownership and load order

The order in `base.html` is significant:

1. Bootstrap.
2. `foundation.css`.
3. `components.css`.
4. The page's `page_css` block.
5. `workspace.css`.
6. The page's `extra_css` block.

Do not alphabetize these links. Moving a rule between files can change its precedence even when its text stays identical.

| File | Responsibility / consumers |
| --- | --- |
| `foundation.css` | Design tokens, application shell, navigation and account foundation. Shared. |
| `components.css` | Shared forms, buttons, tabs, dialogs and feedback. Some historical Task layout overrides remain; inspect consumers before moving them. |
| `workspace.css` | Shared workspace controls, headers, compact rows, badges/dates, related-record links and cross-workspace responsive rules. |
| `task-page.css` | My Work Tasks geometry and page-specific presentation; `page_css`. |
| `issue-page.css` | My Work Issues geometry and page-specific presentation; `page_css`. |
| `contact-page.css` | Contacts page presentation; `page_css`. Generic workspace rules belong in `workspace.css`. |
| `notes.css` | Reusable server-rendered Notes board; currently loaded by Contacts after its page CSS. Dashboard Notes has separate presentation. |
| `event-components.css` | Reusable Event forms and contact picker; loaded by Events, Properties and Dashboard. |
| `event-page.css` | My Work Event list, calendar and detail panels. |
| `property-workspace.css` | Property page and its related-record panels. |
| `dashboard.css` | Dashboard board, calendar, records, dialogs and Notes. |

Event page, Property and Dashboard styles load through `extra_css`; Event components precede the consuming page's styles.

### Choosing where a rule belongs

- Check all template and JavaScript consumers, including dynamically generated Dashboard HTML.
- Put a reusable visual primitive in its shared owner. Keep a genuinely different page density as a scoped page override.
- Prefer the existing tokens and component classes. Do not add a near-identical class just to avoid understanding an existing one.
- Keep responsive rules close to their relevant section when practical, but preserve the cascade during a move.
- Merge identical media conditions only when their adjacency/order makes that safe. Identical conditions do not make distant blocks interchangeable.
- `!important` is not automatically dead code. E3 retained all 113 declarations because removing them without proving precedence could break Bootstrap overrides or hidden-state behavior.

**Lesson from D/E:** Property once lost its layout because generic workspace styles were placed in Contact-only CSS. HTTP 200 responses and absence of horizontal overflow did not detect that regression. Check stylesheet loading, computed layout and the rendered appearance of every consumer.

## Template structure and reuse

Keep the page shell readable as an outline: assets, list panel, detail panel, modal collection, scripts. Extract substantial cohesive sections rather than every few lines.

Use feature-local partials unless there is a real second consumer with the same meaning:

- `templates/includes/command_pagination.html`: common workspace pagination.
- `templates/includes/expandable_text.html`: shared disclosure markup and its JS hooks.
- `task/includes/deadline_detail.html`: shared desktop/mobile Task deadline output.
- `issue/includes/linked_task_metadata.html`: readable status/date output for linked Tasks.
- `contact/includes/contact_form_fields.html`: Add/Edit fields and errors.
- Feature `includes/modals/` directories: complete individual dialogs; their parent collection retains conditions controlling whether each exists.

Paths above are Django template names; feature files live under `<app>/templates/<app>/`.

Small semantic badge adapters can stay. Do not replace them with a universal component taking many flags. The Task modal collection remains compact enough to read without one file per dialog.

### Preserve these contracts

- IDs and matching `for`, `aria-controls`, `aria-labelledby`, `data-bs-target` references.
- Form action/method, field names, CSRF token, validation errors and submitted values.
- `data-*` hooks, selection markers, query parameters and Back-navigation state.
- Template context and tag libraries: a newly extracted partial must load the libraries it uses. Use `include ... only` when the inputs are deliberately explicit; do not blindly apply it to context-heavy dialogs.
- Meaning of dates and states. Existing `task/templatetags/work_status.py` helpers (`status_for`, `relative_day`) are the established source for shared status/date decisions. Terminal records must not acquire active-overdue wording.
- Whitespace in actual text, inline separators and preformatted descriptions. Formatting is not permission to change output.

For a long conditional, first identify the decision. Reuse an existing semantic helper, or give a genuinely repeated block a focused partial. A comment above an unreadable expression is not a substitute for simplifying it.

## Commenting and formatting

Use comments to show section boundaries, ownership and reasons that the code cannot communicate by itself. Avoid narrating every element or declaration.

CSS section headings go **above the entire selector group**, never between comma-separated selectors:

```css
/* Calendar and detail panels fill the available workspace height. */
.event-right-body,
.event-right-body > .tab-pane,
.event-calendar-pane,
.event-detail-pane {
    height: 100%;
    min-height: 0;
}
```

Use Django comments for maintainer notes that should not be sent to the browser:

```django
{# Keep eligibility in the parent; the partial owns the dialog markup. #}
{% if selected_contact %}
    {% include "contact/includes/contact_modals.html" %}
{% endif %}
```

That example illustrates the convention; check the actual page's existing condition before editing it.

A useful JavaScript comment explains a behavioral boundary:

```javascript
// Back should restore this history entry, even if another entry saved a newer position.
```

Prefer named intermediate values and ordinary `if` statements over nested ternaries when a reader must reason through several choices. Comments should remain accurate after extraction.

Current tooling: Prettier uses four-space indentation and a 100-character target; djLint uses the Django profile, four spaces and a 120-character limit. Stylelint deliberately does not enforce broad cascade/naming changes. There is no configured JavaScript linter yet; JavaScript tooling changes should be a separate reviewed step.

## Checking a bounded change

1. Write the scope, consumers, preserved behavior and check plan before editing.
2. Capture representative desktop/phone states before a visual or structural refactor. Include long content, a selected row and an open dialog when relevant.
3. Make one coherent change. Preserve declarations/order for moves; inspect the diff for accidental rewrites.
4. Run the relevant formatter/linter and focused behavioral tests. Do not default to full suites.
5. Check the affected browser states, loaded assets, key computed styles, keyboard/focus and scroll behavior. Compare before/after evidence.
6. Record actual checks, limitations, representative source examples and separate counts for added, removed and moved code. Stop if a purported structural change alters behavior unexpectedly.

Useful commands from the repository root:

```powershell
npm run lint:css
npm run format:css:check
python -m djlint path\to\changed\templates --lint
python -m djlint path\to\changed\templates --check
node --test tests/workspace-filter-url.test.cjs
```

Choose test paths for the behavior actually touched. Run Django tests when template semantics or server-side display logic changes. A screenshot cannot verify submitted values, and a source regex cannot verify layout.

### JavaScript test policy

Keep tests for calculations, keyboard/focus decisions, URL/history state, preserved form values, duplicate submissions and failure handling. Tests for JS geometry/scroll algorithms are useful even though their effects are visual; supplement them with browser checks.

Exact CSS strings, class ordering and tiny presentational choices usually belong in representative browser checks. Before removing a test, identify its assertions individually, preserve any behavior coverage, and record the replacement check. Do not remove a failing test merely to obtain a green run. VM tests use simulated DOMs and do not prove native browser layout, Bootstrap focus traps or back/forward-cache behavior.

## Working conventions

- Plain imperative commit titles, one bounded concern: `Document front-end maintenance conventions` or `Extract shared Event form behavior`.
- No incidental product redesign during refactoring. The settled Property header order is title, state/Added metadata, then address.
- Preserve the user's server on port 8000. Use a separate agent server for browser checks and reuse it rather than repeatedly logging in.
- Seeded test data may be changed for verification. Keep credentials, session files and local evidence out of commits.
- The existing untracked `tests/acceptance/` project is outside this refactoring scope; do not edit or stage it.
- Local continuation references, when available: `build_docs/REFACTOR_HANDOFF.md`, `CSS_HTML_AUDIT.md`, `PRODUCT_DECISIONS.md`, `FINDINGS.md`, `e_cleanup/PLAN.md`, and `chunk_e1_report.html` through `chunk_e3_report.html`. Their historical sections may describe superseded architecture; current source and later completion notes take precedence.
