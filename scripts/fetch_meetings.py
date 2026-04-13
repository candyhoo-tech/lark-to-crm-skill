#!/usr/bin/env python3
"""Fetch Lark calendar events + VC meeting transcripts for a date range.

Usage:
    USER_TOKEN=u-xxx python3 fetch_meetings.py <start_date> <end_date>

    # Example
    USER_TOKEN=u-xxx python3 fetch_meetings.py 2026-04-01 2026-04-13

Outputs:
    /tmp/lark_events.json      — event metadata + matched Minutes tokens
    /tmp/lark_transcripts/     — one .txt per event (obs-token as filename)

Requires: user_access_token with scopes listed in SKILL.md.
"""
import json, os, re, sys, time
import urllib.request, urllib.error
from datetime import datetime, timezone

BASE = "https://open.larksuite.com/open-apis"
U = os.environ.get("USER_TOKEN") or sys.exit("Set USER_TOKEN env var (Lark user_access_token)")
TRANSCRIPT_DIR = "/tmp/lark_transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


def req(path, method="GET", body=None):
    url = f"{BASE}{path}"
    headers = {"Authorization": f"Bearer {U}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as res:
            return res.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()


def reqj(path, method="GET", body=None):
    try:
        return json.loads(req(path, method, body))
    except json.JSONDecodeError:
        return {}


def find_primary_calendar():
    r = reqj("/calendar/v4/calendars")
    for c in r.get("data", {}).get("calendar_list", []):
        if c.get("type") == "primary" and c.get("role") == "owner" and not c.get("is_third_party"):
            return c["calendar_id"]
    sys.exit("No primary calendar found")


def to_ts(date_str, end_of_day=False):
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())


def list_events(cal_id, start_ts, end_ts):
    events = []
    page_token = None
    while True:
        url = f"/calendar/v4/calendars/{cal_id}/events?start_time={start_ts}&end_time={end_ts}&page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        r = reqj(url)
        items = r.get("data", {}).get("items", [])
        events.extend(items)
        page_token = r.get("data", {}).get("page_token")
        if not page_token or not r.get("data", {}).get("has_more"):
            break
    return events


def is_client_meeting(event):
    if event.get("status") != "confirmed":
        return False
    s = (event.get("summary") or "").strip()
    if not s:
        return False
    low = s.lower()
    if low in ("block", "blok", "blocked", "lunch", "client meeting block"):
        return False
    if low.startswith("block") and len(low) < 12:
        return False
    return True


def fetch_transcript_for_event(cal_id, event):
    """Returns (obs_token, transcript_text, minutes_url) or (None, None, None)."""
    eid = event["event_id"]
    st = int(event["start_time"]["timestamp"])
    et = int(event["end_time"]["timestamp"])
    # Get vchat.meeting_url
    ed = reqj(f"/calendar/v4/calendars/{cal_id}/events/{eid}")
    vchat = ed.get("data", {}).get("event", {}).get("vchat", {})
    m = re.search(r"/j/(\d+)", vchat.get("meeting_url", ""))
    if not m:
        return None, None, None
    mno = m.group(1)
    # list_by_no
    r = reqj(f"/vc/v1/meetings/list_by_no?meeting_no={mno}&start_time={st-14400}&end_time={et+14400}")
    briefs = r.get("data", {}).get("meeting_briefs", [])
    if not briefs:
        return None, None, None
    mid = briefs[0]["id"]
    rec = reqj(f"/vc/v1/meetings/{mid}/recording")
    ru = rec.get("data", {}).get("recording", {}).get("url", "") or ""
    tm = re.search(r"/minutes/([a-zA-Z0-9]+)", ru)
    if not tm:
        return None, None, None
    tok = tm.group(1)
    txt = req(f"/minutes/v1/minutes/{tok}/transcript")
    if not txt or len(txt) < 100:
        return tok, None, ru
    return tok, txt, ru


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: fetch_meetings.py <start_date YYYY-MM-DD> <end_date YYYY-MM-DD>")
    start_ts = to_ts(sys.argv[1])
    end_ts = to_ts(sys.argv[2], end_of_day=True)
    cal_id = find_primary_calendar()
    print(f"Primary calendar: {cal_id}")

    events = list_events(cal_id, start_ts, end_ts)
    print(f"Total events: {len(events)}")

    results = []
    for e in events:
        if not is_client_meeting(e):
            continue
        st = int(e["start_time"]["timestamp"])
        dt = datetime.fromtimestamp(st, tz=timezone.utc).strftime("%Y-%m-%d")
        title = e["summary"]
        tok, txt, url = fetch_transcript_for_event(cal_id, e)
        if txt:
            path = f"{TRANSCRIPT_DIR}/{e['event_id']}.txt"
            with open(path, "w") as f:
                f.write(txt)
        results.append({
            "event_id": e["event_id"],
            "date": dt,
            "start_ts": st,
            "title": title,
            "minutes_token": tok,
            "minutes_url": url,
            "transcript_len": len(txt) if txt else 0,
            "transcript_path": f"{TRANSCRIPT_DIR}/{e['event_id']}.txt" if txt else None,
        })
        print(f"{dt} | {title[:55]:55} | obs={tok or '—':25} | tx={len(txt) if txt else 0}")

    with open("/tmp/lark_events.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} events to /tmp/lark_events.json")


if __name__ == "__main__":
    main()
