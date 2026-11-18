# Implementation Tasks

Only tick a box after verifying the result. Work one milestone at a time.

## Milestone 0 — Understand and plan
- [x] Read `reference/Django_Group Assignment.pdf` and `REQUIREMENTS.md`.
- [x] Confirm group members, responsibilities, instructor deadline, and SMS provider (TextBee Android SMS Gateway selected for Philippine recipients).
- [x] Review this plan before coding.

## Milestone 1 — Django foundation
- [x] Create and activate virtual environment.
- [x] Create Django project `sms_project` and app `sms_app`.
- [x] Configure installed app, URLs, templates, static CSS, and database.
- [x] Confirm `python manage.py check` and local server succeed.

## Milestone 2 — Compose form and validation
- [x] Build responsive SMS form with CSRF token.
- [x] Validate required recipient, E.164-format phone number, and nonblank message on the server.
- [x] Show field errors and useful feedback.
- [x] Add tests for valid and invalid form submissions.

## Milestone 3 — SMS integration (TextBee)
- [x] Add HTTP client dependency (`requests`), `requirements.txt`, and `.env.example` keys (`TEXTBEE_API_KEY`, `TEXTBEE_DEVICE_ID`).
- [x] Add SMS service module (`sms_app/services.py`) and load credentials from environment.
- [x] Integrate service with the form view; catch provider and network errors.
- [x] Display provider accepted/queued (`smsBatchId`) vs rejected statuses accurately, plus safe read-only diagnostics (`GET /api/v1/gateway/stats` and `GET /api/v1/gateway/devices`).
- [x] Mock the API for automated tests; never send SMS from unit tests.
- [x] Manually test real SMS with one authorized recipient if provider allows.

## Milestone 4 — One extra feature (SMS History & Modern Dashboard)
- [x] Choose: character counter, live message preview, SQLite message history (`SMSLog`), and summary statistics dashboard.
- [x] Implement and verify chosen features (`SMSLog` model & migrations, masked recipients, short excerpts, `Total Attempts` / `Submitted` / `Failed` cards, `Recent Messages` table, database-error isolation, and responsive layout).

## Milestone 5 — Quality and handoff
- [x] Run validation, failure, and success tests and record results.
- [x] Write README: purpose, members/roles, setup, provider configuration, run, tests, known limitations.
- [x] Generate requirements.txt; verify .gitignore excludes `.env`, `.venv/`, caches, local DB.
- [ ] Push code to GitHub with meaningful member contributions. *(To be completed by group members.)*
- [ ] Record a 3–10 minute video with real functionality and at least one error test. *(To be recorded by group members.)*
- [ ] Email GitHub and video links to instructor using specified subject. *(To be sent by group representative to `prala-an@carsu.edu.ph`, subject `Assignment_IT 120-1stSemSY26-27`.)*
