# ADR 0002: Service Layer for Business Logic, Not Signals or Fat Models

## Status
Accepted

## Context
Django gives three common places to put business logic that isn't pure CRUD:
model methods ("fat models"), signal receivers (`post_save`, `pre_save`,
etc.), or an explicit service layer of plain functions/classes called from
views. The assignment requires activity logging, notification creation,
mention parsing, and dashboard cache invalidation to happen consistently
whenever tasks are created, updated, deleted, or reordered — and caps signal
usage at one for the whole project, with that one signal requiring
justification.

## Decision
We use an **explicit service layer**: `TaskService`, `CommentService`,
`LabelService`, `ActivityLogService`, `NotificationService`,
`ProjectService`, `ProjectMemberService`, `ExportJobService`, and
`OrganizationService`, one per app in `services.py`. Views stay thin — they
resolve the request's organization, call a service method, and serialize the
result. All multi-step business logic (validate → mutate → log activity →
notify → broadcast → invalidate cache) lives in one service method, in one
place, in explicit order.

For example, `TaskService.update_task()` is a single readable call chain:
apply field changes, save, create a notification if there's an assignee,
write an `ActivityLog` entry, broadcast the change over the project's
WebSocket group, and invalidate that organization's cached dashboard. None
of that is hidden behind an implicit `post_save` hook — reading the service
method tells you everything that happens on a task update, in order.

**We use zero Django signals in this project** — stricter than the
assignment's "at most one" allowance. Every side effect that might tempt a
signal (activity logging, notifications, cache invalidation, search-index
maintenance) is either an explicit call in a service method, or — in two
narrow cases — a small model-level method override:

- `Project.delete()` and `Task.delete()` are overridden to perform a soft
  delete (`is_deleted=True`) instead of an actual `DELETE`.
- `Task.save()` is overridden to refresh the persisted `search_vector`
  column after every save, so full-text search stays correct regardless of
  which code path created or updated the task (service layer, DRF
  serializer, Django admin, or a raw `Task.objects.create()` in a test or
  management command).

These are **not signals**. A signal receiver is invisible from the call
site — you can't tell a `post_save` hook exists just by reading
`task.save()`. A model method override is visible at the class definition
and still runs synchronously and predictably; it's a controlled extension of
what "saving this model" means, not an out-of-band listener. We're
comfortable with this distinction because both overrides are narrow,
idempotent, and about the model's own data (soft-delete bookkeeping,
search-index bookkeeping) rather than cross-model business logic like
notifications or dashboard invalidation — that logic stays in the service
layer where it's easy to trace.

## Alternatives Considered
- **Fat models** (business logic as model methods, e.g.
  `task.mark_updated_and_notify()`): rejected as the primary pattern because
  it couples domain logic to the ORM layer and makes it harder to test
  service behavior without a full model round-trip. We do use small model
  method overrides for the two cases above, but not for cross-cutting
  concerns like notifications or activity logging.
- **Signals** (`post_save` on `Task` triggering activity logs/notifications):
  rejected as the default because they make the control flow implicit —
  anyone reading `TaskService.update_task()` would have no way to know a
  notification gets created unless they also knew a signal receiver existed
  elsewhere in the codebase. Signals also make ordering and error handling
  harder to reason about (a receiver raising mid-save behaves differently
  from an explicit call you can wrap in a `try`/`except`), and make write
  paths that bypass `.save()` (bulk `.update()` calls, which
  `TaskService.reorder_task()` uses for position shifting) silently skip
  the logic entirely — which is exactly the kind of "forgot to add a
  filter" bug class the service-layer approach is trying to avoid across
  the whole system.

## Consequence
Anyone extending this codebase should add new business logic as a service
method, not a signal receiver or a fat model method — with the same two
narrow exceptions (soft delete, search-index maintenance) reserved for
housekeeping that's genuinely about a single model's own consistency, not
cross-model side effects.
