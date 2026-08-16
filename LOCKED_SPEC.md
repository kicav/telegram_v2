# Locked Core V1.1 specification

A change that violates an invariant below is an architecture bug.

- UI thread performs rendering/input/progress/commands and lightweight paged reads only; Telegram RPC, file I/O, DB writes and heavy local transforms stay off the UI thread.
- Telegram network I/O runs on one dedicated asyncio loop thread.
- Telegram clients are reused per active account; startup does not connect every account.
- Participant scans use pagination, normalization, deduplication, bounded queues, checkpoints, progress/cancel and batched persistence.
- Working member data is internal; Excel/CSV are import/export only.
- Dedup identity is Telegram user ID; username is fallback only for imported rows that lack an ID.
- Filter operations are local.
- Advanced 2-file operations remain UNION / INTERSECTION / DIFFERENCE.
- Target pre-check builds a RAM set and records COMPLETE/PARTIAL/UNAVAILABLE coverage.
- User-facing workflow hides resolve/pre-check/plan behind a single prepare action.
- INVITE uses one candidate per InviteToChannel RPC.
- REMOVE uses one candidate at a time and requires remove/admin permission.
- Normal action interval is configurable 3–8 seconds, default 5 seconds; it is an attempt interval, not a guaranteed-success interval.
- Server wait overrides local scheduling.
- Duration-less rate restrictions pause; they are never retried in an infinite fixed-delay loop.
- Transient network/server errors use finite 1s, 2s, 4s policy.
- Permission/auth pause the job; privacy/invalid/already/not-member are terminal according to action policy.
- No account switching to bypass server wait.
- Member-action hot path has no XLSX access, large SQL query, sorting, source scan, target resolve, heavy filter or UI rendering.
- SQLite uses WAL and one DBWriter.
- Routine writes are buffered; critical state transitions are immediate.
- Action execution has priority over export/statistics and enables Performance Mode.
- UI events are aggregated to roughly 5–10 refreshes/second.
- Account connection/auth state cannot overwrite persistent job WAITING_SERVER.
- RPC watchdog prevents an in-flight candidate from holding the job indefinitely.
