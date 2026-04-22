#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to post onto Readwise
#
#

from config import TOKEN, log, NEW_HIGH_TITLE, MY_DATABASE
import sys
import sqlite3
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
		created = myResponse.json()
		for h in created:
			try:
				db = sqlite3.connect(MY_DATABASE)
				c = db.cursor()
				c.execute('INSERT INTO highlights VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
					(h.get('book_id', 0),
					 NEW_HIGH_TITLE, '', 'fromAlfred', '', '', '[]', 'books',
					 h.get('readwise_url', ''), '',
					 h.get('id', 0), h.get('text', ''), timestamp_str,
					 h.get('url', ''), '[]', 0, 0,
					 h.get('readwise_url', '')))
				db.commit()
				db.close()
				log(f"Highlight {h.get('id')} inserted into local DB")
			except Exception as e:
				log(f"Failed to insert highlight into local DB: {e}")
		print ("🎯 Highlight created!")
	else:
		print ("❌ error, check input")
        

