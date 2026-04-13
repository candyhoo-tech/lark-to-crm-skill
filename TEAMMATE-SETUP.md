# 🚀 Lark → CRM Sync Setup — Step by Step

This skill auto-pushes your Lark meetings (with transcripts) into the CRM at `chatdaddy-crm.vercel.app`. Takes **~5 min** one-time setup. Then you just say `sync my meetings` and it handles the rest.

---

## What you'll need before you start

- Claude Code installed on your laptop
- Your Lark login (`firstname.lastname@chatdaddy.tech`)
- Your CRM login (ask David if you don't have one — credentials:
  - Benjamin / `chatdaddy123`
  - Candy / `chatdaddy123`
  - David / `chatdaddy123`
  - Others — ask David to reset)
- Ping **Candy on Lark** to get the shared `lark_app_secret` (don't put it in a public chat)

---

## Step 1 — Install the skill

Open Terminal and run:

```bash
git clone https://github.com/candyhoo-tech/lark-to-crm-skill.git ~/.claude/skills/lark-to-crm
cd ~/.claude/skills/lark-to-crm
cp config/user.example.json config/user.json
```

That clones the skill into Claude Code's skills folder.

---

## Step 2 — Get your CRM API key

1. Open **https://chatdaddy-crm.vercel.app** in your browser
2. Log in → top-right profile → **Settings** → **API Keys** → **Create**
3. Name it `Lark Sync — {YourFirstName}`, select your role
4. **Copy the key** (shown once only — save it now)

---

## Step 3 — Fill in `config/user.json`

Open the file (in VS Code or any text editor):

```bash
open ~/.claude/skills/lark-to-crm/config/user.json
```

Replace with your own values:

```json
{
  "owner_name": "YourFirstName",
  "lark_app_id": "cli_a956dc65da78ded0",
  "lark_app_secret": "<ask Candy on Lark DM>",
  "lark_email": "firstname.lastname@chatdaddy.tech",
  "crm_api_key": "crm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "crm_base_url": "https://chatdaddy-crm.vercel.app"
}
```

**Important**:
- `owner_name` must **match your name in CRM** exactly. Check `https://chatdaddy-crm.vercel.app` → top-right profile. If you're "Benjamin", write "Benjamin" (not "ben" or "benjamin.yeoh").
- `lark_app_id` is the shared ChatDaddy team app — you don't need to create your own.
- `lark_app_secret` — **DM Candy on Lark** to get it. Never paste in group chat or public anywhere.

Save the file.

---

## Step 4 — Authorize Lark access (one-time OAuth)

Open this link in your browser (just click it):

```
https://accounts.larksuite.com/open-apis/authen/v1/authorize?app_id=cli_a956dc65da78ded0&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback&state=lark_crm&scope=calendar%3Acalendar%3Areadonly+vc%3Arecord%3Areadonly+vc%3Ameeting%3Areadonly+docx%3Adocument%3Areadonly+contact%3Acontact.base%3Areadonly+minutes%3Aminutes%3Areadonly+minutes%3Aminutes.transcript%3Aexport+minutes%3Aminutes.media%3Aexport+drive%3Adrive%3Areadonly
```

1. Log in with your Lark account
2. You'll see a permission list (Calendar, VC, Minutes, Drive, Contacts) — click **Authorize**
3. Your browser will redirect to `http://localhost:8080/callback?code=XXXXX&state=lark_crm` — the page won't load, that's fine.
4. **Copy the WHOLE URL from the address bar** (including `code=...`)

Keep that URL — you'll paste it in Step 5.

---

## Step 5 — First run

Open Claude Code in the skill folder:

```bash
cd ~/.claude/skills/lark-to-crm
claude
```

Then just say:

> sync my latest meeting to CRM

Claude will:
1. Ask for the OAuth URL from Step 4 → paste it in
2. Fetch your meeting, find the transcript, match to a CRM company
3. **Show you a preview** of what it's going to write
4. You approve → it pushes

That's it. Setup done.

---

## 🎯 Daily usage

Just talk to Claude naturally. Examples:

| You say | What happens |
|---------|--------------|
| `sync my latest meeting` | Pushes the most recent ended meeting |
| `sync today's meetings to CRM` | Pushes all today's completed meetings |
| `day-end sync` | Catches any meeting from today not yet logged |
| `sync meetings from 2026-04-01 to today` | Batch sync a date range |

**What gets pushed per meeting:**
- ✅ Meeting activity (type=meeting, completed)
- 📋 Pinned summary note with topic / discussion / decisions / action items
- 📎 Archive note with full transcript + Lark Minutes URL
- ✅ One task activity per **your** action item (with due date + priority, assigned to you)

**Never duplicates.** If you say `sync today's` three times, only new meetings get pushed.

---

## 🔒 Safety reminders

- **Never commit `config/user.json`** — it has your API keys. The `.gitignore` already excludes it, but don't force-add.
- **Never share `lark_app_secret`** in public channels.
- **Preview before approve** — Claude always shows the plan before writing to CRM. Review the company matches, especially for new clients.

---

## 🆘 Troubleshooting

| Problem | Fix |
|---------|-----|
| `Unauthorized` from CRM | API key wrong or expired — regenerate in CRM Settings |
| `scope error` on OAuth | Click the Step 4 link exactly as-is — don't shorten it |
| `data not exist` on a meeting | That meeting had no VC recording (maybe Zoom/phone). Skipped — no action needed. |
| Activity went to wrong teammate | `owner_name` in your `user.json` doesn't match CRM. Fix it and rerun (skill will not re-push the already-synced ones). |
| Skill says "no config found" | You skipped Step 3 — fill `config/user.json`. |
| Duplicates appeared | State file got wiped. Tell Candy — she'll clean up via Admin Panel. |

---

## 📞 Need help?

Ping **Candy on Lark** — happy to walk through it live the first time.
🦞
