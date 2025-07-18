package readwise

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"readwise-go/internal/database"
)

// Client represents a Readwise API client
type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
}

// Book represents a book from Readwise API
type Book struct {
	UserBookID    int               `json:"user_book_id"`
	Title         string            `json:"title"`
	Author        string            `json:"author"`
	Source        string            `json:"source"`
	CoverImageURL string            `json:"cover_image_url"`
	UniqueURL     string            `json:"unique_url"`
	BookTags      []BookTag         `json:"book_tags"`
	Category      string            `json:"category"`
	ReadwiseURL   string            `json:"readwise_url"`
	SourceURL     string            `json:"source_url"`
	Highlights    []HighlightExport `json:"highlights"`
}

// BookTag represents a book tag
type BookTag struct {
	Name string `json:"name"`
}

// HighlightExport represents a highlight from the export API
type HighlightExport struct {
	ID          int            `json:"id"`
	Text        string         `json:"text"`
	CreatedAt   string         `json:"created_at"`
	URL         string         `json:"url"`
	Tags        []HighlightTag `json:"tags"`
	IsFavorite  bool           `json:"is_favorite"`
	IsDiscard   bool           `json:"is_discard"`
	ReadwiseURL string         `json:"readwise_url"`
}

// HighlightTag represents a highlight tag
type HighlightTag struct {
	Name string `json:"name"`
}

// ExportResponse represents the response from the export API
type ExportResponse struct {
	Results        []Book  `json:"results"`
	NextPageCursor *string `json:"nextPageCursor"`
}

// HighlightCreateRequest represents a request to create a highlight
type HighlightCreateRequest struct {
	Highlights []HighlightCreate `json:"highlights"`
}

// HighlightCreate represents a highlight to be created
type HighlightCreate struct {
	Text          string `json:"text"`
	Title         string `json:"title,omitempty"`
	SourceType    string `json:"source_type,omitempty"`
	HighlightedAt string `json:"highlighted_at,omitempty"`
}

// NewClient creates a new Readwise API client
func NewClient(token string) *Client {
	return &Client{
		baseURL: "https://readwise.io/api/v2",
		token:   token,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// ExportAll fetches all highlights using the export API
func (c *Client) ExportAll() ([]Book, error) {
	var allBooks []Book
	var nextPageCursor *string

	for {
		url := c.baseURL + "/export/"
		req, err := http.NewRequest("GET", url, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set("Authorization", "Token "+c.token)

		if nextPageCursor != nil {
			q := req.URL.Query()
			q.Add("pageCursor", *nextPageCursor)
			req.URL.RawQuery = q.Encode()
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("failed to make request: %w", err)
		}

		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			return nil, fmt.Errorf("API request failed with status %d", resp.StatusCode)
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, fmt.Errorf("failed to read response body: %w", err)
		}

		var exportResp ExportResponse
		if err := json.Unmarshal(body, &exportResp); err != nil {
			return nil, fmt.Errorf("failed to unmarshal response: %w", err)
		}

		allBooks = append(allBooks, exportResp.Results...)
		nextPageCursor = exportResp.NextPageCursor

		if nextPageCursor == nil {
			break
		}
	}

	return allBooks, nil
}

// CreateHighlight creates a new highlight
func (c *Client) CreateHighlight(text, title string) error {
	request := HighlightCreateRequest{
		Highlights: []HighlightCreate{
			{
				Text:          text,
				Title:         title,
				SourceType:    "fromAlfred",
				HighlightedAt: time.Now().Format(time.RFC3339),
			},
		},
	}

	jsonData, err := json.Marshal(request)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/highlights/",
		strings.NewReader(string(jsonData)))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// ConvertToDBHighlight converts API data to database highlight
func ConvertToDBHighlight(book Book, highlight HighlightExport) *database.Highlight {
	// Convert tags to JSON string
	tagsJSON, _ := json.Marshal(highlight.Tags)
	bookTagsJSON, _ := json.Marshal(book.BookTags)

	isFavorite := 0
	if highlight.IsFavorite {
		isFavorite = 1
	}

	isDiscard := 0
	if highlight.IsDiscard {
		isDiscard = 1
	}

	return &database.Highlight{
		UserBookID:      book.UserBookID,
		Title:           book.Title,
		Author:          book.Author,
		Source:          book.Source,
		CoverImageURL:   book.CoverImageURL,
		UniqueURL:       book.UniqueURL,
		BookTags:        string(bookTagsJSON),
		Category:        book.Category,
		ReadwiseURL:     book.ReadwiseURL,
		SourceURL:       book.SourceURL,
		HighID:          highlight.ID,
		HighText:        highlight.Text,
		HighCreatedAt:   highlight.CreatedAt,
		HighURL:         highlight.URL,
		HighTags:        string(tagsJSON),
		HighIsFavorite:  isFavorite,
		HighIsDiscard:   isDiscard,
		HighReadwiseURL: highlight.ReadwiseURL,
	}
}
