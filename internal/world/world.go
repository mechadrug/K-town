package world

import (
    "k-town/internal/config"
)

type LocationType string

const (
    Square     LocationType = "square"
    Workshop   LocationType = "workshop"
    Wilderness LocationType = "wilderness"
)

type Location struct {
    ID       string
    Name     string
    Type     LocationType
    Agents   []string
    Events   []string
    Properties map[string]interface{}
}

type World struct {
    Time      int64
    Weather   string
    Locations map[string]*Location
}

func New(cfg config.Config) *World {
    w := &World{
        Weather:   "clear",
        Locations: make(map[string]*Location),
    }
    w.Locations["square"] = &Location{ID: "square", Name: "Town Square", Type: Square}
    w.Locations["workshop"] = &Location{ID: "workshop", Name: "Workshop", Type: Workshop}
    w.Locations["wilderness"] = &Location{ID: "wilderness", Name: "Wilderness", Type: Wilderness}
    return w
}

func (w *World) Advance(tick int64) {
    w.Time = tick
    hour := tick % 24
    if hour == 6 {
        w.weatherChange()
    }
}

func (w *World) weatherChange() {
    weathers := []string{"clear", "cloudy", "rainy"}
    w.Weather = weathers[w.Time%3]
}
