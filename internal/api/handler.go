package api

import (
    "encoding/json"
    "net/http"
    "sync"
    "time"

    "github.com/gorilla/websocket"
    "k-town/internal/agent"
    "k-town/internal/event"
    "k-town/internal/knowledge"
    "k-town/internal/log"
    "k-town/internal/world"
)

type Handler struct {
    mu       sync.RWMutex
    world    *world.World
    agents   []*agent.Agent
    eventBus *event.Bus
    logger   *log.Logger
    knowledge *knowledge.Engine
    upgrader websocket.Upgrader
    clients  map[*websocket.Conn]bool
    deltaBuf *DeltaBuffer
}

func NewHandler(w *world.World, agents []*agent.Agent, bus *event.Bus, logger *log.Logger, kng *knowledge.Engine) *Handler {
    h := &Handler{
        world:     w,
        agents:    agents,
        eventBus:  bus,
        logger:    logger,
        knowledge: kng,
        upgrader: websocket.Upgrader{
            CheckOrigin: func(r *http.Request) bool { return true },
        },
        clients:  make(map[*websocket.Conn]bool),
        deltaBuf: NewDeltaBuffer(),
    }
    return h
}

func (h *Handler) RegisterRoutes(mux *http.ServeMux) {
    mux.HandleFunc("/api/state", h.handleState)
    mux.HandleFunc("/api/agents/", h.handleAgentDetail)
    mux.HandleFunc("/api/timeline", h.handleTimeline)
    mux.HandleFunc("/api/player/action", h.handlePlayerAction)
    mux.HandleFunc("/ws", h.handleWebSocket)
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    h.mu.RLock()
    defer h.mu.RUnlock()
    if r.URL.Path == "/ws" {
        h.handleWebSocket(w, r)
        return
    }
    if r.URL.Path == "/api/state" {
        h.handleState(w, r)
        return
    }
    if r.URL.Path == "/api/timeline" {
        h.handleTimeline(w, r)
        return
    }
    if r.URL.Path == "/api/player/action" {
        h.handlePlayerAction(w, r)
        return
    }
    if len(r.URL.Path) > len("/api/agents/") && r.URL.Path[:len("/api/agents/")] == "/api/agents/" {
        h.handleAgentDetail(w, r)
        return
    }
    http.NotFound(w, r)
}

func (h *Handler) broadcastLoop(interval time.Duration) {
    ticker := time.NewTicker(interval)
    defer ticker.Stop()
    for range ticker.C {
        h.mu.Lock()
        for conn := range h.clients {
            delta := h.computeStateDelta()
            data, err := json.Marshal(delta)
            if err != nil {
                continue
            }
            if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
                conn.Close()
                delete(h.clients, conn)
            }
        }
        h.mu.Unlock()
    }
}

func (h *Handler) computeStateDelta() StateDelta {
    h.mu.RLock()
    defer h.mu.RUnlock()
    delta := StateDelta{
        Tick:      h.world.Time,
        Weather:   h.world.Weather,
        Timestamp: time.Now().Unix(),
    }
    for _, a := range h.agents {
        delta.Agents = append(delta.Agents, a.ToMap())
    }
    return delta
}

func (h *Handler) addClient(conn *websocket.Conn) {
    h.mu.Lock()
    defer h.mu.Unlock()
    h.clients[conn] = true
}

func (h *Handler) removeClient(conn *websocket.Conn) {
    h.mu.Lock()
    defer h.mu.Unlock()
    delete(h.clients, conn)
    conn.Close()
}

func writeError(w http.ResponseWriter, code int, msg string) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(code)
    json.NewEncoder(w).Encode(map[string]string{"error": msg})
}