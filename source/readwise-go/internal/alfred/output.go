package alfred

import (
	"encoding/json"
	"fmt"
)

// Item represents an Alfred workflow item
type Item struct {
	Title        string            `json:"title"`
	Subtitle     string            `json:"subtitle,omitempty"`
	Arg          string            `json:"arg,omitempty"`
	Valid        bool              `json:"valid,omitempty"`
	QuickLookURL string            `json:"quicklookurl,omitempty"`
	Variables    map[string]string `json:"variables,omitempty"`
	Mods         map[string]Mod    `json:"mods,omitempty"`
	Icon         *Icon             `json:"icon,omitempty"`
}

// Mod represents modifier key actions
type Mod struct {
	Valid    bool   `json:"valid,omitempty"`
	Subtitle string `json:"subtitle,omitempty"`
	Arg      string `json:"arg,omitempty"`
}

// Icon represents an item icon
type Icon struct {
	Path string `json:"path,omitempty"`
}

// Result represents the complete Alfred JSON output
type Result struct {
	Items     []Item            `json:"items"`
	Variables map[string]string `json:"variables,omitempty"`
}

// NewResult creates a new empty result
func NewResult() *Result {
	return &Result{
		Items:     make([]Item, 0),
		Variables: make(map[string]string),
	}
}

// AddItem adds an item to the result
func (r *Result) AddItem(item Item) {
	r.Items = append(r.Items, item)
}

// AddSimpleItem adds a simple item with title and subtitle
func (r *Result) AddSimpleItem(title, subtitle, arg string) {
	r.AddItem(Item{
		Title:    title,
		Subtitle: subtitle,
		Arg:      arg,
		Valid:    true,
	})
}

// AddWarningItem adds a warning item
func (r *Result) AddWarningItem(title, subtitle string) {
	r.AddItem(Item{
		Title:    title,
		Subtitle: subtitle,
		Icon:     &Icon{Path: "icons/Warning.png"},
	})
}

// AddDoneItem adds a completion item
func (r *Result) AddDoneItem(title, subtitle string) {
	r.AddItem(Item{
		Title:    title,
		Subtitle: subtitle,
		Icon:     &Icon{Path: "icons/done.png"},
	})
}

// Print outputs the result as JSON to stdout
func (r *Result) Print() error {
	output, err := json.Marshal(r)
	if err != nil {
		return fmt.Errorf("failed to marshal JSON: %w", err)
	}
	fmt.Println(string(output))
	return nil
}
