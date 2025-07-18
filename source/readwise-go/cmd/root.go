package cmd

import (
	"fmt"
	"os"
)

// Execute is the main entry point for the application
func Execute() error {
	if len(os.Args) < 2 {
		printUsage()
		return nil
	}

	command := os.Args[1]
	args := os.Args[2:]

	switch command {
	case "query":
		return executeQuery(args)
	case "rebuild":
		return executeRebuild(args)
	case "post":
		return executePost(args)
	case "help", "-h", "--help":
		printUsage()
		return nil
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", command)
		printUsage()
		return fmt.Errorf("unknown command: %s", command)
	}
}

func printUsage() {
	fmt.Println("readwise-go - A Go implementation of the Alfred Readwise workflow")
	fmt.Println("")
	fmt.Println("Usage:")
	fmt.Println("  readwise-go <command> [arguments]")
	fmt.Println("")
	fmt.Println("Available Commands:")
	fmt.Println("  query    Search highlights in the database")
	fmt.Println("  rebuild  Rebuild the database from Readwise API")
	fmt.Println("  post     Create a new highlight")
	fmt.Println("  help     Show this help message")
	fmt.Println("")
	fmt.Println("Examples:")
	fmt.Println("  readwise-go query \"search term\"")
	fmt.Println("  readwise-go rebuild")
	fmt.Println("  readwise-go post \"highlight text\"")
}
