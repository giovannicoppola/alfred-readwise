#!/usr/bin/env python3
#
# Script to build/update a sqlite alfred-readwise database
#
#
# Created on Tuesday, April 4, 2023

from config import log, SEARCH_PLATFORM
from readwise_fun import refreshReadwiseDatabase, makeLabelList, refreshReaderDatabase, rebuildLock, clearCooldown
import json
import sys

# Only one refresh at a time (shared with the script filter's automatic rebuild).
# Triggering the keyword again while one is still running used to start a second and
# third copy; they then rate-limited each other on the Readwise API, so none could
# ever finish and the workflow looked hung.
with rebuildLock() as acquired:
    if not acquired:
        log("a rebuild is already running -- not starting another one")
        print(json.dumps({"items": [{
            "title": "Rebuild already in progress",
            "subtitle": "wait for it to finish before starting another",
            "arg": "",
            "icon": {"path": "icons/Warning.png"}
        }]}))
        sys.exit(0)

    # an explicit rebuild is a deliberate act: clear any cooldown from earlier failures
    clearCooldown()

    # "full" forces a rebuild from scratch, which is the only way to drop highlights
    # that were deleted in Readwise; without it the sync only fetches what changed.
    FULL = len(sys.argv) > 1 and sys.argv[1].strip().lower() == "full"
    log ("rebuilding database ⏳..." if FULL else "syncing changes ⏳...")

    if SEARCH_PLATFORM in ("Readwise highlights", "Readwise"):
        refreshReadwiseDatabase(full=FULL)
        makeLabelList()
    if SEARCH_PLATFORM in ("Readwise Reader", "Readwise"):
        refreshReaderDatabase(full=FULL)
    log ("done 👍")
	

result= {"items": [{
    "title": "Done!" ,
    "subtitle": "ready to search now",
    "arg": "",
    "icon": {

            "path": "icons/done.png"
        }
    }]}
print (json.dumps(result))

