# alfred-readwise
## An Alfred Workflow for your [Readwise](https://readwise.io/) account
<a href="https://github.com/giovannicoppola/alfred-readwise/releases/latest/">
<img alt="Downloads"
src="https://img.shields.io/github/downloads/giovannicoppola/alfred-readwise/total?color=purple&label=Downloads"><br/>
</a>

![](images/alfred-readwise.png)

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
	- set the keyword to force refresh (default: `readwise:refresh`)
	- set the Readwise API token (login into your account, then copy it [here](https://readwise.io/access_token))
	- set what to show in results: `books`, `tweets`, `supplementals`, `articles`, `podcasts`
	- set refresh rate (in days). Default: `30`
	- set 'book' name from highlights entered via Alfred. Default: `Highlights from Alfred`
	- set search scope:
		- `Highlight`: search highlight text only
		- `Book`: search book titles only
		- `Both` (default): search across highlights and book titles


<h1 id="usage">Basic Usage 📖</h1>

## Searching your Readwise database 🔍
- launch with keyword (default: `!r`), or custom hotkey
- standard search will be through highlight text and book titles. Multiple word (fragments) supported
- typing `#` will prompt a label search which can be added to the standard search, multiple labels supported
	- `enter` ↩️ will show the highlight in large font and copy to clipboard
	- `command-enter` ⌘↩️ will open the source URL if available (typically for tweets)
	- `ctrl-enter` ^↩️ will open the highlight on Readwise
	- `shift-ctrl-enter` ⇧^↩️ will open all highlights from that book on Readwise


## Entering new highlights ⭐
- Universal Action: new highlights can be created by selecting text in any app, then launching Universal Actions and selecting `Create a new Readwise highlight`. The corresponding text will be assigned to a 'book' titled as set in `alfred-readwise` preferences (default: `Highlights from Alfred`).


## Database refresh 🔄
- will occur according to the rate in days set in `alfred-readwise` preferences, or...
	- `readwise:refresh` to force database refresh


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

- 04-04-2023: version 0.1


<h1 id="feedback">Feedback 🧐</h1>

Feedback welcome! If you notice a bug, or have ideas for new features, please feel free to get in touch either here, or on the [Alfred](https://www.alfredforum.com) forum. 
