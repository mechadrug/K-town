package tick

import (
    "context"
    "fmt"
    "log"
    "time"

    "k-town/internal/agent"
    "k-town/internal/config"
    "k-town/internal/event"
    "k-town/internal/knowledge"
    "k-town/internal/llm"
    "k-town/internal/log"
    "k-town/internal/world"
)

type Engine struct {
    CurrentTick int64
    TickRate    time.Duration
    World       *world.World
    EventBus    *event.Bus
    Agents      []*agent.Agent
    Logger      *log.Logger
    Knowledge   *knowledge.Engine
    LLM         *llm.Client
    ctx         context.Context
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

func (e *Engine) SetAgents(agents []*agent.Agent) {
    e.Agents = agents
}

func (e *Engine) SetLogger(logger *log.Logger) {
    e.Logger = logger
}

func (e *Engine) SetKnowledgeEngine(k *knowledge.Engine) {
    e.Knowledge = k
}

func (e *Engine) SetLLMClient(l *llm.Client) {
    e.LLM = l
}

func (e *Engine) Run(ctx context.Context) {
    e.ctx = ctx
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

    day := (e.CurrentTick / 24) + 1
    hour := int(e.CurrentTick % 24)

    // Get all agent IDs at each location for social interactions
    locationAgents := make(map[string][]string)
    for _, a := range e.Agents {
        locationAgents[a.State.Location] = append(locationAgents[a.State.Location], a.Identity.ID)
    }

    // Process each agent
    for _, a := range e.Agents {
        events := e.EventBus.GetEventsAt(a.State.Location)
        eventStrs := eventsToStrings(events)
        agentsHere := locationAgents[a.State.Location]

        action := a.Tick(hour, agentsHere, eventStrs)

        if e.Logger != nil {
            e.Logger.LogDecision(log.DecisionRecord{
                Tick:       e.CurrentTick,
                AgentID:    a.Identity.ID,
                Action:     action.Description,
                Reason:     string(action.Type),
                Goal:       "",
                Confidence: 0.8,
                Method:     "rule",
            })
        }

        // Process events for knowledge generation
        for _, evt := range events {
            e.processEventForAgent(a, evt)
        }

        // Handle movement
        if action.Type == agent.ActionTypeMove && action.Target != "" {
            a.State.Location = action.Target
        }
    }

    // Clear processed events
    e.EventBus.ClearEvents()

    if hour == 0 && e.CurrentTick > 1 {
        log.Printf("[day %d complete] tick %d", day-1, e.CurrentTick)
    }
}

func (e *Engine) processEventForAgent(a *agent.Agent, evt *event.Event) {
    if e.Knowledge == nil {
        return
    }
    switch evt.Type {
    case event.WeatherChange:
        if weather, ok := evt.Payload["weather"].(string); ok {
            e.Knowledge.Observe(a.Identity.ID, "weather", fmt.Sprintf("Today weather is %s", weather), a.State.Location)
        }
    case event.ResourceFound:
        if res, ok := evt.Payload["resource"].(string); ok {
            e.Knowledge.Observe(a.Identity.ID, "resource", fmt.Sprintf("Found %s in %s", res, evt.Location), evt.Location)
        }
    case event.SocialEncounter:
        if agents, ok := evt.Payload["agents"].([]string); ok {
            for _, id := range agents {
                e.Knowledge.Observe(id, "social", fmt.Sprintf("Met someone at %s", evt.Location), evt.Location)
            }
        }
    case event.ItemCrafted:
        if item, ok := evt.Payload["item"].(string); ok {
            if agentID, ok := evt.Payload["agent_id"].(string); ok {
                e.Knowledge.Observe(agentID, "craft", fmt.Sprintf("Crafted %s", item), evt.Location)
            }
        }
    case event.RumorSpread:
        if claim, ok := evt.Payload["claim"].(string); ok {
            if from, ok := evt.Payload["from"].(string); ok {
                if to, ok := evt.Payload["to"].(string); ok {
                    e.Knowledge.Observe(from, "rumor", claim, evt.Location)
                    e.Knowledge.Observe(to, "rumor", fmt.Sprintf("Heard that %s", claim), evt.Location)
                }
            }
        }
    }
}

func eventsToStrings(events []*event.Event) []string {
    result := make([]string, len(events))
    for i, e := range events {
        result[i] = fmt.Sprintf("%s at %s", e.Type, e.Location)
    }
    return result
}