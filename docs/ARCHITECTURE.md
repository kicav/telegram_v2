# Telegram Migration Studio V1.1 Architecture

## Runtime domains

1. Qt main thread: render/input/event aggregation only.
2. Telegram NetworkRuntime: one dedicated asyncio loop; Telethon clients retained here.
3. DBWriter: one SQLite write owner, WAL mode.
4. WorkerPool: bounded local file/data work.

## Simple Workflow layer

`WorkflowCoordinator` hides technical steps from the UI:

```text
Collect: authenticate → resolve → persist group → create dataset/job → scanner
Invite:  authenticate → resolve target → permission → precheck → planner → preview
Remove:  authenticate → resolve target → remove permission → precheck → remove planner → preview
```

The UI issues user intent; it does not call TelegramGateway or SQL directly.

## Member action executor

`MemberActionExecutor` is shared by INVITE and REMOVE. `MigrationExecutor` remains a compatibility facade for INVITE tests/API.

```text
CandidateBuffer
  ↓
Scheduler 3–8 s
  ↓
ActionCurrentCandidate event
  ↓
RPC watchdog
  ↓
INVITE or REMOVE adapter
  ↓
ErrorMapper
  ↓
ResultClassifier
  ↓
Buffered DB persistence
```

Hot path uses cached `InputUser` and cached target access hash; it performs no per-candidate entity resolution.

## Operation state vs account connection state

V1 stored `BUSY/WAITING_SERVER` directly on account rows, which allowed reconnect to overwrite a server wait with READY. V1.1 treats the account row as connection/auth state and uses the active Job as operation truth.

`AccountStateResolver` combines both for display.

## Rate-limit policy

- Timed FloodWait → Job `WAITING_SERVER`, persisted `waiting_until`, same candidate retried after wait.
- Duration-less rate restriction / PeerFlood → Job `PAUSED`, current candidate remains `RETRY`, no automatic retry loop.
- Network/server transient → finite 1/2/4 policy.
- Auth/permission → pause.
- privacy/invalid/already/not-member → terminal skip where appropriate.

## Remove semantics

For basic Chat: `DeleteChatUserRequest`.

For channel/supergroup: cached `InputChannel` + cached `InputUser` are passed to Telethon's public `kick_participant` helper. The hot path therefore does not resolve target/member entities per candidate, and Core V1.1 treats the operation as remove/kick rather than permanent ban.

## Persistence

Migration/remove items reuse the bounded `migration_items` table for backward compatibility. `JobType.REMOVE` identifies remove jobs. Renaming the table would add migration risk without runtime benefit, so it is intentionally deferred.
