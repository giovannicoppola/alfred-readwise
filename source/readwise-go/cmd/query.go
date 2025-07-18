package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"readwise-go/internal/alfred"
	"readwise-go/internal/config"
	"readwise-go/internal/database"
	"readwise-go/internal/image"
	"readwise-go/internal/readwise"
)

func executeQuery(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("query command requires a search term")
	}

	query := args[0]

	// Load configuration
	cfg, err := config.NewConfig()
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	// Check if database needs rebuilding
	if err := checkDatabaseFreshness(cfg); err != nil {
		config.Log("Database needs updating: %v", err)
		if err := rebuildDatabase(cfg); err != nil {
			return fmt.Errorf("failed to rebuild database: %w", err)
		}
	}

	// Open database
	db, err := database.NewDatabase(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Get available tags for autocomplete
	tags, err := db.GetAllTags()
	if err != nil {
		config.Log("Warning: failed to get tags: %v", err)
		tags = []string{}
	}

	// Prepare Alfred result
	result := alfred.NewResult()

	// Process query for tags
	processedQuery, tagFilters := extractTags(query, tags)

	// Check if user is typing a tag
	if isTypingTag(query) {
		addTagSuggestions(result, query, tags)
		return result.Print()
	}

	// Search highlights
	highlights, err := db.SearchHighlights(processedQuery, cfg.GetEnabledTypes(), cfg.SearchScope, tagFilters)
	if err != nil {
		return fmt.Errorf("failed to search highlights: %w", err)
	}

	// Add results to Alfred output
	for i, highlight := range highlights {
		if i >= 50 { // Limit results
			break
		}

		// Parse tags for display
		var tagNames []string
		if highlight.HighTags != "[]" && highlight.HighTags != "" {
			var tags []map[string]interface{}
			if err := json.Unmarshal([]byte(strings.ReplaceAll(highlight.HighTags, "'", "\"")), &tags); err == nil {
				for _, tag := range tags {
					if name, ok := tag["name"].(string); ok {
						tagNames = append(tagNames, name)
					}
				}
			}
		}

		tagDisplay := ""
		if len(tagNames) > 0 {
			tagDisplay = "🏷️ " + strings.Join(tagNames, ",")
		}

		if highlight.HighIsFavorite == 1 {
			tagDisplay += "❤️"
		}

		subtitle := fmt.Sprintf("%d/%d %s-%s %s", i+1, len(highlights), highlight.Title, highlight.Author, tagDisplay)

		// Quick look path
		quickLookPath := filepath.Join(cfg.ImageHFolder, fmt.Sprintf("%d.jpg", highlight.HighID))

		sourceURLText := "no source URL"
		if highlight.HighURL != "" {
			sourceURLText = "open source URL"
		}

		item := alfred.Item{
			Title:        highlight.HighText,
			Subtitle:     subtitle,
			Valid:        true,
			QuickLookURL: quickLookPath,
			Variables: map[string]string{
				"fullOutput": fmt.Sprintf("%s\n\n%s: %s", highlight.HighText, highlight.Author, highlight.Title),
				"myURL":      highlight.HighReadwiseURL,
				"myStatus":   "completed",
				"myURLall":   highlight.ReadwiseURL,
			},
			Mods: map[string]alfred.Mod{
				"command": {
					Valid:    true,
					Subtitle: sourceURLText,
					Arg:      highlight.HighURL,
				},
			},
			Icon: &alfred.Icon{
				Path: filepath.Join(cfg.ImageFolder, fmt.Sprintf("%d.jpg", highlight.UserBookID)),
			},
		}

		result.AddItem(item)
	}

	// Add no results message if needed
	if len(highlights) == 0 && processedQuery != "" {
		result.AddWarningItem("No matches in your library", "Try a different query")
	}

	return result.Print()
}

func extractTags(query string, availableTags []string) (string, []string) {
	// Find complete tags in the query
	tagRegex := regexp.MustCompile(`#\w+\s`)
	fullTags := tagRegex.FindAllString(query, -1)

	var validTags []string
	processedQuery := query

	for _, tag := range fullTags {
		cleanTag := strings.TrimSpace(strings.TrimPrefix(tag, "#"))
		if contains(availableTags, cleanTag) {
			validTags = append(validTags, cleanTag)
			processedQuery = strings.ReplaceAll(processedQuery, tag, "")
		}
	}

	return strings.TrimSpace(processedQuery), validTags
}

func isTypingTag(query string) bool {
	// Check if user is in the middle of typing a tag (ends with #word)
	tagTypingRegex := regexp.MustCompile(`(?:^| )#[^ ]*$`)
	return tagTypingRegex.MatchString(query)
}

func addTagSuggestions(result *alfred.Result, query string, tags []string) {
	// Extract the partial tag being typed
	tagTypingRegex := regexp.MustCompile(`(?:^| )(#[^ ]*)$`)
	matches := tagTypingRegex.FindStringSubmatch(query)
	if len(matches) < 2 {
		return
	}

	partialTag := matches[1]
	baseQuery := strings.TrimSuffix(query, partialTag)

	// Find matching tags
	var matchingTags []string
	for _, tag := range tags {
		fullTag := "#" + tag
		if strings.HasPrefix(fullTag, partialTag) {
			matchingTags = append(matchingTags, fullTag)
		}
	}

	// Add suggestions
	if len(matchingTags) > 0 {
		for _, tag := range matchingTags {
			result.AddItem(alfred.Item{
				Title:    tag,
				Subtitle: baseQuery,
				Arg:      baseQuery + tag + " ",
				Icon:     &alfred.Icon{Path: "icons/label.png"},
			})
		}
	} else {
		result.AddWarningItem("no labels matching", "try another query?")
	}
}

func checkDatabaseFreshness(cfg *config.Config) error {
	// Check if database file exists
	if _, err := os.Stat(cfg.Database); os.IsNotExist(err) {
		return fmt.Errorf("database does not exist")
	}

	// Check file modification time
	fileInfo, err := os.Stat(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to check database file: %w", err)
	}

	daysSinceModified := int(time.Since(fileInfo.ModTime()).Hours() / 24)
	if daysSinceModified >= cfg.RefreshRate {
		return fmt.Errorf("database is %d days old, refresh rate is %d days", daysSinceModified, cfg.RefreshRate)
	}

	return nil
}

func rebuildDatabase(cfg *config.Config) error {
	config.Log("Rebuilding database...")

	if err := cfg.ValidateRequired(); err != nil {
		return err
	}

	// Create Readwise client
	client := readwise.NewClient(cfg.Token)

	// Fetch all data
	books, err := client.ExportAll()
	if err != nil {
		return fmt.Errorf("failed to export from Readwise: %w", err)
	}

	// Open database
	db, err := database.NewDatabase(cfg.Database)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Clear existing data
	if err := db.ClearHighlights(); err != nil {
		return fmt.Errorf("failed to clear highlights: %w", err)
	}

	// Insert all highlights
	for _, book := range books {
		for _, highlight := range book.Highlights {
			dbHighlight := readwise.ConvertToDBHighlight(book, highlight)
			if err := db.InsertHighlight(dbHighlight); err != nil {
				config.Log("Warning: failed to insert highlight %d: %v", highlight.ID, err)
				continue
			}

			// Create highlight image if it doesn't exist
			imagePath := filepath.Join(cfg.ImageHFolder, fmt.Sprintf("%d.jpg", highlight.ID))
			if _, err := os.Stat(imagePath); os.IsNotExist(err) {
				if err := image.CreateHighlightImage(highlight.Text, book.Author, book.Title, highlight.ID, imagePath); err != nil {
					config.Log("Warning: failed to create image for highlight %d: %v", highlight.ID, err)
				}
			}
		}

		// Download cover image if it doesn't exist
		coverPath := filepath.Join(cfg.ImageFolder, fmt.Sprintf("%d.jpg", book.UserBookID))
		if _, err := os.Stat(coverPath); os.IsNotExist(err) {
			if err := image.DownloadCoverImage(book.CoverImageURL, coverPath); err != nil {
				config.Log("Warning: failed to download cover for book %d: %v", book.UserBookID, err)
			}
		}
	}

	// Rebuild tags
	if err := db.RebuildTags(); err != nil {
		config.Log("Warning: failed to rebuild tags: %v", err)
	}

	config.Log("Database rebuild complete")
	return nil
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
