package config

import (
    "os"

    "gopkg.in/yaml.v3"
)

type Config struct {
    Server struct {
        WSPort   int `yaml:"ws_port"`
        HTTPPort int `yaml:"http_port"`
    } `yaml:"server"`
    Tick struct {
        Rate      string `yaml:"rate"`
        DayLength int    `yaml:"day_length"`
    } `yaml:"tick"`
    World struct {
        Locations int `yaml:"locations"`
        Agents    int `yaml:"agents"`
    } `yaml:"world"`
    LLM struct {
        Provider      string `yaml:"provider"`
        BaseURL       string `yaml:"base_url"`
        APIKey        string `yaml:"api_key"`
        Model         string `yaml:"model"`
        MaxCallsPerTick int  `yaml:"max_calls_per_tick"`
    } `yaml:"llm"`
    Logging struct {
        Level   string `yaml:"level"`
        Output  string `yaml:"output"`
        Persist bool   `yaml:"persist"`
    } `yaml:"logging"`
}

func Load(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    var cfg Config
    if err := yaml.Unmarshal(data, &cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
