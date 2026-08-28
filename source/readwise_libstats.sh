#!/bin/bash
# Script source for the library Text View. Alfred runs it from the workflow
# folder and reads the Text View JSON it prints on stdout.
export PYTHONPATH="$PWD/lib"
/usr/bin/python3 readwise_stats.py library
