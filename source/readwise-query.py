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


from config import TOKEN, ARTICLES_CHECK,BOOKS_CHECK, TWEETS_CHECK, PODCASTS_CHECK, SUPPLEMENTALS_CHECK, log, MY_DATABASE, RefRate, IMAGE_FOLDER, SEARCH_SCOPE
from readwise_fun import refreshReadwiseDatabase, makeLabelList
MYINPUT = sys.argv[1].casefold()
my_checks = {'books': BOOKS_CHECK, 'articles': ARTICLES_CHECK, 'tweets': TWEETS_CHECK, 'podcasts': PODCASTS_CHECK, 'supplementals': SUPPLEMENTALS_CHECK}



def checkingTime ():
## Checking if the database needs to be built or rebuilt
    timeToday = date.today()
    if not os.path.exists(MY_DATABASE):
        log ("Database missing ... building")
        refreshReadwiseDatabase()
        makeLabelList()
    else: 
        databaseTime= (int(os.path.getmtime(MY_DATABASE)))
        dt_obj = datetime.fromtimestamp(databaseTime).date()
        time_elapsed = (timeToday-dt_obj).days
        log (str(time_elapsed)+" days from last update")
        if time_elapsed >= RefRate:
            log ("rebuilding database ⏳...")
            refreshReadwiseDatabase()
            makeLabelList()
            log ("done 👍")
            



def queryItems(database, myInput):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    myCounter = 0
    types = [k for k, v in my_checks.items() if v == '1']
    myTypes = ','.join('?'*len(types))

    # getting list of tags from the database
    tag_statement = "SELECT name FROM tags"
    tag_rows = db.execute(tag_statement).fetchall()
    tagList = [row[0] for row in tag_rows]
    tagList = ['#' + s for s in tagList]

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
        

    # check if the user is trying to enter a tag
    MYMATCH = re.search(r'(?:^| )#[^ ]*$', myInput)
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

        
        
        keywords = mySearchInput.split()
        if len(keywords) > 1:
            conditions = []
            conditions2 = []
            for keyword in keywords:
                if SEARCH_SCOPE == "Text":
                    conditions.append(f"(highText LIKE '%{keyword}%')")
                    conditions_str = " AND ".join(conditions)
            
        
                elif SEARCH_SCOPE == "Book":
                    conditions.append(f"(title LIKE '%{keyword}%')")
                    conditions_str = " AND ".join(conditions)
            
                elif SEARCH_SCOPE == "Both":
                    conditions.append(f"(highText LIKE '%{keyword}%')")
                    conditions1_str = " AND ".join(conditions)
                    conditions2.append(f"(title LIKE '%{keyword}%')")
                    conditions2_str = " AND ".join(conditions2)
                    conditions_str = f'({conditions1_str}) OR ({conditions2_str})' 
            
                    
        else: 
            if SEARCH_SCOPE == "Text":
                conditions_str = f"(highText LIKE '%{mySearchInput}%')"
                    
    
            elif SEARCH_SCOPE == "Book":
                conditions_str = f"(title LIKE '%{mySearchInput}%')"
                
            elif SEARCH_SCOPE == "Both":
                conditions_str = f"(highText LIKE '%{mySearchInput}%' or title LIKE '%{mySearchInput}%')"
    
    
        sql = f"SELECT * FROM highlights WHERE {conditions_str} and category IN ({myTypes}) {tag_sql}"
        log (sql)
        
        rs = db.execute(sql, types).fetchall()
        totCount = len(rs)


        for r in rs:
            myCounter += 1
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
            
            result["items"].append({
                "title": r['highText'],
                
                'subtitle': f"{myCounter}/{totCount} {r['title']}-{r['author']} {myTags}",
                'valid': True,
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
        
    print (json.dumps(result))
    
    	
        
        


def main():
    checkingTime()
    queryItems (MY_DATABASE, MYINPUT)
    
    

if __name__ == '__main__':
    main ()
