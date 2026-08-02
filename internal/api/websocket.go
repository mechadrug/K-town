package api

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
	"k-town/internal/world"
)

// PlayerAction represents an incoming action from a human player.
type PlayerAction struct {
	Type    string                 `json:"type"`
	AgentID string                 `json:"agent_id"`
	Target  string                 `json:"target"`
	Payload map[string]interface{} `json:"payload"`
}

// StateDelta is the incremental state update sent to WebSocket clients.
type StateDelta struct {
	Tick      int64                    `json:"tick"`
	Weather   string                   `json:"weather"`
	Timestamp int64                    `json:"timestamp"`
	Agents    []map[string]interface{} `json:"agents,omitempty"`
	Events    []map[string]interface{} `json:"events,omitempty"`
	Claims    []map[string]interface{} `json:"claims,omitempty"`
}

// handleWebSocket upgrades the connection and starts read/write loops.
func (h *Handler) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("websocket upgrade failed: %v", err)
		return
	}
	h.addClient(conn)
	go h.readLoop(conn)
	go h.writeLoop(conn)
}

// readLoop reads PlayerAction messages from the client.
func (h *Handler) readLoop(conn *websocket.Conn) {
	defer h.removeClient(conn)
	for {
		_, msg, err := conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseNormalClosure) {
				log.Printf("websocket read error: %v", err)
			}
			return
		}
		var action PlayerAction
		if err := json.Unmarshal(msg, &action); err != nil {
			log.Printf("invalid player action: %v", err)
			continue
		}
		log.Printf("received player action: %+v", action)
	}
}

// writeLoop periodically sends StateDelta to the client.
func (h *Handler) writeLoop(conn *websocket.Conn) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		delta := StateDelta{
			Tick:      h.world.Time,
			Weather:   h.world.Weather,
			Timestamp: time.Now().Unix(),
		}
		data, err := json.Marshal(delta)
		if err != nil {
			continue
		}
		if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
			return
		}
	}
}
