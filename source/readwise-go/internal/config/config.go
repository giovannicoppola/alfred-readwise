package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

// Config holds all configuration values
type Config struct {
	Token              string
	ArticlesCheck      string
	TweetsCheck        string
	BooksCheck         string
	PodcastsCheck      string
	SupplementalsCheck string
	NewHighTitle       string
	SearchScope        string
	SearchPlatform     string
	WfBundle           string
	DataFolder         string
	Database           string
	ImageFolder        string
	ImageHFolder       string
	RefreshRate        int
}

// NewConfig creates a new configuration from environment variables
func NewConfig() (*Config, error) {
	dataFolder := os.Getenv("alfred_workflow_data")
	if dataFolder == "" {
		// Fallback for development/testing
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return nil, fmt.Errorf("failed to get home directory: %w", err)
		}
		dataFolder = filepath.Join(homeDir, ".readwise-go")
	}

	database := filepath.Join(dataFolder, "readwise.db")
	imageFolder := filepath.Join(dataFolder, "images")
	imageHFolder := filepath.Join(dataFolder, "images_H")

	// Create directories if they don't exist
	for _, dir := range []string{dataFolder, imageFolder, imageHFolder} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return nil, fmt.Errorf("failed to create directory %s: %w", dir, err)
		}
	}

	refreshRateStr := os.Getenv("RefreshRate")
	refreshRate := 1 // default
	if refreshRateStr != "" {
		if rate, err := strconv.Atoi(refreshRateStr); err == nil {
			refreshRate = rate
		}
	}

	return &Config{
		Token:              os.Getenv("READWISE_TOKEN"),
		ArticlesCheck:      getEnvWithDefault("ARTICLES_CHECK", "1"),
		TweetsCheck:        getEnvWithDefault("TWEETS_CHECK", "1"),
		BooksCheck:         getEnvWithDefault("BOOKS_CHECK", "1"),
		PodcastsCheck:      getEnvWithDefault("PODCASTS_CHECK", "1"),
		SupplementalsCheck: getEnvWithDefault("SUPPLEMENTALS_CHECK", "1"),
		NewHighTitle:       getEnvWithDefault("NEW_HIGH_TITLE", "From Alfred"),
		SearchScope:        getEnvWithDefault("SEARCH_SCOPE", "Both"),
		SearchPlatform:     getEnvWithDefault("SEARCH_PLATFORM", "Readwise"),
		WfBundle:           os.Getenv("alfred_workflow_bundleid"),
		DataFolder:         dataFolder,
		Database:           database,
		ImageFolder:        imageFolder,
		ImageHFolder:       imageHFolder,
		RefreshRate:        refreshRate,
	}, nil
}

// GetEnabledTypes returns a slice of enabled content types
func (c *Config) GetEnabledTypes() []string {
	var types []string
	if c.BooksCheck == "1" {
		types = append(types, "books")
	}
	if c.ArticlesCheck == "1" {
		types = append(types, "articles")
	}
	if c.TweetsCheck == "1" {
		types = append(types, "tweets")
	}
	if c.PodcastsCheck == "1" {
		types = append(types, "podcasts")
	}
	if c.SupplementalsCheck == "1" {
		types = append(types, "supplementals")
	}
	return types
}

// ValidateRequired checks if required configuration values are set
func (c *Config) ValidateRequired() error {
	if c.Token == "" {
		return fmt.Errorf("READWISE_TOKEN environment variable is required")
	}
	return nil
}

func getEnvWithDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// Log writes a message to stderr (for Alfred compatibility)
func Log(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
}
