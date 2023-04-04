#!/usr/bin/env python3
#
# Script to build/update a sqlite alfred-readwise database
#
#
# Created on Tuesday, April 4, 2023

from config import log
from readwise_fun import refreshReadwiseDatabase, makeLabelList
import json
log ("rebuilding database ⏳...")
refreshReadwiseDatabase()
makeLabelList()
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

