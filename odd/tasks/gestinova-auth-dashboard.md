# GESTINOVA authenticated generation dashboard

Deliver a secure, database-backed application that preserves the existing PEI document workflow while adding managed access and billable generation reporting.

## Problem

The current HTTP server is anonymous, stores outputs under a municipality-derived name, and has no durable generation ledger. It cannot safely support per-user billing, retries, administrative user management, or protected downloads.

## Authorized scope

- Add an elegant login and visible `GESTINOVA` wordmark without inventing an official icon.
- Let administrators create users, activate/deactivate accounts, and reset passwords.
- Configure PostgreSQL with `DATABASE_URL` and secrets through environment variables.
- Report completed generations in total, by user, and by billing month.
- Count a generation only after a DOCX is saved successfully.
- Enforce a unique `generation_request_id` and unique output names.
- Protect generation, download, and administration routes.
- Preserve document-generation behavior and the existing Spanish UI language.

## Constraints and decisions

- The dirty primary worktree is read-only for this change. Work occurs only on `feature/gestinova-auth-dashboard` in the dedicated sibling worktree.
- No fetch, push, pull request, merge, or other remote operation is authorized.
- Production must use PostgreSQL through `DATABASE_URL`; tests may inject an isolated deterministic in-memory database without network access.
- Secrets, database files, templates, and generated outputs must not be served as public static files.
- Passwords use Argon2. Authentication uses secure Flask sessions and CSRF protection for state-changing form routes.
- Existing generation functions remain the source of document behavior and are wrapped by the authenticated application.
- TDD mode: no explicit TDD configuration found; use ordinary functional checks.
- Delivery strategy: `ask-on-risk`.

## Review workload forecast

Expected authored change: approximately 1,200–1,700 lines across application infrastructure, templates/styles, tests, and documentation. This exceeds the ~400-line review guideline. No remote delivery will be created. Proposed local review slices are the four work units below; each closes with its own Conventional Commit and can become a chained PR later if requested.

| Slice | Review boundary | Estimated lines | Route | Trigger evidence |
|---|---|---:|---|---|
| 1 | Flask/database/auth foundation | 350–500 | delegated | More than two non-trivial files: app factory, models/security, tests/config |
| 2 | Administrator user lifecycle | 250–400 | delegated | More than two non-trivial files: routes, templates, tests |
| 3 | Protected generation ledger | 350–500 | delegated | More than two non-trivial files: generation integration, persistence, tests/frontend |
| 4 | Dashboard, branding, and operations docs | 300–450 | delegated | More than two non-trivial files: dashboard routes/templates/styles, tests/docs |

`delegated` records the ODD size trigger and intended review slicing. The user explicitly required autonomous non-delegated execution, so implementation remains inline in this session.

## Stable task checklist

- [x] **Task 1 — Establish secure Flask authentication and persistence**
  - Acceptance: app factory starts without remote access; production configuration requires `DATABASE_URL` and `SECRET_KEY`; users are Argon2-hashed; login/logout and active-user checks work; first admin can be created without a public bootstrap route.
  - Checks: auth-focused unit tests, startup/import check, dependency/config review.
  - Commit: `e162d24` (`feat(auth): establish secure application foundation`).
  - Evidence: `python -m unittest -v backend.test_auth` — 4 tests passed; `python -m py_compile backend/app.py backend/models.py` — passed; application factory startup with an isolated in-memory database — passed and listed only login, logout, and authenticated home routes.
- [ ] **Task 2 — Add administrator-managed users**
  - Acceptance: authenticated admins can create accounts, activate/deactivate non-self accounts, and reset passwords; non-admins and anonymous users are denied; CSRF is enforced.
  - Checks: user-management authorization and lifecycle tests.
  - Commit: pending.
  - Evidence: pending.
- [ ] **Task 3 — Protect and account for document generation**
  - Acceptance: generation and download require authentication; one successfully saved DOCX creates one ledger row; failures create none; unique request IDs make retries idempotent; separate requests cannot overwrite outputs; users can only download their own outputs unless administrators are explicitly allowed.
  - Checks: idempotency, failure accounting, output naming, ownership, and compatibility tests.
  - Commit: pending.
  - Evidence: pending.
- [ ] **Task 4 — Deliver billing dashboard, branding, and operational guidance**
  - Acceptance: GESTINOVA appears on login and application screens; admins see total, per-user, and monthly completed generations; ordinary users cannot access metrics; documentation covers environment, PostgreSQL, admin bootstrap, startup, and security boundaries.
  - Checks: metrics/authorization tests, frontend syntax, full suite, startup/import, configured lint/format checks, structural route/secret spot-check.
  - Commit: pending.
  - Evidence: pending.

## Acceptance criteria

- Anonymous requests cannot generate or download documents and cannot access administration.
- Disabled users cannot establish or continue authenticated sessions.
- No plaintext password is stored, logged, or committed.
- A repeated `generation_request_id` returns the existing successful generation and does not increment billing.
- The ledger is written only after the final DOCX save succeeds.
- Output filenames include collision-resistant server-generated identity rather than only municipality text.
- The administrator dashboard can reconcile totals by account and calendar month.
- Existing payload validation and DOCX transformation behavior remains covered.

## Required verification

- `python -m unittest -v`
- Focused tests for authentication, authorization, idempotency, metrics, and generation.
- Application import/startup check without remote services.
- Any configured formatter/linter in check mode, if present.
- `node --check frontend/app.js`
- `python -m py_compile ...`
- `git diff --check`
- Structural inspection of protected routes and static-file boundaries.

## Progress log

- Task 1 completed. Rollback boundary: `backend/app.py`, `backend/models.py`, authentication templates/tests, and the four added dependency declarations. Risk remains high because the forecast exceeds 400 lines; local work-unit slicing continues without remote delivery.
