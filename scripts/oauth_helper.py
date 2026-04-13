#!/usr/bin/env python3
"""Exchange an OAuth callback URL for a Lark user_access_token.

Usage:
    python3 oauth_helper.py 'http://localhost:8080/callback?code=XXX&state=lark_crm'

Saves token to ~/.claude/skills/lark-to-crm/.state/lark_token.json
Requires config/user.json with lark_app_id + lark_app_secret.
"""
import json, os, re, sys
import urllib.request, urllib.error

SKILL_DIR = os.path.expanduser("~/.claude/skills/lark-to-crm")
CONFIG_PATH = f"{SKILL_DIR}/config/user.json"
STATE_DIR = f"{SKILL_DIR}/.state"
TOKEN_PATH = f"{STATE_DIR}/lark_token.json"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"Missing config: {CONFIG_PATH}. Copy config/user.example.json and fill it in.")
    return json.load(open(CONFIG_PATH))


def get_tenant_token(app_id, app_secret):
    r = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(r) as res:
        return json.loads(res.read())["tenant_access_token"]


def exchange_code(tenant_token, code):
    r = urllib.request.Request(
        "https://open.larksuite.com/open-apis/authen/v1/oidc/access_token",
        data=json.dumps({"grant_type": "authorization_code", "code": code}).encode(),
        headers={"Authorization": f"Bearer {tenant_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(r) as res:
        return json.loads(res.read())


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: oauth_helper.py '<callback_url_with_code>'")
    url = sys.argv[1]
    m = re.search(r"[?&]code=([A-Za-z0-9_-]+)", url)
    if not m:
        sys.exit("No code= found in URL. Paste the full callback URL including ?code=...")
    code = m.group(1)

    cfg = load_config()
    tt = get_tenant_token(cfg["lark_app_id"], cfg["lark_app_secret"])
    resp = exchange_code(tt, code)
    if resp.get("code") != 0:
        sys.exit(f"Exchange failed: {resp}")

    data = resp["data"]
    os.makedirs(STATE_DIR, exist_ok=True)
    import time
    data["obtained_at"] = int(time.time())
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Token saved to {TOKEN_PATH}")
    print(f"   expires_in: {data.get('expires_in')}s | scope: {data.get('scope')}")


if __name__ == "__main__":
    main()
