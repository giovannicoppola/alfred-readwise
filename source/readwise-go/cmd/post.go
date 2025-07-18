package cmd

import (
	"fmt"

	"readwise-go/internal/alfred"
	"readwise-go/internal/config"
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

	if err := cfg.ValidateRequired(); err != nil {
		return fmt.Errorf("configuration error: %w", err)
	}

	// Create Readwise client
	client := readwise.NewClient(cfg.Token)

	// Create highlight
	if err := client.CreateHighlight(highlightText, cfg.NewHighTitle); err != nil {
		return fmt.Errorf("failed to create highlight: %w", err)
	}

	// Output success message
	result.AddDoneItem("Highlight created!", "Successfully saved to Readwise")
	return result.Print()
}
