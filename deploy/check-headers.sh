#!/bin/sh
# NT-09: the headers NFR-11 requires, read from the running proxy.
set -eu

base_url="${1:-http://localhost:8080}"
headers=$(curl --silent --head "$base_url/")

for required in Content-Security-Policy X-Content-Type-Options Referrer-Policy X-Frame-Options; do
    if ! printf '%s' "$headers" | grep --quiet --ignore-case "^$required:"; then
        echo "Missing header: $required"
        exit 1
    fi
    echo "Found: $required"
done
