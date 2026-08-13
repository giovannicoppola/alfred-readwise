#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to post onto Readwise
#
#

from config import TOKEN, log, NEW_HIGH_TITLE, MY_DATABASE, IMAGE_FOLDER
from readwise_fun import createImage, _useLocalCover
import sys
import os
import sqlite3
import contextlib
import requests
import datetime
# Alfred always passes an argument here, but a direct run without one should not
# die with an IndexError before anything is logged
MYINPUT = sys.argv[1] if len(sys.argv) > 1 else ''

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
		# The endpoint returns a list of *book* objects, not highlights: there is no
		# "text", no "book_id" and no "readwise_url" on them. Reading those keys stored
		# a row with an empty highText and the book's id in highID, which could never
		# match a search and collided with the next highlight added to the same book.
		# The created highlight ids come back in "modified_highlights"; the text is
		# what we just posted.
		created = myResponse.json()
		try:
			with contextlib.closing(sqlite3.connect(MY_DATABASE)) as db:
				c = db.cursor()
				inserted = 0
				for myBook in created:
					bookID = myBook.get('id', 0)
					for highID in myBook.get('modified_highlights', []):
						c.execute(
							'INSERT OR REPLACE INTO highlights VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
							(bookID,
							 myBook.get('title') or NEW_HIGH_TITLE,
							 myBook.get('author') or '',
							 myBook.get('source') or 'fromAlfred',
							 myBook.get('cover_image_url') or '',
							 '',
							 str(myBook.get('tags', [])),
							 myBook.get('category') or 'books',
							 myBook.get('highlights_url') or '',
							 myBook.get('source_url') or '',
							 highID,
							 MYINPUT,
							 timestamp_str,
							 '', '[]', 0, 0,
							 f"https://readwise.io/open/{highID}"))
						inserted += 1
						# the sync builds a QuickLook image per highlight; do the same
						# here so one added from Alfred looks like any other
						try:
							createImage(MYINPUT, myBook.get('author') or '',
							            myBook.get('title') or NEW_HIGH_TITLE, highID)
						except Exception as e:
							log(f"could not render the QuickLook image: {e}")
						# a book created from Alfred has no cover, so Readwise hands
						# back a placeholder; use the workflow icon instead
						iconPath = f"{IMAGE_FOLDER}{bookID}.jpg"
						if not os.path.exists(iconPath):
							_useLocalCover(iconPath)
				db.commit()
			log(f"{inserted} highlight(s) inserted into local DB")
		except Exception as e:
			log(f"Failed to insert highlight into local DB: {e}")
		print ("🎯 Highlight created!")
	else:
		print ("❌ error, check input")
        

