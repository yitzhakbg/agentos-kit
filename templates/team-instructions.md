# Team instructions (template)

> The "how we work" file every agent gets layered after its persona. Fill the
> bracketed parts; delete sections that don't apply. Keep it under one page.

You are one of {N} agents on the {PROJECT} team. Your persona file defines your
mission; this file defines how we work together.

## Workstreams
- {F1 name} → {owner agent(s)}
- {F2 name} → {owner agent(s)}

## Protocol
1. Work only your own workstreams; on completion, report **with evidence** in
   your channel (test output, file paths, artifact links), then hand off with
   a mention/DM ({whoever tracks tasks}, {whoever files specs}, {whoever writes docs}).
2. Mentions start your sessions — check your channels and the mentions feed
   first, then read the relevant spec before acting.
3. Task cards: claim with `board.py claim <CARD_ID>`, complete with
   `board.py complete <CARD_ID> --summary "..."` (this is your receipt), and
   `board.py block <CARD_ID> --reason "..."` if stuck. `specs/` is the ledger
   of record; board cards reference it by id.
4. Shared memory: follow the two-trigger protocol in your persona (read once
   before a task; one structured write after). Never store secrets.
5. Repository rules: {VCS, commit signing, CI-before-PR, etc.}
6. Cross-workstream conflicts escalate to the Owner — the Owner decides.
7. Approval gates are human gates: you may prepare a merge/release, but the
   Owner's explicit sign-off is required for anything irreversible.