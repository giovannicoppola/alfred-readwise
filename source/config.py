#!/usr/bin/env python3

"""
CONFIG SCRIPT for the alfred-readwise Workflow
"""


import os
import sys

def log(s, *args):
    if args:
        s = s % args
    print(s, file=sys.stderr)


TOKEN = os.getenv('READWISE_TOKEN')
ARTICLES_CHECK = os.getenv('ARTICLES_CHECK')
TWEETS_CHECK = os.getenv('TWEETS_CHECK')
BOOKS_CHECK = os.getenv('BOOKS_CHECK')
PODCASTS_CHECK = os.getenv('PODCASTS_CHECK')
SUPPLEMENTALS_CHECK = os.getenv('SUPPLEMENTALS_CHECK')
NEW_HIGH_TITLE = os.getenv('NEW_HIGH_TITLE')
SEARCH_SCOPE = os.getenv('SEARCH_SCOPE')


WF_BUNDLE = os.getenv('alfred_workflow_bundleid')
DATA_FOLDER = os.getenv('alfred_workflow_data')
MY_DATABASE = f"{DATA_FOLDER}/readwise.db"
IMAGE_FOLDER = f"{DATA_FOLDER}/images/"
IMAGE_H_FOLDER = f"{DATA_FOLDER}/images_H/"
RefRate = int(os.getenv('RefreshRate'))

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

if not os.path.exists(IMAGE_H_FOLDER):
    os.makedirs(IMAGE_H_FOLDER)
