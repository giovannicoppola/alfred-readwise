package image

import (
	"fmt"
	"io"
	"net/http"
	"os"
)

// CreateHighlightImage creates an image for a highlight
// For now, this is a placeholder that creates a simple text file
// In a full implementation, you would use image generation libraries
func CreateHighlightImage(highlightText, author, title string, highlightID int, outputPath string) error {
	// Create a simple text representation for now
	// In production, you'd want to use image libraries like github.com/fogleman/gg
	fullText := fmt.Sprintf("%s\n\n%s: %s", highlightText, author, title)

	return os.WriteFile(outputPath+".txt", []byte(fullText), 0644)
}

// DownloadCoverImage downloads and saves a book cover image
func DownloadCoverImage(url, outputPath string) error {
	if url == "" {
		return copyDefaultIcon(outputPath)
	}

	resp, err := http.Get(url)
	if err != nil {
		return copyDefaultIcon(outputPath)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return copyDefaultIcon(outputPath)
	}

	// Create output file
	out, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("failed to create output file: %w", err)
	}
	defer out.Close()

	// Copy data
	_, err = io.Copy(out, resp.Body)
	if err != nil {
		return fmt.Errorf("failed to save image: %w", err)
	}

	return nil
}

// copyDefaultIcon copies a default icon when cover image is not available
func copyDefaultIcon(outputPath string) error {
	// Try to copy from icons directory
	defaultIcon := "icons/supplementals.png"

	src, err := os.Open(defaultIcon)
	if err != nil {
		// Create a simple placeholder file
		return os.WriteFile(outputPath, []byte("default-image"), 0644)
	}
	defer src.Close()

	dst, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("failed to create output file: %w", err)
	}
	defer dst.Close()

	_, err = io.Copy(dst, src)
	return err
}
