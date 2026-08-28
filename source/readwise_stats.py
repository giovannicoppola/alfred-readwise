#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Statistics reports for the alfred-readwise workflow.

Two reports, both rendered as Markdown for Alfred's Text View with a companion
HTML page for the detail that does not fit in a panel:

  favorites  the highlights you starred, measured against the rest of the
             library, because a count on its own says very little: 14 favorites
             from one author is only interesting once you know whether you have
             20 highlights from them or 2,000. Its HTML page also lists every
             favorite, each linking to Readwise.
  library    the whole library on the same axes -- authors, sources, length,
             timeline -- with each slice measured against the library average.
             Its HTML page deliberately does not list the highlights themselves:
             at several thousand of them the page would be enormous.

Both read the Readwise *highlights* table only. Reader documents are not
covered: they carry no favorite flag, and a Reader document is a whole article
rather than a passage, so it has no comparable length. Both count every
highlight, whatever the category checkboxes in the workflow configuration say;
the category breakdown makes the split explicit.
"""

import html
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from config import FAV_REPORT, LIB_REPORT, MY_DATABASE, log

# How much detail the Markdown view carries. The HTML report is never truncated:
# it exists precisely to hold everything that does not fit in a panel.
TOP_AUTHORS = 15
TOP_RATE_AUTHORS = 8
TOP_SOURCES = 12
RECENT_HIGHLIGHTS = 5
CALENDAR_WEEKS = 53
# rows below this are dropped from the HTML tables and counted in a note instead:
# an author you have one highlight from produces a "100%, ×18.6" row that is
# arithmetic rather than taste, and there are hundreds of them
MIN_AUTHOR_FAVORITES = 2
MIN_AUTHOR_HIGHLIGHTS = 2

# Readwise's own category for the popular highlights it attaches to a book. They
# are not passages you marked, and at most libraries they outnumber the ones that
# are, so the library report keeps them visibly separate rather than letting them
# quietly inflate every count.
SUPPLEMENTAL = 'supplementals'

# Shades for the Markdown contribution calendar, lightest to heaviest. A code
# block is the only place Alfred renders a fixed-width grid, so the "colours"
# have to be characters.
_CAL_CHARS = ['·', '░', '▒', '▓', '█']

# Character-count buckets for the length distribution.
_LENGTH_BUCKETS = [
	(0, 100, "under 100"),
	(100, 200, "100–200"),
	(200, 400, "200–400"),
	(400, 800, "400–800"),
	(800, None, "800+"),
]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _localDay(raw):
	"""Return the local calendar day a highlight was created, or None.

	Readwise stores UTC ('2026-02-22T04:38:46.563Z'), but the question the
	calendar answers is "when was I reading?", which is a local-time question.
	"""
	if not raw:
		return None
	text = str(raw).strip().replace('Z', '+00:00')
	dt = None
	for candidate in (text, text[:19]):
		try:
			dt = datetime.fromisoformat(candidate)
			break
		except ValueError:
			continue
	if dt is None:
		return None
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return dt.astimezone().date()


_SHORT_CATEGORIES = {SUPPLEMENTAL: 'supp', 'books': 'book', 'articles': 'article',
                     'tweets': 'tweet', 'podcasts': 'podcast'}


def _shortCategory(category):
	"""Category name narrow enough for a fixed-width column."""
	return _SHORT_CATEGORIES.get(category, _trim(category, 7))


def _trim(text, width):
	"""Shorten to `width`, collapsing whitespace, for a fixed-width column."""
	text = ' '.join((text or '').split())
	return text if len(text) <= width else text[:width - 1].rstrip() + '…'


def _pct(part, whole):
	return (100.0 * part / whole) if whole else 0.0


def _share(pct):
	"""Format a percentage without rounding a real share down to '0.0%'."""
	if pct <= 0:
		return '0%'
	return f"{pct:.1f}%" if pct >= 0.1 else '<0.1%'


def _median(values):
	return statistics.median(values) if values else 0


def _mean(values):
	return (sum(values) / len(values)) if values else 0


def _bar(value, maximum, width=18, ch='▇'):
	"""A proportional bar. Anything non-zero gets at least one block, so a small
	but real number never renders as nothing at all."""
	if maximum <= 0 or value <= 0:
		return ''
	return ch * max(1, int(round(width * value / maximum)))


def _table(headers, rows, aligns=None):
	"""Lay out rows as fixed-width columns for a Markdown code block.

	Alfred's Markdown does not support tables, so anything tabular has to be
	aligned by hand inside a code block.
	"""
	if not rows:
		return []
	cols = len(headers)
	aligns = aligns or ['<'] * cols
	widths = [len(str(h)) for h in headers]
	for row in rows:
		for i in range(cols):
			widths[i] = max(widths[i], len(str(row[i])))

	def line(cells):
		out = []
		for i, cell in enumerate(cells):
			text = str(cell)
			# the last column is never padded: trailing spaces are invisible but
			# they widen the panel the view has to scroll
			out.append(text if i == cols - 1 else format(text, f"{aligns[i]}{widths[i]}"))
		return '  '.join(out).rstrip()

	return [line(headers), line(['─' * w for w in widths])] + [line(r) for r in rows]


def _thresholds(counts):
	"""Quartile cut-offs for the four non-empty calendar shades.

	Fixed cut-offs would be wrong for both kinds of library: someone adding two
	favorites a month would see a uniformly pale grid, someone clearing a book
	in one sitting a uniformly dark one.
	"""
	nonzero = sorted(c for c in counts if c > 0)
	if not nonzero:
		return [1, 2, 3]
	out = []
	for p in (0.25, 0.5, 0.75):
		value = nonzero[min(len(nonzero) - 1, int(len(nonzero) * p))]
		# strictly increasing, or two shades would mean the same thing
		out.append(max(value, out[-1] + 1 if out else 1))
	return out


def _level(count, thresholds):
	if count <= 0:
		return 0
	for i, t in enumerate(thresholds):
		if count <= t:
			return i + 1
	return 4


def _weekColumnStart(endDay, weeks):
	"""The Sunday that opens a `weeks`-wide calendar ending on `endDay`."""
	# date.weekday() is Monday=0 ... Sunday=6
	lastSunday = endDay - timedelta(days=(endDay.weekday() + 1) % 7)
	return lastSunday - timedelta(weeks=weeks - 1)


def _monthLabelRow(start, weeks, prefix):
	"""Month names above the calendar columns, GitHub-style.

	A three-letter name needs four columns to itself, but a month can start as
	little as two columns after the previous one. Rather than drop that month
	entirely, the label slides right to the first column that fits -- as long as
	that column is still inside the same month.
	"""
	row = [' '] * weeks
	written = -99
	lastMonth = None
	for w in range(weeks):
		day = start + timedelta(days=w * 7)
		if day.month == lastMonth:
			continue
		lastMonth = day.month
		col = max(w, written + 4)
		if col + 3 > weeks or (start + timedelta(days=col * 7)).month != day.month:
			continue
		for i, ch in enumerate(day.strftime('%b')):
			row[col + i] = ch
		written = col
	return prefix + ''.join(row).rstrip()


def _calendar(dayCounts, endDay, weeks=CALENDAR_WEEKS):
	"""A contribution calendar as text: 7 rows of days, one column per week."""
	start = _weekColumnStart(endDay, weeks)
	thresholds = _thresholds(dayCounts.values())
	labels = {1: 'Mon', 3: 'Wed', 5: 'Fri'}
	lines = [_monthLabelRow(start, weeks, ' ' * 4)]
	for r in range(7):
		cells = []
		for w in range(weeks):
			day = start + timedelta(days=w * 7 + r)
			# future days in the current week are not "no activity", they are
			# days that have not happened; leave them blank
			cells.append(' ' if day > endDay else _CAL_CHARS[_level(dayCounts.get(day, 0), thresholds)])
		lines.append(format(labels.get(r, ''), '<4') + ''.join(cells).rstrip())
	lines.append('')
	lines.append('    ' + _legend(thresholds, 'per day'))
	return lines


def _bands(thresholds):
	"""Wording for the five shades, collapsing ranges that hold one value."""
	def band(low, high):
		return str(low) if low == high else f"{low}–{high}"
	return ['none',
	        band(1, thresholds[0]),
	        band(thresholds[0] + 1, thresholds[1]),
	        band(thresholds[1] + 1, thresholds[2]),
	        f">{thresholds[2]}"]


def _legend(thresholds, unit):
	return '  '.join(f"{_CAL_CHARS[i]} {b}" for i, b in enumerate(_bands(thresholds))) + f"   ({unit})"


def _longestStreak(days):
	"""Longest run of consecutive days with at least one favorite."""
	if not days:
		return 0, None, None
	ordered = sorted(days)
	best = (1, ordered[0], ordered[0])
	runStart = ordered[0]
	runLen = 1
	for prev, day in zip(ordered, ordered[1:]):
		if (day - prev).days == 1:
			runLen += 1
		else:
			runStart, runLen = day, 1
		if runLen > best[0]:
			best = (runLen, runStart, day)
	return best


_MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _monthGrid(monthCounts):
	"""Every month you have ever starred anything in, one row per year.

	The 53-week calendar only ever shows the last year, which is the wrong
	window for a library built over several: this is the whole history at a
	glance, at the cost of monthly rather than daily resolution.
	"""
	if not monthCounts:
		return []
	years = sorted({y for y, _ in monthCounts})
	thresholds = _thresholds(monthCounts.values())
	yearTotals = {y: sum(c for (yy, _), c in monthCounts.items() if yy == y) for y in years}
	widest = max(len(f"{t:,}") for t in yearTotals.values())
	# both the header and the rows lay out twelve four-character columns, so the
	# total column lines up without any further arithmetic
	lines = ['      ' + ''.join(format(m, '<4') for m in _MONTH_ABBR)
	         + format('n', f'>{widest}')]
	for year in years:
		cells = ''.join(f" {_CAL_CHARS[_level(monthCounts.get((year, m), 0), thresholds)]}  "
		                for m in range(1, 13))
		lines.append(f"{year:<6}{cells}" + format(f"{yearTotals[year]:,}", f">{widest}"))
	lines.append('')
	lines.append('      ' + _legend(thresholds, 'per month'))
	return lines


# ---------------------------------------------------------------------------
# gathering
# ---------------------------------------------------------------------------

class Stats(object):
	"""Everything both reports need, derived in a single pass over the table.

	Names carry the set they describe: `fav*` counts only starred highlights,
	`lib*` the whole library, and `rest*` the unstarred remainder that the
	favorites report is measured against.
	"""

	def __init__(self):
		self.total = 0
		self.favCount = 0
		self.favorites = []
		self.recent = []
		self.authorAll = Counter()
		self.authorFav = Counter()
		self.authorChars = Counter()
		self.categoryAll = Counter()
		self.categoryFav = Counter()
		self.categoryChars = Counter()
		self.authorSupp = Counter()
		self.sourceAll = Counter()
		self.sourceFav = Counter()
		self.sourceSupp = Counter()
		self.sourceInfo = {}
		# the supplemental split: what Readwise added against what you marked
		self.suppCount = self.ownCount = 0
		self.suppFav = self.ownFav = 0
		self.suppChars, self.ownChars = [], []
		self.suppBooks, self.ownBooks = set(), set()
		self.suppAuthors, self.ownAuthors = set(), set()
		self.favDayCounts = Counter()
		self.favMonthCounts = Counter()
		self.libDayCounts = Counter()
		self.libMonthCounts = Counter()
		self.favChars, self.favWords = [], []
		self.restChars, self.restWords = [], []
		self.allChars, self.allWords = [], []
		self.books, self.favBooks = set(), set()
		self.baseRate = 0.0
		self.favFirstDay = self.favLastDay = None
		self.libFirstDay = self.libLastDay = None


def gather(db):
	"""Read the whole highlights table once and derive everything from it.

	One pass over a few thousand rows is cheaper than the dozen aggregate
	queries the two reports would otherwise need between them, and it keeps the
	favorite and the library figures guaranteed consistent with each other.
	"""
	db.row_factory = sqlite3.Row
	rows = db.execute("SELECT * FROM highlights").fetchall()

	s = Stats()
	s.total = len(rows)

	for r in rows:
		text = r['highText'] or ''
		chars, words = len(text), len(text.split())
		author = (r['author'] or '').strip() or 'Unknown'
		category = (r['category'] or 'other').strip()
		bookID = r['user_book_id']
		s.authorAll[author] += 1
		s.authorChars[author] += chars
		s.categoryAll[category] += 1
		s.categoryChars[category] += chars
		s.sourceAll[bookID] += 1
		s.books.add(bookID)
		# first row wins: every highlight from a book repeats its metadata
		s.sourceInfo.setdefault(bookID, r)
		if category == SUPPLEMENTAL:
			s.authorSupp[author] += 1
			s.sourceSupp[bookID] += 1
			s.suppCount += 1
			s.suppChars.append(chars)
			s.suppBooks.add(bookID)
			s.suppAuthors.add(author)
			s.suppFav += 1 if r['high_is_favorite'] == 1 else 0
		else:
			s.ownCount += 1
			s.ownChars.append(chars)
			s.ownBooks.add(bookID)
			s.ownAuthors.add(author)
			s.ownFav += 1 if r['high_is_favorite'] == 1 else 0
		day = _localDay(r['high_created_at'])
		if day:
			s.libDayCounts[day] += 1
			s.libMonthCounts[(day.year, day.month)] += 1
		if r['high_is_favorite'] == 1:
			s.favorites.append(r)
			s.authorFav[author] += 1
			s.categoryFav[category] += 1
			s.sourceFav[bookID] += 1
			s.favBooks.add(bookID)
			s.favChars.append(chars)
			s.favWords.append(words)
			if day:
				s.favDayCounts[day] += 1
				s.favMonthCounts[(day.year, day.month)] += 1
		else:
			s.restChars.append(chars)
			s.restWords.append(words)

	s.favCount = len(s.favorites)
	s.allChars = s.favChars + s.restChars
	s.allWords = s.favWords + s.restWords
	s.baseRate = _pct(s.favCount, s.total)
	# newest first: a report reads as a diary, and the recent end is the part
	# worth putting near the top of the Markdown view
	byDate = lambda r: (r['high_created_at'] or '')
	s.favorites.sort(key=byDate, reverse=True)
	s.recent = sorted(rows, key=byDate, reverse=True)[:RECENT_HIGHLIGHTS]
	s.favFirstDay, s.favLastDay = _span(s.favDayCounts)
	s.libFirstDay, s.libLastDay = _span(s.libDayCounts)
	return s


def _span(dayCounts):
	days = sorted(dayCounts)
	return (days[0], days[-1]) if days else (None, None)


def _authorRows(s, limit):
	"""Top authors by favorite count, each against their own total."""
	out = []
	for author, favs in s.authorFav.most_common(limit):
		total = s.authorAll[author]
		rate = _pct(favs, total)
		lift = (rate / s.baseRate) if s.baseRate else 0
		out.append((author, favs, total, rate, lift))
	return out


def _rateAuthorRows(s, minimum=10, limit=TOP_RATE_AUTHORS):
	"""Authors you favor most readily, among those you have read enough of.

	Without the minimum this list is nothing but authors with a single highlight
	that happens to be starred, which says nothing about taste.
	"""
	candidates = []
	for author, favs in s.authorFav.items():
		total = s.authorAll[author]
		if total >= minimum:
			candidates.append((author, favs, total, _pct(favs, total)))
	candidates.sort(key=lambda x: (-x[3], -x[1], x[0].lower()))
	return candidates[:limit]


def _libAuthorRows(s, limit=None):
	"""Top authors by how much of the library they account for.

	The favorites report asks "how often did I star this author"; here the
	question is "how much of what I read is this author", so the comparison is
	their share of the library and how their passages compare with the library's
	average length.
	"""
	libMean = _mean(s.allChars)
	out = []
	for author, n in s.authorAll.most_common(limit):
		mean = s.authorChars[author] / n if n else 0
		out.append((author, n, s.authorSupp[author], _pct(n, s.total), mean,
		            (mean / libMean) if libMean else 0, s.authorFav[author]))
	return out


def _sourceRows(s, limit=None):
	"""Most-highlighted sources, with the metadata their first row carries.

	No supplemental count here: Readwise categorises a whole book, so a source is
	either entirely supplemental or not at all, and its category already says so.
	"""
	out = []
	for bookID, n in s.sourceAll.most_common(limit):
		r = s.sourceInfo.get(bookID)
		title = ' '.join(((r['title'] if r else '') or 'Untitled').split())
		author = ((r['author'] if r else '') or 'Unknown').strip()
		category = ((r['category'] if r else '') or '').strip()
		url = (r['readwise_url'] if r else '') or ''
		out.append((bookID, title, author, category, n, s.sourceFav[bookID], url))
	return out


def _categoryRows(s):
	"""Categories with their share, their mean length and their favorite rate."""
	libMean = _mean(s.allChars)
	out = []
	for category, n in s.categoryAll.most_common():
		mean = s.categoryChars[category] / n if n else 0
		out.append((category, n, _pct(n, s.total), mean,
		            (mean / libMean) if libMean else 0,
		            s.categoryFav[category], _pct(s.categoryFav[category], n)))
	return out


def _splitRows(s):
	"""Your own highlights beside the ones Readwise supplied, on the same rows."""
	return [
		('highlights', f"{s.ownCount:,}", f"{s.suppCount:,}"),
		('share of library', _share(_pct(s.ownCount, s.total)),
		 _share(_pct(s.suppCount, s.total))),
		('sources', f"{len(s.ownBooks):,}", f"{len(s.suppBooks):,}"),
		('authors', f"{len(s.ownAuthors):,}", f"{len(s.suppAuthors):,}"),
		('mean characters', f"{_mean(s.ownChars):,.0f}", f"{_mean(s.suppChars):,.0f}"),
		('starred', f"{s.ownFav:,}", f"{s.suppFav:,}"),
		('starred rate', f"{_pct(s.ownFav, s.ownCount):.1f}%",
		 f"{_pct(s.suppFav, s.suppCount):.1f}%"),
	]


def _authorsOverlap(s):
	"""True when some author appears on both sides of the split.

	Sources cannot overlap -- Readwise categorises a whole book -- but an author
	can have one book you highlighted and another Readwise supplied, so the two
	author counts add up to more than the library has. Worth saying rather than
	leaving as an apparent arithmetic error.
	"""
	return len(s.ownAuthors) + len(s.suppAuthors) > len(s.authorAll)


_OVERLAP_NOTE = ("An author with one book you highlighted and another Readwise "
                 "supplied is counted on both sides, so those two do not add up to "
                 "your total.")

_SUPPLEMENTAL_NOTE = (
	"Supplementals are the popular highlights Readwise attaches to a book — they are "
	"not passages you marked yourself. They are counted everywhere below, so wherever "
	"an author or a source is mostly supplemental, most of that number was not put "
	"there by you.")


def _concentration(counter, total, top=10):
	"""Share of the library held by its `top` biggest entries."""
	return _pct(sum(c for _, c in counter.most_common(top)), total)


def _lengthBuckets(values):
	counts = [0] * len(_LENGTH_BUCKETS)
	for v in values:
		for i, (low, high, _) in enumerate(_LENGTH_BUCKETS):
			if v >= low and (high is None or v < high):
				counts[i] += 1
				break
	return counts


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _block(lines):
	return ['```'] + lines + ['```', '']


def _mdTimeline(dayCounts, monthCounts, noun, verb):
	"""The timeline section, identical in shape for both reports.

	`noun` names what is being counted ("favorites", "highlights") and `verb`
	completes "…something on N separate days".
	"""
	md = ["## Timeline", '']
	if not dayCounts:
		md.append(f"None of your {noun} carry a usable creation date.")
		md.append('')
		return md

	md.append(f"The last {CALENDAR_WEEKS} weeks, one column per week:")
	md.append('')
	md += _block(_calendar(dayCounts, datetime.now().date()))
	md.append("All time, one cell per month:")
	md.append('')
	md += _block(_monthGrid(monthCounts))

	busyDay, busyCount = dayCounts.most_common(1)[0]
	streak, streakStart, streakEnd = _longestStreak(dayCounts)
	md.append(f"- Busiest day: **{busyDay:%d %b %Y}** with {busyCount:,} {noun}")
	if monthCounts:
		(by, bm), bc = monthCounts.most_common(1)[0]
		md.append(f"- Busiest month: **{datetime(by, bm, 1):%B %Y}** with {bc:,}")
	md.append(f"- Longest streak: **{streak} day{'s' if streak != 1 else ''}** "
	          f"({streakStart:%d %b %Y} → {streakEnd:%d %b %Y})")
	md.append(f"- {verb} on **{len(dayCounts):,}** separate days")
	md.append('')
	return md


def _mdRecent(rows, heading="## Most recent"):
	"""The newest few highlights, each a clickable Readwise link."""
	md = [heading, '']
	for r in rows:
		day = _localDay(r['high_created_at'])
		text = ' '.join((r['highText'] or '').split())
		if len(text) > 180:
			text = text[:177].rstrip() + '…'
		# a Readwise "title" is sometimes the whole quote -- for a supplemental
		# saved from Goodreads, say -- so it gets the same trim as the text
		title = ' '.join((r['title'] or '').split())
		if len(title) > 70:
			title = title[:67].rstrip() + '…'
		label = f"{(r['author'] or 'Unknown').strip()} — {title}".strip(' —')
		url = r['high_readwise_url'] or ''
		when = f" · {day:%d %b %Y}" if day else ''
		md.append(f"> {text}")
		md.append('')
		# https links are the only ones Alfred's Markdown makes clickable, which
		# is exactly what a readwise.io highlight URL is
		md.append((f"— [{label}]({url})" if url else f"— {label}") + when)
		md.append('')
	return md


def _mdFooter(reportPath, promise):
	return ['---', '',
	        f"**Press <kbd>↩</kbd> to open the full report** — {promise}", '',
	        f"`{reportPath}`"]


def buildFavoritesMarkdown(s, reportPath):
	md = []
	md.append("# ❤️ Favorite highlights")
	md.append('')
	md.append(f"**{s.favCount:,}** of your **{s.total:,}** highlights are favorites "
	          f"— **{s.baseRate:.1f}%** of the library.")
	span = ''
	if s.favFirstDay and s.favLastDay:
		span = f"{s.favFirstDay:%d %b %Y} → {s.favLastDay:%d %b %Y} · "
	md.append(f"{span}{len(s.favBooks):,} of {len(s.books):,} sources · "
	          f"{len(s.authorFav):,} of {len(s.authorAll):,} authors")
	md.append('')

	if not s.favCount:
		md.append("You have not starred anything in Readwise yet — "
		          "there is nothing to report.")
		return '\n'.join(md)

	# ---- authors ----------------------------------------------------------
	md.append("## Authors")
	md.append('')
	md.append(f"`fav` favorites · `all` every highlight you have from them · "
	          f"`rate` the share you starred · `vs lib` how that compares with your "
	          f"library-wide {s.baseRate:.1f}%.")
	md.append('')
	rows = [(a, f"{f:,}", f"{t:,}", f"{r:.0f}%", f"×{l:.1f}")
	        for a, f, t, r, l in _authorRows(s, TOP_AUTHORS)]
	# plain-ASCII column headings on purpose: an emoji is two cells wide in a
	# monospace font, which throws out every column to its right
	md += _block(_table(['author', 'fav', 'all', 'rate', 'vs lib'], rows,
	                    ['<', '>', '>', '>', '>']))

	rateRows = _rateAuthorRows(s)
	if rateRows:
		md.append("### Most readily starred")
		md.append('')
		md.append("Authors you have at least 10 highlights from, ranked by the share "
		          "you marked as favorites.")
		md.append('')
		md += _block(_table(['author', 'rate', 'fav', 'all'],
		                    [(a, f"{r:.0f}%", f"{f:,}", f"{t:,}") for a, f, t, r in rateRows],
		                    ['<', '>', '>', '>']))

	# ---- length -----------------------------------------------------------
	md.append("## Length")
	md.append('')
	favMean, restMean, allMean = _mean(s.favChars), _mean(s.restChars), _mean(s.allChars)
	md += _block(_table(
		['', 'favorites', 'rest of library', 'whole library'],
		[('mean characters', f"{favMean:,.0f}", f"{restMean:,.0f}", f"{allMean:,.0f}"),
		 ('median characters', f"{_median(s.favChars):,.0f}", f"{_median(s.restChars):,.0f}",
		  f"{_median(s.allChars):,.0f}"),
		 ('mean words', f"{_mean(s.favWords):,.0f}", f"{_mean(s.restWords):,.0f}",
		  f"{_mean(s.allWords):,.0f}"),
		 ('longest', f"{max(s.favChars):,}", f"{max(s.restChars):,}" if s.restChars else '—',
		  f"{max(s.allChars):,}")],
		['<', '>', '>', '>']))
	if restMean:
		delta = _pct(favMean - restMean, restMean)
		verb = 'longer' if delta >= 0 else 'shorter'
		md.append(f"Your favorites run **{abs(delta):.0f}% {verb}** than the highlights "
		          f"you did not star.")
		md.append('')

	favBuckets = _lengthBuckets(s.favChars)
	restBuckets = _lengthBuckets(s.restChars)
	favTotal, restTotal = sum(favBuckets) or 1, sum(restBuckets) or 1
	widest = max(max(_pct(b, favTotal) for b in favBuckets),
	             max(_pct(b, restTotal) for b in restBuckets))
	md.append("Distribution, by characters — favorites against the rest:")
	md.append('')
	md += _block(_table(
		['chars', 'favorites', '%', 'rest', '%'],
		[(label,
		  _bar(_pct(favBuckets[i], favTotal), widest, 14),
		  f"{_pct(favBuckets[i], favTotal):.0f}%",
		  _bar(_pct(restBuckets[i], restTotal), widest, 14),
		  f"{_pct(restBuckets[i], restTotal):.0f}%")
		 for i, (_, _, label) in enumerate(_LENGTH_BUCKETS)],
		['>', '<', '>', '<', '>']))

	# ---- timeline ---------------------------------------------------------
	md += _mdTimeline(s.favDayCounts, s.favMonthCounts, 'favorites', 'Starred something')

	# ---- categories -------------------------------------------------------
	md.append("## Where they come from")
	md.append('')
	catRows = []
	for category, favs in s.categoryFav.most_common():
		total = s.categoryAll[category]
		catRows.append((category, f"{favs:,}", f"{total:,}", f"{_pct(favs, total):.1f}%",
		                f"{_pct(favs, s.favCount):.0f}%"))
	md += _block(_table(['category', 'fav', 'all', 'rate', 'share'], catRows,
	                    ['<', '>', '>', '>', '>']))

	# ---- recent, with real links -----------------------------------------
	md += _mdRecent(s.favorites[:RECENT_HIGHLIGHTS], "## Most recently starred")
	md += _mdFooter(reportPath,
	                f"every one of your {s.favCount:,} favorites, grouped by source, each "
	                f"linking straight to Readwise, plus the calendar in colour.")
	return '\n'.join(md)


def buildLibraryMarkdown(s, reportPath):
	md = []
	md.append("# 📚 Your Readwise library")
	md.append('')
	md.append(f"**{s.total:,}** highlights from **{len(s.books):,}** sources by "
	          f"**{len(s.authorAll):,}** authors.")
	span = ''
	if s.libFirstDay and s.libLastDay:
		years = (s.libLastDay - s.libFirstDay).days / 365.25
		perYear = f" · about {s.total / years:,.0f} a year" if years >= 1 else ''
		span = f"{s.libFirstDay:%d %b %Y} → {s.libLastDay:%d %b %Y}{perYear} · "
	md.append(f"{span}**{s.favCount:,}** starred ({s.baseRate:.1f}%)")
	md.append('')

	if not s.total:
		md.append("There is nothing in the local database yet — run the refresh keyword "
		          "and come back.")
		return '\n'.join(md)

	# ---- what is actually yours -------------------------------------------
	if s.suppCount:
		md.append(f"**{s.ownCount:,} of those are your own** "
		          f"({_share(_pct(s.ownCount, s.total))}). The other "
		          f"**{s.suppCount:,}** ({_share(_pct(s.suppCount, s.total))}) are "
		          f"**supplementals**.")
		md.append('')
		md.append("## Your own highlights vs supplementals")
		md.append('')
		md.append(_SUPPLEMENTAL_NOTE)
		md.append('')
		md += _block(_table(['', 'yours', 'supplementals'], _splitRows(s),
		                    ['<', '>', '>']))
		if _authorsOverlap(s):
			md.append(_OVERLAP_NOTE)
			md.append('')

	# ---- authors ----------------------------------------------------------
	md.append("## Authors")
	md.append('')
	md.append(f"`n` highlights · `supp` how many of those are supplementals · `share` "
	          f"of the whole library · `chars` their mean highlight length · `vs lib` "
	          f"against your library-wide {_mean(s.allChars):,.0f} · `fav` how many you "
	          f"starred.")
	md.append('')
	# plain-ASCII column headings on purpose: an emoji is two cells wide in a
	# monospace font, which throws out every column to its right
	md += _block(_table(
		['author', 'n', 'supp', 'share', 'chars', 'vs lib', 'fav'],
		[(a, f"{n:,}", f"{supp:,}", _share(sh), f"{mean:,.0f}", f"×{lift:.2f}", f"{fav:,}")
		 for a, n, supp, sh, mean, lift, fav in _libAuthorRows(s, TOP_AUTHORS)],
		['<', '>', '>', '>', '>', '>', '>']))
	md.append(f"Your top 10 authors account for **{_concentration(s.authorAll, s.total):.0f}%** "
	          f"of the library; the top 50 for "
	          f"**{_concentration(s.authorAll, s.total, 50):.0f}%**.")
	md.append('')

	# ---- sources ----------------------------------------------------------
	md.append("## Most highlighted sources")
	md.append('')
	md += _block(_table(
		['source', 'author', 'type', 'n', 'fav'],
		[(_trim(title, 40), _trim(author, 22), _shortCategory(category), f"{n:,}", f"{fav:,}")
		 for _, title, author, category, n, fav, _ in _sourceRows(s, TOP_SOURCES)],
		['<', '<', '<', '>', '>']))

	# ---- length -----------------------------------------------------------
	md.append("## Length")
	md.append('')
	md += _block(_table(
		['', 'characters', 'words'],
		[('mean', f"{_mean(s.allChars):,.0f}", f"{_mean(s.allWords):,.0f}"),
		 ('median', f"{_median(s.allChars):,.0f}", f"{_median(s.allWords):,.0f}"),
		 ('longest', f"{max(s.allChars):,}", f"{max(s.allWords):,}"),
		 ('shortest', f"{min(s.allChars):,}", f"{min(s.allWords):,}"),
		 ('total', f"{sum(s.allChars):,}", f"{sum(s.allWords):,}")],
		['<', '>', '>']))

	buckets = _lengthBuckets(s.allChars)
	bucketTotal = sum(buckets) or 1
	widest = max(_pct(b, bucketTotal) for b in buckets)
	md.append("Distribution, by characters:")
	md.append('')
	md += _block(_table(
		['chars', '', '%', 'n'],
		[(label, _bar(_pct(buckets[i], bucketTotal), widest, 22),
		  f"{_pct(buckets[i], bucketTotal):.0f}%", f"{buckets[i]:,}")
		 for i, (_, _, label) in enumerate(_LENGTH_BUCKETS)],
		['>', '<', '>', '>']))

	# ---- timeline ---------------------------------------------------------
	md += _mdTimeline(s.libDayCounts, s.libMonthCounts, 'highlights', 'Highlighted something')

	# ---- categories -------------------------------------------------------
	md.append("## Where they come from")
	md.append('')
	md.append("`chars` mean length in that category, `vs lib` against the library average, "
	          "`fav` the share of it you starred.")
	md.append('')
	md += _block(_table(
		['category', 'n', 'share', 'chars', 'vs lib', 'fav'],
		[(c, f"{n:,}", f"{sh:.0f}%", f"{mean:,.0f}", f"×{lift:.2f}", f"{rate:.1f}%")
		 for c, n, sh, mean, lift, _, rate in _categoryRows(s)],
		['<', '>', '>', '>', '>', '>']))

	# ---- recent, with real links -----------------------------------------
	md += _mdRecent(s.recent)
	md += _mdFooter(reportPath,
	                "the calendar in colour, every author and every source, and the full "
	                "length breakdown. The highlights themselves are not listed: at "
	                f"{s.total:,} of them the page would be enormous — the favorites "
	                "report is where the quotes live.")
	return '\n'.join(md)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light dark;
  --bg: #fbfaf8; --panel: #ffffff; --ink: #1c1a17; --muted: #6f6a62;
  --line: #e6e1d8; --accent: #d81b60; --accent-soft: #fce4ec;
  --l0: #ecebe7; --l1: #ffd6e0; --l2: #ff9ebb; --l3: #f4638e; --l4: #d81b60;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14120f; --panel: #1d1a17; --ink: #ece7de; --muted: #9c948a;
    --line: #322d27; --accent: #f4638e; --accent-soft: #3a1626;
    --l0: #26221e; --l1: #4a1526; --l2: #7d1f3d; --l3: #b32a57; --l4: #f4638e;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 40px 24px 96px; }
h1 { font-size: 30px; margin: 0 0 6px; letter-spacing: -0.02em; }
h2 { font-size: 20px; margin: 44px 0 14px; letter-spacing: -0.01em; }
h3 { font-size: 15px; margin: 26px 0 10px; color: var(--muted); font-weight: 600;
     text-transform: uppercase; letter-spacing: 0.06em; }
p.lede { color: var(--muted); margin: 0 0 28px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.tile .n { font-size: 26px; font-weight: 650; letter-spacing: -0.02em; }
.tile .k { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th { font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); font-weight: 600; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tablewrap { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
.meter { display: block; height: 7px; border-radius: 4px; background: var(--accent); min-width: 2px; }
.meter.soft { background: var(--accent-soft); }
/* a bar column has no text to size it, so it would otherwise collapse to the
   width of a 2px meter and every bar would look identical */
td.bar, th.bar { width: 20%; min-width: 80px; }
/* supplementals are not passages you marked, so they are called out rather than
   left to blend into the counts beside them. A badge rather than coloured text:
   the accent is also the link colour, and "supplementals" in a table cell would
   otherwise read as something to click. */
.suppmark { display: inline-block; padding: 1px 8px; border-radius: 20px;
  background: var(--accent-soft); color: var(--accent); font-weight: 600;
  font-size: 12px; white-space: nowrap; }
.tile.own { border-color: var(--accent); }
.tile.supp { background: var(--accent-soft); border-color: var(--accent); }
.tile.supp .k { color: var(--accent); }
.cal { overflow-x: auto; padding-bottom: 6px; }
.cal table { border-collapse: separate; border-spacing: 3px; width: auto; }
.cal td, .cal th { padding: 0; border: 0; }
.cal .day { width: 11px; height: 11px; border-radius: 2px; background: var(--l0); }
.cal .lv1 { background: var(--l1); } .cal .lv2 { background: var(--l2); }
.cal .lv3 { background: var(--l3); } .cal .lv4 { background: var(--l4); }
.cal .empty { background: transparent; }
.cal .mon { font-size: 10px; color: var(--muted); text-align: left; }
.cal .dow { font-size: 10px; color: var(--muted); padding-right: 4px; white-space: nowrap; }
.calhead { display: flex; justify-content: space-between; align-items: baseline; margin: 22px 0 6px; }
.calhead .y { font-weight: 650; }
.calhead .c { color: var(--muted); font-size: 13px; }
.legend { display: flex; gap: 5px; align-items: center; color: var(--muted); font-size: 12px; margin-top: 8px; }
.legend i { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
#filter { width: 100%; padding: 10px 12px; font-size: 15px; border-radius: 9px;
  border: 1px solid var(--line); background: var(--panel); color: var(--ink); margin: 6px 0 20px; }
.src { margin: 0 0 22px; padding: 16px 18px; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px; }
.src > h4 { margin: 0 0 2px; font-size: 16px; }
.src > .by { margin: 0 0 12px; color: var(--muted); font-size: 13px; }
.hl { margin: 0; padding: 9px 0 9px 14px; border-left: 3px solid var(--accent-soft); }
.hl + .hl { border-top: 1px solid var(--line); }
.hl .t { margin: 0 0 5px; white-space: pre-wrap; }
.hl .m { font-size: 12px; color: var(--muted); }
.hl .m a { white-space: nowrap; }
.tag { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 20px;
  background: var(--accent-soft); color: var(--accent); margin-right: 5px; }
footer { margin-top: 60px; color: var(--muted); font-size: 12px;
  border-top: 1px solid var(--line); padding-top: 16px; }
.none { color: var(--muted); font-style: italic; }
</style>
</head>
<body>
<div class="wrap">
"""

_HTML_TAIL = """</div>
<script>
(function () {
  var box = document.getElementById('filter');
  if (!box) return;
  var sources = Array.prototype.slice.call(document.querySelectorAll('.src'));
  var empty = document.getElementById('noresults');
  box.addEventListener('input', function () {
    var q = box.value.trim().toLowerCase();
    var shown = 0;
    sources.forEach(function (src) {
      var any = false;
      Array.prototype.forEach.call(src.querySelectorAll('.hl'), function (hl) {
        var hit = !q || hl.dataset.s.indexOf(q) !== -1;
        hl.style.display = hit ? '' : 'none';
        if (hit) any = true;
      });
      // a source whose own title matches keeps all of its highlights
      var titleHit = q && src.dataset.s.indexOf(q) !== -1;
      if (titleHit) {
        Array.prototype.forEach.call(src.querySelectorAll('.hl'), function (hl) {
          hl.style.display = '';
        });
        any = true;
      }
      src.style.display = any ? '' : 'none';
      if (any) shown++;
    });
    empty.style.display = shown ? 'none' : '';
  });
})();
</script>
</body>
</html>
"""


def _esc(text):
	return html.escape(text or '', quote=True)


def _htmlHead(title):
	return _HTML_HEAD.replace('__TITLE__', _esc(title))


def _htmlCalendars(dayCounts, monthCounts, heading, noun):
	"""Colour calendars plus the by-month table: identical for both reports."""
	out = [f'<h2>{heading}</h2>']
	if not dayCounts:
		out.append('<p class="none">No usable creation dates.</p>')
		return out
	thresholds = _thresholds(dayCounts.values())
	out.append('<div class="legend">less'
	           + ''.join(f'<i style="background:var(--l{i})"></i>' for i in range(5))
	           + 'more <span style="margin-left:10px">'
	           + _esc('(' + ', '.join(_bands(thresholds)[1:]) + f' {noun} per day)')
	           + '</span></div>')
	for year in sorted({d.year for d in dayCounts}, reverse=True):
		out.append(_htmlCalendar(year, dayCounts, thresholds, noun))

	if monthCounts:
		months = sorted(monthCounts, reverse=True)[:24]
		# scaled against the months on show, not against an all-time peak that may
		# be years off the bottom of the table
		peak = max(monthCounts[k] for k in months)
		out.append('<h3>The last two years, by month</h3>')
		out.append(_htmlTable(
			['month', '', noun],
			[(f"{datetime(y, m, 1):%B %Y}", _meter(monthCounts[(y, m)], peak),
			  f"{monthCounts[(y, m)]:,}") for (y, m) in months],
			{2}, bars={1}))
	return out


def _htmlFooter(s, generated, note):
	return (f'<footer>alfred-readwise · {note} · '
	        f'generated {generated:%Y-%m-%d %H:%M}</footer>')


def _htmlCalendar(year, dayCounts, thresholds, noun):
	"""One year of the contribution calendar as an HTML grid."""
	from datetime import date as _date
	first, last = _date(year, 1, 1), _date(year, 12, 31)
	today = datetime.now().date()
	if last > today:
		last = today
	start = first - timedelta(days=(first.weekday() + 1) % 7)
	weeks = ((last - start).days // 7) + 1
	total = sum(c for d, c in dayCounts.items() if d.year == year)

	out = [f'<div class="calhead"><span class="y">{year}</span>'
	       f'<span class="c">{total:,} {noun}</span></div>',
	       '<div class="cal"><table><tr><td></td>']
	# month labels, one cell per week column
	lastMonth = None
	written = -99
	for w in range(weeks):
		# the first column opens on the Sunday before 1 January, which belongs to
		# the previous December; clamp, or every year would be labelled "Dec"
		day = max(start + timedelta(days=w * 7), first)
		label = ''
		if day.month != lastMonth and day <= last:
			lastMonth = day.month
			# a three-letter name is wider than one 14px column, so give it three
			# to itself rather than letting two months overprint each other
			if w - written >= 3:
				label = day.strftime('%b')
				written = w
		out.append(f'<td class="mon">{label}</td>')
	out.append('</tr>')

	labels = {1: 'Mon', 3: 'Wed', 5: 'Fri'}
	for r in range(7):
		out.append(f'<tr><td class="dow">{labels.get(r, "")}</td>')
		for w in range(weeks):
			day = start + timedelta(days=w * 7 + r)
			if day < first or day > last:
				out.append('<td><div class="day empty"></div></td>')
				continue
			count = dayCounts.get(day, 0)
			level = _level(count, thresholds)
			title = f"{count} on {day:%d %b %Y}" if count else f"{day:%d %b %Y}"
			out.append(f'<td><div class="day lv{level}" title="{title}"></div></td>')
		out.append('</tr>')
	out.append('</table></div>')
	return '\n'.join(out)


def _htmlTable(headers, rows, numeric, bars=frozenset()):
	def cls(i):
		return 'n' if i in numeric else ('bar' if i in bars else '')

	out = ['<div class="tablewrap"><table><tr>']
	for i, h in enumerate(headers):
		out.append(f'<th class="{cls(i)}">{_esc(h)}</th>')
	out.append('</tr>')
	for row in rows:
		out.append('<tr>')
		for i, cell in enumerate(row):
			out.append(f'<td class="{cls(i)}">{cell}</td>')
		out.append('</tr>')
	out.append('</table></div>')
	return '\n'.join(out)


def _suppCell(supp, total):
	"""How much of a row is Readwise's rather than yours.

	Called out when it is most of the row: that is the case where the count beside
	it says more about what Readwise attached to a book than about what you read.
	"""
	if not supp:
		return '—'
	share = _pct(supp, total)
	cls = ' class="suppmark"' if share >= 50 else ''
	return f'<span{cls}>{supp:,} ({share:.0f}%)</span>'


def _categoryCell(category):
	return (f'<span class="suppmark">{_esc(category)}</span>'
	        if category == SUPPLEMENTAL else _esc(category))


def _meter(value, maximum, soft=False):
	"""A bar scaled against the largest value in its own table.

	Scaling against 100% instead would leave every bar a sliver in a table whose
	biggest number is 5%, which tells the reader nothing.
	"""
	width = max(2.0, 100.0 * value / maximum) if maximum > 0 and value > 0 else 0
	return f'<span class="meter{" soft" if soft else ""}" style="width:{width:.0f}%"></span>'


def _tagNames(raw):
	"""Tag names on a highlight, using the shared parser when it is importable."""
	try:
		from readwise_fun import _parseTagField
	except Exception:
		return []
	try:
		return sorted(set(_parseTagField(raw)))
	except Exception:
		return []


def buildFavoritesHTML(s):
	out = [_htmlHead('Readwise favorites')]
	generated = datetime.now()
	out.append('<h1>❤️ Readwise favorites</h1>')
	span = ''
	if s.favFirstDay and s.favLastDay:
		span = f"{s.favFirstDay:%d %B %Y} – {s.favLastDay:%d %B %Y}. "
	out.append(f'<p class="lede">{span}Generated {generated:%d %B %Y, %H:%M} '
	           f'by the alfred-readwise workflow.</p>')

	out.append('<div class="tiles">')
	for value, key in [
		(f"{s.favCount:,}", "favorites"),
		(f"{s.baseRate:.1f}%", "of the library"),
		(f"{len(s.favBooks):,}", f"sources (of {len(s.books):,})"),
		(f"{len(s.authorFav):,}", f"authors (of {len(s.authorAll):,})"),
		(f"{_mean(s.favChars):,.0f}", "mean characters"),
		(f"{len(s.favDayCounts):,}", "active days"),
	]:
		out.append(f'<div class="tile"><div class="n">{value}</div><div class="k">{key}</div></div>')
	out.append('</div>')

	if not s.favCount:
		out.append('<p class="none">No favorites in your library yet.</p>')
		out.append(_HTML_TAIL)
		return ''.join(out)

	# ---- calendars --------------------------------------------------------
	out += _htmlCalendars(s.favDayCounts, s.favMonthCounts, 'When you starred them', 'favorites')

	# ---- authors ----------------------------------------------------------
	out.append('<h2>Authors, against the rest of your library</h2>')
	out.append(f'<p class="lede">You star <strong>{s.baseRate:.1f}%</strong> of everything '
	           f'you highlight. “×” is how much more often than that you starred this author.</p>')
	# a single starred highlight from an author you have one highlight from reads
	# as "100%, ×18.6", which is arithmetic rather than taste; those go in the
	# count at the foot of the table instead of adding a hundred rows to it
	listed = [a for a in _authorRows(s, len(s.authorFav)) if a[1] >= MIN_AUTHOR_FAVORITES]
	hidden = len(s.authorFav) - len(listed)
	peak = max((a[3] for a in listed), default=1)
	rows = [(_esc(author), f"{favs:,}", f"{total:,}", f"{rate:.1f}%",
	         _meter(rate, peak), f"×{lift:.1f}")
	        for author, favs, total, rate, lift in listed]
	out.append(_htmlTable(['author', 'favorites', 'all highlights', 'rate', '', 'vs library'],
	                      rows, {1, 2, 3, 5}, bars={4}))
	if hidden:
		out.append(f'<p class="lede">…and {hidden:,} more authors with a single favorite '
		           f'each. All of them appear in the list of highlights below.</p>')

	# ---- length -----------------------------------------------------------
	out.append('<h2>Length</h2>')
	rows = [
		('mean characters', f"{_mean(s.favChars):,.0f}", f"{_mean(s.restChars):,.0f}",
		 f"{_mean(s.allChars):,.0f}"),
		('median characters', f"{_median(s.favChars):,.0f}", f"{_median(s.restChars):,.0f}",
		 f"{_median(s.allChars):,.0f}"),
		('mean words', f"{_mean(s.favWords):,.0f}", f"{_mean(s.restWords):,.0f}",
		 f"{_mean(s.allWords):,.0f}"),
		('median words', f"{_median(s.favWords):,.0f}", f"{_median(s.restWords):,.0f}",
		 f"{_median(s.allWords):,.0f}"),
		('longest', f"{max(s.favChars):,}", f"{max(s.restChars):,}" if s.restChars else '—',
		 f"{max(s.allChars):,}"),
		('shortest', f"{min(s.favChars):,}", f"{min(s.restChars):,}" if s.restChars else '—',
		 f"{min(s.allChars):,}"),
	]
	out.append(_htmlTable(['', 'favorites', 'rest of library', 'whole library'], rows, {1, 2, 3}))

	favBuckets = _lengthBuckets(s.favChars)
	restBuckets = _lengthBuckets(s.restChars)
	favTotal, restTotal = sum(favBuckets) or 1, sum(restBuckets) or 1
	out.append('<h3>Distribution</h3>')
	rows = []
	widest = max(max(_pct(b, favTotal) for b in favBuckets),
	             max(_pct(b, restTotal) for b in restBuckets))
	for i, (_, _, label) in enumerate(_LENGTH_BUCKETS):
		fp, rp = _pct(favBuckets[i], favTotal), _pct(restBuckets[i], restTotal)
		rows.append((label, _meter(fp, widest), f"{fp:.0f}%",
		             _meter(rp, widest, soft=True), f"{rp:.0f}%"))
	out.append(_htmlTable(['characters', 'favorites', '%', 'rest of library', '%'],
	                      rows, {2, 4}, bars={1, 3}))

	# ---- categories -------------------------------------------------------
	out.append('<h2>Where they come from</h2>')
	rows = []
	for category, favs in s.categoryFav.most_common():
		total = s.categoryAll[category]
		rows.append((_esc(category), f"{favs:,}", f"{total:,}", f"{_pct(favs, total):.1f}%",
		             f"{_pct(favs, s.favCount):.0f}%"))
	out.append(_htmlTable(['category', 'favorites', 'all', 'rate', 'share of favorites'],
	                      rows, {1, 2, 3, 4}))

	# ---- every highlight --------------------------------------------------
	out.append(f'<h2>All {s.favCount:,} favorites</h2>')
	out.append('<input id="filter" type="search" placeholder="Filter by text, author or title…" '
	           'autocomplete="off">')

	bySource = defaultdict(list)
	for r in s.favorites:
		bySource[r['user_book_id']].append(r)
	# most-starred source first, so the page opens on what you loved most
	for bookID in sorted(bySource, key=lambda b: (-len(bySource[b]),
	                                              (bySource[b][0]['title'] or '').lower())):
		items = bySource[bookID]
		head = items[0]
		title = (head['title'] or 'Untitled').strip()
		author = (head['author'] or 'Unknown').strip()
		bookURL = head['readwise_url'] or ''
		heading = f'<a href="{_esc(bookURL)}">{_esc(title)}</a>' if bookURL else _esc(title)
		blob = _esc(f"{title} {author}".lower())
		out.append(f'<div class="src" data-s="{blob}">')
		out.append(f'<h4>{heading}</h4>')
		out.append(f'<p class="by">{_esc(author)} · {len(items)} favorite'
		           f'{"s" if len(items) != 1 else ""} · {_esc(head["category"] or "")}</p>')
		for r in items:
			text = (r['highText'] or '').strip()
			day = _localDay(r['high_created_at'])
			meta = []
			if r['high_readwise_url']:
				meta.append(f'<a href="{_esc(r["high_readwise_url"])}">open in Readwise</a>')
			sourceURL = r['source_url'] or r['highURL'] or ''
			if sourceURL:
				meta.append(f'<a href="{_esc(sourceURL)}">source</a>')
			if day:
				meta.append(f"{day:%d %b %Y}")
			meta.append(f"{len(text):,} characters")
			tags = ''.join(f'<span class="tag">{_esc(t)}</span>' for t in _tagNames(r['highTags']))
			search = _esc(' '.join(text.lower().split()))
			out.append(f'<div class="hl" data-s="{search}">'
			           f'<p class="t">{_esc(text)}</p>'
			           f'<div class="m">{tags}{" · ".join(meta)}</div></div>')
		out.append('</div>')
	out.append('<p class="none" id="noresults" style="display:none">Nothing matches that filter.</p>')

	out.append(_htmlFooter(s, generated,
	                       f'{s.favCount:,} favorites out of {s.total:,} highlights'))
	out.append(_HTML_TAIL)
	return '\n'.join(out)


def buildLibraryHTML(s):
	"""The whole library, on the same axes as the favorites page.

	Deliberately without the highlights themselves: listing several thousand
	passages would make a page many megabytes heavy for no gain -- searching
	them is what the workflow's main keyword is for, and the favorites page
	already carries the ones worth re-reading.
	"""
	out = [_htmlHead('Readwise library')]
	generated = datetime.now()
	out.append('<h1>📚 Your Readwise library</h1>')
	span = ''
	if s.libFirstDay and s.libLastDay:
		span = f"{s.libFirstDay:%d %B %Y} – {s.libLastDay:%d %B %Y}. "
	out.append(f'<p class="lede">{span}Generated {generated:%d %B %Y, %H:%M} '
	           f'by the alfred-readwise workflow.</p>')

	out.append('<div class="tiles">')
	for value, key, mark in [
		(f"{s.total:,}", "highlights", ''),
		(f"{s.ownCount:,}", f"your own ({_share(_pct(s.ownCount, s.total))})", ' own'),
		(f"{s.suppCount:,}", f"supplementals ({_share(_pct(s.suppCount, s.total))})", ' supp'),
		(f"{len(s.books):,}", "sources", ''),
		(f"{len(s.authorAll):,}", "authors", ''),
		(f"{s.favCount:,}", f"starred ({s.baseRate:.1f}%)", ''),
		(f"{_mean(s.allChars):,.0f}", "mean characters", ''),
		(f"{len(s.libDayCounts):,}", "active days", ''),
	]:
		out.append(f'<div class="tile{mark}"><div class="n">{value}</div>'
		           f'<div class="k">{key}</div></div>')
	out.append('</div>')

	if not s.total:
		out.append('<p class="none">The local database has no highlights in it yet.</p>')
		out.append(_HTML_TAIL)
		return '\n'.join(out)

	# ---- what is actually yours -------------------------------------------
	if s.suppCount:
		out.append('<h2>Your own highlights vs supplementals</h2>')
		out.append(f'<p class="lede">{_esc(_SUPPLEMENTAL_NOTE)}</p>')
		out.append(_htmlTable(['', 'yours', 'supplementals'], _splitRows(s), {1, 2}))
		if _authorsOverlap(s):
			out.append(f'<p class="lede">{_esc(_OVERLAP_NOTE)}</p>')

	# ---- calendars --------------------------------------------------------
	out += _htmlCalendars(s.libDayCounts, s.libMonthCounts,
	                      'When you highlighted', 'highlights')

	# ---- authors ----------------------------------------------------------
	libMean = _mean(s.allChars)
	out.append('<h2>Authors</h2>')
	out.append(f'<p class="lede">Your top 10 authors account for '
	           f'<strong>{_concentration(s.authorAll, s.total):.0f}%</strong> of the library, '
	           f'the top 50 for <strong>{_concentration(s.authorAll, s.total, 50):.0f}%</strong>. '
	           f'“×” compares their mean highlight length with your library-wide '
	           f'{libMean:,.0f} characters.</p>')
	listed = [a for a in _libAuthorRows(s) if a[1] >= MIN_AUTHOR_HIGHLIGHTS]
	hidden = len(s.authorAll) - len(listed)
	peak = max((a[1] for a in listed), default=1)
	out.append(_htmlTable(
		['author', 'highlights', '', 'supplemental', 'share', 'mean chars',
		 'vs library', 'starred'],
		[(_esc(a), f"{n:,}", _meter(n, peak), _suppCell(supp, n), _share(sh),
		  f"{mean:,.0f}", f"×{lift:.2f}", f"{fav:,}")
		 for a, n, supp, sh, mean, lift, fav in listed],
		{1, 3, 4, 5, 6, 7}, bars={2}))
	if hidden:
		out.append(f'<p class="lede">…and {hidden:,} more authors you have a single '
		           f'highlight from.</p>')

	# ---- sources ----------------------------------------------------------
	out.append('<h2>Sources</h2>')
	sources = [r for r in _sourceRows(s) if r[4] >= MIN_AUTHOR_HIGHLIGHTS]
	hiddenSources = len(s.books) - len(sources)
	peak = max((r[4] for r in sources), default=1)
	rows = [((f'<a href="{_esc(url)}">{_esc(title)}</a>' if url else _esc(title)),
	         _esc(author), _categoryCell(category), f"{n:,}", _meter(n, peak), f"{fav:,}")
	        for _, title, author, category, n, fav, url in sources]
	out.append(_htmlTable(['source', 'author', 'category', 'highlights', '', 'starred'],
	                      rows, {3, 5}, bars={4}))
	if hiddenSources > 0:
		out.append(f'<p class="lede">…and {hiddenSources:,} more sources you have a single '
		           f'highlight from.</p>')

	# ---- length -----------------------------------------------------------
	out.append('<h2>Length</h2>')
	out.append(_htmlTable(
		['', 'characters', 'words'],
		[('mean', f"{_mean(s.allChars):,.0f}", f"{_mean(s.allWords):,.0f}"),
		 ('median', f"{_median(s.allChars):,.0f}", f"{_median(s.allWords):,.0f}"),
		 ('longest', f"{max(s.allChars):,}", f"{max(s.allWords):,}"),
		 ('shortest', f"{min(s.allChars):,}", f"{min(s.allWords):,}"),
		 ('total', f"{sum(s.allChars):,}", f"{sum(s.allWords):,}")],
		{1, 2}))

	buckets = _lengthBuckets(s.allChars)
	bucketTotal = sum(buckets) or 1
	widest = max(_pct(b, bucketTotal) for b in buckets)
	out.append('<h3>Distribution</h3>')
	out.append(_htmlTable(
		['characters', '', '%', 'highlights'],
		[(label, _meter(_pct(buckets[i], bucketTotal), widest),
		  f"{_pct(buckets[i], bucketTotal):.0f}%", f"{buckets[i]:,}")
		 for i, (_, _, label) in enumerate(_LENGTH_BUCKETS)],
		{2, 3}, bars={1}))

	# ---- categories -------------------------------------------------------
	out.append('<h2>Where they come from</h2>')
	peak = max((c[1] for c in _categoryRows(s)), default=1)
	out.append(_htmlTable(
		['category', 'highlights', '', 'share', 'mean chars', 'vs library', 'starred'],
		[(_esc(c), f"{n:,}", _meter(n, peak), _share(sh), f"{mean:,.0f}",
		  f"×{lift:.2f}", f"{fav:,} ({rate:.1f}%)")
		 for c, n, sh, mean, lift, fav, rate in _categoryRows(s)],
		{1, 3, 4, 5, 6}, bars={2}))

	out.append(f'<p class="lede">The highlights themselves are not listed here — at '
	           f'{s.total:,} of them this page would be enormous. Search them with the '
	           f'workflow\'s main keyword, or open the favorites report for the '
	           f'{s.favCount:,} you starred.</p>')
	out.append(_htmlFooter(s, generated,
	                       f'{s.total:,} highlights from {len(s.books):,} sources'))
	out.append(_HTML_TAIL)
	return '\n'.join(out)


def writeReport(html_text, path):
	folder = os.path.dirname(path)
	if folder and not os.path.exists(folder):
		os.makedirs(folder)
	with open(path, 'w', encoding='utf-8') as fh:
		fh.write(html_text)
	return path


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

# The two reports differ only in which builders they call, which file they write
# and what they are called, so they are described here rather than branched on
# throughout.
REPORTS = {
	'favorites': {
		'title': '❤️ Favorite highlights',
		'path': FAV_REPORT,
		'markdown': buildFavoritesMarkdown,
		'html': buildFavoritesHTML,
		'empty': lambda s: not s.favCount,
		'emptyfooter': 'nothing starred yet',
	},
	'library': {
		'title': '📚 Your Readwise library',
		'path': LIB_REPORT,
		'markdown': buildLibraryMarkdown,
		'html': buildLibraryHTML,
		'empty': lambda s: not s.total,
		'emptyfooter': 'nothing in the database yet',
	},
}


def _emit(markdown, footer, path):
	print(json.dumps({
		"response": markdown,
		"footer": footer,
		# the report path travels onward as a variable so ↩ can open the file, and
		# the Markdown itself so ⌘↩ can copy it. Both reports use the same two
		# names, so they can share one pair of actions in the workflow.
		"variables": {
			"statsReportPath": path,
			"statsReportMarkdown": markdown,
		},
		"behaviour": {"response": "replace", "scroll": "start"},
	}))


def main():
	which = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'favorites'
	report = REPORTS.get(which)
	if report is None:
		log(f"unknown report '{which}', falling back to favorites")
		report = REPORTS['favorites']
	title, path = report['title'], report['path']

	if not os.path.exists(MY_DATABASE):
		_emit(f"# {title}\n\nYour library has not been downloaded yet.\n\n"
		      "Run the refresh keyword (`readwise:refresh` by default) first, then "
		      "come back.", "no database yet", path)
		return

	db = sqlite3.connect(MY_DATABASE)
	try:
		s = gather(db)
	except sqlite3.OperationalError as e:
		log(f"{which} report: {e}")
		_emit(f"# {title}\n\nNo highlights table in the local database.\n\n"
		      "These reports read your Readwise **highlights**; if you have the workflow "
		      "set to Reader only, run a rebuild with highlights included first.",
		      "no highlights in the database", path)
		return
	finally:
		db.close()

	try:
		writeReport(report['html'](s), path)
		# with nothing to report there is no report to promise
		footer = ("↩ open the full HTML report   ·   ⌘↩ copy this summary"
		          if not report['empty'](s) else report['emptyfooter'])
	except Exception as e:
		# the summary is still worth showing even if the file could not be written
		log(f"could not write the HTML report: {e}")
		footer = "⌘↩ copy this summary (the HTML report could not be written)"

	_emit(report['markdown'](s, path), footer, path)


if __name__ == '__main__':
	main()
