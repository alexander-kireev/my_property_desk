# Property Operations Manager

> Current status: Technical design and project setup.

## Overview

Property Operations Manager is a web application for organising a small property portfolio and the day-to-day operational work associated with it.

The public product pages live in `pages/templates/pages/` and share `templates/public_base.html`, the public header/footer includes, and `static/public/` assets. The signed-in workspace keeps its existing `templates/base.html` shell. Login and registration reuse their existing Django forms and account views with the public layout.

The Contact page emails reports and messages through Django's configured email backend. Set `PMS_CONTACT_EMAIL` to the inbox that should receive them, alongside the SMTP settings in `.env.example`. Reports can be anonymous and may include up to three PNG, JPG or WebP screenshots (5 MB each, 12 MB total); uploaded files are attached to the outgoing email and are not stored by the application.

Forgot-password requests use the same email backend and a one-hour link. Requests are limited by email address and `REMOTE_ADDR` using hashed, database-backed counters; deployment behind a reverse proxy should ensure `REMOTE_ADDR` identifies the intended client source. Run migrations before enabling the public reset route. HTTPS must be enabled on the deployed site for reset links to work securely. See `accounts/PASSWORD_RESET_POLICY.md` for the full flow and delivery limitation.

It is intended to bring properties, contacts, issues, tasks, events, notes and scheduling information into one lightweight system without the overhead of enterprise property-management software.

## Target user

The primary user is an individual managing approximately 5–50 properties.

Version 1.0 is manager-facing. Other people involved in property operations, including landlords, tenants, contractors and agents, are represented as Contacts rather than application users.

## Planned V1 scope

Version 1.0 is planned to provide:

- A public-facing product website
- Account registration and authentication
- Property portfolio management
- Contact and property-role management
- Creation and management of Issues, Tasks and Events
- Calendar-based scheduling of Tasks and Events
- Contextual Notes and NotesBoards
- A portfolio dashboard and calendar
- Read-only access to historical operational records

## Technology

- Python 3.14
- Django 5.2.17 LTS
- PostgreSQL 18
- Server-rendered HTML and CSS with Bootstrap

## Development approach

This is a personal portfolio and learning project intended to strengthen practical skills in system design, relational database modelling, Django development, testing and deployment.

Development follows a structured but lightweight software-development lifecycle: requirements analysis, domain modelling, technical design, incremental implementation, continuous testing and iteration. The process emphasises useful engineering discipline without unnecessary ceremony.

## Development formatting

When available locally, `docs/MAINTAINER_GUIDE.md` describes front-end ownership, shared templates, commenting conventions and focused checks. It is intentionally Git-ignored and is not included in a fresh clone.

Install the optional formatting tools after installing the application requirements:

Use a Node.js version supported by ESLint: 20.19+, 22.13+ or 24+. This tooling baseline was checked with Node 24.19.

```powershell
pip install -r requirements-dev.txt
npm install
```

Check the authored CSS and Django templates without changing them:

```powershell
npm run lint:css
npm run format:css:check
python -m djlint accounts contact event issue note pages property task templates --lint
python -m djlint accounts contact event issue note pages property task templates --check
```

Format CSS or a bounded group of templates, then review the diff before committing:

```powershell
npm run format:css
python -m djlint path\to\templates --reformat
```

CSS rules that could alter the cascade or impose a new naming scheme are deliberately excluded from the initial lint baseline. Those changes belong in reviewed refactoring work rather than automatic formatting.

JavaScript correctness checks cover all authored browser scripts:

```powershell
npm run lint:js
npm run format:js:check
```

JavaScript formatting covers every authored `static/js/*.js` file. Use `npm run format:js` to format them. See the maintainer guide for module ownership and focused browser checks.

## Project status

Python checks cover the authored application code, excluding historical migrations and local tools:

```powershell
python -m ruff check accounts config contact event issue note pages property task manage.py
python -m ruff format --check accounts config contact event issue note pages property task manage.py
```

Use `python -m ruff format path/to/file.py` for a bounded formatting change. Review import changes and run the affected tests; formatting does not replace behaviour checks.

Requirements and domain analysis are substantially complete. Technical design and application setup are now underway.
