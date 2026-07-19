#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to post onto Readwise
#
#

from config import TOKEN, log, NEW_HIGH_TITLE
import sys
import datetime

MYINPUT = sys.argv[1] if len(sys.argv) > 1 else ""

if not MYINPUT.strip():
    print("⚠️ Nothing to save — empty highlight")
    sys.exit(0)

if not TOKEN:
    print("⚠️ No Readwise token — set it in the workflow configuration")
    sys.exit(1)

import requests

timestamp_str = datetime.datetime.now().isoformat()

try:
    myResponse = requests.post(
        url="https://readwise.io/api/v2/highlights/",
        headers={"Authorization": f"Token {TOKEN}"},
        json={
            "highlights": [{
                "text": MYINPUT,
                "title": NEW_HIGH_TITLE,

                "source_type": "fromAlfred",

                "highlighted_at": timestamp_str,
            }]
        },
        timeout=30,
    )
except requests.RequestException as e:
    log(f"request failed: {e}")
    print("❌ Could not reach Readwise — check your connection")
    sys.exit(1)

if myResponse.status_code in (200, 201):
    print("🎯 Highlight created!")
else:
    log(f"HTTP {myResponse.status_code}: {myResponse.text[:200]}")
    print(f"❌ Error saving highlight (HTTP {myResponse.status_code})")
    sys.exit(1)
