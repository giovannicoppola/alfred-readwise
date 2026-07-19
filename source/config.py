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


def _getenv(name, default=""):
    value = os.getenv(name)
    return value if value not in (None, "") else default


TOKEN = os.getenv('READWISE_TOKEN')
# Checkboxes export '1'/'0'; treat a missing variable as checked so a stale
# prefs.plist doesn't silently hide every result
ARTICLES_CHECK = _getenv('ARTICLES_CHECK', '1')
TWEETS_CHECK = _getenv('TWEETS_CHECK', '1')
BOOKS_CHECK = _getenv('BOOKS_CHECK', '1')
PODCASTS_CHECK = _getenv('PODCASTS_CHECK', '1')
SUPPLEMENTALS_CHECK = _getenv('SUPPLEMENTALS_CHECK', '1')
NEW_HIGH_TITLE = _getenv('NEW_HIGH_TITLE', 'Highlights from Alfred')
SEARCH_SCOPE = _getenv('SEARCH_SCOPE', 'Both')

try:
    RefRate = int(_getenv('RefreshRate', '30'))
except ValueError:
    RefRate = 30

WF_BUNDLE = os.getenv('alfred_workflow_bundleid')
# Fall back to the conventional location so the scripts also run from a terminal
DATA_FOLDER = _getenv(
    'alfred_workflow_data',
    os.path.expanduser(
        '~/Library/Application Support/Alfred/Workflow Data/alfred-readwise'
    ),
)
MY_DATABASE = f"{DATA_FOLDER}/readwise.db"
IMAGE_FOLDER = f"{DATA_FOLDER}/images/"
IMAGE_H_FOLDER = f"{DATA_FOLDER}/images_H/"

for folder in (DATA_FOLDER, IMAGE_FOLDER, IMAGE_H_FOLDER):
    os.makedirs(folder, exist_ok=True)
