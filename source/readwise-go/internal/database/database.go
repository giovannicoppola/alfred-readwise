package database

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"
	// For SQLite support, run: go get github.com/mattn/go-sqlite3
	// _ "github.com/mattn/go-sqlite3"
)

// Highlight represents a highlight in the database
type Highlight struct {
	UserBookID      int    `json:"user_book_id"`
	Title           string `json:"title"`
	Author          string `json:"author"`
	Source          string `json:"source"`
	CoverImageURL   string `json:"cover_image_url"`
	UniqueURL       string `json:"unique_url"`
	BookTags        string `json:"book_tags"`
	Category        string `json:"category"`
	ReadwiseURL     string `json:"readwise_url"`
	SourceURL       string `json:"source_url"`
	HighID          int    `json:"high_id"`
	HighText        string `json:"high_text"`
	HighCreatedAt   string `json:"high_created_at"`
	HighURL         string `json:"high_url"`
	HighTags        string `json:"high_tags"`
	HighIsFavorite  int    `json:"high_is_favorite"`
	HighIsDiscard   int    `json:"high_is_discard"`
	HighReadwiseURL string `json:"high_readwise_url"`
}

// Tag represents a tag in the database
type Tag struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

// Database wraps the SQL database connection
type Database struct {
	db *sql.DB
}

// NewDatabase creates a new database connection
func NewDatabase(dbPath string) (*Database, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	database := &Database{db: db}
	if err := database.createTables(); err != nil {
		return nil, fmt.Errorf("failed to create tables: %w", err)
	}

	return database, nil
}

// Close closes the database connection
func (d *Database) Close() error {
	return d.db.Close()
}

// createTables creates the necessary database tables
func (d *Database) createTables() error {
	highlightsTable := `
	CREATE TABLE IF NOT EXISTS highlights (
		user_book_id INT,
		title TEXT,
		author TEXT,
		source TEXT,
		cover_image_url TEXT,
		unique_url TEXT,
		book_tags TEXT,
		category TEXT,
		readwise_url TEXT,
		source_url TEXT,
		highID INT,
		highText TEXT,
		high_created_at TEXT,
		highURL TEXT,
		highTags TEXT,
		high_is_favorite INT,
		high_is_discard INT,
		high_readwise_url TEXT
	)`

	tagsTable := `
	CREATE TABLE IF NOT EXISTS tags (
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL
	)`

	if _, err := d.db.Exec(highlightsTable); err != nil {
		return fmt.Errorf("failed to create highlights table: %w", err)
	}

	if _, err := d.db.Exec(tagsTable); err != nil {
		return fmt.Errorf("failed to create tags table: %w", err)
	}

	return nil
}

// ClearHighlights drops and recreates the highlights table
func (d *Database) ClearHighlights() error {
	if _, err := d.db.Exec("DROP TABLE IF EXISTS highlights"); err != nil {
		return fmt.Errorf("failed to drop highlights table: %w", err)
	}
	return d.createTables()
}

// InsertHighlight inserts a highlight into the database
func (d *Database) InsertHighlight(h *Highlight) error {
	query := `
	INSERT INTO highlights VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

	_, err := d.db.Exec(query,
		h.UserBookID, h.Title, h.Author, h.Source, h.CoverImageURL,
		h.UniqueURL, h.BookTags, h.Category, h.ReadwiseURL, h.SourceURL,
		h.HighID, h.HighText, h.HighCreatedAt, h.HighURL, h.HighTags,
		h.HighIsFavorite, h.HighIsDiscard, h.HighReadwiseURL,
	)

	if err != nil {
		return fmt.Errorf("failed to insert highlight: %w", err)
	}
	return nil
}

// SearchHighlights searches for highlights based on query and enabled types
func (d *Database) SearchHighlights(query string, enabledTypes []string, searchScope string, tagFilters []string) ([]Highlight, error) {
	var conditions []string
	var args []interface{}

	// Handle search scope (Text, Book, or Both)
	if query != "" {
		keywords := strings.Fields(query)
		if len(keywords) > 1 {
			var keywordConditions []string
			for _, keyword := range keywords {
				switch searchScope {
				case "Text":
					keywordConditions = append(keywordConditions, "(highText LIKE ?)")
					args = append(args, "%"+keyword+"%")
				case "Book":
					keywordConditions = append(keywordConditions, "(title LIKE ?)")
					args = append(args, "%"+keyword+"%")
				case "Both":
					keywordConditions = append(keywordConditions, "(highText LIKE ? OR title LIKE ?)")
					args = append(args, "%"+keyword+"%", "%"+keyword+"%")
				}
			}
			conditions = append(conditions, "("+strings.Join(keywordConditions, " AND ")+")")
		} else {
			switch searchScope {
			case "Text":
				conditions = append(conditions, "(highText LIKE ?)")
				args = append(args, "%"+query+"%")
			case "Book":
				conditions = append(conditions, "(title LIKE ?)")
				args = append(args, "%"+query+"%")
			case "Both":
				conditions = append(conditions, "(highText LIKE ? OR title LIKE ?)")
				args = append(args, "%"+query+"%", "%"+query+"%")
			}
		}
	}

	// Handle category filtering
	if len(enabledTypes) > 0 {
		placeholders := make([]string, len(enabledTypes))
		for i, t := range enabledTypes {
			placeholders[i] = "?"
			args = append(args, t)
		}
		conditions = append(conditions, "category IN ("+strings.Join(placeholders, ",")+")")
	}

	// Handle tag filtering
	for _, tag := range tagFilters {
		conditions = append(conditions, "highTags LIKE ?")
		args = append(args, "%"+tag+"%")
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	querySQL := "SELECT * FROM highlights " + whereClause
	rows, err := d.db.Query(querySQL, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query highlights: %w", err)
	}
	defer rows.Close()

	var highlights []Highlight
	for rows.Next() {
		var h Highlight
		err := rows.Scan(
			&h.UserBookID, &h.Title, &h.Author, &h.Source, &h.CoverImageURL,
			&h.UniqueURL, &h.BookTags, &h.Category, &h.ReadwiseURL, &h.SourceURL,
			&h.HighID, &h.HighText, &h.HighCreatedAt, &h.HighURL, &h.HighTags,
			&h.HighIsFavorite, &h.HighIsDiscard, &h.HighReadwiseURL,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan highlight: %w", err)
		}
		highlights = append(highlights, h)
	}

	return highlights, nil
}

// GetAllTags returns all unique tags from the database
func (d *Database) GetAllTags() ([]string, error) {
	rows, err := d.db.Query("SELECT name FROM tags")
	if err != nil {
		return nil, fmt.Errorf("failed to query tags: %w", err)
	}
	defer rows.Close()

	var tags []string
	for rows.Next() {
		var tag string
		if err := rows.Scan(&tag); err != nil {
			return nil, fmt.Errorf("failed to scan tag: %w", err)
		}
		tags = append(tags, tag)
	}

	return tags, nil
}

// GetDatabaseAge returns the age of the database in days
func (d *Database) GetDatabaseAge(dbPath string) (int, error) {
	info, err := d.db.Query("SELECT name FROM sqlite_master WHERE type='table' AND name='highlights'")
	if err != nil {
		return 0, err
	}
	defer info.Close()

	if !info.Next() {
		return -1, nil // Database doesn't exist or is empty
	}

	// Get file modification time
	// This is a simplified approach - you might want to store a timestamp in the database instead
	return 0, nil
}

// RebuildTags extracts and rebuilds the tags table from highlights
func (d *Database) RebuildTags() error {
	// Drop and recreate tags table
	if _, err := d.db.Exec("DROP TABLE IF EXISTS tags"); err != nil {
		return fmt.Errorf("failed to drop tags table: %w", err)
	}

	if err := d.createTables(); err != nil {
		return fmt.Errorf("failed to recreate tags table: %w", err)
	}

	// Get all highlight tags
	rows, err := d.db.Query("SELECT highTags FROM highlights")
	if err != nil {
		return fmt.Errorf("failed to query highlight tags: %w", err)
	}
	defer rows.Close()

	tagSet := make(map[string]bool)
	for rows.Next() {
		var tagsJSON string
		if err := rows.Scan(&tagsJSON); err != nil {
			continue
		}

		// Parse the JSON tags
		var tags []map[string]interface{}
		if err := json.Unmarshal([]byte(strings.ReplaceAll(tagsJSON, "'", "\"")), &tags); err != nil {
			continue // Skip malformed JSON
		}

		for _, tag := range tags {
			if name, ok := tag["name"].(string); ok {
				tagSet[name] = true
			}
		}
	}

	// Insert unique tags
	for tagName := range tagSet {
		_, err := d.db.Exec("INSERT INTO tags (name) VALUES (?)", tagName)
		if err != nil {
			return fmt.Errorf("failed to insert tag %s: %w", tagName, err)
		}
	}

	return nil
}

// GetLastModified returns the last modification time of the database
func GetLastModified(dbPath string) (time.Time, error) {
	// This would typically check file modification time
	// For now, return current time
	return time.Now(), nil
}
