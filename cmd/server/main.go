package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "k-town/internal/agent"
    "k-town/internal/api"
    "k-town/internal/config"
    "k-town/internal/event"
    "k-town/internal/knowledge"
    "k-town/internal/llm"
    "k-town/internal/log"
    "k-town/internal/tick"
    "k-town/internal/world"
)

func main() {
    cfg, err := config.Load("config.yaml")
    if err != nil {
        log.Printf("Warning: using defaults, config load failed: %v", err)
        cfg = defaultConfig()
    }

    log.Printf("=== K-town Server Starting ===")
    log.Printf("LLM: %s @ %s", cfg.LLM.Model, cfg.LLM.BaseURL)
    log.Printf("World: %d locations, %d agents", cfg.World.Locations, cfg.World.Agents)

    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    evtBus := event.NewBus()
    evtBuilder := event.NewScheduledEventBuilder(evtBus)
    w := world.New(cfg.World)
    logger := log.New()
    llmClient := llm.NewClient(cfg.LLM.BaseURL, cfg.LLM.APIKey, cfg.LLM.Model, cfg.LLM.Provider)
    kng := knowledge.NewEngine(knowledge.NewStore())

    agents := agent.PopulateAgents()
    for _, a := range agents {
        a.State.CurrentTask = &agent.Task{Description: "idle", Location: a.State.Location}
        logger.LogWorldEvent(log.WorldEventRecord{
            Tick: 0, EventType: "agent_spawned", Location: a.State.Location,
            Actors: []string{a.Identity.ID}, Payload: nil,
        })
    }
    log.Printf("Spawned %d agents", len(agents))

    engine := tick.NewEngine(cfg.Tick, w, evtBus)
    engine.SetAgents(agents)
    engine.SetLogger(logger)
    engine.SetKnowledgeEngine(kng)
    engine.SetLLMClient(llmClient)

    handler := api.NewHandler(w, agents, evtBus, logger, kng)

    agentIDs := make([]string, len(agents))
    for i, a := range agents {
        agentIDs[i] = a.Identity.ID
    }
    evtBuilder.GenerateDailySchedule(1, agentIDs)

    go engine.Run(ctx)

    addr := fmt.Sprintf(":%d", cfg.Server.HTTPPort)
    log.Printf("HTTP server listening on %s", addr)
    log.Printf("WebSocket endpoint: ws://localhost:%d/ws", cfg.Server.HTTPPort)

    go func() {
        if err := http.ListenAndServe(addr, handler); err != nil && err != http.ErrServerClosed {
            log.Printf("HTTP server error: %v", err)
        }
    }()

    sig := make(chan os.Signal, 1)
    signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
    <-sig

    log.Println("=== Shutting down K-town server ===")
    time.Sleep(100 * time.Millisecond)
}

func defaultConfig() *config.Config {
    return &config.Config{}
}