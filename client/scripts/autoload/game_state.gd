extends Signal

# Global game state singleton

# Agent data: {id: {name, role, mood, location_id, memory[], claims[], relationships{}}}
var agents: Dictionary = {}

# Location data: {id: {name, type, position: Vector2, agent_ids: []}}
var locations: Dictionary = {}

# Current world tick
var current_tick: int = 0

# Weather: "sunny", "rainy", "cloudy", "stormy"
var weather: String = "sunny"

# Currently selected agent ID (empty if none)
var selected_agent_id: String = ""

# Current view tick (for replay mode)
var current_view_tick: int = 0

# Mode: "live" or "replay"
var mode: String = "live"

# #### Signals ####
signal agent_selected(agent_id: String)
signal state_updated()
signal tick_changed(new_tick: int)
signal mode_changed(new_mode: String)
signal weather_changed(new_weather: String)

func _ready():
    pass

func set_agent(agent_id: String, data: Dictionary):
    agents[agent_id] = data
    state_updated.emit()

func get_agent(agent_id: String) -> Dictionary:
    return agents.get(agent_id, {})

func set_location(loc_id: String, data: Dictionary):
    locations[loc_id] = data
    state_updated.emit()

func set_tick(tick: int):
    current_tick = tick
    if mode == "live":
        current_view_tick = tick
    tick_changed.emit(tick)

func select_agent(agent_id: String):
    selected_agent_id = agent_id
    agent_selected.emit(agent_id)

func set_weather(w: String):
    weather = w
    weather_changed.emit(w)

func set_mode(m: String):
    mode = m
    mode_changed.emit(m)
