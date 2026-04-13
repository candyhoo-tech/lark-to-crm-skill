# 📘 Lark → CRM Sync Setup — Step by Step (For Dummies)

Follow each step exactly. Don't skip. Takes **5 minutes**.

End result: you can say `sync my meetings` and it writes everything to CRM automatically.

---

## 🧾 What this does

Every time you open a Lark meeting with a client, it auto-records. This skill:
1. Pulls that meeting from your Lark calendar
2. Grabs the transcript
3. Writes to the matching client's CRM deal — meeting log + summary + your action items

You do **nothing** after setup except say `sync my meetings`.

---

## ✅ Before you start — you need 3 things

| Thing | Where to get it |
|---|---|
| Your CRM login | Ask David if you don't have one |
| Your Lark login | `firstname.lastname@chatdaddy.tech` |
| Terminal on your laptop | Mac: "Terminal" app / Windows: "PowerShell" |

---

## Step 1 — Open Terminal

**Mac**: Press `Cmd + Space`, type "Terminal", press Enter.
**Windows**: Press Windows key, type "PowerShell", press Enter.

A black (or blue) window opens. That's it. Leave it open.

---

## Step 2 — Copy-paste this into Terminal, press Enter

```bash
git clone https://github.com/candyhoo-tech/lark-to-crm-skill.git ~/.claude/skills/lark-to-crm
```

Wait ~5 seconds. You'll see some "Cloning... done." messages. Good.

Then copy-paste this next, press Enter:

```bash
cp ~/.claude/skills/lark-to-crm/config/user.example.json ~/.claude/skills/lark-to-crm/config/user.json
```

No output = success. Don't worry.

---

## Step 3 — Get your CRM API key

1. Open **https://chatdaddy-crm.vercel.app** in your browser
2. Log in with your CRM account  
   (if you don't have one yet: ping David — default password is `chatdaddy123`, he'll reset yours)
3. Click your **profile picture** (top-right corner)
4. Click **Settings**
5. Click **API Keys** (left menu)
6. Click the **+ Create** button
7. Fill in:
   - Name: `Lark Sync — {your first name}` (e.g. `Lark Sync — Benjamin`)
   - Role: pick yours (admin / sales / cs)
8. Click **Create**
9. You'll see a LONG string starting with `crm_`. **Copy the whole thing and paste it in a note somewhere** — you only see it once.

Example: `crm_29aef32141915be173e06e844082c4360dbf9fadf51f23b28ef16c7a98de2f90`

---

## Step 4 — Ping Candy for the Lark app secret

Open Lark → DM **Candy** → paste:

> Hi Candy, I'm setting up the Lark-to-CRM skill. Can you DM me the `lark_app_secret` for `cli_a956dc65da78ded0`?

Wait for her reply. It's a long random string. **Copy it.** Don't share in group chat ever.

---

## Step 5 — Fill in the config file

Open the config file. Copy-paste this into Terminal:

```bash
open ~/.claude/skills/lark-to-crm/config/user.json
```

(On Windows: `notepad C:\Users\YourName\.claude\skills\lark-to-crm\config\user.json`)

A text editor opens. You'll see:

```json
{
  "owner_name": "YourFirstName",
  "lark_app_id": "cli_xxxxxxxxxxxxxxxx",
  "lark_app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
  "lark_email": "firstname.lastname@chatdaddy.tech",
  "crm_api_key": "crm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "crm_base_url": "https://chatdaddy-crm.vercel.app"
}
```

**Replace every `xxx...` with your real values.** Keep the quotes. Keep the commas. Example for Benjamin:

```json
{
  "owner_name": "Benjamin",
  "lark_app_id": "cli_a956dc65da78ded0",
  "lark_app_secret": "goOmthf...(whatever Candy sent)...",
  "lark_email": "benjamin.yeoh@chatdaddy.tech",
  "crm_api_key": "crm_29aef...(your key from Step 3)...",
  "crm_base_url": "https://chatdaddy-crm.vercel.app"
}
```

⚠️ **`owner_name` MUST match your name in CRM exactly**. Open CRM → profile → see your name. Type it exactly (capitalization matters: "Benjamin" not "benjamin", not "benjamin.yeoh").

**Save the file** (Cmd+S on Mac, Ctrl+S on Windows). Close the editor.

---

## Step 6 — Authorize Lark (one-time click)

Copy this whole link. Paste into your browser:

```
https://accounts.larksuite.com/open-apis/authen/v1/authorize?app_id=cli_a956dc65da78ded0&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback&state=lark_crm&scope=calendar%3Acalendar%3Areadonly+vc%3Arecord%3Areadonly+vc%3Ameeting%3Areadonly+docx%3Adocument%3Areadonly+contact%3Acontact.base%3Areadonly+minutes%3Aminutes%3Areadonly+minutes%3Aminutes.transcript%3Aexport+minutes%3Aminutes.media%3Aexport+drive%3Adrive%3Areadonly
```

What happens:
1. Lark login page — log in with your Lark account
2. You see a list of permissions (Calendar, VC, Minutes, Drive, Contacts) — click the big blue **Authorize** button
3. Your browser tries to go to `http://localhost:8080/callback?code=xxxxx&state=lark_crm`
4. **The page will look broken** — that's EXPECTED. It says "This site can't be reached" or similar. **Don't close it.**
5. Look at your browser's **address bar** at the top — the URL is:
   ```
   http://localhost:8080/callback?code=SOMETHING&state=lark_crm
   ```
6. **Click into the address bar, select ALL of it (Cmd+A / Ctrl+A), copy (Cmd+C / Ctrl+C)**

Keep this URL copied. You need it in the next step.

---

## Step 7 — Save your Lark token

Back in Terminal, paste this (replace `PASTE_YOUR_URL_HERE`):

```bash
python3 ~/.claude/skills/lark-to-crm/scripts/oauth_helper.py 'PASTE_YOUR_URL_HERE'
```

Example — replace only the URL part between the quotes:

```bash
python3 ~/.claude/skills/lark-to-crm/scripts/oauth_helper.py 'http://localhost:8080/callback?code=6LKoIcdxEx1BQC8dpCC3H08KyCTIbagx&state=lark_crm'
```

Press Enter. You should see:

```
✅ Token saved to /Users/.../lark_token.json
   expires_in: 7200s | scope: calendar:calendar:readonly ...
```

If you see `✅` — you're done with setup.

If you see an error — screenshot it and DM Candy.

---

## 🎉 You're set up

From now on, anywhere you're in Claude Code, just say:

> **sync my latest meeting to CRM**

And Claude does everything.

---

## 🗣️ Daily commands — just talk to Claude

| Say this | What happens |
|---|---|
| `sync my latest meeting` | Logs the most recent ended meeting |
| `sync today's meetings` | Logs all today's ended meetings |
| `day-end sync` | Checks what's missing from today, logs those |
| `sync meetings from 2026-04-10 to today` | Batch sync a range |

Claude will:
1. Show you **which meetings it's about to log + which companies match**
2. Ask you to approve (type `ok` or `yes`)
3. Write to CRM
4. Give you the CRM link to check

**It never duplicates.** Say "sync today's" 10 times — only new meetings get pushed.

---

## 🆘 If something breaks

| What you see | What to do |
|---|---|
| `Unauthorized` or red error from CRM | Your `crm_api_key` is wrong. Redo Step 3, paste the new key into `user.json` |
| `scope error` when clicking the Lark link | Copy-paste the full link again (maybe got cut off) |
| `no config found` | You skipped Step 5. Do it now. |
| `app bot_id not found` | DM Candy — tenant-level Lark approval issue |
| Wrong teammate name shows on activity | `owner_name` in `user.json` doesn't match CRM. Fix it, re-run. Old wrong ones need Candy to clean up. |
| Token expired (after 30 days idle) | Redo Step 6 + Step 7 |

**Anything else**: DM Candy 🦞. She'll screen-share walk through it.

---

## 🔐 Important safety rules

1. **Never commit `config/user.json`** — it's in `.gitignore` already, but just don't force add.
2. **Never paste `lark_app_secret` in a group chat**. DM only.
3. **Always preview before approving** — Claude shows you the plan first. Read the company matches. If something looks wrong (e.g. it matched "ABC Ltd" when you meant "ABCD Ltd"), say "no" and tell Claude the correct company.

---

## 🤖 Optional — Full auto-sync (runs every 10 min in background)

If you want the sync to happen WITHOUT you ever saying anything — a background job runs every 10 min, fetches new ended meetings, matches CRM companies, and posts meeting activities + transcript notes.

**Action items + structured summaries** still get added the next time you open Claude Code and say `review auto-synced meetings` (LLM work).

Install:

```bash
bash ~/.claude/skills/lark-to-crm/scripts/install_auto_sync.sh
```

Check it's running:

```bash
launchctl list | grep lark-to-crm
tail -f ~/.claude/skills/lark-to-crm/.state/auto-sync.log
```

Uninstall:

```bash
bash ~/.claude/skills/lark-to-crm/scripts/install_auto_sync.sh uninstall
```

**Ambiguous matches** (e.g. company name has 3 CRM hits) are queued to `.state/pending-review.json` — Claude will surface them next time you open it.

**Caveat**: only runs while your Mac is on + awake. Combine with `day-end sync` to catch anything missed.

Windows/Linux: use `cron` instead — add `*/10 * * * * python3 ~/.claude/skills/lark-to-crm/scripts/auto_sync.py` to your crontab.

---

Made with 🦞 by Candy.
