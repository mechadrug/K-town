package api

import (
    "encoding/json"
    "net/http"
    "strconv"
    "strings"
)

func (h *Handler) handleState(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        writeError(w, http.StatusMethodNotAllowed, "GET required")
        return
    }
    w.Header().Set("Content-Type", "application/json")
    response := map[string]interface{}{
        "tick":      h.world.Time,
        "weather":   h.world.Weather,
        "locations": h.world.Locations,
        "agents":    agentsToMaps(h.agents),
    }
    json.NewEncoder(w).Encode(response)
}

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
    for _, a := range h.agents {
        if a.Identity.ID == id {
            w.Header().Set("Content-Type", "application/json")
            json.NewEncoder(w).Encode(a.ToMap())
            return
        }
    }
    writeError(w, http.StatusNotFound, "agent not found")
}

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
    _ = day
    events := h.logger.QueryWorldEvents(100)
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(events)
}

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
    h.processPlayerAction(action)
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}