#!/bin/bash
# Setup script for readwise-go

echo "Setting up readwise-go..."

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Error: Go is not installed. Please install Go 1.21 or later."
    exit 1
fi

# Initialize go module if not exists
if [ ! -f "go.mod" ]; then
    echo "Initializing Go module..."
    go mod init readwise-go
fi

# Add SQLite dependency
echo "Adding SQLite dependency..."
go get github.com/mattn/go-sqlite3

# Tidy up dependencies
echo "Tidying dependencies..."
go mod tidy

# Build the application
echo "Building readwise-go..."
go build -o readwise-go main.go

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo ""
    echo "Usage:"
    echo "  ./readwise-go query \"search term\""
    echo "  ./readwise-go rebuild" 
    echo "  ./readwise-go post \"highlight text\""
    echo ""
    echo "Make sure to set your READWISE_TOKEN environment variable."
else
    echo "❌ Build failed. Please check the errors above."
    exit 1
fi
