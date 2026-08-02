package tick

import (
    "log"
    "time"

    "k-town/internal/config"
    "k-town/internal/event"
    "k-town/internal/world"
)

type Engine struct {
    CurrentTick int64
    TickRate    time.Duration
    World       *world.World
    EventBus    *event.Bus
}

func NewEngine(cfg config.Config, w *world.World, bus *event.Bus) *Engine {
    rate, _ := time.ParseDuration(cfg.Tick.Rate)
    if rate == 0 {
        rate = time.Second
    }
    return &Engine{
        TickRate: rate,
        World:    w,
        EventBus: bus,
    }
}

func (e *Engine) Run(ctx context.Context) {
    ticker := time.NewTicker(e.TickRate)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            e.Step()
        }
    }
}

func (e *Engine) Step() {
    e.CurrentTick++
    e.World.Advance(e.CurrentTick)
    e.EventBus.FlushScheduled(e.CurrentTick)
    log.Printf("[tick %d] world time: %02d:00, weather: %s",
        e.CurrentTick, e.CurrentTick%24, e.World.Weather)
}
