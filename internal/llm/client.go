package llm

import (
    "context"
    "fmt"
)

type Client struct {
    BaseURL  string
    APIKey   string
    Model    string
    Provider string
}

func NewClient(baseURL, apiKey, model, provider string) *Client {
    return &Client{
        BaseURL:  baseURL,
        APIKey:   apiKey,
        Model:    model,
        Provider: provider,
    }
}

func (c *Client) Call(ctx context.Context, prompt string) (string, error) {
    // TODO: implement actual HTTP call to LLM provider
    return fmt.Sprintf("[LLM %s] response for: %s", c.Model, prompt), nil
}