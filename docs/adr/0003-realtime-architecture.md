# ADR 0003: Project-Scoped Django Channels with JWT Authorization

## Status
Accepted

## Context
The assignment requires a WebSocket endpoint per project, where clients
connected to that project receive JSON events when tasks in it are
created, updated, or deleted — authenticated and authorized per project, not
just per user.

The first implementation had all of this wrong in the same way the REST
API's tenant isolation could have gone wrong: a single global `tasks` group
that every connected client joined regardless of which project (or
organization) they belonged to, using Channels' default
`AuthMiddlewareStack` (session-based, not JWT), with no authorization check
at connect time at all.

## Decision
**Routing** (`config/routing.py`): the WebSocket endpoint is
`ws/projects/<int:project_id>/tasks/`, not a single global path. Each
project gets its own Channels group, named `project_<project_id>`.

**Authentication** (`common/ws_auth.py`): a custom `JWTAuthMiddleware`
replaces Channels' `AuthMiddlewareStack` in `config/asgi.py`. It reads a
`token` query-string parameter, validates it with SimpleJWT's `AccessToken`
(the same access token issued by the REST login endpoint), and resolves
`scope['user']` — falling back to `AnonymousUser` for a missing or invalid
token. This reuses the same JWT the REST API already trusts, rather than
inventing a parallel WebSocket-only auth scheme.

**Authorization** (`tasks/consumers.py`): `TaskConsumer.connect()` rejects
before `accept()` is ever called, in two steps:
1. Unauthenticated (`AnonymousUser`) → close with code `4401`.
2. Authenticated but not a `Membership` of the project's organization →
   close with code `4403`.

Only after both checks pass does the consumer `group_add` the client into
`project_<project_id>` and accept the connection. These codes mirror HTTP's
401/403 semantics since the WebSocket protocol doesn't have standard
equivalents — worth calling out explicitly since they're a project
convention, not a spec.

**Broadcasting** (`tasks/services.py`): `TaskService.broadcast_task_update()`
sends to `project_{task.project_id}` instead of a global group, so an event
for a task in Project A is structurally impossible to deliver to a client
connected to Project B — there's no shared group for it to leak through.

**Authorization model chosen**: we authorize against `Membership`
(organization-level), the same check the REST permission classes
(`HasOrganizationAccess`, etc.) already use — not `ProjectMember`. In this
codebase, `ProjectMember` tracks which org members are *assigned to* a
project (a subset for UI/reporting purposes); it isn't used as an access
gate anywhere else in the API. Using `Membership` keeps the WebSocket
authorization story consistent with how every other endpoint in this
project already decides "can this user touch this organization's data" —
introducing a stricter, `ProjectMember`-based gate just for WebSockets would
mean users could read a project's tasks over REST but not receive live
updates for it, which is an inconsistency we'd have to explain and defend,
not a security improvement.

## Alternatives Considered
- **Session-based `AuthMiddlewareStack`** (Channels' default): rejected —
  the assignment explicitly requires JWT auth on the WebSocket connection,
  and session auth doesn't work for a stateless JWT-based API client
  anyway (no cookie to send).
- **JWT in a WebSocket subprotocol header** instead of a query string:
  considered, since query strings can end up in server logs. Query string
  was chosen for simplicity and because it's the most broadly supported
  approach across WebSocket client libraries (subprotocol-based auth
  requires more client-side plumbing). This is a reasonable place to
  reconsider if this were a production system rather than a training
  assignment — logging middleware/proxies should be configured to redact
  the `token` param.
- **Single global group with server-side filtering per event** (i.e. every
  client joins one group, and the consumer decides per-event whether to
  forward it): rejected because it pushes authorization into the hot path
  of every broadcast rather than the connection boundary, and because a bug
  in the per-event filter is a silent cross-tenant leak rather than a loud
  connection rejection.
- **`ProjectMember` as the authorization gate**: considered and rejected
  for the consistency reason above — see "Authorization model chosen".

## Testing
`tasks/tests.py` covers three cases with `channels.testing.WebsocketCommunicator`:
a member of the project's organization connecting and receiving a broadcast
event; an unauthenticated connection attempt being rejected; and an
authenticated user from a *different* organization being rejected. These
map directly to the three failure/success paths in `connect()`.
