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
import shutil
import requests
import urllib.request
from config import MY_DATABASE, TOKEN, log, IMAGE_FOLDER


def refreshReadwiseDatabase ():
	full_data = []
	next_page_cursor = None
	while True:
		params = {}
		if next_page_cursor:
			params['pageCursor'] = next_page_cursor
		log ("Making export api request with params " + str(params) + "...")
		
		response = requests.get(
			url="https://readwise.io/api/v2/export/",
			params=params,
			headers={"Authorization": f"Token {TOKEN}"}, verify=False
		)
		full_data.extend(response.json()['results'])
		next_page_cursor = response.json().get('nextPageCursor')
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
	
	
	
	db.commit()
	
	#retrieving all the images
	select_statement = "SELECT user_book_id, cover_image_url FROM highlights"
	
	c.execute(select_statement)

	rs = c.fetchall()
	
	for rec in rs:
		if rec[1]:
			ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
			if not os.path.exists(ICON_PATH):
				log ("retrieving image" + ICON_PATH)
				try:
					urllib.request.urlretrieve(rec[1], ICON_PATH)
				except urllib.error.URLError as e:
				    # If an exception occurs, print an error message and delete the file if it exists
					log(f"Failed to download file: {e.reason}")
					ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
					src = 'icons/supplementals.png'
					shutil.copy(src, ICON_PATH)

		else:
			ICON_PATH = f'{IMAGE_FOLDER}{rec[0]}.jpg'
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