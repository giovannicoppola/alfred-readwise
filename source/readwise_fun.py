#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script to build/update a sqlite readwise database
#
#
#Partly cloudy ⛅️  🌡️+40°F (feels +32°F, 55%) 🌬️↘19mph 🌔&m Sun Apr  2 10:07:01 2023
#W13Q2 – 92 ➡️ 272 – 326 ❇️ 38



import ast
import json
import sqlite3
import os
import re
import shutil
import filecmp
import contextlib
import requests
import urllib.request
from datetime import datetime, timezone, timedelta
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

# Some books have no cover art, and instead of omitting the URL both Readwise and
# Amazon hand back a placeholder image. Downloading those produces a tiny blank or
# generic tile that looks like a failed download, so recognise them and use the
# workflow's own icon instead. Matched on the URL, which is stable and explicit.
_LOCAL_COVER = 'icons/supplementals.png'
_PLACEHOLDER_COVER_MARKERS = (
	'static/images/default-book-icon',   # Readwise's generic book icon
	'01RmK+J4pJL',                       # Amazon's blank-image placeholder
)


def _isPlaceholderCover(url):
	return bool(url) and any(marker in url for marker in _PLACEHOLDER_COVER_MARKERS)


def _useLocalCover(iconPath):
	"""Put the workflow's own icon at iconPath, unless it is already there."""
	try:
		if os.path.exists(iconPath) and filecmp.cmp(_LOCAL_COVER, iconPath, shallow=False):
			return
		shutil.copy(_LOCAL_COVER, iconPath)
	except OSError as e:
		log(f"could not apply the fallback cover to {iconPath}: {e}")

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
	if os.path.exists(_LOCK_PATH) and _lockIsStale():
		try:
			os.remove(_LOCK_PATH)    # holder is gone; clear the way for O_EXCL below
		except OSError:
			pass
	try:
		# create-exclusive so two script filters starting in the same instant cannot
		# both decide the lock is free: exactly one open() can win
		fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
	except FileExistsError:
		yield False
		return
	except OSError:
		yield True               # can't lock; better to refresh than to block forever
		return
	try:
		with os.fdopen(fd, "w") as f:
			f.write(str(os.getpid()))
	except OSError:
		pass
	try:
		yield True
	finally:
		try:
			os.remove(_LOCK_PATH)
		except OSError:
			pass


# ---------------------------------------------------------------------------
# Incremental sync
#
# Both APIs accept an `updatedAfter` timestamp and return only what changed since
# then. A full sync of a large library is dozens of pages and always trips the
# 20 requests/minute limit, costing a minute of dead waiting; an incremental sync
# is normally a single page. The watermark for each source is kept in a sync_state
# table inside the same database.
#
# Incremental sync cannot see deletions -- a highlight deleted in Readwise stays in
# the local database until a full rebuild. Pass full=True (or run the rebuild
# keyword with the argument "full") to start from scratch.
# ---------------------------------------------------------------------------

# rewind the watermark slightly so an edit made *during* a sync is not missed
_WATERMARK_SAFETY_SECONDS = 120

# Incremental sync never notices deletions, so fall back to a full sync periodically.
# This keeps the database honest without needing a separate keyword for it.
_FULL_RESYNC_DAYS = 30


def _utcNow():
	return datetime.now(timezone.utc)


def _apiTimestamp(dt):
	return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def _ensureSyncState(db):
	db.execute("CREATE TABLE IF NOT EXISTS sync_state (key TEXT PRIMARY KEY, value TEXT)")


def _getSyncState(db, key):
	_ensureSyncState(db)
	row = db.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
	return row[0] if row else None


def _setSyncState(db, key, value):
	_ensureSyncState(db)
	db.execute("INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)", (key, value))


def _fullSyncDue(db, key):
	"""True if a from-scratch sync has not run for a while (or ever)."""
	stamp = _getSyncState(db, key)
	if not stamp:
		return True
	try:
		last = datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
	except ValueError:
		return True
	return (_utcNow() - last) > timedelta(days=_FULL_RESYNC_DAYS)


def _tableExists(db, name):
	return db.execute(
		"SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
	).fetchone() is not None


def _indexExists(db, name):
	return db.execute(
		"SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
	).fetchone() is not None


def _fetchAllPages(url, label, extraParams=None):
	"""Page through an endpoint. Returns (results, complete).

	`complete` is False when a page failed, so the caller knows not to advance the
	sync watermark past data it never actually received.
	"""
	results = []
	next_page_cursor = None
	page = 0
	while True:
		page += 1
		params = dict(extraParams or {})
		if next_page_cursor:
			params['pageCursor'] = next_page_cursor
		log(f"{label}: fetching page {page}...")

		response = _apiGet(url, params, label)
		if response is None:
			return results, False

		data = response.json()
		batch = data.get('results', [])
		results.extend(batch)
		log(f"{label}: got {len(batch)} (total: {len(results)})")

		next_page_cursor = data.get('nextPageCursor')
		if not next_page_cursor:
			return results, True


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

		# Retry-After may legally be an HTTP-date rather than a number of seconds;
		# an unparseable value must not turn a retryable 429 into a traceback
		try:
			retry_after = int(response.headers.get('Retry-After', 60))
		except (TypeError, ValueError):
			retry_after = 60
		retry_after = min(retry_after, _MAX_RETRY_WAIT)
		if attempt == _MAX_RATE_LIMIT_RETRIES:
			log(f"{label}: still rate limited after {_MAX_RATE_LIMIT_RETRIES} attempts -- giving up. "
			    "Wait a few minutes and rebuild again; check no other rebuild is already running.")
			return None
		log(f"{label}: rate limited, waiting {retry_after}s "
		    f"(attempt {attempt}/{_MAX_RATE_LIMIT_RETRIES})...")
		_time.sleep(retry_after)
	return None


def refreshReadwiseDatabase (full=False):
	startedAt = _utcNow()
	db = sqlite3.connect(MY_DATABASE)

	# Decide between an incremental and a full sync. A database written by an older
	# version has no unique index on highID, so INSERT OR REPLACE could not de-duplicate
	# -- rebuild it once from scratch instead.
	since = None if full else _getSyncState(db, 'highlights_synced_at')
	if since and not (_tableExists(db, 'highlights') and _indexExists(db, 'idx_highlights_highID')):
		log("Readwise: database predates incremental sync, doing one full rebuild")
		since = None
	if since and _fullSyncDue(db, 'highlights_full_synced_at'):
		log(f"Readwise: no full sync in {_FULL_RESYNC_DAYS} days, doing one now to catch deletions")
		since = None

	extraParams = {'updatedAfter': since} if since else {}
	if since:
		log(f"Readwise: incremental sync of changes since {since}")
	else:
		log("Readwise: full sync")

	full_data, complete = _fetchAllPages(
		"https://readwise.io/api/v2/export/", "Readwise API", extraParams)

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
	if not complete and since:
		# a partial incremental result is safe to keep -- the watermark simply is not
		# advanced, so whatever was missed is picked up next time
		log("Readwise: sync incomplete, keeping existing data and watermark")
	if not complete and not since:
		# a partial *full* result would mean dropping the table and refilling it with
		# a fraction of the library, which is worse than doing nothing
		log("Readwise: full sync incomplete, leaving the database untouched")
		# ...but sqlite3.connect() has already created the file, so on a first-ever
		# sync the database would exist with no highlights table at all and every later
		# query would raise "no such table". Leave an empty table behind so the
		# workflow degrades to "no results" instead of dying.
		db.execute(sql_create.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
		db.commit()
		db.close()
		return False

	c = db.cursor()
	if since is None:
		c.execute(sql_drop)
		c.execute(sql_create)
	elif not _tableExists(db, 'highlights'):
		c.execute(sql_create)
	# highID is what INSERT OR REPLACE keys on, so an edited highlight updates its
	# row in place instead of being appended a second time
	c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_highlights_highID ON highlights(highID)")

	touchedBooks = set()
	highlightCount = 0
	for myBook in full_data:
		touchedBooks.add(myBook['user_book_id'])
		for myHigh in myBook['highlights']:
			highlightCount += 1

			c.execute('INSERT OR REPLACE INTO highlights VALUES ( ?, ?, ?, ?, ?, ?,?, ?, ?, ?, ?, ?, ?,?,?,?,?,?)',
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
	# On an incremental sync only the books that actually changed are considered.
	if since is not None and touchedBooks:
		placeholders = ','.join('?' * len(touchedBooks))
		c.execute(
			"SELECT DISTINCT user_book_id, cover_image_url FROM highlights "
			f"WHERE user_book_id IN ({placeholders})", list(touchedBooks))
	elif since is not None:
		c.execute("SELECT DISTINCT user_book_id, cover_image_url FROM highlights WHERE 0")
	else:
		c.execute("SELECT DISTINCT user_book_id, cover_image_url FROM highlights")

	rs = c.fetchall()

	for rec in rs:
		ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
		# no cover, or a known placeholder standing in for one: use our own icon and
		# do not spend a request fetching an image we would only throw away
		if not rec[1] or _isPlaceholderCover(rec[1]):
			_useLocalCover(ICON_PATH)
		elif not os.path.exists(ICON_PATH):
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
				_useLocalCover(ICON_PATH)

	# Placeholder covers downloaded by earlier versions are already on disk, and an
	# incremental sync only looks at the books it touched, so sweep every book with a
	# placeholder URL. No network involved: it is one query plus a byte comparison.
	c.execute(
		"SELECT DISTINCT user_book_id, cover_image_url FROM highlights "
		"WHERE cover_image_url IS NOT NULL AND cover_image_url != ''")
	replaced = 0
	for bookID, url in c.fetchall():
		if not _isPlaceholderCover(url):
			continue
		iconPath = f'{IMAGE_FOLDER}{bookID}.jpg'
		if not (os.path.exists(iconPath) and filecmp.cmp(_LOCAL_COVER, iconPath, shallow=False)):
			_useLocalCover(iconPath)
			replaced += 1
	if replaced:
		log(f"replaced {replaced} placeholder cover(s) with the workflow icon")

	# Only advance the watermark when every page arrived. It is rewound slightly so a
	# highlight edited while the sync was running is picked up next time rather than
	# falling into the gap between "fetched" and "recorded".
	if complete:
		watermark = _apiTimestamp(startedAt - timedelta(seconds=_WATERMARK_SAFETY_SECONDS))
		_setSyncState(db, 'highlights_synced_at', watermark)
		if since is None:
			_setSyncState(db, 'highlights_full_synced_at', _apiTimestamp(startedAt))
	db.commit()
	db.close()
	log(f"Readwise: {'full' if since is None else 'incremental'} sync stored "
	    f"{highlightCount} highlights from {len(touchedBooks)} books")
	# report success/failure by return value: callers need to know a sync failed, and
	# these functions deliberately do not raise on API errors
	return complete

def _parseTagField(raw):
	"""Return the tag names held in one stored tag field.

	Two shapes are stored. Highlights keep a Python repr of a list of dicts,
	[{'id': 1, 'name': 'italy'}]; Reader documents keep JSON keyed by tag name,
	{"genetics": {"name": "genetics", ...}}, and may be null or empty.
	"""
	if not raw:
		return []
	try:
		value = json.loads(raw)
	except (ValueError, TypeError):
		try:
			# the highlight form is a Python literal, not JSON -- a tag containing an
			# apostrophe used to break the old str.replace("'", '"') approach
			value = ast.literal_eval(raw)
		except (ValueError, SyntaxError):
			return []
	if isinstance(value, dict):
		return [k if not isinstance(v, dict) else v.get('name', k) for k, v in value.items()]
	if isinstance(value, list):
		return [t.get('name') for t in value if isinstance(t, dict) and t.get('name')]
	return []


def makeLabelList():
	db=sqlite3.connect(MY_DATABASE)
	c = db.cursor()

	# Count per tag as well as collecting names, so the '#' picker can show how much
	# each label holds. Counting here means it costs one pass per sync rather than a
	# query per keystroke. A tag is counted once per highlight/document, not once per
	# occurrence.
	highCounts = {}
	readerCounts = {}
	for (raw,) in c.execute("SELECT highTags FROM highlights").fetchall():
		for name in set(_parseTagField(raw)):
			highCounts[name] = highCounts.get(name, 0) + 1
	# Reader documents carry their own labels, and the '#' picker has to offer them
	# too -- otherwise a Reader-only tag can never be selected.
	if _tableExists(db, 'reader_documents'):
		for (raw,) in c.execute("SELECT tags FROM reader_documents").fetchall():
			for name in set(_parseTagField(raw)):
				readerCounts[name] = readerCounts.get(name, 0) + 1

	unique_names = [n for n in set(highCounts) | set(readerCounts) if n]
	#log (f"===== UNIQUE TAG NAMES: {unique_names}")
	

	# create the table
	c.execute( "DROP TABLE IF EXISTS tags" )
	c.execute('''CREATE TABLE tags
					(id INTEGER PRIMARY KEY,
					name TEXT NOT NULL,
					high_count INTEGER NOT NULL DEFAULT 0,
					reader_count INTEGER NOT NULL DEFAULT 0)''')

	# insert the unique names into the table

	for name in unique_names:
		#log (f"===== inserting: {name}")
		c.execute('INSERT INTO tags (name, high_count, reader_count) VALUES (?, ?, ?)',
			(name, highCounts.get(name, 0), readerCounts.get(name, 0)))

	# commit the changes and close the connection
	db.commit()
	db.close()
            		
					

def refreshReaderDatabase(full=False):
	startedAt = _utcNow()
	db = sqlite3.connect(MY_DATABASE)

	since = None if full else _getSyncState(db, 'reader_synced_at')
	if since and not _tableExists(db, 'reader_documents'):
		since = None
	if since and _fullSyncDue(db, 'reader_full_synced_at'):
		log(f"Reader: no full sync in {_FULL_RESYNC_DAYS} days, doing one now to catch deletions")
		since = None
	# the summary/notes columns were added later; an older table cannot be topped up
	if since:
		try:
			db.execute("SELECT summary, notes FROM reader_documents LIMIT 1")
		except sqlite3.OperationalError:
			log("Reader: table predates the summary/notes columns, doing one full rebuild")
			since = None

	extraParams = {'updatedAfter': since} if since else {}
	if since:
		log(f"Reader: incremental sync of changes since {since}")
	else:
		log("Reader: full sync")

	full_data, complete = _fetchAllPages(
		"https://readwise.io/api/v3/list/", "Reader API", extraParams)

	if not complete and not since:
		log("Reader: full sync incomplete, leaving the database untouched")
		# as above: leave an empty table so the "is the Reader table missing?" probe in
		# the script filter stops firing a fresh full sync on every keystroke
		db.execute("""CREATE TABLE IF NOT EXISTS reader_documents (
				id TEXT PRIMARY KEY, title TEXT, author TEXT, category TEXT,
				source TEXT, url TEXT, source_url TEXT, site_name TEXT,
				image_url TEXT, location TEXT, tags TEXT, created_at TEXT,
				updated_at TEXT, summary TEXT, notes TEXT)""")
		db.commit()
		db.close()
		return False

	c = db.cursor()
	if since is None:
		c.execute("DROP TABLE IF EXISTS reader_documents")
	c.execute("""CREATE TABLE IF NOT EXISTS reader_documents (
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

	if complete:
		watermark = _apiTimestamp(startedAt - timedelta(seconds=_WATERMARK_SAFETY_SECONDS))
		_setSyncState(db, 'reader_synced_at', watermark)
		if since is None:
			_setSyncState(db, 'reader_full_synced_at', _apiTimestamp(startedAt))
	db.commit()
	db.close()
	log(f"Reader: {'full' if since is None else 'incremental'} sync stored "
	    f"{len(full_data)} documents")
	return complete


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