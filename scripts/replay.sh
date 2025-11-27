#!/bin/bash

LOGFILE="15.log"
BASE_URL="http://localhost:12345"

# Extract JSON payloads
mapfile -t PAYLOADS < <(grep '^{.*}$' "$LOGFILE")

index=0
last_sent_index=-1

send_request() {
    local payload="$1"
    echo "----- Sending request #$((index+1)) -----"
    curl -s -X POST "$BASE_URL/card" \
         -H "Content-Type: application/json; charset=utf-8" \
         -H "User-Agent: okhttp/4.9.1" \
         -d "$payload"
    echo -e "\n----------------------------------------"
}

while true; do
    echo -n "[Enter/n] next, p previous, q quit > "
    read -r cmd

    case "$cmd" in
        ""|n)
            # Next request
            if (( index >= ${#PAYLOADS[@]} )); then
                echo "No more requests."
                exit 0
            fi
            send_request "${PAYLOADS[$index]}"
            last_sent_index=$index
            ((index++))
            ;;
        p)
            # Previous request
            if (( last_sent_index < 0 )); then
                echo "No previous request to resend."
            else
                send_request "${PAYLOADS[$last_sent_index]}"
            fi
            ;;
        q)
            echo "Quit."
            exit 0
            ;;
        *)
            echo "Unknown command."
            ;;
    esac
done
