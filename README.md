# ShipStream Backend

A multi-tenant project collaboration platform backend built with Django REST
Framework — organizations manage projects, tasks, and team collaboration,
with real-time updates, async background processing, and tenant-isolated
data at every layer.

Built for the ShipStream Backend Assignment. This README covers setup,
architecture, and the design decisions worth defending in a walkthrough; see
[`docs/adr/`](docs/adr/) for the three ADRs going deeper on tenancy, the
service-layer approach, and the real-time architecture.

---

## Tech Stack

- Python 3.13
- Django 6.0
- Django REST Framework
- PostgreSQL 16
- Redis 7
- Celery + Celery Beat
- Django Channels (WebSockets, Redis channel layer)
- SimpleJWT
- drf-spectacular (OpenAPI)
- Docker / Docker Compose
- pytest + pytest-django + factory_boy

---

## Running the Project

### With Docker (recommended — works from a clean machine with only Docker installed)

```bash
git clone https://github.com/Dhanush-appiness/ShipStream.git
cd ShipStream
cp .env.example .env   # adjust values if needed, defaults work for local dev
docker compose up --build
```

`docker compose up` starts Postgres, Redis, the Django app, a Celery worker,
and Celery Beat, and the `django` service automatically runs
`python manage.py migrate` followed by `python manage.py seed_demo_data`
before serving — no manual migration or seeding step required.

The API is then available at `http://localhost:8000/`.

### Without Docker

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
cp .env.example .env           # point DB_HOST/REDIS_HOST at localhost instead of container names

python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

You'll also need Postgres and Redis running locally (or point `.env` at
existing instances), and separate terminals for the Celery worker and beat
scheduler if you want async/scheduled jobs to actually run:

```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

### Seed Data

`python manage.py seed_demo_data` creates 2 organizations, 5 users with
mixed roles (including one user belonging to both organizations, to exercise
multi-tenancy), 3 projects, 9 tasks across all 4 statuses, labels, and a
comment with an `@mention` that triggers a notification. All seeded users
share the password `password123` — this is demo-only data, not meant to
resemble real credentials. Pass `--flush` to wipe and reseed.

### Running Tests

```bash
pytest
```

Tests use a separate `config.settings.test` module (LocMemCache instead of
Redis, eager Celery execution, in-memory Channels layer) so the suite
doesn't require Redis to be running.

---

## Architecture Overview

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` model (email login, no username), JWT auth (register/login/logout/token-blacklist), password reset |
| `organizations` | `Organization` (tenant), `Membership` (role-scoped org membership), `Invitation`, the `X-Org-ID` tenant middleware |
| `projects` | `Project`, `ProjectMember`, CSV `ExportJob` + async generation |
| `tasks` | `Task`, `Comment`, `Label`, `ActivityLog`, `Notification`, task filtering/search/dashboard, the project-scoped WebSocket consumer |
| `common` | cross-cutting infrastructure: tenant-aware querysets/managers (`managers.py`), permission classes (`permissions.py`), the custom exception handler, JWT WebSocket auth middleware (`ws_auth.py`), the `seed_demo_data` management command |
| `config` | settings (split into `base` / `dev` / `prod` / `test`), URL routing, Celery app + beat schedule, ASGI/Channels routing |

**Request flow for an authenticated API call**: JWT is validated by DRF's
`JWTAuthentication` → the relevant permission class
(`HasOrganizationAccess`, `IsOrganizationMemberOrReadOnly`, or
`IsOrganizationAdmin`) calls `get_request_organization()`
(`common/permissions.py`) to resolve the `X-Org-ID` header against the
user's `Membership` rows → the view calls a service-layer method
(`tasks/services.py`, `projects/services.py`, etc.) with the resolved
organization → the service queries through a tenant-scoped manager
(`Model.objects.for_organization(org)`) and performs whatever mutation +
side effects (activity log, notification, cache invalidation, WebSocket
broadcast) are needed, all in one explicit call chain.

See [ADR 0001](docs/adr/0001-multi-tenancy.md) for why shared-schema
tenancy was chosen over schema-per-tenant or database-per-tenant, and for an
honest note on where `TenantMiddleware` does *not* do the enforcement work
for JWT-authenticated requests (that happens in the permission classes).

See [ADR 0002](docs/adr/0002-service-layer.md) for why business logic lives
in a service layer rather than signals or fat models — this project uses
**zero** Django signals.

See [ADR 0003](docs/adr/0003-realtime-architecture.md) for the WebSocket
architecture: project-scoped groups (`project_<id>`), JWT authentication on
connect, and per-project authorization against `Membership`.

---

## Async & Scheduled Work (Celery)

- **Broker**: Redis (`CELERY_BROKER_URL`).
- **Mention notification emails**: dispatched from
  `CommentService.create_comment()` when an `@email` mention resolves to a
  member of the active organization.
- **Weekly digest** (`send_all_weekly_digests`, scheduled via Celery Beat
  every Monday 09:00 UTC): fans out one `send_weekly_digest(org_id)` task
  per active organization, which itself sends **one email per member**
  containing *that member's own* open/overdue task counts — not an
  org-wide count blasted to everyone.
- **CSV export**: `POST /api/v1/projects/exports/` returns **202 Accepted**
  with a job id immediately; `generate_export` runs in Celery, writes every
  task belonging to the project to a CSV, and marks the job `Completed`
  with a `file_url` pointing at `GET /api/v1/projects/exports/<id>/download/`.
  Poll `GET /api/v1/projects/exports/<id>/` for status; the download
  endpoint returns 409 until the job is actually complete.

### Idempotency & Retry Strategy

All Celery tasks in this project are configured with retry + backoff
(`max_retries=3`, either explicit `self.retry(countdown=60)` or
`autoretry_for` with `retry_kwargs`), and idempotency is handled per-task
based on what "running twice" would otherwise duplicate:

- **`generate_export`**: idempotent via an explicit status check — if the
  `ExportJob` is already `Completed` when the task runs (e.g. a retry after
  a broker redelivery), it returns the existing `file_url` immediately
  instead of regenerating the file.
- **`send_mention_notification_email`**: idempotent via a
  `Notification.email_sent_at` timestamp, set after a successful send and
  checked before sending. A retried/redelivered task for the same
  notification is a no-op if the email already went out.
- **`send_weekly_digest`**: retries on failure like the others, but does
  **not** currently have a duplicate-send guard — a retry after a partial
  failure (e.g. the process crashes after some members' emails have already
  been sent) could re-send the digest to those members. This is an accepted
  trade-off for a non-critical, informational weekly email; guarding it
  properly would need a per-(organization, user, week) send-log table,
  which felt like disproportionate schema for a "some people might get two
  digest emails in a rare crash scenario" risk. Worth raising if asked in
  the walkthrough — the fix is understood, just not implemented.

---

## Caching Strategy

The project dashboard (`GET /api/v1/tasks/dashboard/` —
status counts, overdue count, per-assignee workload, all computed as
database aggregations) is cached in Redis:

- **Key**: `dashboard:org:<organization_id>` — scoped per organization, so
  one tenant's cache churn never evicts another's.
- **TTL**: 300 seconds, as a safety net in case an invalidation path is ever
  missed.
- **Invalidation**: explicit `cache.delete()` calls in
  `TaskService.create_task`, `update_task`, `delete_task`, and
  `reorder_task` — i.e. every path that can change a task's status,
  assignee, or existence invalidates that organization's cached dashboard
  immediately, rather than waiting for the TTL. See
  `tasks/tests.py::test_task_dashboard_cache_invalidates_on_status_change`
  for a test that would fail (stale cached counts) if this invalidation
  were ever removed.

`ProjectListCreateView` also uses a blanket `cache_page(60)` on the project
list endpoint — a coarser, TTL-only cache without explicit invalidation,
which is an acceptable trade-off there since project lists change far less
often than task status.

---

## Database Indexing Decisions

- **`task_project_status_pos_idx`** — composite index on
  `Task(project, status, position)`. This matches the exact access pattern
  of `TaskService.get_tasks()`, which always filters to an organization's
  tasks and orders by `status, position` for kanban-column rendering —
  a composite B-tree index lets Postgres satisfy that filter + sort without
  a separate sort step.
- **`task_due_date_idx`** — plain index on `Task.due_date`, supporting the
  overdue-task filters used by both the dashboard aggregation and the
  weekly digest.
- **`task_search_vector_gin`** — a `GinIndex` on a persisted
  `SearchVectorField` (`Task.search_vector`), kept up to date by an override
  of `Task.save()` rather than computed inline per search request. Free-text
  search (`TaskService.search_tasks`) filters and ranks against this stored
  column directly, which is what lets Postgres actually use the GIN index —
  building the `SearchVector` inline on every query (the original
  implementation) can't benefit from a stored index the same way.

A data migration (`tasks/migrations/0008_backfill_task_search_vector.py`)
backfills `search_vector` for any tasks that existed before the field did.

---

## API Documentation

- Swagger UI: `http://localhost:8000/api/docs/` (also available at
  `/api/schema/swagger-ui/`)
- ReDoc: `http://localhost:8000/api/schema/redoc/`
- Raw OpenAPI schema: `http://localhost:8000/api/schema/`

All endpoints are under `/api/v1/...`, using DRF's `URLPathVersioning`
(`ALLOWED_VERSIONS=['v1']` in settings) so a `/api/v2/` can be added later
without touching existing v1 routes.

---

## Environment Variables

See `.env.example` for the full list. `SECRET_KEY` and all database/Redis
connection details are read from the environment (via `python-dotenv`) —
nothing sensitive is hardcoded in `config/settings/`, and `.env` itself is
git-ignored.

---

## Project Structure

```
accounts/        custom User model, JWT auth, password reset
organizations/    Organization, Membership, Invitation, tenant middleware
projects/        Project, ProjectMember, ExportJob + CSV export task
tasks/           Task, Comment, Label, ActivityLog, Notification, dashboard, WebSocket consumer
common/          tenant-aware managers, permissions, exception handler, ws auth, seed command
config/          settings (base/dev/prod/test), urls, celery app, asgi/routing
docs/adr/        architecture decision records
docker-compose.yml
Dockerfile
manage.py
```

---

## CI

`.github/workflows/django.yml` runs on every push/PR to `main`: installs
dependencies, lints with `ruff check .`, type-checks with `mypy .`, runs
migrations, then runs the actual pytest suite with coverage enforcement
(`pytest --cov=. --cov-fail-under=85`). All three gates — lint, types, and
coverage — are verified clean/passing locally as of this writing (ruff: 0
violations; the CI workflow runs Ruff, mypy, migrations, and the pytest suite
with an 85% minimum coverage requirement). The workflow previously ran
`python manage.py test`, which doesn't properly discover this project's
pytest-style suite (fixtures via `conftest.py`, not `unittest.TestCase`
subclasses) — that's fixed now.

---

## Author

Dhanush J
