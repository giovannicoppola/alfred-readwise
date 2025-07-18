# Readwise Go - Makefile

BINARY_NAME=readwise-go
MAIN_FILE=main.go

# Default target
.PHONY: all
all: build

# Build the application
.PHONY: build
build:
	go build -o $(BINARY_NAME) $(MAIN_FILE)

# Build with optimizations for production
.PHONY: build-prod
build-prod:
	CGO_ENABLED=1 go build -ldflags="-s -w" -o $(BINARY_NAME) $(MAIN_FILE)

# Clean build artifacts
.PHONY: clean
clean:
	rm -f $(BINARY_NAME)
	rm -f $(BINARY_NAME)-*

# Run tests
.PHONY: test
test:
	go test ./...

# Format code
.PHONY: fmt
fmt:
	go fmt ./...

# Run linter
.PHONY: lint
lint:
	golangci-lint run

# Install dependencies
.PHONY: deps
deps:
	go mod tidy
	go mod download

# Cross-compile for different platforms
.PHONY: build-all
build-all: build-macos build-linux build-windows

.PHONY: build-macos
build-macos:
	GOOS=darwin GOARCH=amd64 CGO_ENABLED=1 go build -o $(BINARY_NAME)-macos-amd64 $(MAIN_FILE)
	GOOS=darwin GOARCH=arm64 CGO_ENABLED=1 go build -o $(BINARY_NAME)-macos-arm64 $(MAIN_FILE)

.PHONY: build-linux
build-linux:
	GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build -o $(BINARY_NAME)-linux-amd64 $(MAIN_FILE)

.PHONY: build-windows
build-windows:
	GOOS=windows GOARCH=amd64 CGO_ENABLED=1 go build -o $(BINARY_NAME)-windows-amd64.exe $(MAIN_FILE)

# Install the binary
.PHONY: install
install: build
	cp $(BINARY_NAME) /usr/local/bin/

# Development setup
.PHONY: dev-setup
dev-setup:
	go mod init readwise-go || true
	go mod tidy

# Run the application (for testing)
.PHONY: run-query
run-query:
	./$(BINARY_NAME) query "$(QUERY)"

.PHONY: run-rebuild
run-rebuild:
	./$(BINARY_NAME) rebuild

.PHONY: run-post
run-post:
	./$(BINARY_NAME) post "$(TEXT)"

# Help
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build        - Build the application"
	@echo "  build-prod   - Build with production optimizations"
	@echo "  build-all    - Cross-compile for all platforms"
	@echo "  clean        - Remove build artifacts"
	@echo "  test         - Run tests"
	@echo "  fmt          - Format code"
	@echo "  lint         - Run linter"
	@echo "  deps         - Install dependencies"
	@echo "  install      - Install binary to /usr/local/bin"
	@echo "  dev-setup    - Initialize development environment"
	@echo "  run-query    - Run query command (use QUERY=... make run-query)"
	@echo "  run-rebuild  - Run rebuild command"
	@echo "  run-post     - Run post command (use TEXT=... make run-post)"
	@echo "  help         - Show this help"
