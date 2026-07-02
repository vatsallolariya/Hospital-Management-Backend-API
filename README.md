# Hospital Management Backend API

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.17-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)

A Django REST Framework backend for managing a hierarchical hospital network —
**Headquarters → Sub Headquarters → Doctors → Medical Reps (MRs)** — and their
daily field **Visits**. It provides JWT authentication, five-level role-based
access control (RBAC), role-scoped dashboard metrics, and filterable reporting.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Architecture](#2-architecture)
   - [2.1 Role Hierarchy](#21-role-hierarchy)
   - [2.2 RBAC Matrix](#22-rbac-matrix)
   - [2.3 Data Setup Workflow](#23-data-setup-workflow)
3. [Getting Started](#3-getting-started)
   - [3.1 Prerequisites](#31-prerequisites)
   - [3.2 Clone & Environment Setup](#32-clone--environment-setup)
   - [3.3 Database (Docker Compose)](#33-database-docker-compose)
   - [3.4 Migrate & Seed](#34-migrate--seed)
   - [3.5 Run the Server](#35-run-the-server)
   - [3.6 Run Tests](#36-run-tests)
4. [Configuration Reference](#4-configuration-reference-env)
5. [API Summary](#5-api-summary)
6. [Postman Collection](#6-postman-collection)

---

## 1. Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.2 |
| API | Django REST Framework 3.17 |
| Auth | `djangorestframework-simplejwt` (access + refresh, blacklist on logout) |
| Database | PostgreSQL 15 (via Docker Compose) |
| Filtering | `django-filter` + DRF `SearchFilter` / `OrderingFilter` |
| Config | `django-environ` |
| Testing | Django `APITestCase`, `factory_boy`, `coverage` |

---

## 2. Architecture

The project is organized as modular Django apps, one per bounded context, with
DRF ViewSets and Routers. RBAC is enforced in two layers everywhere it matters:

1. **Permission classes** — each app's `permissions.py`, built on
   `common/permissions.py`'s `RoleBasedCRUDPermission`, gates which HTTP
   actions a role may attempt.
2. **Queryset scoping** — `common/mixins.py`'s `HierarchyScopedQuerysetMixin`,
   applied per ViewSet, restricts *which rows* are visible or editable. This
   is what stops, for example, an HQ Admin from reading another HQ's data even
   if they guess a valid ID.

```text
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

### 2.1 Role Hierarchy

```text
Super Admin    → all Headquarters (global)
HQ Admin       → one Headquarters (own HQ + its Sub HQs)
HQ Staff       → one Headquarters (own HQ only, no Sub HQ)
Sub HQ Staff   → one Sub Headquarters
Medical Rep    → attached to a Headquarters OR a Sub Headquarters,
                 further scoped to only their assigned Doctors/Visits
```

`User.headquarters` / `User.sub_headquarters` are nullable foreign keys,
validated per role in `accounts/models.py`:

- `HQ_ADMIN` / `HQ_STAFF` require `headquarters`.
- `SUB_HQ_STAFF` requires `sub_headquarters`.
- `MR` requires exactly one of the two.

`Doctor` enforces the same "exactly one parent" rule between `headquarters`
and `sub_headquarters`.

### 2.2 RBAC Matrix

| Module | Super Admin | HQ Admin | HQ Staff | Sub HQ Staff | MR |
|---|---|---|---|---|---|
| Users | Full CRUD (all) | Full CRUD (HQ Staff/Sub HQ Staff/MR, own HQ) | — | — | — |
| Headquarters | Full CRUD (all) | Read own | Read own | — | — |
| Sub Headquarters | Full CRUD (all) | Full CRUD (own HQ) | Read (own HQ) | Read own | — |
| Doctors | Full CRUD (all) | Full CRUD (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Read own assigned only |
| Visits | Full CRUD (all) | Read/manage (own HQ) | Full CRUD (own HQ) | Full CRUD (own Sub HQ) | Create/update own only (mark visit) |
| Dashboard | Global counts | HQ-scoped counts | HQ-scoped counts | Sub HQ-scoped counts | Self-scoped |
| Reports | All, any filter | Filtered to own HQ | Filtered to own HQ | Filtered to own Sub HQ | Filtered to self |

> **Hierarchy inheritance.** Per the spec's "hierarchy-based role permissions",
> a higher role inherits the capabilities of the roles beneath it, scoped to
> its own part of the hierarchy. This is why **HQ Admin** — although the roles
> list names it as managing HQ Staff, Sub HQs and users — also has write access
> to Doctors and Visits within its own HQ: those are capabilities of the HQ
> Staff sitting below it. Row-level access is always constrained to the user's
> own HQ / Sub HQ by the queryset-scoping layer.

### 2.3 Data Setup Workflow

A fresh database contains only the seeded Super Admin. Because every entity
depends on the one above it in the hierarchy, build data **top-down** in this
order (this is also the order the Postman requests are meant to be run in):

| # | Who does it | Create | Why / depends on |
|---|---|---|---|
| 1 | — | **Log in** as Super Admin (`admin@gmail.com`) | Get the access token; nothing works without it |
| 2 | Super Admin | **Headquarters** (e.g. "Mumbai Zone HQ") | The root of the tree; everything hangs off an HQ |
| 3 | Super Admin / HQ Admin | **Sub Headquarters** (optional) | Belongs to an HQ; skip it for a small, single-office setup |
| 4 | Super Admin | **HQ Admin** user | The zone manager who can then run steps 5–8 themselves |
| 5 | Super Admin / HQ Admin | **HQ Staff / Sub HQ Staff** users (optional) | Office-level clerks |
| 6 | Super Admin / HQ Admin | **MR** user | The field rep who logs Visits |
| 7 | Super Admin / HQ / Sub HQ | **Doctor** | The person an MR visits |
| 8 | Super Admin / HQ / Sub HQ | Assign MR to Doctor (`PATCH doctor.assigned_mr`) | Lets that MR create Visits for this Doctor |
| 9 | MR (or any manager) | **Visit**, then **mark-visit** | The actual field activity being tracked |

There is **no "Sub HQ Admin" role** — a Sub Headquarters is managed by the HQ
Admin of its parent Headquarters.

**Location fields per role.** When creating a User, `headquarters` /
`sub_headquarters` are validated per role (`accounts/models.py`,
`accounts/serializers.py`). Sending the wrong combination returns a 400:

| Role | `headquarters` | `sub_headquarters` |
|---|:---:|:---:|
| `SUPER_ADMIN` | omit | omit |
| `HQ_ADMIN` | **required** | omit |
| `HQ_STAFF` | **required** | omit |
| `SUB_HQ_STAFF` | omit | **required** |
| `MR` | exactly **one** of the two | exactly **one** of the two |

`Doctor` follows the same "exactly one of `headquarters` / `sub_headquarters`"
rule. When a non-MR creates a **Visit**, `mr` is required in the body and must
be an MR under the same HQ / Sub HQ as the Doctor; when an MR creates a Visit,
`mr` is set to that MR automatically and the Doctor must be one assigned to them.

---

## 3. Getting Started

### 3.1 Prerequisites

- Python 3.12+
- Docker (for PostgreSQL) — or a local PostgreSQL 15 instance

### 3.2 Clone & Environment Setup

```bash
git clone https://github.com/vatsallolariya/Hospital-Management-Backend-API.git
cd Hospital-Management-Backend-API

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env if you want non-default DB credentials or a custom secret key
```

### 3.3 Database (Docker Compose)

```bash
docker compose up -d
```

This starts a `postgres:15` container (`hospital_api_db`) using the
credentials in `.env`. By default the container's `5432` is published on host
port `5433` (to avoid clashing with a locally installed Postgres) — set
`POSTGRES_PORT=5433` in `.env` accordingly. Django itself runs on the host and
connects via `POSTGRES_HOST=localhost`.

### 3.4 Migrate & Seed

```bash
python manage.py migrate

python manage.py seed_superadmin
# or explicitly:
python manage.py seed_superadmin --email admin@gmail.com --password admin123
```

`seed_superadmin` reads `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` from `.env`
by default, or accepts `--email` / `--password` / `--first-name` /
`--last-name` flags. It's idempotent — re-running it updates the existing
Super Admin rather than erroring.

### 3.5 Run the Server

```bash
python manage.py runserver
```

- API root: `http://localhost:8000/api/v1/`
- Django admin: `http://localhost:8000/admin/`

### 3.6 Run Tests

```bash
python manage.py test --settings=config.settings.test
```

`config/settings/test.py` swaps the password hasher for a fast MD5-based one
so the suite runs in seconds instead of tens of minutes (real hashing is
irrelevant to correctness in tests, and every seeded fixture user would
otherwise pay a real PBKDF2 hash). Always use `--settings=config.settings.test`
for local test runs.

With coverage:

```bash
coverage run manage.py test --settings=config.settings.test --noinput
coverage report -m
```

---

## 4. Configuration Reference (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_DB` | Database name | `hospital_api` |
| `POSTGRES_USER` | Database user | `hospital_api` |
| `POSTGRES_PASSWORD` | Database password | `hospital_api` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5433` |
| `DJANGO_SECRET_KEY` | Django secret key — set a real random value outside local dev | `change-me-in-prod` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `SUPERADMIN_EMAIL` | Used by `seed_superadmin` | `admin@gmail.com` |
| `SUPERADMIN_PASSWORD` | Used by `seed_superadmin` | `admin123` |

`.env.example` mirrors this table with placeholder (non-secret) values — copy
it to `.env` and adjust locally. **Never commit a real `.env`.**

Settings are split by environment:

- `config/settings/dev.py` — `DEBUG=True`, used by `manage.py` locally.
- `config/settings/prod.py` — `DEBUG=False`, enforces HTTPS/secure cookies. Set
  `DJANGO_SETTINGS_MODULE=config.settings.prod` when deploying.
- `config/settings/test.py` — fast password hasher for the test suite.

---

## 5. API Summary

All endpoints require `Authorization: Bearer <access_token>` unless noted.
List endpoints support `?search=`, `?ordering=`, `?page=`, and `?page_size=` in
addition to the filters listed below.

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/v1/auth/login/` | No auth required. Returns `access` + `refresh` JWTs (claims include `role`, `headquarters_id`, `sub_headquarters_id`) |
| POST | `/api/v1/auth/refresh/` | No auth required. Exchanges `refresh` for a new `access` (+ rotated `refresh`) |
| POST | `/api/v1/auth/logout/` | Blacklists the supplied `refresh` token |
| GET | `/api/v1/auth/me/` | Current user's profile, role, and hierarchy scope |
| GET/POST | `/api/v1/users/` | Super Admin or HQ Admin only. Filters: `?role=&headquarters=&sub_headquarters=&is_active=`. HQ Admin can only create/manage `HQ_STAFF` / `SUB_HQ_STAFF` / `MR` under their own Headquarters |
| GET/PUT/PATCH/DELETE | `/api/v1/users/{id}/` | `PATCH {"is_active": false}` deactivates without deleting; `DELETE` is a hard delete (cascades to an MR's Visits, same as Doctor deletion) |
| GET/POST | `/api/v1/headquarters/` | Full CRUD, RBAC-scoped (see [§2.2](#22-rbac-matrix)) |
| GET/PUT/PATCH/DELETE | `/api/v1/headquarters/{id}/` | |
| GET/POST | `/api/v1/sub-headquarters/` | Filter: `?headquarters=` |
| GET/PUT/PATCH/DELETE | `/api/v1/sub-headquarters/{id}/` | |
| GET/POST | `/api/v1/doctors/` | Filters: `?headquarters=&sub_headquarters=&assigned_mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/doctors/{id}/` | |
| GET/POST | `/api/v1/visits/` | Filters: `?status=&date=&doctor=&mr=` |
| GET/PUT/PATCH/DELETE | `/api/v1/visits/{id}/` | |
| POST | `/api/v1/visits/{id}/mark-visit/` | MR action: sets `status=COMPLETED`, stamps `check_in_time`, optionally accepts `remarks` / `purpose` |
| GET | `/api/v1/dashboard/summary/` | Role-scoped counts: `total_headquarters`, `total_sub_headquarters`, `total_doctors`, `total_mrs`, `todays_visits`, `completed_visits`, `pending_visits` |
| GET | `/api/v1/reports/visits/` | Filters: `?start_date=&end_date=&headquarters=&sub_headquarters=&mr=&doctor=&status=` |

---

## 6. Postman Collection

Import both files from [`postman/`](postman/) into Postman:

- `Hospital_Management_API.postman_collection.json` — every endpoint above,
  grouped by module.
- `Hospital_Management_API.postman_environment.json` — defines `base_url`
  (`http://localhost:8000/api/v1`), plus empty `access_token` /
  `refresh_token` variables.

The **Auth → Login** request has a *Tests* script that automatically saves
`access` and `refresh` from the response into the environment, so every other
request (set to use `Bearer {{access_token}}`) works right after logging in.
Log in as different seeded roles and re-run a request to see the RBAC
scoping/403s described in [§2.2](#22-rbac-matrix).
