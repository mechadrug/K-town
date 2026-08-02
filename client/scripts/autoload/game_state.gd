extends Node

# Global game state singleton (autoload in project settings)

var agents = {}
var locations = {}
var current_tick = 0
var weather = "clear"
var selected_agent_id = ""
var current_view_tick = 0
var mode = "live"

signal agent_selected(agent_id)
signal state_updated()
signal tick_changed(new_tick)
signal mode_changed(new_mode)
signal weather_changed(new_weather)

func set_agent(agent_id, data):
    agents[agent_id] = data
    state_updated.emit()

func get_agent(agent_id):
    return agents.get(agent_id, {})

func set_location(loc_id, data):
    locations[loc_id] = data
    state_updated.emit()

func set_tick(tick):
    current_tick = tick
    if mode == "live":
        current_view_tick = tick
    tick_changed.emit(tick)

func select_agent(agent_id):
    selected_agent_id = agent_id
    agent_selected.emit(agent_id)

func set_weather(w):
    weather = w
    weather_changed.emit(w)

func set_mode(m):
    mode = m
    mode_changed.emit(m)
