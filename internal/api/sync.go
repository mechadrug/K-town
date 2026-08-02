package api

import (
	"sync"
	"time"

	"k-town/internal/world"
)

// DeltaBuffer stores previous state for delta computation.
type DeltaBuffer struct {
	mu        sync.RWMutex
	prevWorld *world.World
}

// NewDeltaBuffer creates a new DeltaBuffer.
func NewDeltaBuffer() *DeltaBuffer {
	return &DeltaBuffer{}
}

// Update stores the current world state as the previous state.
func (d *DeltaBuffer) Update(w *world.World) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.prevWorld = w
}

// ComputeDelta calculates the difference between the previous and current world state.
func (d *DeltaBuffer) ComputeDelta(curr *world.World) StateDelta {
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
	return delta
}
