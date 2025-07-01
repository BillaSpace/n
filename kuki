#!/bin/bash

# Make the script executable (self-executing on first run)
chmod +x "$0" 2>/dev/null

# URL of the cookies.txt file
URL="https://v0-mongo-db-api-setup.vercel.app/api/cookies.txt"

# Directory to save the file
OUTPUT_DIR="cookies"
OUTPUT_FILE="$OUTPUT_DIR/cookies.txt"

# Create the directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Download the file using curl
if curl -fsSL "$URL" -o "$OUTPUT_FILE"; then
    echo "Cookies Pr Token saved to $OUTPUT_FILE"
else
    echo "Failed to download Token from cookies.txt"
    exit 1
fi
