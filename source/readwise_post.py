#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to post onto Readwise
#
#

from config import TOKEN, log, NEW_HIGH_TITLE
import sys
import requests
import datetime
MYINPUT = sys.argv[1]

now = datetime.datetime.now()
timestamp_str = now.isoformat()


result = {"items": []}

if MYINPUT == '':
    result['items'].append({
        "title": "Create a new Readwise highlight",
            'subtitle': "↩️ to save",
            'valid': True,
            
            "icon": {
                #"path": 'icons/Warning.png'
            }
            
    })

    
    

else:

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
		}
	)
	if (myResponse.status_code) == 200:
		print ("🎯 Highlight created!")
	else:
		print ("❌ error, check input")
        

