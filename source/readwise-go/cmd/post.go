package cmd

import (
	"fmt"
	"time"

	"readwise-go/internal/alfred"
	"readwise-go/internal/config"
	"readwise-go/internal/database"
	"readwise-go/internal/readwise"
)

func executePost(args []string) error {
	result := alfred.NewResult()

	// If no input provided, show prompt
	if len(args) == 0 {
		result.AddItem(alfred.Item{
			Title:    "Create a new Readwise highlight",
			Subtitle: "↩️ to save",
			Valid:    true,
		})
		return result.Print()
	}

	highlightText := args[0]
	config.Log("[DEBUG post] highlight text: %q", highlightText)
	if highlightText == "" {
		result.AddItem(alfred.Item{
			Title:    "Create a new Readwise highlight",
			Subtitle: "↩️ to save",
			Valid:    true,
		})
		return result.Print()
	}

	// Load configuration
	cfg, err := config.NewConfig()
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}
	config.Log("[DEBUG post] config loaded — token length: %d, NewHighTitle: %q, database: %s", len(cfg.Token), cfg.NewHighTitle, cfg.Database)

	if err := cfg.ValidateRequired(); err != nil {
		return fmt.Errorf("configuration error: %w", err)
	}

	// Create Readwise client
	client := readwise.NewClient(cfg.Token)

	// Create highlight via API
	config.Log("[DEBUG post] calling CreateHighlight...")
	created, err := client.CreateHighlight(highlightText, cfg.NewHighTitle)
	if err != nil {
		config.Log("[DEBUG post] CreateHighlight failed: %v", err)
		return fmt.Errorf("failed to create highlight: %w", err)
	}
	config.Log("[DEBUG post] CreateHighlight succeeded, %d highlight(s) returned", len(created))

	// Insert into local database
	db, err := database.NewDatabase(cfg.Database)
	if err != nil {
		config.Log("[DEBUG post] failed to open database: %v", err)
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	for _, h := range created {
		dbHighlight := &database.Highlight{
			UserBookID:      h.BookID,
			Title:           cfg.NewHighTitle,
			Author:          "",
			Source:          "fromAlfred",
			CoverImageURL:   "",
			UniqueURL:       "",
			BookTags:        "[]",
			Category:        "books",
			ReadwiseURL:     h.ReadwiseURL,
			SourceURL:       "",
			HighID:          h.ID,
			HighText:        h.Text,
			HighCreatedAt:   time.Now().Format(time.RFC3339),
			HighURL:         h.URL,
			HighTags:        "[]",
			HighIsFavorite:  0,
			HighIsDiscard:   0,
			HighReadwiseURL: h.ReadwiseURL,
		}
		if err := db.InsertHighlight(dbHighlight); err != nil {
			config.Log("[DEBUG post] failed to insert highlight %d into DB: %v", h.ID, err)
		} else {
			config.Log("[DEBUG post] highlight %d inserted into local DB", h.ID)
		}
	}

	// Output success message
	result.AddDoneItem("Highlight created!", "Successfully saved to Readwise")
	return result.Print()
}
