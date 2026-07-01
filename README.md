# Hospital Management Backend API

A Django REST Framework backend for managing a hierarchical hospital network:
Headquarters → Sub Headquarters, Doctors, Medical Reps (MRs), and their daily
Visits — with JWT authentication, 5-level role-based access control, dashboard
metrics, and filterable reports.

Built against `Python_DRF_Hospital_Assessment_Task.pdf`. See
[IMPLEMENTATION_PLAN_1.md](IMPLEMENTATION_PLAN_1.md) for the full phase-by-phase
design log this project was built from.

---

## 1. Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.2 |
| API | Django REST Framework 3.17 |
| Auth | `djangorestframework-simplejwt` (access + refresh, blacklist on logout) |
| Database | PostgreSQL 15 (Docker Compose) |
| Filtering | `django-filter` + DRF `SearchFilter` / `OrderingFilter` |
| Config | `django-environ` |
| Testing | Django `APITestCase`, `factory_boy`, `coverage` |
| CI | GitHub Actions (`.github/workflows/tests.yml`) |

---

## 2. Architecture

Modular Django apps, one per bounded context, DRF ViewSets + Routers. RBAC is
enforced in two layers everywhere it matters:

1. **Permission classes** (per-app `permissions.py`, built on
   `common/permissions.py`'s `RoleBasedCRUDPermission`) gate which HTTP
   actions a role may attempt.
2. **Queryset scoping** (`common/mixins.py`'s `HierarchyScopedQuerysetMixin`,
   applied per-ViewSet) restricts *which rows* are visible/editable — this is
   what stops, e.g., an HQ Admin from reading another HQ's data even if they
   guess an ID.

```
config/          settings/{base,dev,prod,test}.py, urls.py, wsgi.py, asgi.py
accounts/        custom User model, JWT auth views (login/refresh/logout/me)
organizations/   Headquarters, SubHeadquarters models + CRUD
doctors/         Doctor model + CRUD
visits/          Visit model, CRUD, status transitions, mark-visit action
dashboard/       role-scoped summary metrics (no models of its own)
reports/         filtered/paginated Visit reporting endpoint
common/          shared permission base classes, pagination, hierarchy mixin, test factories
tests/           cross-module integration, full RBAC matrix, and edge-case tests
postman/         Postman collection + environment
```

All routes are versioned under `/api/v1/`.

### 2.1 Role hierarchy

```
Super Admin    → all Headquarters (global)
HQ Admin       → one Headquarters (own HQ + its Sub HQs)
HQ Staff       → one Headquarters (own HQ only, no Sub HQ)
Sub HQ Staff   → one SubHeadquarters
Medical Rep    → attached to a Headquarters OR a SubHeadquarters,
                 further scoped to only their assigned Doctors/Visits
```

`User.headquarters` / `User.sub_headquarters` are nullable FKs validated per
role in `accounts/models.py` (`HQ_ADMIN`/`HQ_STAFF` require `headquarters`,
`SUB_HQ_STAFF` requires `sub_headquarters`, `MR` requires exactly one of the
two). `Doctor` enforces the same "exactly one parent" rule between
`headquarters` and `sub_headquarters`.

### 2.2 RBAC matrix

| Module | Super Admin | HQ Admin | HQ Staff | Sub HQ Staff | MR |
|---|---|---|---|---|---|
| Headquarters | Full CRUD (all) | Read own | Read own | — | — |
| Sub Headquarters | Full CRUD (all) | Full CRUD (own HQ) | Read (own HQ) | Read own | — |
| Doctors | Full CRUD (all) | Full CRUD (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Read own assigned only |
| Visits | Full CRUD (all) | Read/manage (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Create/update own only (mark visit) |
| Dashboard | Global counts | HQ-scoped counts | HQ-scoped counts | Sub HQ-scoped counts | Self-scoped |
| Reports | All, any filter | Filtered to own HQ | Filtered to own HQ | Filtered to own Sub HQ | Filtered to self |

---

## 3. Setup

### 3.1 Prerequisites

- Python 3.12+
- Docker (for PostgreSQL) — or a local PostgreSQL 15 instance

### 3.2 Clone & environment

```bash
git clone <this-repo-url>
cd Hospital-Management-Backend-API

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env if you want non-default DB credentials / secret key
```

### 3.3 Database (Docker Compose)

```bash
docker compose up -d
```

This starts a `postgres:15` container (`hospital_api_db`) using the
credentials in `.env`. Django itself runs on the host, connecting via
`POSTGRES_HOST=localhost`.

### 3.4 Migrate & seed

```bash
python manage.py migrate

python manage.py seed_superadmin
# or explicitly:
python manage.py seed_superadmin --email admin@hospital.local --password change-me
```

`seed_superadmin` reads `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` from `.env`
by default, or accepts `--email`/`--password`/`--first-name`/`--last-name`
flags. It's idempotent — re-running it updates the existing Super Admin
rather than erroring.

### 3.5 Run

```bash
python manage.py runserver
```

- API root: `http://localhost:8000/api/v1/`
- Django admin: `http://localhost:8000/admin/`

### 3.6 Run tests

```bash
python manage.py test --settings=config.settings.test
```

`config/settings/test.py` swaps the password hasher to a fast MD5-based one
so the suite runs in seconds instead of tens of minutes (real hashing is
irrelevant to correctness in tests, and every seeded fixture user otherwise
pays a real PBKDF2 hash). Always use `--settings=config.settings.test` for
local test runs and CI.

With coverage:

```bash
coverage run manage.py test --settings=config.settings.test --noinput
coverage report -m
```

CI (`.github/workflows/tests.yml`) runs the same commands against a
Postgres 15 service container on every push/PR.

---

## 4. Configuration reference (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_DB` | Database name | `hospital_api` |
| `POSTGRES_USER` | Database user | `hospital_api` |
| `POSTGRES_PASSWORD` | Database password | `hospital_api` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `DJANGO_SECRET_KEY` | Django secret key — set a real random value outside local dev | `change-me-in-prod` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | (empty) |
| `SUPERADMIN_EMAIL` | Used by `seed_superadmin` | `admin@hospital.local` |
| `SUPERADMIN_PASSWORD` | Used by `seed_superadmin` | `change-me` |

`.env.example` mirrors this table with placeholder (non-secret) values — copy
it to `.env` and adjust locally. Never commit a real `.env`.

Settings are split by environment:
- `config/settings/dev.py` — `DEBUG=True`, used by `manage.py` locally.
- `config/settings/prod.py` — `DEBUG=False`, enforces HTTPS/secure cookies. Set
  `DJANGO_SETTINGS_MODULE=config.settings.prod` when deploying.
- `config/settings/test.py` — fast password hasher for the test suite.

---

## 5. API Summary

All endpoints require `Authorization: Bearer <access_token>` unless noted.
List endpoints support `?search=`, `?ordering=`, `?page=`, `?page_size=` in
addition to the filters listed.

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/v1/auth/login/` | No auth required. Returns `access` + `refresh` JWTs (claims include `role`, `headquarters_id`, `sub_headquarters_id`) |
| POST | `/api/v1/auth/refresh/` | No auth required. Exchanges `refresh` for a new `access` (+ rotated `refresh`) |
| POST | `/api/v1/auth/logout/` | Blacklists the supplied `refresh` token |
| GET | `/api/v1/auth/me/` | Current user's profile, role, and hierarchy scope |
| GET/POST | `/api/v1/headquarters/` | Full CRUD, RBAC-scoped (§2.2) |
| GET/PUT/PATCH/DELETE | `/api/v1/headquarters/{id}/` | |
| GET/POST | `/api/v1/sub-headquarters/` | Filter: `?headquarters=` |
| GET/PUT/PATCH/DELETE | `/api/v1/sub-headquarters/{id}/` | |
| GET/POST | `/api/v1/doctors/` | Filters: `?headquarters=&sub_headquarters=&assigned_mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/doctors/{id}/` | |
| GET/POST | `/api/v1/visits/` | Filters: `?status=&date=&doctor=&mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/visits/{id}/` | |
| POST | `/api/v1/visits/{id}/mark-visit/` | MR action: sets `status=COMPLETED`, stamps `check_in_time`, optionally accepts `remarks`/`purpose` |
| GET | `/api/v1/dashboard/summary/` | Role-scoped counts: `total_headquarters`, `total_sub_headquarters`, `total_doctors`, `total_mrs`, `todays_visits`, `completed_visits`, `pending_visits` |
| GET | `/api/v1/reports/visits/` | Filters: `?start_date=&end_date=&headquarters=&sub_headquarters=&mr=&doctor=&status=` |

> **Note:** a `/api/v1/users/` endpoint for scoped user provisioning was scoped
> in the original design (see IMPLEMENTATION_PLAN_1.md §5) but intentionally
> deferred — out of scope for this submission. Users are currently created via
> Django admin or `seed_superadmin`.

---

## 6. Postman Collection

Import both files from [`postman/`](postman/) into Postman:

- `Hospital_Management_API.postman_collection.json` — every endpoint above,
  grouped by module.
- `Hospital_Management_API.postman_environment.json` — defines `base_url`
  (`http://localhost:8000/api/v1`), plus empty `access_token`/`refresh_token`
  variables.

The **Auth → Login** request has a *Tests* script that automatically saves
`access` and `refresh` from the response into the environment, so every other
request (set to use `Bearer {{access_token}}`) works right after logging in.
Log in as different seeded roles and re-run a request to see the RBAC
scoping/403s described in §2.2.

---

## 7. Deployment notes

The app is platform-agnostic (Render / Railway / EC2 + Nginx + Gunicorn, etc).
At minimum:

1. Provision a PostgreSQL 15 instance and set `POSTGRES_*` env vars.
2. Set `DJANGO_SECRET_KEY` to a real random value and `DJANGO_ALLOWED_HOSTS`
   to your domain.
3. Set `DJANGO_SETTINGS_MODULE=config.settings.prod`.
4. Run `python manage.py migrate` and `python manage.py collectstatic`.
5. Seed the initial Super Admin with `python manage.py seed_superadmin`.
6. Start the app with a production WSGI server, e.g.
   `gunicorn config.wsgi:application`.
