package cmd

import (
	"readwise-go/internal/alfred"
	"readwise-go/internal/config"
)

func executeRebuild(args []string) error {
	// Load configuration
	cfg, err := config.NewConfig()
	if err != nil {
		return err
	}

	// Rebuild the database
	if err := rebuildDatabase(cfg); err != nil {
		return err
	}

	// Output success message in Alfred format
	result := alfred.NewResult()
	result.AddDoneItem("Done!", "ready to search now")

	return result.Print()
}
