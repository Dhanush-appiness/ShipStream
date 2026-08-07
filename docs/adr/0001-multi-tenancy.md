# ADR 0001: Shared-Schema Multi-Tenancy with Header-Based Org Context

## Status
Accepted

## Context
ShipStream needs to isolate data between organizations (tenants). Django/DRF
projects commonly choose between three tenancy models:

1. **Database-per-tenant** — each organization gets its own database.
2. **Schema-per-tenant** — each organization gets its own Postgres schema,
   shared database (e.g. `django-tenants`).
3. **Shared-schema, row-level isolation** — every tenant's rows live in the
   same tables, isolated by a foreign key to `Organization`.

We also needed to decide how a request declares which organization it's
acting as, given a user can belong to more than one.

## Decision
We chose **shared-schema, row-level tenancy**. Every tenant-owned model
(`Project`, `Task`, `Label`, `ActivityLog`, `Notification`, `Comment`, ...)
carries a direct or indirect foreign key back to `Organization`.

The active organization for a request is resolved from the **`X-Org-ID`
header**, not a URL prefix or subdomain. Given a user can belong to multiple
organizations (`Membership` is a many-to-many through table between `User`
and `Organization`), a header lets the same JWT be reused across
organizations without re-authenticating, and keeps URLs identical regardless
of which org the client is currently acting as.

Isolation is enforced in two layers, not by remembering `.filter(org=...)`
in every view:

- **Tenant-aware managers/querysets**: `Task`, `Project` (and other models)
  use custom managers (`common/managers.py`) exposing a
  `.for_organization(organization)` queryset method, layered on top of a
  `SoftDeleteQuerySet` that already excludes soft-deleted rows by default.
  Views and services call `Model.objects.for_organization(org)` rather than
  hand-writing the filter each time.
- **`get_request_organization()` (`common/permissions.py`)**: resolves and
  caches the request's active `Organization` from the `X-Org-ID` header,
  cross-checked against `Membership` — a header naming an org the user
  doesn't belong to resolves to `None`, which every permission class then
  rejects.

**Known nuance worth documenting explicitly**: `TenantMiddleware`
(`organizations/middleware.py`) also attempts to resolve
`request.organization`, but for JWT-authenticated API calls this is
effectively a no-op — Django's classic `AuthenticationMiddleware` only
populates `request.user` from session auth, and DRF's `JWTAuthentication`
doesn't run until the view layer wraps the request. So for token-based
requests, the middleware sees `request.user` as anonymous and leaves
`request.organization` as `None`. The tenant boundary that actually matters
for the API is enforced by `get_request_organization()` inside the
permission classes (`HasOrganizationAccess`, `IsOrganizationMemberOrReadOnly`,
`IsOrganizationAdmin`), which run after DRF authentication has populated
`request.user`. The middleware is harmless (session-authenticated requests,
e.g. the Django admin, still benefit from it) but isn't where API isolation
actually happens — that's a fair follow-up question to expect in the
walkthrough.

## Alternatives Considered
- **Schema-per-tenant**: gives stronger isolation and lets you drop a
  tenant's schema wholesale, but migrations must run per-schema, cross-tenant
  reporting queries get harder, and connection pooling is more complex. Not
  justified at this project's scale (a training assignment, not a live
  multi-thousand-tenant SaaS).
- **Database-per-tenant**: strongest isolation, but operationally heavy —
  every new signup provisions a new database, and shared infrastructure
  (Celery, cross-tenant admin tooling) needs a tenant-routing layer. Massive
  overkill here.
- **URL-prefix tenancy** (e.g. `/orgs/<slug>/projects/`): considered instead
  of the header. Rejected because it makes every URL tenant-shaped even
  though the assignment's versioning requirement (`/api/v1/...` with a clean
  path to `/api/v2/...`) already claims the URL path; layering tenant
  identity into the same path adds ambiguity about which prefix means what.
  A header keeps tenant selection orthogonal to versioning and resource
  paths.

## When We'd Reconsider
If a single organization's data volume or compliance requirements (e.g. a
customer demanding physical data isolation, or one tenant's write volume
degrading others') became a problem, schema-per-tenant is the natural next
step — same Postgres instance, `search_path` swap per request, no
application-level tenant filtering needed anymore. Database-per-tenant would
only make sense at a scale where regulatory isolation is non-negotiable per
customer, which is well beyond what shared-schema roll-your-own filtering
can defend.
