package api

import (
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"k-town/internal/event"
	"k-town/internal/log"
	"k-town/internal/world"
)

// Handler manages HTTP and WebSocket connections for the game server.
type Handler struct {
	mu       sync.RWMutex
	world    *world.World
	eventBus *event.Bus
	logger   *log.Logger
	upgrader websocket.Upgrader
	clients  map[*websocket.Conn]bool
	deltaBuf *DeltaBuffer
}

// NewHandler creates a new Handler instance.
func NewHandler(w *world.World, bus *event.Bus, logger *log.Logger) *Handler {
	h := &Handler{
		world:    w,
		eventBus: bus,
		logger:   logger,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
		clients:  make(map[*websocket.Conn]bool),
		deltaBuf: NewDeltaBuffer(),
	}
	return h
}

// RegisterRoutes sets up all HTTP routes on the given mux.
func (h *Handler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/state", h.handleState)
	mux.HandleFunc("/api/agents/", h.handleAgentDetail)
	mux.HandleFunc("/api/timeline", h.handleTimeline)
	mux.HandleFunc("/api/player/action", h.handlePlayerAction)
	mux.HandleFunc("/ws", h.handleWebSocket)
}

// broadcastLoop periodically sends state deltas to all connected WebSocket clients.
func (h *Handler) broadcastLoop(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		delta := h.deltaBuf.ComputeDelta(h.world)
		data, err := json.Marshal(delta)
		if err != nil {
			continue
		}
		h.mu.Lock()
		for conn := range h.clients {
			if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
				conn.Close()
				delete(h.clients, conn)
			}
		}
		h.mu.Unlock()
	}
}

// addClient registers a new WebSocket client.
func (h *Handler) addClient(conn *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.clients[conn] = true
}

// removeClient cleans up a disconnected WebSocket client.
func (h *Handler) removeClient(conn *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.clients, conn)
	conn.Close()
}

// writeError sends a JSON error response.
func writeError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
