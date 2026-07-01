# Hospital Management Backend API — Implementation Plan

Source requirement: `Python_DRF_Hospital_Assessment_Task.pdf`
Stated assessment duration: 3 hours. This plan is intentionally more thorough than a 3-hour build —
use the full roadmap as the reference architecture, and see **Appendix B** for how to compress it
back into a 3-hour execution sequence if this is being done as a timed assessment submission.

> **Scope note:** The PDF's deliverables list (GitHub repo, README, requirements.txt, `.env.example`,
> Postman Collection) contains no frontend/UI requirement — this is a pure DRF backend assessment.
> Wherever "frontend tasks" are requested, they are mapped to **API-consumer deliverables**: Postman
> collection design, example requests/responses, and API documentation. If a real frontend is added
> later, it would be a separate consumer of this API and does not change the backend design below.

---

## 1. Requirements Traceability (nothing missed)

| # | Requirement from PDF | Covered in |
|---|---|---|
| 1 | JWT Authentication | Phase 2 |
| 2 | Headquarters CRUD | Phase 3 |
| 3 | Sub Headquarters CRUD | Phase 3 |
| 4 | Doctor CRUD | Phase 4 |
| 5 | Visit Management | Phase 5 |
| 6 | Role Based Access Control (5-level hierarchy) | Phase 2 (framework), enforced in Phases 3–6 |
| 7 | Dashboard APIs | Phase 6 |
| 8 | Reports with Filters | Phase 6 |
| 9 | Search, Pagination & Sorting | Phase 6 (framework), applied to all list endpoints from Phase 3 onward |
| 10 | Dashboard metrics: Total HQs, Total Sub HQs, Total Doctors, Total MRs, Today's Visits, Completed Visits, Pending Visits | Phase 6 |
| 11 | Hierarchy: Super Admin → HQ → (HQ Admin → HQ Staff / MR) & (Sub HQ → Sub HQ Staff / MR) | Phase 1 (data model), Phase 2 (permissions) |
| 12 | Deliverable: GitHub Repository | Phase 0 (init) → Phase 8 (finalize) |
| 13 | Deliverable: README | Phase 8 |
| 14 | Deliverable: requirements.txt | Phase 0 (created), Phase 8 (finalized/pinned) |
| 15 | Deliverable: .env.example | Phase 0 (created), Phase 8 (finalized) |
| 16 | Deliverable: Postman Collection | Phase 8 (built incrementally per phase, exported at the end) |

---

## 2. Technology Stack & Architecture

**Stack (per PDF + supporting libraries):**

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.x |
| API | Django REST Framework 3.15+ |
| Auth | `djangorestframework-simplejwt` (access + refresh tokens, blacklist on logout) |
| Database | PostgreSQL 15, run via Docker (docker-compose), set up in Phase 0 |
| Filtering | `django-filter` (DjangoFilterBackend) + DRF `SearchFilter` / `OrderingFilter` |
| Config | `django-environ` or `python-decouple` for `.env` handling |
| Docs | `drf-spectacular` (OpenAPI/Swagger) — optional but cheap to add, complements Postman |
| Testing | Django `APITestCase` / `pytest-django` + `factory_boy` for fixtures |
| Dev tooling | Git, `black`/`flake8` (optional) |
| Deployment target | Render / Railway / AWS EC2 + Nginx + Gunicorn (any is fine; plan is platform-agnostic) |

**Architecture style:** Modular Django apps, one per bounded context, DRF ViewSets + Routers,
permission classes doing hierarchy-scoping at the queryset level (not just endpoint-level allow/deny).

**Recommended app layout:**

```
hospital_api/
├── config/                # settings/, urls.py, wsgi.py, asgi.py
│   └── settings/
│       ├── base.py
│       ├── dev.py
│       └── prod.py
├── accounts/               # custom User model, JWT auth views, user management
├── organizations/          # Headquarters, SubHeadquarters models + CRUD
├── doctors/                # Doctor model + CRUD
├── visits/                 # Visit model, visit CRUD, status transitions
├── dashboard/              # aggregation endpoints (no models of its own)
├── reports/                # filtered reporting endpoints (reuses Visit/Doctor querysets)
├── common/                 # shared permission classes, pagination, mixins, filters
├── requirements.txt
├── .env.example
├── manage.py
└── postman/
    └── Hospital_Management_API.postman_collection.json
```

**API versioning:** prefix all routes with `/api/v1/`.

---

## 3. Database Design

### 3.1 Entity summary

| Model | Key fields | Belongs to |
|---|---|---|
| `User` (custom) | `email`(unique, USERNAME_FIELD), `role`, `headquarters` (FK, nullable), `sub_headquarters` (FK, nullable), `phone`, `created_by` (self FK), `is_active`, timestamps | — |
| `Headquarters` | `name`(unique), `code`(unique), `address`, `city`, `state`, `is_active`, `created_by` (FK User), timestamps | Super Admin |
| `SubHeadquarters` | `headquarters` (FK), `name`, `code`, `address`, `is_active`, `created_by` (FK User), timestamps | Headquarters |
| `Doctor` | `name`, `specialization`, `phone`, `email`, `clinic_name`, `address`, `headquarters` (FK, nullable), `sub_headquarters` (FK, nullable), `assigned_mr` (FK User, role=MR, nullable), `is_active`, `created_by`, timestamps | Headquarters **or** SubHeadquarters (exactly one) |
| `Visit` | `doctor` (FK), `mr` (FK User), `visit_date`, `status` (`PENDING`/`COMPLETED`/`CANCELLED`), `check_in_time`, `remarks`, `purpose`, timestamps | Doctor + MR |

**Design decision:** "Visit Management" and "daily reports" are modeled as a **single `Visit`
entity** — an MR "marks a visit" by transitioning `status` and filling `check_in_time`, and
"submits a daily report" by filling `remarks`/`purpose` on that same record. The Reports module
is a read/filter layer over `Visit`, not a separate table. *Alternative:* if a stricter reading is
needed, split into `Visit` (schedule/status) + `DailyReport` (1:1 or 1:many narrative log) — flagged
here so it's a conscious choice, not an oversight.

### 3.2 Role hierarchy → data ownership

```
Super Admin        → all Headquarters (global)
HQ Admin            → one Headquarters (own HQ + its Sub HQs)
HQ Staff            → one Headquarters (own HQ only, no Sub HQ)
Sub HQ Staff        → one SubHeadquarters
Medical Rep (MR)    → attached to either a Headquarters OR a SubHeadquarters,
                        scoped further to only their assigned Doctors/Visits
```

`User.headquarters` and `User.sub_headquarters` are both nullable FKs; validation ensures the
correct one is set per role (e.g. `HQ_ADMIN`/`HQ_STAFF` require `headquarters`, `SUB_HQ_STAFF`
requires `sub_headquarters`, `MR` requires exactly one of the two).

### 3.3 Indexes / constraints

- `User.role`, `User.headquarters_id`, `User.sub_headquarters_id` — indexed (used in every scoped query).
- `Doctor.headquarters_id`, `Doctor.sub_headquarters_id`, `Doctor.assigned_mr_id` — indexed.
- `Visit.visit_date`, `Visit.status` — composite index `(visit_date, status)` for dashboard "today's/completed/pending" counts.
- `Visit.mr_id` — indexed (MR's own visit list is the most frequent query).
- `SubHeadquarters`: `unique_together (headquarters, code)`.
- `Doctor`: DB-level `CheckConstraint` or model `clean()` enforcing exactly one of `headquarters`/`sub_headquarters`.

---

## 4. Role-Based Access Control Matrix

| Module | Super Admin | HQ Admin | HQ Staff | Sub HQ Staff | MR |
|---|---|---|---|---|---|
| Headquarters | Full CRUD (all) | Read own | Read own | — | — |
| Sub Headquarters | Full CRUD (all) | Full CRUD (own HQ) | Read (own HQ) | Read own | — |
| User management | Full CRUD (all) | Create/manage HQ Staff, Sub HQ Staff, MR under own HQ | — | — | — |
| Doctors | Full CRUD (all) | Full CRUD (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Read own assigned only |
| Visits | Full CRUD (all) | Read/manage (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Create/update own only (mark visit, submit report) |
| Dashboard | Global counts | HQ-scoped counts | HQ-scoped counts | Sub HQ-scoped counts | Self-scoped (optional) |
| Reports | All, any filter | Filtered to own HQ | Filtered to own HQ | Filtered to own Sub HQ | Filtered to self |

Enforcement happens in two layers, both required:
1. **Permission classes** (`common/permissions.py`) gate which actions a role may attempt.
2. **Queryset scoping** in each ViewSet's `get_queryset()` restricts *which rows* are visible/editable — this is what actually prevents an HQ Admin from reading another HQ's data even if they guess an ID.

---

## 5. API Endpoint Map

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/v1/auth/login/` | Returns access + refresh JWT |
| POST | `/api/v1/auth/refresh/` | Refresh access token |
| POST | `/api/v1/auth/logout/` | Blacklists refresh token |
| GET | `/api/v1/auth/me/` | Current user profile + role + scope |
| GET/POST | `/api/v1/users/` | Scoped user management (create staff/MR under hierarchy) |
| GET/PUT/PATCH/DELETE | `/api/v1/users/{id}/` | |
| GET/POST | `/api/v1/headquarters/` | search, pagination, ordering |
| GET/PUT/PATCH/DELETE | `/api/v1/headquarters/{id}/` | |
| GET/POST | `/api/v1/sub-headquarters/` | filter by `?headquarters=` |
| GET/PUT/PATCH/DELETE | `/api/v1/sub-headquarters/{id}/` | |
| GET/POST | `/api/v1/doctors/` | filter by `?headquarters=&sub_headquarters=&assigned_mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/doctors/{id}/` | |
| GET/POST | `/api/v1/visits/` | filter by `?status=&date=&doctor=&mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/visits/{id}/` | |
| POST | `/api/v1/visits/{id}/mark-visit/` | MR action: sets `COMPLETED` + `check_in_time` |
| GET | `/api/v1/dashboard/summary/` | role-scoped counts (7 metrics from PDF) |
| GET | `/api/v1/reports/visits/` | `?start_date=&end_date=&headquarters=&sub_headquarters=&mr=&doctor=&status=&search=&ordering=&page=` |

All list endpoints share: `?search=`, `?ordering=`, `?page=`/`?page_size=` via a common pagination + filter backend config in `common/`.

---

## 6. Phase-Wise Roadmap

### Phase 0 — Project Initiation & Environment Setup
**Goal:** repo, environment, and skeleton exist and run.

- Backend tasks: `git init`, create GitHub repo, Python 3.12 venv, install Django/DRF/psycopg2/simplejwt/django-filter, `django-admin startproject config .`, create the 6 apps listed in §2, configure `settings/base.py`, `dev.py`, `prod.py` split, PostgreSQL via `docker-compose.yml` + `.env`, wire `django-environ`.
- API dev requirements: none yet — confirm `/admin/` and a health-check route load.
- Client/Postman tasks: create empty Postman collection + environment (base_url, token vars).
- Testing: verify `manage.py runserver` boots, DB connects.
- Deployment activities: none yet (local only). PostgreSQL runs via `docker compose up -d` (see `docker-compose.yml`); Django itself still runs on the host, pointed at the container via `POSTGRES_HOST=localhost`.
- Dependencies: none (starting point).
- **Milestone/deliverable:** PostgreSQL container running via Docker Compose (done — see `docker-compose.yml`, `.env`, `.env.example`); runnable empty Django project connected to it, committed as first commit, `requirements.txt` finalized.

> **Status:** Docker Compose + PostgreSQL 15 container (`hospital_api_db`) is set up and verified healthy. Remaining Phase 0 work: Django project/app scaffolding, `requirements.txt`, `git init`.

### Phase 1 — Domain Modeling & Database Design
**Goal:** all data models exist and match §3.

- Backend tasks: custom `User` model (`AUTH_USER_MODEL`) with `role` choices + hierarchy FKs; `Headquarters`, `SubHeadquarters`, `Doctor`, `Visit` models; model-level validation (`clean()`/constraints) for role↔scope consistency and Doctor's single-parent rule; register all in Django admin for manual inspection; initial migrations; management command to seed one Super Admin.
- API dev requirements: none (no endpoints yet), but serializers' field lists can be stubbed.
- Client/Postman tasks: none yet.
- Testing: model-level unit tests (constraint violations rejected, `str()` methods, FK cascade behavior on delete).
- Deployment activities: none.
- Dependencies: requires Phase 0 environment.
- **Milestone/deliverable:** `python manage.py migrate` runs clean; Django admin shows all 5 models with correct relationships; a seeded Super Admin can log into `/admin/`.

> **Status:** Done. Custom `accounts.User` (email login, role choices, hierarchy FKs) plus `Headquarters`,
> `SubHeadquarters`, `Doctor`, `Visit` models are implemented with `clean()`/`CheckConstraint` validation,
> registered in Django admin, and migrated cleanly (Django auto-split the accounts↔organizations circular
> FK across two migrations). `manage.py seed_superadmin` seeds/updates a Super Admin. 25 model-level tests
> pass (`python manage.py test accounts organizations doctors visits`).

### Phase 2 — Authentication & RBAC Framework
**Goal:** JWT login works; permission/scoping framework is reusable across all future modules.

- Backend tasks: wire `djangorestframework-simplejwt` (`TokenObtainPairView`, `TokenRefreshView`, blacklist app for logout), `/auth/me/` endpoint, build `common/permissions.py` (role-check permission classes: `IsSuperAdmin`, `IsHQAdminOrAbove`, etc.), build a reusable `HierarchyScopedQuerysetMixin` in `common/mixins.py` that filters any queryset by `request.user.role/headquarters/sub_headquarters`.
- API dev requirements: `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/`, `GET /auth/me/`.
- Client/Postman tasks: add auth requests to Postman with a test script that auto-saves `access_token` into the environment for reuse by later requests.
- Testing: login success/failure, token refresh, expired/blacklisted token rejection, `/auth/me/` returns correct role/scope per seeded user of each role.
- Deployment activities: none.
- Dependencies: requires Phase 1 `User` model.
- **Milestone/deliverable:** All 5 role types (seeded via management command/fixtures) can authenticate and retrieve their own profile; permission/scoping utilities are ready for reuse.

> **Status:** Done (backend + testing). `djangorestframework-simplejwt` wired for
> `POST /api/v1/auth/login/` (custom `CustomTokenObtainPairSerializer` embeds
> `role`/`headquarters_id`/`sub_headquarters_id` claims), `POST /api/v1/auth/refresh/`,
> `POST /api/v1/auth/logout/` (blacklists the refresh token via `token_blacklist`),
> and `GET /api/v1/auth/me/`. `common/permissions.py` provides `IsSuperAdmin`,
> `IsHQAdmin`, `IsHQStaff`, `IsSubHQStaff`, `IsMR`, `IsHQAdminOrAbove`,
> `IsHQStaffOrAbove`, `IsSubHQStaffOrAbove`. `common/mixins.py` provides
> `HierarchyScopedQuerysetMixin` (configurable `hq_lookup_field`/`sub_hq_lookup_field`,
> ready to apply starting Phase 3). 8 new tests cover login success/failure,
> inactive-user rejection, token refresh, expired-token rejection, refresh-token
> blacklisting on logout, and per-role `/auth/me/` scope (33/33 tests passing).
> **Remaining:** Postman collection requests for the auth flow (per plan, built
> incrementally / exported at Phase 8); `/api/v1/users/` user-management CRUD was
> intentionally deferred to a later phase, not part of this pass.

### Phase 3 — Organizational Hierarchy CRUD (Headquarters & Sub Headquarters)
**Goal:** first real business CRUD, and the pattern every later module repeats.

- Backend tasks: `Headquarters`/`SubHeadquarters` serializers + ModelViewSets, apply RBAC matrix (§4) via permission classes + `get_queryset()` scoping, wire `django-filter` + `SearchFilter` + `OrderingFilter` + pagination (this becomes the template for Phases 4–5).
- API dev requirements: full CRUD endpoints per §5 for both resources, with `search`/`ordering`/`page` support.
- Client/Postman tasks: add Headquarters + Sub Headquarters CRUD requests to Postman for each role (to demonstrate 403s where expected).
- Testing: CRUD happy-path per role; negative tests (HQ Admin cannot see/edit another HQ; HQ Staff cannot create a new HQ).
- Deployment activities: none.
- Dependencies: requires Phase 2 (auth + scoping mixin) and Phase 1 models.
- **Milestone/deliverable:** Super Admin can manage all HQs/Sub HQs; HQ Admin correctly restricted to their own; search/pagination/sorting demonstrably working on these endpoints.

> **Status:** Done. `HeadquartersViewSet`/`SubHeadquartersViewSet` (`organizations/views.py`) implement full
> CRUD with explicit `get_queryset()` scoping per role, gated by `HeadquartersPermission`/
> `SubHeadquartersPermission` (`organizations/permissions.py`), built on a new reusable
> `RoleBasedCRUDPermission` base added to `common/permissions.py`. `SubHeadquartersSerializer` blocks
> an HQ Admin from creating/reassigning a Sub HQ outside their own HQ. Routes wired at
> `/api/v1/headquarters/` and `/api/v1/sub-headquarters/` via `organizations/urls.py`. Along the way,
> found and fixed a real gap: `?page_size=` wasn't wired up (`DEFAULT_PAGINATION_CLASS` had no
> `page_size_query_param`) — added `common/pagination.py` (`StandardPagination`) to fix it. 24 new API
> tests added (full CRUD + RBAC matrix per role, cross-HQ negative access, search/ordering/pagination);
> full suite is 59/59 passing (`python manage.py test`).

### Phase 4 — Doctor Management
**Goal:** doctors CRUD, correctly scoped and assignable to MRs.

- Backend tasks: `Doctor` serializer + ViewSet reusing the Phase 3 pattern, enforce single-parent (HQ *or* Sub HQ) validation in serializer, support assigning/reassigning `assigned_mr` (must belong to same HQ/Sub HQ scope), filter by `headquarters`/`sub_headquarters`/`assigned_mr`.
- API dev requirements: full CRUD per §5 with filters; validation errors return clear 400s for scope mismatches.
- Client/Postman tasks: Doctor CRUD requests per role, including an MR request proving read-only access to only their assigned doctors.
- Testing: creation validation (rejects doctor with both/neither HQ and Sub HQ set), assignment scope validation, MR read-only enforcement.
- Deployment activities: none.
- Dependencies: requires Phase 3 (Headquarters/SubHeadquarters must exist to attach doctors to).
- **Milestone/deliverable:** Doctors can be created/assigned at the correct hierarchy level; MR sees only their assigned subset.

> **Status:** Done. `DoctorSerializer` (`doctors/serializers.py`) enforces the single-parent rule
> (exactly one of `headquarters`/`sub_headquarters`) and per-role scope at create/update time (HQ Admin
> limited to own HQ — directly or via its Sub HQs; HQ Staff limited to own HQ directly; Sub HQ Staff
> limited to own Sub HQ), plus `assigned_mr` validation (must have role `MR`, and must belong to the
> same Headquarters/Sub Headquarters as the Doctor). `DoctorViewSet` (`doctors/views.py`) reuses
> `HierarchyScopedQuerysetMixin` from Phase 2/3 for queryset scoping, overriding `scope_queryset_to_mr`
> so an MR only ever sees their own assigned Doctors (not the whole HQ/Sub HQ, per §4) — the one
> deviation from the mixin's default MR scoping, called out in its docstring. Gated by
> `DoctorPermission` (`doctors/permissions.py`, built on `RoleBasedCRUDPermission`): all five roles can
> read (queryset scoping narrows what each sees), MR is read-only. Routes wired at `/api/v1/doctors/`
> via `doctors/urls.py`. 26 new API tests added (list/retrieve scoping per role, search/filter/ordering,
> create/update/delete happy-path and cross-scope negative tests, `assigned_mr` role/scope validation);
> full suite is 85/85 passing (`python manage.py test`).

### Phase 5 — Visit Management & Daily Reporting
**Goal:** MRs can mark visits and submit reports; staff/admin roles can review them.

- Backend tasks: `Visit` serializer + ViewSet, `status` transition logic (`PENDING → COMPLETED`/`CANCELLED`), `mark-visit` custom action for MRs, scoping so MR only ever sees/edits their own visits, HQ/Sub HQ staff see all visits within their scope.
- API dev requirements: CRUD + `POST /visits/{id}/mark-visit/`, filters by `status`/`date`/`doctor`/`mr`.
- Client/Postman tasks: Postman requests simulating an MR's daily flow (create visit → mark complete → view own report history).
- Testing: status transition rules enforced (e.g. can't "complete" an already-cancelled visit), scoping tests per role, date-based queries return correct rows.
- Deployment activities: none.
- Dependencies: requires Phase 4 (Doctor) and Phase 2 (MR identity/scoping).
- **Milestone/deliverable:** End-to-end visit lifecycle works for an MR; HQ/Sub HQ staff can view/manage visits within their scope.

> **Status:** Done. `VisitSerializer` (`visits/serializers.py`) forces `mr` to the requesting
> user for MR-role creates/updates (ignoring any client-supplied `mr`), validates a doctor is
> the MR's own assigned doctor, and for HQ Admin/HQ Staff/Sub HQ Staff validates the supplied
> `mr`/`doctor` pair are role-consistent and within the caller's HQ/Sub HQ scope (mirroring the
> Doctor `assigned_mr` pattern from Phase 4). Status-transition rules are enforced via
> `validate_status`: once a visit is `COMPLETED`/`CANCELLED` it is terminal (no further status
> changes), and a direct PATCH cannot jump `PENDING` → `COMPLETED` — that must go through
> `POST /api/v1/visits/{id}/mark-visit/`, which sets `status=COMPLETED` and stamps
> `check_in_time`, optionally updating `remarks`/`purpose` in the same call (the "submit a daily
> report" step per §3.2's design decision). `VisitViewSet` (`visits/views.py`) reuses
> `HierarchyScopedQuerysetMixin` with `hq_lookup_field='doctor__headquarters'` /
> `sub_hq_lookup_field='doctor__sub_headquarters'`, overriding `scope_queryset_to_mr` so an MR
> only ever sees their own Visits (not the whole HQ/Sub HQ). Filtering uses a small
> `VisitFilterSet` exposing `?date=` (aliased to `visit_date`) alongside `?status=&doctor=&mr=`
> per §5. `VisitPermission` (`visits/permissions.py`) branches on `view.action` (not just HTTP
> method) so HQ Admin gets read + update/mark-visit but not create/delete — the one role whose
> access is "manage" rather than "full CRUD" per §4 — while Super Admin/HQ Staff/Sub HQ Staff get
> full CRUD within scope and MR gets create/update (never delete) restricted to their own rows.
> Routes wired at `/api/v1/visits/` via `visits/urls.py`. 31 new API tests added (list/retrieve
> scoping per role, filter/search/ordering, create/update/delete RBAC incl. MR `mr`-field
> spoofing rejected, and the full status-transition matrix incl. mark-visit); full suite is
> 116/116 passing (`python manage.py test`).

### Phase 6 — Dashboard APIs & Reports with Filters
**Goal:** aggregate/reporting layer on top of all prior data.

- Backend tasks: `dashboard` app with a single `summary` view computing the 7 metrics (Total HQs, Total Sub HQs, Total Doctors, Total MRs, Today's Visits, Completed Visits, Pending Visits) scoped per requesting role using `annotate`/`aggregate`; `reports` app exposing a filtered/paginated/sortable Visit report endpoint (`start_date`/`end_date`/`headquarters`/`sub_headquarters`/`mr`/`doctor`/`status`).
- API dev requirements: `GET /dashboard/summary/`, `GET /reports/visits/` per §5.
- Client/Postman tasks: Postman requests per role showing scoped dashboard numbers differ correctly (e.g. HQ Admin's totals ≠ Super Admin's), and report filter combinations.
- Testing: dashboard counts verified against known seeded data per role scope; report filter combinations return expected row counts; pagination/sorting correctness on large filtered sets.
- Deployment activities: none.
- Dependencies: requires Phases 3–5 (needs real HQ/Sub HQ/Doctor/Visit data to aggregate over).
- **Milestone/deliverable:** All 7 dashboard metrics correct and role-scoped; reports endpoint supports every filter combination from the PDF plus search/pagination/sorting.

### Phase 7 — Testing & Quality Assurance
**Goal:** confidence the whole system is correct, not just each part in isolation.

- Backend tasks: consolidate `factory_boy` factories for all 5 roles + full hierarchy fixture set; write cross-module integration tests (e.g., full lifecycle: Super Admin creates HQ → HQ Admin creates Sub HQ + Doctor → MR marks visit → dashboard reflects it).
- API dev requirements: none new — this phase verifies existing endpoints.
- Client/Postman tasks: run the full Postman collection with the Postman/Newman CLI as a smoke test; export the final collection + environment.
- Testing: full permission matrix test sweep (every role × every module × every verb), edge cases (expired tokens, invalid filters, empty results, pagination boundaries), coverage report.
- Deployment activities: add a GitHub Actions workflow running `pytest`/`manage.py test` on push (optional but cheap).
- Dependencies: requires all of Phases 2–6 complete.
- **Milestone/deliverable:** Green test suite with the full RBAC matrix covered; Postman collection runs clean end-to-end via Newman.

> **Status:** Done (Postman/Newman deferred to Phase 8 — no collection exists yet, see that phase's
> deliverable). Before writing new tests, found and fixed a real problem: the existing 138-test suite
> took 40+ minutes to run because Django's default PBKDF2 password hasher (measured at ~0.9s/call on
> this machine) was hashing real passwords for every `setUp()`-created fixture user. Added
> `config/settings/test.py` (extends `dev.py`) setting `PASSWORD_HASHERS` to the fast MD5 hasher for
> tests only — full suite now runs in ~8–10s. All test/CI commands use
> `--settings=config.settings.test` from here on. Added `factory_boy`/`coverage` to `requirements.txt`
> and built shared `common/factories.py` (`HeadquartersFactory`, `SubHeadquartersFactory`, per-role
> `UserFactory` subclasses that go through `create_user`/`create_superuser` so password hashing and
> `User.clean()` scope validation both run, `DoctorFactory`, `VisitFactory`) — used only by the three
> new Phase 7 test modules below; existing per-app `tests.py` files keep their own hand-rolled fixtures
> unchanged (already passing, no reason to churn them). Added a new top-level `tests/` package:
> `tests/test_integration.py` (one full lifecycle end-to-end through the real API: Super Admin creates
> an HQ → HQ Admin creates a Sub HQ + Doctor → MR creates and marks a Visit complete → dashboard and
> reports reflect it at every hierarchy level), `tests/test_permission_matrix.py` (22 tests,
> table-driven sweep of all 5 roles × 6 resources × list/retrieve/create/update/delete against the §4
> RBAC matrix — verified directly against each resource's permission class), and
> `tests/test_edge_cases.py` (14 tests: invalid filter values correctly 400 rather than 500 or a silent
> empty result, empty search/filter results return 200 with `count: 0`, pagination past the last page
> 404s and `page_size` is clamped/tolerant of bad input, expired/malformed/missing JWTs 401 on
> dashboard/reports/doctors/visits). Full suite is now 175/175 passing
> (`python manage.py test --settings=config.settings.test`) with 97% statement coverage
> (`.coveragerc` excludes migrations/config/admin/apps boilerplate; see `coverage report -m`). Added
> `.github/workflows/tests.yml`: Postgres 15 service container, install `requirements.txt`, migrate and
> run the suite with coverage on every push/PR (not yet pushed/triggered — added locally only).

### Phase 8 — Documentation, Packaging & Deployment
**Goal:** the actual deliverables list from the PDF, finalized.

- Backend tasks: finalize `requirements.txt` (pinned versions), finalize `.env.example` (every required env var, no real secrets), write `README.md` (setup steps, architecture overview, hierarchy/permission explanation, how to run migrations/seed data/tests, API summary table), tag a release/clean commit history.
- API dev requirements: none new — freeze and document what exists.
- Client/Postman tasks: final Postman collection export placed in repo (`postman/`), with a short usage note in the README on how to import it and which environment variables it expects.
- Testing: fresh-clone smoke test — clone the repo into a clean folder, follow only the README, confirm it runs.
- Deployment activities: (optional/stretch, see Phase 9) — if deploying, provision PostgreSQL + web service, set env vars, run migrations, `collectstatic`, start Gunicorn behind the platform's proxy.
- Dependencies: requires Phase 7 passing tests.
- **Milestone/deliverable:** All 5 PDF deliverables exist in the repo (GitHub repo, README, requirements.txt, .env.example, Postman Collection) and a clean clone can be set up from the README alone.

### Phase 9 — Production Hardening & CI/CD *(stretch, beyond PDF scope)*
**Goal:** optional polish if time allows beyond the assessment's minimum bar.

- Backend tasks: structured logging, request throttling (`DEFAULT_THROTTLE_RATES`), `django-cors-headers` if a real frontend will consume this later, health-check endpoint, add the Django app itself to `docker-compose.yml` (Postgres is already containerized as of Phase 0) for a full one-command spin-up.
- Deployment activities: GitHub Actions CI (lint + test on every PR) → CD to chosen platform on merge to `main`; Sentry or similar error tracking (optional).
- Testing: load-test the dashboard/report endpoints if dataset size is a concern; verify migrations are reversible.
- Dependencies: requires Phase 8.
- **Milestone/deliverable:** One-command local spin-up via Docker Compose; CI gate on `main`.

---

## 7. Phase Dependency Chain

```
Phase 0 (env/repo)
   ↓
Phase 1 (models)
   ↓
Phase 2 (auth + RBAC framework)  ← everything below depends on this
   ↓
Phase 3 (HQ / Sub HQ CRUD)
   ↓
Phase 4 (Doctor CRUD)  — needs Phase 3's HQ/Sub HQ to attach to
   ↓
Phase 5 (Visit Management)  — needs Phase 4's Doctors + Phase 2's MR identity
   ↓
Phase 6 (Dashboard & Reports)  — needs real data from Phases 3–5
   ↓
Phase 7 (Testing)  — needs all endpoints to exist
   ↓
Phase 8 (Docs & Deliverables)  — needs Phase 7 passing
   ↓
Phase 9 (Hardening/CI/CD, optional)
```

Phases 3–5 are each internally reusable templates (serializer → viewset → permission → filter), so
once Phase 3 establishes the pattern, Phases 4–5 are largely mechanical repetition with different
scoping rules.

---

## Appendix A — Dashboard Metric Definitions (for Phase 6 implementation clarity)

| Metric | Definition | Scoping |
|---|---|---|
| Total HQs | `Headquarters.objects.count()` | Super Admin only sees full count; other roles see 1 or 0 |
| Total Sub HQs | `SubHeadquarters.objects.count()` | scoped to own HQ for HQ Admin/Staff |
| Total Doctors | `Doctor.objects.count()` | scoped per role per §4 |
| Total MRs | `User.objects.filter(role=MR).count()` | scoped per role |
| Today's Visits | `Visit.objects.filter(visit_date=today).count()` | scoped |
| Completed Visits | `Visit.objects.filter(status=COMPLETED)` (optionally date-ranged) | scoped |
| Pending Visits | `Visit.objects.filter(status=PENDING)` (optionally date-ranged) | scoped |

## Appendix B — 3-Hour Fast-Track Sequence (if used as a timed assessment submission)

If this is being submitted under the original 3-hour constraint, compress the above into this order,
skipping anything marked *stretch*:

1. **0:00–0:20** — Phase 0 + Phase 1 (project skeleton, all models, one migration, admin registration).
2. **0:20–0:50** — Phase 2 (JWT login/refresh/me, permission classes, scoping mixin).
3. **0:50–1:30** — Phase 3 + Phase 4 (HQ, Sub HQ, Doctor CRUD — copy-paste the same viewset pattern 3x).
4. **1:30–2:00** — Phase 5 (Visit CRUD + mark-visit action).
5. **2:00–2:30** — Phase 6 (dashboard summary + filtered reports endpoint).
6. **2:30–2:50** — Phase 8 only (README, requirements.txt, .env.example, quick Postman export) — skip Phase 7's full test sweep, keep only a handful of smoke tests if time remains.
7. **2:50–3:00** — final commit, push, sanity-check a clean clone.

Skip Phase 9 entirely under the 3-hour constraint.
