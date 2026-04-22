#!/usr/bin/env python3
#
# Script to build/update a sqlite alfred-readwise database
#
#
# Created on Tuesday, April 4, 2023

from config import log, SEARCH_PLATFORM
from readwise_fun import refreshReadwiseDatabase, makeLabelList, refreshReaderDatabase
import json
log ("rebuilding database ⏳...")
if SEARCH_PLATFORM in ("Readwise highlights", "Readwise"):
    refreshReadwiseDatabase()
    makeLabelList()
if SEARCH_PLATFORM in ("Readwise Reader", "Readwise"):
    refreshReaderDatabase()
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

