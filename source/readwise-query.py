"""
Readwise query
part of the alfred-readwise workflow
"""
import sys
import os
import json
from datetime import datetime, date
import sqlite3
import re


from config import ARTICLES_CHECK, BOOKS_CHECK, TWEETS_CHECK, PODCASTS_CHECK, SUPPLEMENTALS_CHECK, log, MY_DATABASE, RefRate, IMAGE_FOLDER, IMAGE_H_FOLDER, SEARCH_SCOPE
from readwise_fun import refreshReadwiseDatabase, makeLabelList, parse_tags

MYINPUT = sys.argv[1].casefold() if len(sys.argv) > 1 else ""
my_checks = {'books': BOOKS_CHECK, 'articles': ARTICLES_CHECK, 'tweets': TWEETS_CHECK, 'podcasts': PODCASTS_CHECK, 'supplementals': SUPPLEMENTALS_CHECK}


def errorItem(title, subtitle):
    return {
        "title": title,
        "subtitle": subtitle,
        "valid": False,
        "icon": {"path": "icons/Warning.png"},
    }


def checkingTime():
    ## Checking if the database needs to be built or rebuilt.
    ## Returns an error message if the database is missing and cannot be built.
    timeToday = date.today()
    if not os.path.exists(MY_DATABASE):
        log("Database missing ... building")
        try:
            refreshReadwiseDatabase()
            makeLabelList()
        except Exception as e:
            log(f"build failed: {e}")
            return str(e)
    else:
        databaseTime = int(os.path.getmtime(MY_DATABASE))
        dt_obj = datetime.fromtimestamp(databaseTime).date()
        time_elapsed = (timeToday - dt_obj).days
        log(str(time_elapsed) + " days from last update")
        if time_elapsed >= RefRate:
            log("rebuilding database ⏳...")
            try:
                refreshReadwiseDatabase()
                makeLabelList()
                log("done 👍")
            except Exception as e:
                # keep searching the stale database rather than failing
                log(f"refresh failed, using cached database: {e}")
                os.utime(MY_DATABASE)  # don't retry on every keystroke
    return None


def likeParam(term):
    """LIKE pattern matching the term anywhere, with wildcards escaped."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def buildConditions(keywords, scope):
    """SQL condition + parameters for the current search scope."""
    if not keywords:
        return "1=1", []
    text_sql = " AND ".join(["highText LIKE ? ESCAPE '\\'"] * len(keywords))
    title_sql = " AND ".join(["title LIKE ? ESCAPE '\\'"] * len(keywords))
    params = [likeParam(k) for k in keywords]
    if scope == "Text":
        return f"({text_sql})", params
    if scope == "Book":
        return f"({title_sql})", params
    return f"(({text_sql}) OR ({title_sql}))", params + params


def queryItems(database, myInput):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    myCounter = 0
    types = [k for k, v in my_checks.items() if v == '1']
    myTypes = ','.join('?' * len(types))

    # getting list of tags from the database
    tag_statement = "SELECT name FROM tags"
    tag_rows = db.execute(tag_statement).fetchall()
    tagList = [row[0] for row in tag_rows]
    tagList = ['#' + s for s in tagList]

    # initializing JSON output
    result = {"items": [], "variables": {}}
    mySearchInput = myInput.strip()

    # extracting any full tags from current input, adding them to the sql query
    fullTags = [s.strip() for s in re.findall('#[^ ]+ ', myInput)]

    tag_conditions = []
    tag_params = []
    for currTag in fullTags:
        if currTag in tagList:  # if it is a real tag
            mySearchInput = mySearchInput.replace(currTag, '').strip()
            tag_conditions.append("highTags LIKE ? ESCAPE '\\'")
            tag_params.append(likeParam(currTag[1:]))

    # check if the user is trying to enter a tag
    MYMATCH = re.search(r'(?:^| )#[^ ]*$', myInput)
    if MYMATCH is not None:

        MYFLAG = MYMATCH.group(0).lstrip(' ')
        myInput = myInput.replace(MYFLAG, '')

        mySubset = [i for i in tagList if MYFLAG in i]

        # adding a complete tag if the user selects it from the list
        if mySubset:
            for thislabel in mySubset:
                result["items"].append({
                    "title": thislabel,
                    "subtitle": myInput,
                    "arg": myInput + thislabel + " ",
                    "icon": {
                        "path": "icons/label.png"
                    }
                })
        else:
            result["items"].append({
                "title": "no labels matching",
                "subtitle": "try another query?",
                "arg": " ",
                "icon": {
                    "path": "icons/Warning.png"
                }
            })

    else:

        conditions_str, params = buildConditions(mySearchInput.split(), SEARCH_SCOPE)

        sql = f"SELECT * FROM highlights WHERE {conditions_str} and category IN ({myTypes})"
        all_params = params + types
        if tag_conditions:
            sql += " AND " + " AND ".join(tag_conditions)
            all_params += tag_params
        log(sql)

        try:
            rs = db.execute(sql, all_params).fetchall()
        except sqlite3.Error as e:
            log(f"database error: {e}")
            result["items"].append(errorItem(
                "Database error", "Try rebuilding with the refresh keyword"
            ))
            print(json.dumps(result))
            return
        totCount = len(rs)

        for r in rs:
            myCounter += 1
            myURL = r['high_readwise_url']
            myURLall = r['readwise_url']
            myTags = ''
            tags = parse_tags(r['highTags'])
            if tags:
                myTags = "🏷️ " + ",".join(x['name'] for x in tags)
            if r['high_is_favorite'] == 1:
                myTags = myTags + '❤️'

            if r['highURL']:
                sourceURLstring = "open source URL"
            else:
                sourceURLstring = "no source URL"
            myQuickLook = f"{IMAGE_H_FOLDER}{r['highID']}.jpg"
            result["items"].append({
                "title": r['highText'],

                'subtitle': f"{myCounter}/{totCount} {r['title']}-{r['author']} {myTags}",
                'valid': True,
                "quicklookurl": myQuickLook,
                'variables': {
                    "fullOutput": f"{r['highText']}\n\n{r['author']}: {r['title']}",
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

        if MYINPUT and not rs:
            result["items"].append({
                "title": "No matches in your library",
                "subtitle": "Try a different query",
                "arg": "",
                "icon": {
                    "path": "icons/Warning.png"
                }

            })

    print(json.dumps(result))


def main():
    error = checkingTime()
    if error:
        print(json.dumps({"items": [errorItem("Could not build the Readwise database", error)]}))
        return
    queryItems(MY_DATABASE, MYINPUT)


if __name__ == '__main__':
    main()
