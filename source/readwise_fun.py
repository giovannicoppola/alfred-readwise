#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to build/update a sqlite readwise database
#
#
#Partly cloudy ⛅️  🌡️+40°F (feels +32°F, 55%) 🌬️↘19mph 🌔&m Sun Apr  2 10:07:01 2023
#W13Q2 – 92 ➡️ 272 – 326 ❇️ 38



import json
import sqlite3
import os
import re
import shutil
import contextlib
import requests
import urllib.request
from config import MY_DATABASE, TOKEN, log, IMAGE_FOLDER, IMAGE_H_FOLDER, SEARCH_PLATFORM

try:
	from PIL import Image, ImageDraw, ImageFont
	_PIL_AVAILABLE = True
except Exception:
	_PIL_AVAILABLE = False
	log("[createImage] Pillow not available; QuickLook previews disabled.")

# ---------------------------------------------------------------------------
# Layout constants (adapted from alfred-kindle highlight_images.py)
# ---------------------------------------------------------------------------
_IMG_W = 1200
_IMG_H_MIN = 420
_IMG_H_MAX = 1600
_DPI = 96
_PADDING = 40
_BG = (252, 250, 245)
_FG = (20, 20, 20)
_MUTED = (110, 108, 102)
_ACCENT = (181, 153, 70)
_BORDER = (200, 195, 185)
_BORDER_W = 4
_BODY_GAP = 18

_USER_FONTS = os.path.expanduser("~/Library/Fonts")
_SERIF_CANDIDATES = [
	f"{_USER_FONTS}/Newsreader-Medium.ttf",
	f"{_USER_FONTS}/Newsreader-Regular.ttf",
	f"{_USER_FONTS}/Newsreader-VariableFont_opsz,wght.ttf",
	"/Library/Fonts/Newsreader-Medium.ttf",
	"/Library/Fonts/Newsreader-Regular.ttf",
	"/System/Library/Fonts/Supplemental/Georgia.ttf",
	"/Library/Fonts/Georgia.ttf",
	"/System/Library/Fonts/Supplemental/Charter.ttc",
	"/System/Library/Fonts/Palatino.ttc",
	"/System/Library/Fonts/NewYork.ttf",
	"Georgia.ttf",
]
_SANS_CANDIDATES = [
	"/System/Library/Fonts/Helvetica.ttc",
	"/System/Library/Fonts/HelveticaNeue.ttc",
	"/System/Library/Fonts/SFNSDisplay.ttf",
	"Helvetica.ttf",
]

_FONT_CACHE = {}

_PARAGRAPH_BREAK_RE = re.compile(r"\s*\n\s*\n\s*")
_INLINE_WS_RE = re.compile(r"\s+")


def _normalize_body(text):
	if not text:
		return ""
	paragraphs = _PARAGRAPH_BREAK_RE.split(text)
	cleaned = [_INLINE_WS_RE.sub(" ", p).strip() for p in paragraphs]
	return "\n\n".join(p for p in cleaned if p)


def _load_font(candidates, size):
	key = (tuple(candidates), size)
	if key in _FONT_CACHE:
		return _FONT_CACHE[key]
	for path in candidates:
		try:
			f = ImageFont.truetype(path, size)
			_FONT_CACHE[key] = f
			return f
		except Exception:
			continue
	f = ImageFont.load_default()
	_FONT_CACHE[key] = f
	return f


def _wrap_for_font(draw, text, font, max_width):
	out = []
	for paragraph in text.splitlines() or [""]:
		words = paragraph.split(" ")
		line = ""
		for w in words:
			candidate = f"{line} {w}".strip()
			if draw.textlength(candidate, font=font) <= max_width:
				line = candidate
			else:
				if line:
					out.append(line)
				line = w
		out.append(line)
	return out


def _line_height(font):
	ascent, descent = font.getmetrics()
	return ascent + descent


def createImage(highText, highAuthor, highTitle, highID):
	if not _PIL_AVAILABLE:
		return

	out_path = f"{IMAGE_H_FOLDER}{highID}.jpg"

	body_font = _load_font(_SERIF_CANDIDATES, 30)
	footer_font = _load_font(_SANS_CANDIDATES, 20)

	body_lh = _line_height(body_font) + 10
	footer_lh = _line_height(footer_font)

	max_width = _IMG_W - (2 * _PADDING) - 8

	# Measure pass
	scratch = Image.new("RGB", (1, 1), _BG)
	sdraw = ImageDraw.Draw(scratch)

	body_text = _normalize_body(highText)
	body_lines = _wrap_for_font(sdraw, body_text, body_font, max_width)

	body_max_lines = (_IMG_H_MAX - _IMG_H_MIN) // body_lh + 10
	truncated = False
	if len(body_lines) > body_max_lines:
		body_lines = body_lines[:body_max_lines]
		truncated = True

	footer_bits = []
	if highTitle:
		footer_bits.append(highTitle)
	if highAuthor:
		footer_bits.append(highAuthor)
	footer_text = "   ·   ".join(footer_bits)

	# Compute canvas height
	h_total = _PADDING
	h_total += body_lh * len(body_lines)
	if footer_text:
		h_total += _BODY_GAP + footer_lh
	h_total += _PADDING

	img_h = max(_IMG_H_MIN, min(_IMG_H_MAX, h_total))

	# Draw pass
	image = Image.new("RGB", (_IMG_W, img_h), _BG)
	draw = ImageDraw.Draw(image)

	# Accent stripe
	draw.rectangle([(0, 0), (8, img_h)], fill=_ACCENT)

	y = _PADDING

	# Re-trim body if clamped
	reserved_for_tail = 0
	if footer_text:
		reserved_for_tail += _BODY_GAP + footer_lh
	reserved_for_tail += _PADDING
	body_budget = img_h - y - reserved_for_tail
	max_body_lines = max(1, body_budget // body_lh)
	if len(body_lines) > max_body_lines:
		body_lines = body_lines[:max_body_lines]
		truncated = True

	if truncated and body_lines:
		while body_lines and draw.textlength(
			body_lines[-1] + " …", font=body_font
		) > max_width:
			body_lines[-1] = body_lines[-1][:-1]
		body_lines[-1] = body_lines[-1].rstrip() + " …"

	for line in body_lines:
		draw.text((_PADDING + 8, y), line, font=body_font, fill=_FG)
		y += body_lh

	if footer_text:
		fy = img_h - _PADDING - footer_lh
		while draw.textlength(footer_text, font=footer_font) > max_width and len(footer_text) > 40:
			footer_text = footer_text[:-1]
		draw.text((_PADDING + 8, fy), footer_text, font=footer_font, fill=_MUTED)

	# Frame
	draw.rectangle(
		[(0, 0), (_IMG_W - 1, img_h - 1)],
		outline=_BORDER, width=_BORDER_W,
	)

	image.info["dpi"] = _DPI
	tmp_path = out_path + ".tmp"
	image.save(tmp_path, "JPEG", dpi=(_DPI, _DPI), quality=85, optimize=True)
	os.replace(tmp_path, out_path)





# Rate-limit handling. A 429 used to be retried forever, so a rebuild that hit the
# limit never finished and never reported anything -- it just reconnected once a
# minute until the workflow was killed. Retries are now bounded and the wait is
# capped, so the rebuild either succeeds or tells you why it stopped.
_MAX_RATE_LIMIT_RETRIES = 5
_MAX_RETRY_WAIT = 120

# cover-image downloads must never block the rebuild forever
_COVER_TIMEOUT = 20

# ---------------------------------------------------------------------------
# Rebuild lock
#
# Refreshes are triggered from two places: the explicit rebuild keyword, and the
# script filter (which rebuilds when the database is stale or the Reader table is
# missing). The script filter runs on every keystroke, so a Reader table that fails
# to build meant every keystroke launched another full API sync. Those copies then
# rate-limited each other and none could finish. One refresh at a time, and a short
# cooldown after a failure, keeps that from happening.
# ---------------------------------------------------------------------------
_LOCK_PATH = f"{os.path.dirname(MY_DATABASE)}/rebuild.lock"
_COOLDOWN_PATH = f"{os.path.dirname(MY_DATABASE)}/rebuild.cooldown"
_COOLDOWN_SECONDS = 600


def _lockIsStale():
	try:
		with open(_LOCK_PATH) as f:
			pid = int(f.read().strip())
	except (OSError, ValueError):
		return True
	if pid == os.getpid():
		return True
	try:
		os.kill(pid, 0)          # signal 0 only tests whether the process exists
	except OSError:
		return True              # holder died, e.g. Alfred killed the script filter
	return False


def inCooldown():
	"""True if a refresh failed recently and we should not immediately retry."""
	import time as _time
	try:
		age = _time.time() - os.path.getmtime(_COOLDOWN_PATH)
	except OSError:
		return False
	return age < _COOLDOWN_SECONDS


def startCooldown():
	try:
		with open(_COOLDOWN_PATH, "w") as f:
			f.write("")
	except OSError:
		pass


def clearCooldown():
	try:
		os.remove(_COOLDOWN_PATH)
	except OSError:
		pass


@contextlib.contextmanager
def rebuildLock():
	"""Context manager yielding True if this process may refresh, False otherwise."""
	if os.path.exists(_LOCK_PATH) and not _lockIsStale():
		yield False
		return
	try:
		with open(_LOCK_PATH, "w") as f:
			f.write(str(os.getpid()))
	except OSError:
		yield True               # can't lock; better to refresh than to block forever
		return
	try:
		yield True
	finally:
		try:
			os.remove(_LOCK_PATH)
		except OSError:
			pass


def _apiGet(url, params, label):
	"""GET with bounded 429 retries. Returns a 200 response, or None to stop paging."""
	import time as _time
	for attempt in range(1, _MAX_RATE_LIMIT_RETRIES + 1):
		try:
			response = requests.get(
				url=url,
				params=params,
				headers={"Authorization": f"Token {TOKEN}"},
				timeout=30
			)
		except requests.exceptions.RequestException as e:
			log(f"{label}: request failed: {e}")
			return None

		if response.status_code != 429:
			if response.status_code != 200:
				log(f"{label}: error {response.status_code}: {response.text[:200]}")
				return None
			return response

		retry_after = min(int(response.headers.get('Retry-After', 60)), _MAX_RETRY_WAIT)
		if attempt == _MAX_RATE_LIMIT_RETRIES:
			log(f"{label}: still rate limited after {_MAX_RATE_LIMIT_RETRIES} attempts -- giving up. "
			    "Wait a few minutes and rebuild again; check no other rebuild is already running.")
			return None
		log(f"{label}: rate limited, waiting {retry_after}s "
		    f"(attempt {attempt}/{_MAX_RATE_LIMIT_RETRIES})...")
		_time.sleep(retry_after)
	return None


def refreshReadwiseDatabase ():
	full_data = []
	next_page_cursor = None
	page = 0
	while True:
		page += 1
		params = {}
		if next_page_cursor:
			params['pageCursor'] = next_page_cursor
		log(f"Readwise API: fetching page {page}...")

		response = _apiGet("https://readwise.io/api/v2/export/", params, "Readwise API")
		if response is None:
			break

		data = response.json()
		results = data.get('results', [])
		full_data.extend(results)
		log(f"Readwise API: got {len(results)} books (total: {len(full_data)})")

		next_page_cursor = data.get('nextPageCursor')
		if not next_page_cursor:
			break
	
	
	db=sqlite3.connect(MY_DATABASE)	
	sql_drop = "DROP TABLE IF EXISTS highlights" 
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
	c.execute(sql_drop)
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
				str(myBook['book_tags']),
				myBook['category'],
				myBook['readwise_url'],
				myBook['source_url'],
				myHigh['id'],
				myHigh['text'],
				myHigh['created_at'],
				myHigh['url'],
				str(myHigh['tags']),
				myHigh['is_favorite'],
				myHigh['is_discard'],
				myHigh['readwise_url']
			
			))

			
			quickLookPath = f"{IMAGE_H_FOLDER}{myHigh['id']}.jpg"
			if not os.path.exists(quickLookPath):
				createImage(myHigh['text'],myBook['author'],myBook['title'],myHigh['id'])
	
	
	
	db.commit()
	
	#retrieving all the images
	# DISTINCT matters: there is one row per highlight, so without it this loop ran
	# once per highlight (thousands of times) instead of once per book, and a cover
	# that failed to download was retried on every one of that book's highlights.
	select_statement = "SELECT DISTINCT user_book_id, cover_image_url FROM highlights"

	c.execute(select_statement)

	rs = c.fetchall()

	for rec in rs:
		ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
		if rec[1]:
			if not os.path.exists(ICON_PATH):
				log ("retrieving image" + ICON_PATH)
				try:
					# an explicit timeout is essential: urlretrieve otherwise inherits
					# the default socket timeout of None and one unresponsive cover
					# host blocks the whole rebuild indefinitely
					with contextlib.closing(urllib.request.urlopen(rec[1], timeout=_COVER_TIMEOUT)) as resp, \
					     open(ICON_PATH, 'wb') as out:
						shutil.copyfileobj(resp, out)
				except Exception as e:
					# catch broadly: timeouts, SSL errors and malformed URLs are not
					# all URLError, and one bad cover must not abort the rebuild
					log(f"Failed to download file: {e}")
					if os.path.exists(ICON_PATH):
						os.remove(ICON_PATH)
					src = 'icons/supplementals.png'
					shutil.copy(src, ICON_PATH)

		else:
			src = 'icons/supplementals.png'
			shutil.copy(src, ICON_PATH)

	
	
	db.close()

def makeLabelList():
	db=sqlite3.connect(MY_DATABASE)	
	select_statement = "SELECT highTags FROM highlights"
	c = db.cursor()   
	c.execute(select_statement)

	rs = c.fetchall()
	
	
	
	all_dicts = []
	for label in rs:
		myTags = json.loads (label[0].replace("'", '"'))
		#log (f"===== myTags from table: {myTags}")
		for Tag in myTags:
		    #log (f"===== single Tag from table: {Tag}")
    # Convert dictionary to tuple to make it hashable
		    all_dicts.append (Tag)
	
	unique_names = list(set(d['name'] for d in all_dicts))
	#log (f"===== UNIQUE TAG NAMES: {unique_names}")
	

	# create the table
	c.execute( "DROP TABLE IF EXISTS tags" )
	c.execute('''CREATE TABLE tags
					(id INTEGER PRIMARY KEY,
					name TEXT NOT NULL)''')

	# insert the unique names into the table

	for name in unique_names:
		#log (f"===== inserting: {name}")
		c.execute('INSERT INTO tags (name) VALUES (?)', (name,))

	# commit the changes and close the connection
	db.commit()
	db.close()
            		
					

def refreshReaderDatabase():
	full_data = []
	next_page_cursor = None
	page = 0
	while True:
		page += 1
		params = {}
		if next_page_cursor:
			params['pageCursor'] = next_page_cursor
		log(f"Reader API: fetching page {page}...")

		response = _apiGet("https://readwise.io/api/v3/list/", params, "Reader API")
		if response is None:
			break

		data = response.json()
		results = data.get('results', [])
		full_data.extend(results)
		log(f"Reader API: got {len(results)} docs (total: {len(full_data)})")

		next_page_cursor = data.get('nextPageCursor')
		if not next_page_cursor:
			break

	db = sqlite3.connect(MY_DATABASE)
	c = db.cursor()
	c.execute("DROP TABLE IF EXISTS reader_documents")
	c.execute("""CREATE TABLE reader_documents (
			id TEXT PRIMARY KEY,
			title TEXT,
			author TEXT,
			category TEXT,
			source TEXT,
			url TEXT,
			source_url TEXT,
			site_name TEXT,
			image_url TEXT,
			location TEXT,
			tags TEXT,
			created_at TEXT,
			updated_at TEXT,
			summary TEXT,
			notes TEXT
			)""")

	for doc in full_data:
		c.execute('INSERT OR REPLACE INTO reader_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
			(doc.get('id', ''),
			 doc.get('title', ''),
			 doc.get('author', ''),
			 doc.get('category', ''),
			 doc.get('source', ''),
			 doc.get('url', ''),
			 doc.get('source_url', ''),
			 doc.get('site_name', ''),
			 doc.get('image_url', ''),
			 doc.get('location', ''),
			 json.dumps(doc.get('tags', {})),
			 doc.get('created_at', ''),
			 doc.get('updated_at', ''),
			 doc.get('summary', ''),
			 doc.get('notes', ''),
			))

	db.commit()
	db.close()
	log(f"Reader database refreshed with {len(full_data)} documents")


"""
OBSOLETE FUNCTIONS


def getBooks():
    url = "https://readwise.io/api/v2/books/"

    headers = {
        "Authorization": f"Token {TOKEN}"
    }

    response = requests.get(url, headers=headers)

    myBooks = response.json()
    myCounter = 0
    result = {"items": [], "variables":{}}

    types = [k for k, v in my_checks.items() if v == '1']
    

    myDict = [x for x in myBooks['results'] if x.get('category') in types]
    totCount = len(myDict)

    for currBook in myDict:
        ICON_PATH = 'icons/icon.png'
        if MYINPUT in currBook['title'].casefold():
            myCounter += 1
            result["items"].append({
            "title": currBook['title'],
            
            'subtitle': f"{myCounter}/{totCount}",
            'valid': True,
            
            "icon": {
                "path": f"icons/{currBook['category']}.png"
            },
            'arg': ''
                }) 
            
    print (json.dumps(result))
    return myBooks['results']

    
def getBookType(myBookID):
    response = requests.get(
        url=f"https://readwise.io/api/v2/books/{myBookID}/",
        headers={"Authorization": f"Token {TOKEN}"}
    )

    myBook = response.json()
    log (myBook)
    return myBook['category']

def getHighlights():
    url = "https://readwise.io/api/v2/highlights/"

    headers = {
        "Authorization": f"Token {TOKEN}"
    }

    response = requests.get(url, headers=headers)

    myHighs = response.json()['results']
    myCounter = 0
    myHighSel = []
    result = {"items": [], "variables":{}}

    for myHigh in myHighs:
        myType = getBookType(myHigh['book_id'])
        types = [k for k, v in my_checks.items() if v == '1']
        if myType in my_checks:
            myHighSel.append(myHigh)
    
    return myHighs



    
    totCount = len(myHigh)

    for currBook in myHighSel:
        
        if MYINPUT in currBook['text'].casefold():
            myCounter += 1
            result["items"].append({
            "title": currBook['text'],
            
            'subtitle': f"{myCounter}/{totCount}",
            'valid': True,
            
            "icon": {
                "path": f"icons/highlight.png"
            },
            'arg': ''
                }) 
            #print (currBook['title'])
    print (json.dumps(result))
    


def dict2db(json_data, myTable):

	db=sqlite3.connect(MY_DATABASE)	
		
	
	# thanks to https://www.codeproject.com/Tips/4067936/Load-JSON-File-with-Array-of-Objects-to-SQLite3-On
	column_list = []
	column = []
	for data in json_data:
		column = list(data.keys())
		for col in column:
			if col not in column_list:
				column_list.append(col)

	
	value = []
	values = [] 
	for data in json_data:
		for i in column_list:
			value.append(str(dict(data).get(i)))   
		values.append(list(value)) 
		value.clear()
	

	
# sql statement

	create_sql = "create table if not exists " + myTable + " ({0})".format(" text,".join(column_list))
	insert_sql = "insert into " + myTable + " ({0}) values (?{1})".format(",".join(column_list), ",?" * (len(column_list)-1))    
	drop_sql = "DROP TABLE IF EXISTS "+ myTable  
# execution	
	c = db.cursor()   
	c.execute(drop_sql)
	c.execute(create_sql)
	c.executemany(insert_sql , values)
	values.clear()
	db.commit()







	c.close()

def mergeHigh():
	db=sqlite3.connect(MY_DATABASE)	
	sql_merge_statement = '''CREATE TABLE highlighted_merged AS SELECT books.id, books.title, books.author,books.category,books.highlights_url, highlights.*
               FROM highlights
               LEFT OUTER JOIN books ON books.id = highlights.book_id'''
	drop_sql = "DROP TABLE IF EXISTS highlighted_merged"   
# execution	
	c = db.cursor()   
	c.execute(drop_sql)
	c.execute(sql_merge_statement)
	
	db.commit()
	c.close()


"""