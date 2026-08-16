# Agent rules

Before changing Core V1.1 read `LOCKED_SPEC.md`. Do not weaken or reinterpret those invariants. Do not add automatic account rotation, proxy rotation, FloodWait bypass, bulk multi-user invite RPCs, or spreadsheet access in the member-action hot path. Keep non-core extensions outside the `tms` core dependency graph.
