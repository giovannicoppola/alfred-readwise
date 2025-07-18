package main

import (
	"readwise-go/cmd"
	"testing"
)

func TestExecuteHelp(t *testing.T) {
	// Test that help command doesn't return an error
	// This is a basic smoke test
	err := cmd.Execute()
	if err != nil {
		t.Errorf("Execute() returned error: %v", err)
	}
}
