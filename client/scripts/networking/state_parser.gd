extends Node

# Parses incoming state from server and updates GameState

func parse_state(data: Dictionary) -> void:
    if data.get("type") != "state":
        return
    if data.has("tick"):
        GameState.set_tick(data["tick"])
    if data.has("weather"):
        GameState.set_weather(data["weather"])
    if data.has("agents"):
        for agent_data in data["agents"]:
            parse_agent(agent_data)
    if data.has("locations"):
        for loc_data in data["locations"]:
            GameState.set_location(loc_data["id"], loc_data)

func parse_agent(data: Dictionary) -> void:
    var agent_id: String = data.get("id", "")
    if agent_id == "":
        return
    var agent: Dictionary = {
        "id": agent_id,
        "name": data.get("name", "Unknown"),
        "role": data.get("role", "citizen"),
        "mood": data.get("mood", "neutral"),
        "location_id": data.get("location_id", ""),
        "memory": data.get("memory", []),
        "claims": data.get("claims", []),
        "relationships": data.get("relationships", {})
    }
    GameState.set_agent(agent_id, agent)

func parse_event(data: Dictionary) -> void:
    if data.get("type") != "event":
        return
    var event_data = {
        "id": data.get("id", ""),
        "event_type": data.get("event_type", ""),
        "tick": data.get("tick", 0),
        "location_id": data.get("location_id", ""),
        "participants": data.get("participants", []),
        "description": data.get("description", ""),
        "data": data.get("data", {})
    }
    # Forward to UI handlers
    GameState.state_updated.emit()

func parse_claim(data: Dictionary) -> void:
    var claim = {
        "id": data.get("id", ""),
        "agent_id": data.get("agent_id", ""),
        "content": data.get("content", ""),
        "confidence": data.get("confidence", 0.5),
        "source": data.get("source", ""),
        "tick": data.get("tick", 0)
    }
    var agent_id = claim["agent_id"]
    if GameState.agents.has(agent_id):
        var agent = GameState.agents[agent_id]
        agent["claims"].append(claim)
        GameState.set_agent(agent_id, agent)
