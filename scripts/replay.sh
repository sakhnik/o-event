#!/bin/bash

LOGFILE="15.log"
BASE_URL="http://localhost:12345"

# Extract JSON payloads (lines starting with '{') and POST them
grep '^{.*}$' "$LOGFILE" | while read -r payload; do
    curl -s -X POST "$BASE_URL/card" \
         -H "Content-Type: application/json; charset=utf-8" \
         -H "User-Agent: okhttp/4.9.1" \
         -d "$payload"
    echo   # newline between requests
done
