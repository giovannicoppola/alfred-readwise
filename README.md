# alfred-readwise
## An Alfred Workflow for your [Readwise](https://readwise.io/) account
<a href="https://github.com/giovannicoppola/alfred-readwise/releases/latest/">
<img alt="Downloads"
src="https://img.shields.io/github/downloads/giovannicoppola/alfred-readwise/total?color=purple&label=Downloads"><br/>
</a>
<a href="https://alfred.app/workflows/giovannicoppola/readwise/">
<img alt="Gallery Downloads"
src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fgiovannicoppola%2Falfred-gallery-downloads%2Fmain%2Fdownloads.json&query=%24.readwise%5B0%5D.display&label=Gallery%20Downloads&color=blue&logo=alfred"><br/>
</a>

![](images/alfred-readwise.png)

![](images/alfred-readwise.gif)

<!-- MarkdownTOC autolink="true" bracket="round" depth="3" autoanchor="true" -->

- [Motivation](#motivation)
- [Setting up](#setting-up)
- [Basic Usage](#usage)
- [Known Issues](#known-issues)
- [Acknowledgments](#acknowledgments)
- [Changelog](#changelog)
- [Feedback](#feedback)

<!-- /MarkdownTOC -->


<h1 id="motivation">Motivation ✅</h1>

- Quickly list, search, and open your Readwise highlights
- Add new highlights to your account through Alfred



<h1 id="setting-up">Setting up ⚙️</h1>

### Needed
- Alfred 5 with Powerpack license
- A [Readwise](https://readwise.io) license
- Python3 (howto [here](https://www.freecodecamp.org/news/python-version-on-mac-update/))
- Download `alfred-readwise` [latest release](https://github.com/giovannicoppola/alfred-readwise/releases/latest)



## Default settings 
- In Alfred, open the 'Configure Workflow' menu in `alfred-readwise` preferences
	- set the keyword for the workflow (default: `!r`)
	- set the keyword to force refresh (default: `readwise:refresh`) — syncs only what changed
	- set the keyword for a full rebuild (default: `readwise:rebuild`) — downloads everything again
	- set the Readwise API token (login into your account, then copy it [here](https://readwise.io/access_token))
	- set what to show in results: `books`, `tweets`, `supplementals`, `articles`, `podcasts`
	- set refresh rate (in days). Default: `30`
	- set 'book' name from highlights entered via Alfred. Default: `Highlights from Alfred`
	- set search scope. This applies to **Readwise highlights** only — Reader documents are always searched by title, author and site name, since those are how you look for an article:
		- `Main` (default): search the highlight text only
		- `Include metadata`: also search the book title and author. Note that an author match returns every highlight from that book.


<h1 id="usage">Basic Usage 📖</h1>

## Searching your Readwise database 🔍
- launch with keyword (default: `!r`), or custom hotkey
- standard search will be through highlight text and book titles. Multiple word (fragments) supported
- typing `#` will prompt a label search which can be added to the standard search, multiple labels supported
- type `--reader` or `--readwise` to restrict results to that platform for the current query
	- `enter` ↩️ will show the highlight in large font and copy to clipboard
	- `shift-enter` ⇧↩️ will show the highlight in large font and copy to clipboard without closing Alfred
	- `command-enter` ⌘↩️ will open the source URL if available (typically for tweets)
	- `ctrl-enter` ^↩️ will open the highlight on Readwise
	- `shift-ctrl-enter` ⇧^↩️ will open all highlights from that book on Readwise
	- `shift` alone: Quicklook of your highlight.


## Entering new highlights ⭐
- Universal Action: new highlights can be created by selecting text in any app, then launching Universal Actions and selecting `Create a new Readwise highlight`. The corresponding text will be assigned to a 'book' titled as set in `alfred-readwise` preferences (default: `Highlights from Alfred`).


## Database refresh 🔄
- will occur according to the rate in days set in `alfred-readwise` preferences, or...
	- `readwise:refresh` — sync just what changed since the last run. This is normally near-instant, because it asks the API only for highlights and documents updated since then.
	- `readwise:rebuild` — download everything again from scratch. Slower (minutes for a large library, as the API rate-limits long syncs), but it is the only way to remove highlights you deleted in Readwise, since an incremental sync cannot see deletions. This also runs automatically every 30 days.


<h1 id="known-issues">Limitations & known issues ⚠️</h1>

- None for now, but I have not done extensive testing, let me know if you see anything!



<h1 id="acknowledgments">Acknowledgments 😀</h1>

- Thanks to the [Alfred forum](https://www.alfredforum.com) community!
- Icons: 
	- https://www.iconarchive.com/show/multipurpose-alphabet-icons-by-hydrattz/Letter-R-violet-icon.html
	- https://www.flaticon.com/free-icon/book_3145755?term=book&related_id=3145755
	- https://www.flaticon.com/free-icon/podcast_2628834?term=podcast&page=1&position=8&origin=search&related_id=2628834
	- https://www.flaticon.com/free-icon/twitter_3670151?term=tweet&page=1&position=3&origin=search&related_id=3670151
	- https://www.flaticon.com/free-icon/additional_9710962?term=additional&page=1&position=12&origin=search&related_id=9710962
	- https://www.flaticon.com/free-icon/tags_1374863?term=label&page=1&position=19&origin=search&related_id=1374863
	- https://www.flaticon.com/free-icon/checkbox_1168610?term=done&page=1&position=18&origin=search&related_id=1168610
	- https://www.flaticon.com/free-icon/operating-system_10294204?term=update&page=1&position=30&origin=search&related_id=10294204

<h1 id="changelog">Changelog 🧰</h1>

### New in version 0.4

**Readwise Reader support** 📖
- New `Search Platform` setting: search **Readwise highlights** (default), **Readwise Reader**, or both
- Type `--reader` or `--readwise` anywhere in a query to restrict results to one platform, whatever the setting says
- Reader documents are matched on title, author and site name. `SEARCH_SCOPE` now applies to highlights only
- On a Reader document, <kbd>^</kbd><kbd>↩</kbd> opens the document in Reader and <kbd>⌘</kbd><kbd>↩</kbd> opens the original article — the same way <kbd>⌘</kbd><kbd>↩</kbd> opens the source of a highlight
- New `Open Reader documents in` setting: `Browser` (default) or `Reader app`. Only relevant when Reader documents are in your results, and it falls back to the browser if the app isn't installed
- Reader results include the summary and notes in the text view

**Much faster refreshes** ⚡
- A refresh now syncs only what changed instead of downloading your whole library each time. On a library of ~5,800 highlights and ~4,700 Reader documents this took a refresh from **2m05s to under a second**
- New `readwise:rebuild` keyword for a from-scratch rebuild, which is the only way to drop highlights deleted in Readwise. It also runs automatically every 30 days

**Fixes** 🕷️
- A refresh could never finish: hitting Readwise's rate limit retried forever, and because the search rebuilt a missing Reader table on every keystroke, each keystroke started another sync that rate-limited the others
- Searching for a word containing an apostrophe failed instead of returning results
- TLS certificate verification is enabled again on both API calls
- Highlights created from Alfred were saved without their text, so they could never be found; they are now searchable straight away, with a QuickLook preview
- A missing `PIL`/Pillow module no longer stops the workflow — see the note on QuickLook previews below
- Books with no cover art show the workflow icon instead of a blank placeholder
- A blank refresh-rate field no longer crashes every script on startup
- API error handling with rate-limit retry and timeouts

> **A note on QuickLook previews.** <kbd>⌘</kbd><kbd>Y</kbd> on a highlight shows a typeset preview, but that needs the Python **Pillow** library, which is *not* bundled with the workflow — unlike `requests`, Pillow ships compiled code that cannot be vendored for both Apple Silicon and Intel from one copy. Without it the workflow runs normally and simply shows no preview. To enable them: `pip3 install --user Pillow`. Previews are being reworked to drop the dependency entirely — see [#5](https://github.com/giovannicoppola/alfred-readwise/issues/5).

- 04-04-2023: version 0.1


<h1 id="feedback">Feedback 🧐</h1>

Feedback welcome! If you notice a bug, or have ideas for new features, please feel free to get in touch either here, or on the [Alfred](https://www.alfredforum.com) forum. 
