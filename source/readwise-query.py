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


from config import TOKEN, ARTICLES_CHECK,BOOKS_CHECK, TWEETS_CHECK, PODCASTS_CHECK, SUPPLEMENTALS_CHECK, log, MY_DATABASE, RefRate, IMAGE_FOLDER, IMAGE_H_FOLDER, SEARCH_SCOPE, SEARCH_PLATFORM
from readwise_fun import refreshReadwiseDatabase, makeLabelList, refreshReaderDatabase
MYINPUT = sys.argv[1].casefold()
my_checks = {'books': BOOKS_CHECK, 'articles': ARTICLES_CHECK, 'tweets': TWEETS_CHECK, 'podcasts': PODCASTS_CHECK, 'supplementals': SUPPLEMENTALS_CHECK}



log(f"SEARCH_PLATFORM = '{SEARCH_PLATFORM}'")
SEARCH_READWISE = SEARCH_PLATFORM in ("Readwise highlights", "Readwise")
SEARCH_READER = SEARCH_PLATFORM in ("Readwise Reader", "Readwise")
log(f"SEARCH_READWISE = {SEARCH_READWISE}, SEARCH_READER = {SEARCH_READER}")

def refreshAll():
    if SEARCH_READWISE:
        refreshReadwiseDatabase()
        makeLabelList()
    if SEARCH_READER:
        refreshReaderDatabase()

def checkingTime ():
## Checking if the database needs to be built or rebuilt
    timeToday = date.today()
    if not os.path.exists(MY_DATABASE):
        log ("Database missing ... building")
        refreshAll()
    else:
        # Check if reader_documents table needs to be created
        if SEARCH_READER:
            try:
                db = sqlite3.connect(MY_DATABASE)
                db.execute("SELECT 1 FROM reader_documents LIMIT 1")
                db.close()
            except Exception:
                log("Reader table missing ... building")
                refreshReaderDatabase()

        databaseTime= (int(os.path.getmtime(MY_DATABASE)))
        dt_obj = datetime.fromtimestamp(databaseTime).date()
        time_elapsed = (timeToday-dt_obj).days
        log (str(time_elapsed)+" days from last update")
        if time_elapsed >= RefRate:
            log ("rebuilding database ⏳...")
            refreshAll()
            log ("done 👍")
            



def queryItems(database, myInput):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    myCounter = 0
    types = [k for k, v in my_checks.items() if v == '1']
    myTypes = ','.join('?'*len(types))

    # getting list of tags from the database (only relevant for Readwise highlights)
    tagList = []
    if SEARCH_READWISE:
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
    for currTag  in fullTags:
        if currTag.strip() in tagList: #if it is a real tag
            mySearchInput = re.sub(currTag, '', mySearchInput).strip()
            currTag = currTag[1:].strip()
            tag_sql = f"{tag_sql} AND highTags LIKE '%{currTag}%'"


    # check if the user is trying to enter a tag (only for Readwise mode)
    MYMATCH = re.search(r'(?:^| )#[^ ]*$', myInput) if SEARCH_READWISE else None
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
        if SEARCH_READWISE:
            if SEARCH_SCOPE == "All":
                rw_columns = ["highText", "title", "author"]
            else:
                rw_columns = ["highText"]

            keywords = mySearchInput.split()
            if keywords:
                kw_clauses = []
                for kw in keywords:
                    col_matches = [f"{col} LIKE '%{kw}%'" for col in rw_columns]
                    kw_clauses.append(f"({' OR '.join(col_matches)})")
                conditions_str = " AND ".join(kw_clauses)
            else:
                conditions_str = "1=1"

            sql = f"SELECT * FROM highlights WHERE ({conditions_str}) and category IN ({myTypes}) {tag_sql}"
            log (sql)

            rs = db.execute(sql, types).fetchall()
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

        # Search Reader documents
        if SEARCH_READER:
            if SEARCH_SCOPE == "All":
                reader_columns = ["title", "author", "site_name"]
            else:
                reader_columns = ["title"]

            keywords = mySearchInput.split()
            if keywords:
                kw_clauses = []
                for kw in keywords:
                    col_matches = [f"{col} LIKE '%{kw}%'" for col in reader_columns]
                    kw_clauses.append(f"({' OR '.join(col_matches)})")
                reader_conditions = " AND ".join(kw_clauses)
            else:
                reader_conditions = "1=1"

            reader_sql = f"SELECT * FROM reader_documents WHERE {reader_conditions} ORDER BY updated_at DESC"
            log(reader_sql)

            try:
                reader_rs = db.execute(reader_sql).fetchall()
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

                result["items"].append({
                    "title": r['title'],
                    'subtitle': subtitle,
                    'valid': True,
                    'variables': {
                        "fullOutput": r['title'],
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
