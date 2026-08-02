package main

import (
    "context"
    "fmt"
    "log"
    "os"
    "os/signal"
    "syscall"

    "k-town/internal/config"
    "k-town/internal/event"
    "k-town/internal/tick"
    "k-town/internal/world"
)

func main() {
    cfg, err := config.Load("config.yaml")
    if err != nil {
        log.Fatalf("Failed to load config: %v", err)
    }

    log.Printf("K-town server starting (LLM: %s @ %s)", cfg.LLM.Model, cfg.LLM.BaseURL)

    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    evtBus := event.NewBus()
    w := world.New(cfg.World)
    engine := tick.NewEngine(cfg.Tick, w, evtBus)

    go engine.Run(ctx)

    sig := make(chan os.Signal, 1)
    signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
    <-sig
    log.Println("Shutting down K-town server...")
}
