package readwise

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"readwise-go/internal/config"
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

// HighlightCreateResponse represents a single highlight returned by the create API
type HighlightCreateResponse struct {
	ID            int    `json:"id"`
	Text          string `json:"text"`
	Title         string `json:"title"`
	SourceType    string `json:"source_type"`
	HighlightedAt string `json:"highlighted_at"`
	BookID        int    `json:"book_id"`
	URL           string `json:"url"`
	ReadwiseURL   string `json:"readwise_url"`
}

// CreateHighlight creates a new highlight and returns the API response
func (c *Client) CreateHighlight(text, title string) ([]HighlightCreateResponse, error) {
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
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}
	config.Log("[DEBUG CreateHighlight] POST URL: %s", c.baseURL+"/highlights/")
	config.Log("[DEBUG CreateHighlight] request body: %s", string(jsonData))

	req, err := http.NewRequest("POST", c.baseURL+"/highlights/",
		strings.NewReader(string(jsonData)))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	config.Log("[DEBUG CreateHighlight] sending request...")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		config.Log("[DEBUG CreateHighlight] HTTP error: %v", err)
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	config.Log("[DEBUG CreateHighlight] response status: %d", resp.StatusCode)
	config.Log("[DEBUG CreateHighlight] response body: %s", string(body))

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	var created []HighlightCreateResponse
	if err := json.Unmarshal(body, &created); err != nil {
		config.Log("[DEBUG CreateHighlight] failed to parse response: %v", err)
		return nil, fmt.Errorf("failed to parse create response: %w", err)
	}

	return created, nil
}

// ReaderDocument represents a document from the Readwise Reader API (v3)
type ReaderDocument struct {
	ID        string                 `json:"id"`
	Title     string                 `json:"title"`
	Author    string                 `json:"author"`
	Category  string                 `json:"category"`
	Source    string                 `json:"source"`
	URL       string                 `json:"url"`
	SourceURL string                 `json:"source_url"`
	SiteName  string                 `json:"site_name"`
	ImageURL  string                 `json:"image_url"`
	Location  string                 `json:"location"`
	Tags      map[string]interface{} `json:"tags"`
	CreatedAt string                 `json:"created_at"`
	UpdatedAt string                 `json:"updated_at"`
}

// ReaderListResponse represents the response from the Reader list API
type ReaderListResponse struct {
	Count          int              `json:"count"`
	NextPageCursor *string          `json:"nextPageCursor"`
	Results        []ReaderDocument `json:"results"`
}

// FetchReaderDocuments fetches all documents from Readwise Reader
func (c *Client) FetchReaderDocuments() ([]ReaderDocument, error) {
	var allDocs []ReaderDocument
	var nextPageCursor *string

	for {
		url := "https://readwise.io/api/v3/list/"
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

		config.Log("[DEBUG FetchReaderDocuments] fetching page (cursor: %v)...", nextPageCursor)
		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("failed to make request: %w", err)
		}

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			return nil, fmt.Errorf("Reader API request failed with status %d: %s", resp.StatusCode, string(body))
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, fmt.Errorf("failed to read response body: %w", err)
		}

		var listResp ReaderListResponse
		if err := json.Unmarshal(body, &listResp); err != nil {
			return nil, fmt.Errorf("failed to unmarshal response: %w", err)
		}

		allDocs = append(allDocs, listResp.Results...)
		config.Log("[DEBUG FetchReaderDocuments] fetched %d documents (total: %d)", len(listResp.Results), len(allDocs))

		nextPageCursor = listResp.NextPageCursor
		if nextPageCursor == nil {
			break
		}
	}

	return allDocs, nil
}

// ConvertToDBReaderDocument converts an API Reader document to a database ReaderDocument
func ConvertToDBReaderDocument(doc ReaderDocument) *database.ReaderDocument {
	tagsJSON, _ := json.Marshal(doc.Tags)

	return &database.ReaderDocument{
		ID:        doc.ID,
		Title:     doc.Title,
		Author:    doc.Author,
		Category:  doc.Category,
		Source:    doc.Source,
		URL:       doc.URL,
		SourceURL: doc.SourceURL,
		SiteName:  doc.SiteName,
		ImageURL:  doc.ImageURL,
		Location:  doc.Location,
		Tags:      string(tagsJSON),
		CreatedAt: doc.CreatedAt,
		UpdatedAt: doc.UpdatedAt,
	}
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
