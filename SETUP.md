# Setup Guide — Lark to CRM Sync

First-time setup. Takes ~15 minutes. Do this once per user.

At the end you'll have a `config/user.json` file that the skill reads every time. Your name will appear as the `assignedTo` on every activity you log.

## Step 1 — Create a Lark custom app

1. Go to **https://open.larksuite.com** → top right click **Developer Console**
2. Click **Create Custom App**
3. Fill:
   - **App Name**: `CRM Auto Logger — {YourFirstName}`
   - **Description**: `Sync Lark meetings to CRM`
   - **Icon**: upload any image (required)
4. Click **Create**

## Step 2 — Enable Bot feature

1. Left menu → **Add Features** → click **Bot** → **Enable**
2. Fill Bot name, upload icon, save

## Step 3 — Add required permissions

Left menu → **Permissions & Scopes** → click **User token scopes** tab (NOT Tenant token scopes).

Tick ALL of these:

**Minutes**
- `minutes:minutes:readonly`
- `minutes:minutes.basic:read`
- `minutes:minutes.transcript:export`
- `minutes:minutes.media:export`

**Calendar**
- `calendar:calendar:readonly`

**VC**
- `vc:meeting:readonly`
- `vc:record:readonly`

**Drive**
- `drive:drive:readonly`
- `docx:document:readonly`

**Contacts**
- `contact:contact.base:readonly`

Click **Apply for Release** → go to **Admin Console** (https://admin.larksuite.com → Workplace → App Management → find your app) → approve pending permission requests.

## Step 4 — Register redirect URL

Left menu → **Security Settings** → **Redirect URL** → Add:
```
http://localhost:8080/callback
```

## Step 5 — Release app version

Left menu → **Version Management & Release** → **Create Version**:
- Version: `1.0.0`
- Availability: **Custom Range** → add yourself only
- Submit → approve in Admin Console

## Step 6 — Get CRM API key

1. Go to `https://chatdaddy-crm.vercel.app`
2. Log in → **Settings** → **API Keys** → **Create**
3. Name it (e.g. "Lark Sync Agent — {YourFirstName}"), select your role
4. Copy the key (shown once only)

## Step 7 — Get Lark app credentials

In the Lark app Developer Console → **Credentials & Basic Info** → copy:
- **App ID** (looks like `cli_xxxxxxxx`)
- **App Secret** (long random string)

## Step 8 — Write your config file

Copy `config/user.example.json` to `config/user.json` and fill in:

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

**`owner_name` must match how you appear in the CRM team list** (case-sensitive). Check `https://chatdaddy-crm.vercel.app` → your profile. If your CRM user is "Candy", put "Candy" — not "candy" or "candy.hoo".

`config/user.json` is in `.gitignore` — never commit it.

## Step 9 — OAuth authorize (first time only)

Open `config/oauth_url.template.txt`, replace `{APP_ID}` with your App ID, paste in browser:

1. Log in with your Lark account, approve the permissions listed
2. Browser redirects to `http://localhost:8080/callback?code=XXXX&state=lark_crm` — the page won't load, that's fine
3. **Copy the full URL from the address bar** — the `code=XXXX` is what matters
4. Paste it to Claude when asked (or run `scripts/oauth_helper.py <full_callback_url>` to save the token)

Tokens are saved to `.state/lark_token.json`. Access token lasts 2h; refresh token lasts 30d — the skill auto-refreshes.

## Done

Just tell Claude something like:
- "sync today's meetings to CRM"
- "sync my latest meeting to CRM"
- "day-end sync"

Claude reads your config, checks which meetings haven't been logged yet, previews the mapping, and on your approval pushes activities + pinned summary notes + action-item tasks to CRM.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `app bot_id not found` | Bot feature not enabled — redo Step 2 + re-release version |
| `scope error. Please edit and try again` | Missing scope in app config OR you ticked Tenant instead of User — redo Step 3 on the **User token scopes** tab |
| OAuth returns only `auth:user.id:read` scope | Didn't pass `&scope=...` in URL — use the full URL from Step 9 |
| `Unauthorized` from CRM | API key revoked or wrong — regenerate in Step 6 |
| `data not exist` on recording endpoint | Meeting had no VC recording, or it's a future meeting that hasn't happened yet |
| Activity logged to wrong teammate | `owner_name` in config doesn't match CRM team list — update and rerun (skill will create a new activity; old one will be duplicated until PATCH/DELETE endpoints are live) |
| Skill creates a duplicate activity | State file got wiped. Skill has a CRM fallback that greps `[lark_event_id: ...]` tag — check it runs. If duplicates exist, ask CRM owner to enable DELETE endpoint. |
