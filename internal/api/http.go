package api

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"strings"
)

// handleState returns the full world state as JSON.
func (h *Handler) handleState(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "GET required")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(h.world)
}

// handleAgentDetail returns details for a single agent.
// URL format: GET /api/agents/:id
func (h *Handler) handleAgentDetail(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "GET required")
		return
	}
	id := strings.TrimPrefix(r.URL.Path, "/api/agents/")
	if id == "" {
		writeError(w, http.StatusBadRequest, "agent id required")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"agent_id": id})
}

// handleTimeline returns world events for a given day.
// Query param: GET /api/timeline?day=N
func (h *Handler) handleTimeline(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "GET required")
		return
	}
	dayStr := r.URL.Query().Get("day")
	day, err := strconv.Atoi(dayStr)
	if err != nil || day < 0 {
		day = 0
	}
	events := h.logger.QueryWorldEvents(100)
	_ = day // future: filter events by day
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(events)
}

// handlePlayerAction accepts a player action and applies it to the world.
func (h *Handler) handlePlayerAction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "POST required")
		return
	}
	var action PlayerAction
	if err := json.NewDecoder(r.Body).Decode(&action); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	log.Printf("player action received: %+v", action)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
