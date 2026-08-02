package api

import (
    "encoding/json"
    "log"
    "net/http"
    "time"

    "github.com/gorilla/websocket"
    "k-town/internal/agent"
)

type PlayerAction struct {
    Type    string                 ` + "`json:\"type\"`" + `
    AgentID string                 ` + "`json:\"agent_id\"`" + `
    Target  string                 ` + "`json:\"target\"`" + `
    Payload map[string]interface{} ` + "`json:\"payload\"`" + `
}

type StateDelta struct {
    Tick      int64                    ` + "`json:\"tick\"`" + `
    Weather   string                   ` + "`json:\"weather\"`" + `
    Timestamp int64                    ` + "`json:\"timestamp\"`"+ `
    Agents    []map[string]interface{} ` + "`json:\"agents,omitempty\"`"+ `
    Events    []map[string]interface{} ` + "`json:\"events,omitempty\"`"+ `
    Claims    []map[string]interface{} ` + "`json:\"claims,omitempty\"`"+ `
}

func (h *Handler) handleWebSocket(w http.ResponseWriter, r *http.Request) {
    conn, err := h.upgrader.Upgrade(w, r, nil)
    if err != nil {
        log.Printf("websocket upgrade failed: %v", err)
        return
    }
    h.addClient(conn)
    go h.wsReadLoop(conn)
    go h.wsWriteLoop(conn)
}

func (h *Handler) wsReadLoop(conn *websocket.Conn) {
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
        h.processPlayerAction(action)
    }
}

func (h *Handler) wsWriteLoop(conn *websocket.Conn) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    for range ticker.C {
        delta := h.computeStateDelta()
        data, err := json.Marshal(delta)
        if err != nil {
            continue
        }
        if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
            return
        }
    }
}

func (h *Handler) processPlayerAction(action PlayerAction) {
    switch action.Type {
    case "move":
        for _, a := range h.agents {
            if a.Identity.ID == action.AgentID || action.AgentID == "" {
                a.State.Location = action.Target
                return
            }
        }
    case "claim":
        if h.knowledge != nil && action.Payload != nil {
            subject, _ := action.Payload["subject"].(string)
            claim, _ := action.Payload["claim"].(string)
            agentID, _ := action.Payload["agent_id"].(string)
            if subject != "" && claim != "" && agentID != "" {
                h.knowledge.Observe(agentID, subject, claim, "square")
            }
        }
    case "interact":
        log.Printf("player interaction: %+v", action.Payload)
    }
}

func agentsToMaps(agents []*agent.Agent) []map[string]interface{} {
    result := make([]map[string]interface{}, len(agents))
    for i, a := range agents {
        result[i] = a.ToMap()
    }
    return result
}