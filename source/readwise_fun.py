#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to build/update a sqlite readwise database
#


import json
import sqlite3
import os
import shutil
import time
import ast
import textwrap
from config import MY_DATABASE, TOKEN, log, IMAGE_FOLDER, IMAGE_H_FOLDER


def parse_tags(raw):
	"""Parse a tags column value. New rows are JSON; old databases stored
	the Python repr of the list, so fall back to literal_eval."""
	if not raw or raw in ("[]", ""):
		return []
	try:
		return json.loads(raw)
	except (json.JSONDecodeError, ValueError):
		try:
			return ast.literal_eval(raw)
		except (ValueError, SyntaxError):
			return []


def createImage(highText, highAuthor, highTitle, highID):
	# PIL is only needed when generating quicklook images: import lazily so
	# searching still works if Pillow is not installed
	from PIL import Image, ImageDraw, ImageFont

	# Compile the string to be shown
	toShow = f"{highText}\n\n{highAuthor}: {highTitle}"

	image_width = 1200
	image_height = 800
	dpi = 96

	# Set the font size and maximum width for text wrapping
	font_size = 30
	max_width = 1000

	# Set the padding value (in pixels)
	padding = 20

	# Set the background color
	background_color = (255, 255, 255)

	# Set the font type
	font_type = "Georgia.ttf"

	# Set the line spacing (adjust as needed)
	line_spacing = 20

	# Set the border color
	border_color = (128, 128, 128)
	border_width = 5

	# Create a new image with the specified background color
	image = Image.new("RGB", (image_width, image_height), background_color)
	draw = ImageDraw.Draw(image)

	# Set the font and font size
	font = ImageFont.truetype(font_type, font_size)

	# Wrap the text to multiple lines, preserving newline characters
	wrapped_text = ""
	for line in toShow.splitlines():
		wrapped_text += textwrap.fill(line, width=int(max_width / (font_size / 2))) + "\n"

	# Calculate the total text height based on the number of lines and line spacing
	line_height = font.getbbox("A")[3] - font.getbbox("A")[1]

	# Set the DPI for higher resolution
	image.info["dpi"] = dpi

	# Draw the wrapped text on the image
	text_x = padding
	text_y = padding
	for line in wrapped_text.split('\n'):
		draw.text((text_x, text_y), line, font=font, fill="black")
		text_y += line_height + line_spacing

	# Add a border to the image
	draw.rectangle([(0, 0), (image_width - 1, image_height - 1)], outline=border_color, width=border_width)

	# Save the image as a JPEG file with higher resolution
	image.save(f"{IMAGE_H_FOLDER}{highID}.jpg", "JPEG", dpi=(dpi, dpi))


def fetchReadwiseExport():
	"""Download the full highlight export, following pagination and
	respecting rate limits. Raises RuntimeError with a readable message."""
	if not TOKEN:
		raise RuntimeError("No Readwise token — set it in the workflow configuration")

	import requests

	full_data = []
	next_page_cursor = None
	while True:
		params = {}
		if next_page_cursor:
			params['pageCursor'] = next_page_cursor
		log("Making export api request with params " + str(params) + "...")

		response = requests.get(
			url="https://readwise.io/api/v2/export/",
			params=params,
			headers={"Authorization": f"Token {TOKEN}"},
			timeout=60,
		)
		if response.status_code == 429:
			wait = int(response.headers.get("Retry-After", "5"))
			log(f"Rate limited, waiting {wait}s...")
			time.sleep(wait)
			continue
		if response.status_code == 401:
			raise RuntimeError("Readwise rejected the token — check the workflow configuration")
		if response.status_code != 200:
			raise RuntimeError(f"Readwise API error (HTTP {response.status_code})")

		payload = response.json()
		full_data.extend(payload['results'])
		next_page_cursor = payload.get('nextPageCursor')
		if not next_page_cursor:
			break
	return full_data


def refreshReadwiseDatabase():
	# Fetch everything BEFORE touching the database, and rebuild inside a
	# transaction: any failure rolls back and keeps the previous database
	full_data = fetchReadwiseExport()

	db = sqlite3.connect(MY_DATABASE)
	sql_create = """CREATE TABLE highlights (
			user_book_id INT,
			title TEXT,
			author TEXT,
			source TEXT,
			cover_image_url TEXT,
			unique_url TEXT,
			book_tags TEXT,
			category TEXT,
			readwise_url TEXT,
			source_url TEXT,
			highID INT,
			highText TEXT,
			high_created_at TEXT,
			highURL TEXT,
			highTags TEXT,
			high_is_favorite INT,
			high_is_discard INT,
			high_readwise_url TEXT
			)
			"""
	c = db.cursor()
	try:
		c.execute("DROP TABLE IF EXISTS highlights")
		c.execute(sql_create)

		for myBook in full_data:
			for myHigh in myBook['highlights']:
				c.execute('INSERT INTO highlights VALUES ( ?, ?, ?, ?, ?, ?,?, ?, ?, ?, ?, ?, ?,?,?,?,?,?)',
					(myBook['user_book_id'],
					myBook['title'],
					myBook['author'],
					myBook['source'],
					myBook['cover_image_url'],
					myBook['unique_url'],
					json.dumps(myBook['book_tags']),
					myBook['category'],
					myBook['readwise_url'],
					myBook['source_url'],
					myHigh['id'],
					myHigh['text'],
					myHigh['created_at'],
					myHigh['url'],
					json.dumps(myHigh['tags']),
					myHigh['is_favorite'],
					myHigh['is_discard'],
					myHigh['readwise_url']
				))
		db.commit()
	except Exception:
		db.rollback()
		db.close()
		raise

	# Generate quicklook images and fetch cover images only after the
	# database is safely committed
	for myBook in full_data:
		for myHigh in myBook['highlights']:
			quickLookPath = f"{IMAGE_H_FOLDER}{myHigh['id']}.jpg"
			if not os.path.exists(quickLookPath):
				try:
					createImage(myHigh['text'], myBook['author'], myBook['title'], myHigh['id'])
				except Exception as e:
					log(f"Could not create quicklook image for {myHigh['id']}: {e}")

	# retrieving all the cover images
	import urllib.request
	import urllib.error

	select_statement = "SELECT DISTINCT user_book_id, cover_image_url FROM highlights"
	c.execute(select_statement)
	rs = c.fetchall()

	for rec in rs:
		ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
		if os.path.exists(ICON_PATH):
			continue
		if rec[1]:
			log("retrieving image " + ICON_PATH)
			try:
				urllib.request.urlretrieve(rec[1], ICON_PATH)
			except (urllib.error.URLError, OSError) as e:
				log(f"Failed to download file: {e}")
				shutil.copy('icons/supplementals.png', ICON_PATH)
		else:
			shutil.copy('icons/supplementals.png', ICON_PATH)

	db.close()


def makeLabelList():
	db = sqlite3.connect(MY_DATABASE)
	select_statement = "SELECT highTags FROM highlights"
	c = db.cursor()
	c.execute(select_statement)
	rs = c.fetchall()

	unique_names = set()
	for label in rs:
		for Tag in parse_tags(label[0]):
			unique_names.add(Tag['name'])

	try:
		c.execute("DROP TABLE IF EXISTS tags")
		c.execute('''CREATE TABLE tags
						(id INTEGER PRIMARY KEY,
						name TEXT NOT NULL)''')

		for name in sorted(unique_names):
			c.execute('INSERT INTO tags (name) VALUES (?)', (name,))

		db.commit()
	except Exception:
		db.rollback()
		raise
	finally:
		db.close()
