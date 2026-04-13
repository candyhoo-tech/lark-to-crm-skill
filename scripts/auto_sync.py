#!/usr/bin/env python3
"""Auto-sync: non-interactive polling sync from Lark calendar → CRM.

Designed to run every 10 min via launchd / cron. Does the mechanical work
(fetch transcript, match CRM company, log meeting activity + transcript
note). Leaves summary generation + action-item extraction to the next time
the user opens Claude Code — those require an LLM.

State:
  ~/.claude/skills/lark-to-crm/.state/synced-events.json
  ~/.claude/skills/lark-to-crm/.state/lark_token.json
  ~/.claude/skills/lark-to-crm/.state/pending-review.json   (ambiguous / no-match events)
  ~/.claude/skills/lark-to-crm/.state/auto-sync.log

Ambiguous matches are NEVER auto-posted — queued for user review.
"""
import json, os, re, sys, time, traceback
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

SKILL_DIR = os.path.expanduser("~/.claude/skills/lark-to-crm")
CONFIG_PATH = f"{SKILL_DIR}/config/user.json"
STATE_DIR = f"{SKILL_DIR}/.state"
SYNCED_PATH = f"{STATE_DIR}/synced-events.json"
TOKEN_PATH = f"{STATE_DIR}/lark_token.json"
PENDING_PATH = f"{STATE_DIR}/pending-review.json"
LOG_PATH = f"{STATE_DIR}/auto-sync.log"
TRANSCRIPT_DIR = f"{STATE_DIR}/transcripts"

os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


def log(msg):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    print(msg)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path))
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def http(method, url, headers=None, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ─── Lark token management ──────────────────────────────────────

def get_tenant_token(app_id, app_secret):
    status, body = http(
        "POST",
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        {"Content-Type": "application/json"},
        {"app_id": app_id, "app_secret": app_secret},
    )
    return json.loads(body)["tenant_access_token"]


def refresh_user_token(cfg, refresh_token):
    tt = get_tenant_token(cfg["lark_app_id"], cfg["lark_app_secret"])
    status, body = http(
        "POST",
        "https://open.larksuite.com/open-apis/authen/v1/refresh_access_token",
        {"Authorization": f"Bearer {tt}", "Content-Type": "application/json"},
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    j = json.loads(body)
    if j.get("code") != 0:
        return None
    return j["data"]


def get_user_token(cfg):
    tok = load_json(TOKEN_PATH, None)
    if not tok:
        raise SystemExit("No Lark token cached. Run oauth_helper.py first.")
    obtained = tok.get("obtained_at", 0)
    expires = tok.get("expires_in", 0)
    if time.time() < obtained + expires - 300:  # 5 min grace
        return tok["access_token"]
    # expired — refresh
    log("Refreshing Lark user token")
    fresh = refresh_user_token(cfg, tok["refresh_token"])
    if not fresh:
        log("ERROR: refresh failed — user must re-run OAuth flow")
        raise SystemExit("Lark token refresh failed")
    fresh["obtained_at"] = int(time.time())
    save_json(TOKEN_PATH, fresh)
    return fresh["access_token"]


# ─── Calendar + VC + Minutes ────────────────────────────────────

def larkget(path, user_token):
    status, body = http("GET", f"https://open.larksuite.com/open-apis{path}", {"Authorization": f"Bearer {user_token}"})
    if status >= 400:
        log(f"Lark GET {path} → {status} {body[:200]}")
    try:
        return json.loads(body)
    except Exception:
        return {"__raw__": body, "__status__": status}


def find_primary_calendar(user_token):
    r = larkget("/calendar/v4/calendars", user_token)
    for c in r.get("data", {}).get("calendar_list", []):
        if c.get("type") == "primary" and c.get("role") == "owner" and not c.get("is_third_party"):
            return c["calendar_id"]
    raise SystemExit("No primary calendar")


def list_events(cal_id, start_ts, end_ts, user_token):
    events, page_token = [], None
    while True:
        url = f"/calendar/v4/calendars/{cal_id}/events?start_time={start_ts}&end_time={end_ts}&page_size=100"
        if page_token: url += f"&page_token={page_token}"
        r = larkget(url, user_token)
        events.extend(r.get("data", {}).get("items", []))
        page_token = r.get("data", {}).get("page_token")
        if not page_token or not r.get("data", {}).get("has_more"):
            break
    return events


def get_event_detail(cal_id, event_id, user_token):
    return larkget(f"/calendar/v4/calendars/{cal_id}/events/{event_id}", user_token).get("data", {}).get("event", {})


def fetch_transcript(ev, user_token):
    vchat = ev.get("vchat", {})
    m = re.search(r"/j/(\d+)", vchat.get("meeting_url", "") or "")
    if not m:
        return None, None, None
    mno = m.group(1)
    st = int(ev["start_time"]["timestamp"]); et = int(ev["end_time"]["timestamp"])
    r = larkget(f"/vc/v1/meetings/list_by_no?meeting_no={mno}&start_time={st-14400}&end_time={et+14400}", user_token)
    briefs = r.get("data", {}).get("meeting_briefs", [])
    if not briefs:
        return None, None, None
    mid = briefs[0]["id"]
    rec = larkget(f"/vc/v1/meetings/{mid}/recording", user_token)
    ru = rec.get("data", {}).get("recording", {}).get("url", "") or ""
    tm = re.search(r"/minutes/([a-zA-Z0-9]+)", ru)
    if not tm:
        return None, None, None
    tok = tm.group(1)
    _, txt = http("GET", f"https://open.larksuite.com/open-apis/minutes/v1/minutes/{tok}/transcript", {"Authorization": f"Bearer {user_token}"})
    return tok, txt if txt and len(txt) > 100 else None, ru


# ─── CRM ────────────────────────────────────────────────────────

def crm_req(cfg, method, path, body=None):
    headers = {"Authorization": f"Bearer {cfg['crm_api_key']}", "Content-Type": "application/json"}
    url = f"{cfg['crm_base_url']}/api{path}"
    status, body_s = http(method, url, headers, body)
    try:
        return status, json.loads(body_s) if body_s else {}
    except Exception:
        return status, {"__raw__": body_s[:300]}


def search_company(cfg, keyword):
    _, r = crm_req(cfg, "GET", f"/companies?search={urllib.request.quote(keyword)}")
    return r.get("data", []) if isinstance(r, dict) else []


def extract_company_name(title):
    t = title.strip()
    m = re.match(r".*-\s*[+\d\s]+\s*-\s*([^|]+?)\s*\|\s*Client Booking", t, re.I)
    if m: return m.group(1).strip()
    m = re.match(r"ChatDaddy\s*x\s*(.+?)(?:\s*\|.*)?$", t, re.I)
    if m:
        inner = m.group(1).strip()
        parts = re.split(r"\s+x\s+", inner)
        return parts[-1].strip()
    return t[:60]


def match_crm(cfg, title):
    keyword = extract_company_name(title)
    variants = [keyword]
    if " " in keyword: variants.append(keyword.replace(" ", ""))
    if "(" in keyword: variants.append(keyword.split("(")[0].strip())
    seen = set(); matches = []
    for v in variants:
        for c in search_company(cfg, v):
            if c["id"] in seen: continue
            seen.add(c["id"]); matches.append(c)
    return keyword, matches


def get_deal_for_company(cfg, company_id):
    _, c = crm_req(cfg, "GET", f"/companies/{company_id}")
    deals = (c.get("deals") or []) if isinstance(c, dict) else []
    active = [d for d in deals if d.get("status") not in ("closed_won", "closed_lost")]
    pool = active or deals
    pool.sort(key=lambda d: d.get("subscriptionStartDate") or "", reverse=True)
    if not pool:
        return None
    return pool[0]


# ─── Main loop ──────────────────────────────────────────────────

def is_client_meeting(e):
    if e.get("status") != "confirmed": return False
    s = (e.get("summary") or "").strip()
    if not s: return False
    low = s.lower()
    if low in ("block", "blok", "blocked", "lunch", "client meeting block"): return False
    if low.startswith("block") and len(low) < 12: return False
    return True


def run_once():
    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        raise SystemExit(f"Missing {CONFIG_PATH}")
    owner = cfg.get("owner_name", "CS Agent")

    user_token = get_user_token(cfg)
    cal_id = find_primary_calendar(user_token)

    # Today 00:00 UTC+8 → now
    now = datetime.now(timezone.utc)
    tz8 = timezone(timedelta(hours=8))
    today8 = now.astimezone(tz8).replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(today8.timestamp())
    end_ts = int(now.timestamp())

    events = list_events(cal_id, start_ts, end_ts, user_token)
    ended = [e for e in events if is_client_meeting(e) and int(e["end_time"]["timestamp"]) < int(now.timestamp())]
    log(f"Scan: {len(ended)} confirmed+ended meetings today")

    synced = load_json(SYNCED_PATH, {})
    pending = load_json(PENDING_PATH, {})
    new_count = 0

    for e in ended:
        eid = e["event_id"]
        if eid in synced:
            continue
        title = e["summary"]
        log(f"Processing: {title} ({eid})")
        try:
            detail = get_event_detail(cal_id, eid, user_token)
            tok, txt, minutes_url = fetch_transcript(detail, user_token)

            keyword, matches = match_crm(cfg, title)
            if len(matches) != 1:
                pending[eid] = {
                    "title": title, "start_ts": int(e["start_time"]["timestamp"]),
                    "minutes_url": minutes_url, "minutes_token": tok,
                    "matches": [{"id": m["id"], "name": m["name"]} for m in matches],
                    "reason": "no_match" if not matches else "ambiguous",
                    "detected_at": now.isoformat(),
                }
                save_json(PENDING_PATH, pending)
                log(f"  ⏸ {'ambiguous' if matches else 'no match'} — queued for review")
                continue

            company = matches[0]
            deal = get_deal_for_company(cfg, company["id"])
            if not deal:
                status, deal = crm_req(cfg, "POST", "/deals", {
                    "title": f"{title} — New Business", "companyId": company["id"],
                    "owner": owner, "dealType": "new_business", "status": "lead",
                })
                if status >= 400:
                    log(f"  ❌ failed to create deal: {deal}")
                    continue
            deal_id = deal["id"]

            dt = datetime.fromtimestamp(int(e["start_time"]["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d")
            desc = f"Meeting on {dt}. Event: {title}."
            if minutes_url: desc += f"\nMinutes: {minutes_url}"
            if txt: desc += f"\nTranscript: {len(txt)} chars — see archive note."
            else: desc += "\nNo transcript recorded."
            desc += f"\n\n[lark_event_id: {eid}]"

            status_, act = crm_req(cfg, "POST", "/activities", {
                "dealId": deal_id, "type": "meeting", "title": f"{title[:80]} — {dt}",
                "description": desc, "status": "completed", "dueDate": dt,
                "assignedTo": owner, "priority": "medium",
            })
            if status_ >= 400:
                log(f"  ❌ activity post failed: {act}")
                continue
            activity_id = act.get("id")

            note_id = None
            if txt:
                tpath = f"{TRANSCRIPT_DIR}/{eid}.txt"
                with open(tpath, "w") as f: f.write(txt)
                note_body = f"Auto-synced transcript — {dt}\nEvent: {title}\n"
                if minutes_url: note_body += f"Lark Minutes: {minutes_url}\n"
                note_body += "\n---\n\n" + txt
                status_, note = crm_req(cfg, "POST", "/notes", {
                    "dealId": deal_id, "content": note_body[:50000], "createdBy": owner, "pinned": False,
                })
                if status_ < 400: note_id = note.get("id")

            synced[eid] = {
                "activity_id": activity_id, "transcript_note_id": note_id,
                "deal_id": deal_id, "company_id": company["id"],
                "minutes_url": minutes_url, "minutes_token": tok,
                "synced_at": now.isoformat(),
                "summary_pending": True,  # flagged so next Claude Code run adds summary + action items
                "auto": True,
            }
            save_json(SYNCED_PATH, synced)
            new_count += 1
            log(f"  ✅ synced: deal={deal_id} activity={activity_id} note={note_id}")

        except Exception as ex:
            log(f"  ❌ exception: {ex}\n{traceback.format_exc()}")

    log(f"Done. {new_count} new meetings synced. {len(pending)} pending review.")
    return new_count, len(pending)


if __name__ == "__main__":
    try:
        run_once()
    except Exception as e:
        log(f"FATAL: {e}\n{traceback.format_exc()}")
        sys.exit(1)
