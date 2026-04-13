---
name: lark-to-crm
description: Sync Lark calendar meetings (with auto-fetched VC recording transcripts) to ChatDaddy CRM. Use when the user wants to log past meetings from their Lark calendar into CRM with meeting activities + transcript notes + Candy-style action-item tasks on the matching company/deal. Also use for day-end "catch-up" sweeps where the agent scans for meetings not yet logged and logs only the missing ones.
---

# Lark → ChatDaddy CRM Sync

End-to-end: Lark calendar event → VC recording → Minutes transcript → CRM meeting activity + pinned summary note + action-item tasks attached to the correct company's deal. Idempotent: running multiple times in a day never creates duplicates.

## When to use

The user says something like:
- "sync my meetings from [date] to CRM" / "sync 今天的 meetings 到 CRM"
- "sync 刚开完的 meeting" → single most recent ended event
- "day-end sync" / "放工检查" → catch-up sweep: log anything from today not yet in CRM
- "log my Lark calls into CRM"

## Before anything else — load per-user config

Read `~/.claude/skills/lark-to-crm/config/user.json`. It contains:

```json
{
  "owner_name": "<first name as shown in CRM team list>",
  "lark_app_id": "cli_xxxxxxxxxxxxxxxx",
  "lark_app_secret": "xxxxx",
  "lark_email": "firstname.lastname@chatdaddy.tech",
  "crm_api_key": "crm_xxxxxxxx",
  "crm_base_url": "https://chatdaddy-crm.vercel.app"
}
```

**If this file is missing → do not proceed. Walk the user through `SETUP.md`**, which ends with writing this config file. Use `config/user.example.json` as the template.

Use `owner_name` as the value for `assignedTo` (activity) and `createdBy` (note) on ALL writes. Never hardcode a name.

## Fetching a fresh Lark user_access_token

Tokens live 2h; refresh tokens live 30d. Store in `~/.claude/skills/lark-to-crm/.state/lark_token.json`.

1. If `.state/lark_token.json` has a non-expired `access_token`, reuse it.
2. If `refresh_token` is valid, call `POST /open-apis/authen/v2/oauth/token` with `grant_type=refresh_token` to get a new access_token. Save it.
3. If both expired → user needs to re-authorize: build the auth URL from `config/oauth_url.template.txt` using their `lark_app_id` + required scopes, ask them to click it and paste the callback URL back. Exchange code for tokens via `POST /open-apis/authen/v1/oidc/access_token`. Save to state.

## Workflow

1. **Load credentials + state file.** Load `config/user.json`, `.state/lark_token.json`, `.state/synced-events.json` (create empty if missing). If creds missing → redirect to `SETUP.md`.
2. **Fetch events.** Call `scripts/fetch_meetings.py` with date range interpreted from the user's request:
   - "今天刚开完的" / "sync today's meetings" → today 00:00 in user's local tz → now
   - "最近一场" / "last meeting" / "latest" → pick single most recent confirmed + ended event
   - "day-end" / "end of day sync" / "放工 sync" → today 00:00 → now (catch-up mode)
   - Explicit date range → use it
3. **Skip already-synced events.** For each event, check:
   - **Local state**: event_id in `.state/synced-events.json` → skip with `⏭ already synced on {date}`
   - **CRM fallback**: if state file is empty/missing/stale, for each event, GET CRM activities for the matched company's recent deals; look for `[lark_event_id: <eid>]` in description → skip if found
4. **Fetch transcripts** (for non-skipped events): extract VC meeting_no → `list_by_no` → meeting id → `/recording` → Minutes URL → `/minutes/v1/minutes/{obs_token}/transcript`. Save to `/tmp/lark_transcripts/{event_id}.txt`.
5. **Match to CRM company.** For each event:
   - Extract company keyword from title. Patterns:
     - Client Booking: `<Person> - <Phone> - <COMPANY> | Client Booking`
     - ChatDaddy meeting: `ChatDaddy x <COMPANY> | ...` or `ChatDaddy x <Person> x <COMPANY>`
   - Search CRM with **multiple name variants** (e.g. "HeClinic" AND "He Clinic" AND the primary contact's name). Dedupe rule is hard — never create a duplicate company. When CRM has multiple hits with the same name, flag and ask.
   - Classify: ✅ unambiguous match, ⚠️ ambiguous (multiple hits), ❌ no match
6. **User confirmation** (preview-first is mandatory):
   - Show table of all non-skipped events with match status
   - Explicitly list skipped-already-synced count ("3 meetings already in CRM — skipping")
   - Ask about ambiguous / no-match / new-company cases — list them with suggestion per meeting, let user batch-answer
7. **Execute + generate summaries** once user approves:
   - Read transcript → generate a Markdown summary with: **Topic**, **Client context**, **Key discussion points**, **Issues raised**, **Decisions / commitments**, **Action items** (prefixed `[{owner_name}]` vs `[Client]`), **Follow-up** (method + timing), and a header line with date, event title, Lark Minutes URL.
   - **Extract `[{owner_name}]` action items** — each one becomes its own `type=task` activity on the same deal with:
     - status=pending
     - assignedTo = config.owner_name
     - dueDate inferred from transcript (e.g. "by tomorrow" → +1 day; "next week" → Monday; "by Friday" → next Friday) else default today + 1 business day
     - priority=high if urgent language ("critical", "urgent", "ASAP", specific same-day deadline) else medium
     - Title: short imperative (e.g. "Send HeClinic Pro plan quote")
     - Description: one-line context + `[lark_event_id: {event_id}]`
     - **Skip vague items** — only actionable tasks. Don't log "monitor progress" or "follow up when convenient".
   - For each meeting: find latest non-closed deal on company via `GET /companies/{id}`; create a minimal deal (dealType=new_business, status=lead, owner=config.owner_name) if none exists.
   - POST `/api/activities` (meeting): type=meeting, status=completed, dueDate=meeting date, assignedTo=config.owner_name, description = brief topic line + `\n\n[lark_event_id: {event_id}]` (idempotency marker — do NOT remove).
   - POST `/api/activities` (one per action item): type=task, per above.
   - POST `/api/notes` pinned=true, createdBy=config.owner_name, with the full structured summary (NOT raw transcript).
   - POST `/api/notes` pinned=false, with full transcript + Minutes URL as archive. Cap content at 50K chars.
   - Record in `.state/synced-events.json` including all new activity/note IDs.
8. **Report**: tabulate "{X} synced, {Y} already-logged, {Z} skipped (no VC / no match / user-rejected), {W} failures". Include deep links (`/deals/{deal_id}`) for the just-synced ones.

## Idempotency (CRITICAL)

Never log the same Lark event twice. Two independent checks:

1. **Primary** — `~/.claude/skills/lark-to-crm/.state/synced-events.json`:
```json
{
  "<lark_event_id>": {
    "activity_id": 87,
    "summary_note_id": 51,
    "transcript_note_id": 19,
    "task_activity_ids": [111, 112],
    "deal_id": 5038,
    "company_id": 1545,
    "minutes_url": "https://...larksuite.com/minutes/obs...",
    "synced_at": "2026-04-13T10:35:00Z"
  }
}
```

2. **Fallback** — every activity description ends with `[lark_event_id: <eid>]`. If state file is lost or user runs skill from another machine, query CRM activities for the matched company's deals and grep descriptions for this tag before logging.

On day-end sync, report missed events clearly: "You had 6 meetings today, 4 synced earlier, 2 missed — logging now."

## Rules & guardrails

- **Dedupe hard rule**: ALWAYS search multiple name variants before creating a company. Meeting/deal titles MUST include the canonical company name so future searches find them.
- **Preview-first**: NEVER bulk-write without showing the mapping table and getting user approval. Users prefer "preview-first" mode.
- **Ambiguous = ask, never guess**: if a meeting can't be unambiguously matched, don't log — ask.
- **Amounts in CRM are cents**, dates ISO. Activity types: `call|meeting|email|task`. `assignedTo` and `createdBy` both come from `config.owner_name`.
- **Transcript-less meetings**: still log the meeting activity with metadata + "no transcript" note. Don't fabricate content.
- **Future meetings** (end_time > now) have no recording yet — skip transcript fetch, still log the activity if the user asks.
- **Large transcripts**: cap note content to 50,000 chars. Always include Minutes URL in the note header so the full doc stays accessible.
- **Sensitive data**: NEVER commit `config/user.json` or `.state/*.json`. These are in `.gitignore`.

## Common pitfalls

- **"app bot_id not found"** → Lark app needs Bot feature enabled + version released.
- **Tenant token can't read user calendar** → must use user_access_token via OAuth. Tenant token is only for the bot's own resources.
- **OAuth grants only `auth:user.id:read` by default** → must pass all required scopes in `&scope=...` on the authorize URL. Scopes must also be enabled in the app's "User token scopes" (not Tenant) and approved by admin.
- **Minutes are NOT in Drive search results** — they live in a separate namespace (`obs...` tokens). Discover via VC: `list_by_no` → `/meetings/{id}/recording` → extract token from URL.
- **Event meeting_no ≠ meeting id**. Always call `list_by_no` first to convert.
- **Some events have no VC meeting** (phone calls, Zoom, external) — handle gracefully, skip transcript.
- **CRM PATCH/DELETE**: at time of writing, `/api/activities` and `/api/notes` only support POST/GET. If `PATCH ?id=X` or `DELETE ?id=X` 405s, the endpoint hasn't been deployed yet — fall back to append-only (POST a corrected summary, leave the original). Ask CRM owner to deploy the PATCH/DELETE routes.

## Files

- `SETUP.md` — first-time Lark app + OAuth setup + per-user config creation (give to new users)
- `config/user.example.json` — template for `config/user.json` (not committed)
- `config/oauth_url.template.txt` — OAuth authorize URL template (fill in app_id)
- `scripts/fetch_meetings.py` — pull events + transcripts from Lark
- `scripts/sync_to_crm.py` — write activities + notes to CRM (reference implementation)
- `scripts/oauth_helper.py` — exchange OAuth code for tokens
- `.gitignore` — excludes `config/user.json`, `.state/`, transcripts

## Key endpoints reference

Lark (international `larksuite.com`; replace with `feishu.cn` for China):
- `POST /open-apis/auth/v3/tenant_access_token/internal` — tenant token
- `POST /open-apis/authen/v1/oidc/access_token` — exchange OAuth code
- `POST /open-apis/authen/v2/oauth/token` — refresh user token
- `GET /open-apis/calendar/v4/calendars` — list user calendars (user token)
- `GET /open-apis/calendar/v4/calendars/{cal_id}/events?start_time=&end_time=` — list events
- `GET /open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}` — event detail (vchat.meeting_url)
- `GET /open-apis/vc/v1/meetings/list_by_no?meeting_no=X&start_time=&end_time=` — meeting_no → id
- `GET /open-apis/vc/v1/meetings/{id}/recording` — get Minutes URL
- `GET /open-apis/minutes/v1/minutes/{obs_token}/transcript` — plain text transcript

CRM (`{config.crm_base_url}/api`):
- `GET /companies?search=X` — search by name
- `GET /companies/{id}` — full company with deals + contacts
- `POST /companies` — create company
- `POST /deals` — create deal
- `POST /activities` — log activity (requires dealId, type, title, dueDate, status)
- `POST /notes` — add note to deal

## Required OAuth scopes

User token scopes (enabled in app under "User token scopes" tab AND approved by admin AND requested on authorize URL):

```
calendar:calendar:readonly
vc:meeting:readonly
vc:record:readonly
minutes:minutes:readonly
minutes:minutes.transcript:export
minutes:minutes.media:export
drive:drive:readonly
docx:document:readonly
contact:contact.base:readonly
```
