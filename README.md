# lark-to-crm

Claude Code skill that syncs ChatDaddy team's Lark calendar meetings (with auto-fetched VC recording transcripts) to the CRM at `chatdaddy-crm.vercel.app`.

For each meeting you attended in Lark VC, the skill:

1. Pulls the event from your Lark calendar
2. Fetches the Lark Minutes transcript via the VC recording API
3. Matches the client to an existing CRM company (with multi-variant dedupe search)
4. Generates a structured summary: topic, discussion points, issues, decisions, **action items**, follow-up
5. Writes to the matched deal in CRM:
   - Meeting activity (type=meeting, completed)
   - Pinned summary note
   - Archive note with full transcript + Minutes URL
   - **Task activities** — one per action item assigned to you, with inferred due date + priority

Idempotent — running multiple times per day never creates duplicates.

## Install

Clone into your Claude Code skills directory:

```bash
git clone https://github.com/candyhoo-tech/lark-to-crm-skill.git ~/.claude/skills/lark-to-crm
cd ~/.claude/skills/lark-to-crm
cp config/user.example.json config/user.json
```

Then follow [`SETUP.md`](./SETUP.md) to create your Lark custom app (15 min), fill in `config/user.json`, and run the OAuth flow once.

## Usage

Just talk to Claude Code naturally:

- `sync my latest meeting to CRM`
- `sync today's meetings to CRM`
- `sync meetings from 2026-04-01 to today`
- `day-end sync` — catches anything from today not yet logged

Claude will:
1. Load your config + state
2. Fetch calendar + transcripts
3. **Preview** the matches (companies + already-synced events skipped)
4. Ask before writing anything
5. Push to CRM + update local state

## Files

| File | What it does |
|------|--------------|
| `SKILL.md` | Main agent instructions — the workflow Claude follows |
| `SETUP.md` | First-time Lark app + OAuth + config setup |
| `config/user.example.json` | Template — copy to `user.json` and fill in |
| `config/oauth_url.template.txt` | OAuth authorize URL template |
| `scripts/fetch_meetings.py` | Reference implementation for pulling events + transcripts |
| `scripts/sync_to_crm.py` | Reference implementation for writing to CRM |
| `scripts/oauth_helper.py` | Exchange OAuth code for tokens |
| `.state/` | Local state (gitignored) — synced-events registry + cached Lark token |

## Safety

- `config/user.json` and `.state/*` are in `.gitignore` — they contain your API keys and OAuth tokens. Never commit.
- Every write to CRM includes an idempotency tag `[lark_event_id: <id>]` — even if state is wiped, the skill won't duplicate.
- Preview-first — Claude always shows the plan before writing.

## License

Internal ChatDaddy tool — not for external distribution.
