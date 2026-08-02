package api

import (
    "sync"
    "time"

    "k-town/internal/agent"
    "k-town/internal/world"
)

type DeltaBuffer struct {
    mu        sync.RWMutex
    prevWorld *world.World
    prevAgents []*agent.Agent
}

func NewDeltaBuffer() *DeltaBuffer {
    return &DeltaBuffer{}
}

func (d *DeltaBuffer) Update(w *world.World, agents []*agent.Agent) {
    d.mu.Lock()
    defer d.mu.Unlock()
    d.prevWorld = w
    d.prevAgents = agents
}

func (d *DeltaBuffer) ComputeDelta(curr *world.World, currAgents []*agent.Agent) StateDelta {
    d.mu.RLock()
    defer d.mu.RUnlock()
    delta := StateDelta{
        Tick:      curr.Time,
        Weather:   curr.Weather,
        Timestamp: time.Now().Unix(),
    }
    if d.prevWorld != nil && d.prevWorld.Weather != curr.Weather {
        delta.Events = append(delta.Events, map[string]interface{}{
            "type": "weather_change",
            "from": d.prevWorld.Weather,
            "to":   curr.Weather,
        })
    }
    for _, a := range currAgents {
        delta.Agents = append(delta.Agents, a.ToMap())
    }
    return delta
}