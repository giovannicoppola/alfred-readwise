# Readwise Go

A Go implementation of the Alfred Readwise workflow, providing a single entry point with multiple commands.

## Features

- **Query**: Search through your Readwise highlights with text and tag filtering
- **Rebuild**: Refresh your local database from the Readwise API
- **Post**: Create new highlights directly from Alfred

## Migration from Python

This Go application provides the same functionality as the original Python workflow:

- `readwise-query.py` → `readwise-go query`
- `readwise-rebuild.py` → `readwise-go rebuild`  
- `readwise_post.py` → `readwise-go post`

## Installation

### Prerequisites

- Go 1.21 or later
- SQLite3
- Readwise API token

### Building

```bash
cd readwise-go
go mod tidy
go build -o readwise-go main.go
```

### Environment Variables

The application requires the same environment variables as the Python version:

- `READWISE_TOKEN` - Your Readwise API token (required)
- `ARTICLES_CHECK` - Enable articles (1/0, default: 1)
- `TWEETS_CHECK` - Enable tweets (1/0, default: 1)
- `BOOKS_CHECK` - Enable books (1/0, default: 1)
- `PODCASTS_CHECK` - Enable podcasts (1/0, default: 1)
- `SUPPLEMENTALS_CHECK` - Enable supplementals (1/0, default: 1)
- `NEW_HIGH_TITLE` - Title for new highlights (default: "From Alfred")
- `SEARCH_SCOPE` - Search scope: "Text", "Book", or "Both" (default: "Both")
- `RefreshRate` - Days between database refreshes (default: 1)
- `alfred_workflow_data` - Data directory (auto-detected in Alfred)

## Usage

### Query/Search
```bash
./readwise-go query "search term"
./readwise-go query "search term #tag"
./readwise-go query "#tag"
```

### Rebuild Database
```bash
./readwise-go rebuild
```

### Create Highlight
```bash
./readwise-go post "This is my new highlight"
```

### Help
```bash
./readwise-go help
```

## Project Structure

```
readwise-go/
├── main.go                    # Entry point
├── cmd/
│   ├── root.go               # CLI routing
│   ├── query.go              # Search functionality
│   ├── rebuild.go            # Database rebuild
│   └── post.go               # Create highlights
├── internal/
│   ├── config/               # Configuration management
│   ├── database/             # SQLite operations
│   ├── readwise/             # API client
│   ├── image/                # Image generation
│   └── alfred/               # Alfred JSON output
└── go.mod
```

## Differences from Python Version

1. **Single binary**: No need for Python runtime or pip dependencies
2. **Simplified dependencies**: Only requires SQLite3
3. **Better error handling**: Structured error handling throughout
4. **Type safety**: Go's type system prevents many runtime errors
5. **Performance**: Faster startup and execution
6. **Image generation**: Simplified (can be enhanced with proper image libraries)

## Development

### Adding Dependencies

To add image generation libraries or other dependencies:

```bash
go get github.com/fogleman/gg
go get github.com/golang/freetype
```

Then update the `internal/image/generator.go` file to use proper image generation.

### Testing

```bash
go test ./...
```

### Cross-compilation

Build for different platforms:

```bash
# macOS
GOOS=darwin GOARCH=amd64 go build -o readwise-go-macos main.go

# Linux
GOOS=linux GOARCH=amd64 go build -o readwise-go-linux main.go

# Windows
GOOS=windows GOARCH=amd64 go build -o readwise-go-windows.exe main.go
```

## Alfred Integration

Replace the Python script calls in your Alfred workflow with:

1. Query: `/path/to/readwise-go query "{query}"`
2. Rebuild: `/path/to/readwise-go rebuild`
3. Post: `/path/to/readwise-go post "{query}"`

The JSON output format is identical to the Python version, so no workflow changes are needed.

## License

This project maintains the same license as the original Python implementation.
