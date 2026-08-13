""" 
Readwise query
part of the alfred-readwise workflow
Light rain, mist 🌦   🌡️+56°F (feels +52°F, 72%) 🌬️↗7mph 🌔&m Sat Apr  1 20:43:15 2023
W13Q2 – 91 ➡️ 273 – 325 ❇️ 39

"""
import sys
import os
import json
from datetime import datetime, date
import sqlite3
import re
import contextlib


from config import TOKEN, ARTICLES_CHECK,BOOKS_CHECK, TWEETS_CHECK, PODCASTS_CHECK, SUPPLEMENTALS_CHECK, log, MY_DATABASE, RefRate, IMAGE_FOLDER, IMAGE_H_FOLDER, SEARCH_SCOPE, SEARCH_PLATFORM
from readwise_fun import refreshReadwiseDatabase, makeLabelList, refreshReaderDatabase, rebuildLock, inCooldown, startCooldown, clearCooldown
MYINPUT = sys.argv[1].casefold()
my_checks = {'books': BOOKS_CHECK, 'articles': ARTICLES_CHECK, 'tweets': TWEETS_CHECK, 'podcasts': PODCASTS_CHECK, 'supplementals': SUPPLEMENTALS_CHECK}



log(f"SEARCH_PLATFORM = '{SEARCH_PLATFORM}'")
SEARCH_READWISE = SEARCH_PLATFORM in ("Readwise highlights", "Readwise")
SEARCH_READER = SEARCH_PLATFORM in ("Readwise Reader", "Readwise")
log(f"SEARCH_READWISE = {SEARCH_READWISE}, SEARCH_READER = {SEARCH_READER}")

def refreshAll():
    ok = True
    if SEARCH_READWISE:
        ok = refreshReadwiseDatabase() and ok
        # only worth rebuilding the tag list if the highlights sync actually landed
        if ok:
            makeLabelList()
    if SEARCH_READER:
        ok = refreshReaderDatabase() and ok
    return ok

def guardedRefresh(what, fn):
    """Run a refresh only if no other one is in progress and we are not cooling down.

    This runs from the script filter, i.e. on every keystroke, so it must never
    start a second concurrent sync and must back off after a failure rather than
    retrying on the next character typed.
    """
    if inCooldown():
        log(f"{what}: skipped, a recent refresh failed (cooling down)")
        return
    with rebuildLock() as acquired:
        if not acquired:
            log(f"{what}: skipped, another refresh is already running")
            return
        try:
            # a failed sync does not raise -- it reports False -- so the cooldown has
            # to be driven by the return value, otherwise a persistently failing sync
            # is retried on every single keystroke
            if fn() is False:
                log(f"{what}: did not complete, backing off")
                startCooldown()
            else:
                clearCooldown()
        except Exception as e:
            log(f"{what}: failed: {e}")
            startCooldown()

def checkingTime ():
## Checking if the database needs to be built or rebuilt
    timeToday = date.today()
    if not os.path.exists(MY_DATABASE):
        log ("Database missing ... building")
        guardedRefresh("initial build", refreshAll)
    else:
        # Check if reader_documents table needs to be created or updated
        if SEARCH_READER:
            readerTableOK = True
            # closing() matters: the probe raising is the expected path, and this runs
            # on every keystroke, so a leaked connection per keystroke adds up
            try:
                with contextlib.closing(sqlite3.connect(MY_DATABASE)) as db:
                    db.execute("SELECT summary FROM reader_documents LIMIT 1")
            except Exception:
                readerTableOK = False
            if not readerTableOK:
                log("Reader table missing or outdated ... rebuilding")
                guardedRefresh("Reader table build", refreshReaderDatabase)

        databaseTime= (int(os.path.getmtime(MY_DATABASE)))
        dt_obj = datetime.fromtimestamp(databaseTime).date()
        time_elapsed = (timeToday-dt_obj).days
        log (str(time_elapsed)+" days from last update")
        if time_elapsed >= RefRate:
            # must go through guardedRefresh like every other refresh site: the database
            # mtime is not touched until the sync commits, so while a slow sync runs
            # every new keystroke would otherwise see it as still stale and start
            # another concurrent one
            log ("rebuilding database ⏳...")
            guardedRefresh("scheduled refresh", refreshAll)
            log ("done 👍")
            



def queryItems(database, myInput):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    myCounter = 0
    types = [k for k, v in my_checks.items() if v == '1']
    myTypes = ','.join('?'*len(types))

    def likeParam(term):
        """Build a LIKE pattern matching `term` anywhere, with wildcards escaped.

        Search terms are user input, so they are always bound as parameters rather
        than interpolated into the SQL. Escaping % and _ keeps them literal, and
        the backslash is the ESCAPE character declared on every LIKE below.
        """
        escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        return f"%{escaped}%"

    search_readwise = SEARCH_READWISE
    search_reader = SEARCH_READER
    if '--reader' in myInput:
        search_readwise = False
        search_reader = True
        myInput = myInput.replace('--reader', '').strip()
    elif '--readwise' in myInput:
        search_readwise = True
        search_reader = False
        myInput = myInput.replace('--readwise', '').strip()
    log(f"Inline filter: search_readwise={search_readwise}, search_reader={search_reader}")

    # getting list of tags from the database (only relevant for Readwise highlights)
    tagList = []
    if search_readwise:
        try:
            tag_statement = "SELECT name FROM tags"
            tag_rows = db.execute(tag_statement).fetchall()
            tagList = ['#' + row[0] for row in tag_rows]
        except Exception as e:
            log(f"Tags query failed: {e}")

    #initializing JSON output
    result = {"items": [], "variables":{}}
    mySearchInput = myInput.strip()

    # extracting any full tags from current input, adding them to the sql query
    fullTags = re.findall('#[^ ]+ ', myInput)
    fullTags = [s.strip() for s in fullTags]

    tag_sql = ""
    tag_params = []
    for currTag  in fullTags:
        if currTag.strip() in tagList: #if it is a real tag
            mySearchInput = re.sub(currTag, '', mySearchInput).strip()
            currTag = currTag[1:].strip()
            tag_sql = f"{tag_sql} AND highTags LIKE ? ESCAPE '\\'"
            tag_params.append(likeParam(currTag))


    # check if the user is trying to enter a tag (only for Readwise mode)
    MYMATCH = re.search(r'(?:^| )#[^ ]*$', myInput) if search_readwise else None
    if (MYMATCH !=None):

        MYFLAG = MYMATCH.group(0).lstrip(' ')
        mySearchInput = re.sub(MYFLAG,'',myInput)
        myInput = re.sub(MYFLAG,'',myInput)

        mySubset = [i for i in tagList if MYFLAG in i]

        # adding a complete tag if the user selects it from the list
        if mySubset:
            for thislabel in mySubset:
                result["items"].append({
                "title": thislabel,
                "subtitle": myInput,
                "arg": myInput+thislabel+" ",
                "icon": {
                        "path": f"icons/label.png"
                    }
                })
        else:
            result["items"].append({
            "title": "no labels matching",
            "subtitle": "try another query?",
            "arg": " ",
            "icon": {
                    "path": f"icons/Warning.png"
                }
            })


    else:

        totalResults = 0

        # Search Readwise highlights
        if search_readwise:
            if SEARCH_SCOPE == "All":
                rw_columns = ["highText", "title", "author"]
            else:
                rw_columns = ["highText"]

            keywords = mySearchInput.split()
            kw_params = []
            if keywords:
                kw_clauses = []
                for kw in keywords:
                    col_matches = [f"{col} LIKE ? ESCAPE '\\'" for col in rw_columns]
                    kw_clauses.append(f"({' OR '.join(col_matches)})")
                    kw_params.extend([likeParam(kw)] * len(rw_columns))
                conditions_str = " AND ".join(kw_clauses)
            else:
                conditions_str = "1=1"

            sql = f"SELECT * FROM highlights WHERE ({conditions_str}) and category IN ({myTypes}) {tag_sql}"
            log (sql)

            # parameter order must follow the placeholders: keywords, then categories, then tags
            rs = db.execute(sql, kw_params + types + tag_params).fetchall()
            totCount = len(rs)

            for r in rs:
                myCounter += 1
                totalResults += 1
                myURL = r['high_readwise_url']
                myURLall = r['readwise_url']
                myTags = ''
                if r['highTags'] != "[]":
                    myTags = json.loads (r['highTags'].replace("'", '"'))
                    myTags = ",".join ([x['name'] for x in myTags])
                    myTags = f"🏷️ {myTags}"
                    if r['high_is_favorite'] == 1:
                        myTags = myTags+'❤️'

                if r['highURL']:
                    sourceURLstring = f"open source URL"
                else:
                    sourceURLstring = "no source URL"
                myQuickLook = f"{IMAGE_H_FOLDER}{r['highID']}.jpg"
                result["items"].append({
                    "title": r['highText'],
                    'subtitle': f"{myCounter}/{totCount} {r['title']}-{r['author']} {myTags}",
                    'valid': True,
                    "quicklookurl": myQuickLook,
                    'variables': {
                        "fullOutput": f"> {r['highText']}\n\n— *{r['author']}*: **{r['title']}**",
                        "myURL": myURL,
                        "myStatus": 'completed',
                        "myURLall": myURLall
                    },
                    "mods": {
                        "command": {
                            "valid": 'true',
                            "subtitle": f"{sourceURLstring}",
                            "arg": r['highURL']
                        }},
                    "icon": {
                        "path": f"{IMAGE_FOLDER}{r['user_book_id']}.jpg"
                    },
                    'arg': ''
                        })

        # Search Reader documents.
        # Author and site name are always searched here, unlike highlights, where the
        # scope setting still applies. A Reader document is a whole article, so its
        # author and source are how you look for it ("that piece by X", "something on
        # Y"); matching them cannot flood the results the way an author match on a
        # book does, which would pull in every highlight from it.
        if search_reader:
            reader_columns = ["title", "author", "site_name"]

            keywords = mySearchInput.split()
            reader_params = []
            if keywords:
                kw_clauses = []
                for kw in keywords:
                    col_matches = [f"{col} LIKE ? ESCAPE '\\'" for col in reader_columns]
                    kw_clauses.append(f"({' OR '.join(col_matches)})")
                    reader_params.extend([likeParam(kw)] * len(reader_columns))
                reader_conditions = " AND ".join(kw_clauses)
            else:
                reader_conditions = "1=1"

            reader_sql = f"SELECT * FROM reader_documents WHERE {reader_conditions} ORDER BY updated_at DESC"
            log(reader_sql)

            try:
                reader_rs = db.execute(reader_sql, reader_params).fetchall()
            except Exception as e:
                log(f"Reader query failed (table may not exist yet): {e}")
                reader_rs = []

            readerCount = len(reader_rs)
            readerCounter = 0

            for r in reader_rs:
                readerCounter += 1
                totalResults += 1

                subtitle = f"📖 Reader {readerCounter}/{readerCount}"
                if r['author']:
                    subtitle += f" — {r['author']}"
                if r['category']:
                    subtitle += f" [{r['category']}]"

                openURL = r['source_url'] or r['url'] or ''
                urlText = "open in browser" if openURL else "no URL"

                title = r['title'] or '(no title)'
                fullParts = [f"## {title}"]
                author = r['author'] or ''
                if author:
                    fullParts.append(f"*{author}*")
                try:
                    if r['summary']:
                        fullParts.append(f"> {r['summary']}")
                    if r['notes']:
                        fullParts.append(f"**Notes:** {r['notes']}")
                except (IndexError, KeyError):
                    pass
                fullOutput = "\n\n".join(fullParts)

                result["items"].append({
                    "title": r['title'] or '(no title)',
                    'subtitle': subtitle,
                    'valid': True,
                    'variables': {
                        "fullOutput": fullOutput,
                        "myURL": r['url'] or '',
                        "myStatus": 'completed',
                    },
                    "mods": {
                        "ctrl": {
                            "valid": 'true',
                            "subtitle": urlText,
                            "arg": openURL
                        }},
                    'arg': ''
                        })

        if MYINPUT and totalResults == 0:
            result["items"].append({
                "title": "No matches in your library",
                "subtitle": "Try a different query",
                "arg": "",
                "icon": {
                    "path": "icons/Warning.png"
                    }
                    })
        
    print (json.dumps(result))
    
    	
        
        


def main():
    checkingTime()
    queryItems (MY_DATABASE, MYINPUT)
    
    

if __name__ == '__main__':
    main ()
