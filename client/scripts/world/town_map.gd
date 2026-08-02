extends Node2D

# Town map - manages locations and agent sprites

const LOCATION_POSITIONS = {
    "square": Vector2(640, 360),
    "workshop": Vector2(320, 240),
    "wilderness": Vector2(960, 480)
}

var agent_sprites = {}
var location_nodes = {}

@onready var _locations_container = $Locations
@onready var _agents_container = $Agents

func _ready():
    _init_locations()

func _init_locations():
    for loc_id in LOCATION_POSITIONS:
        var scene = preload("res://scenes/World/Location.tscn")
        var node = scene.instantiate()
        node.name = loc_id
        node.position = LOCATION_POSITIONS[loc_id]
        _locations_container.add_child(node)
        location_nodes[loc_id] = node

func spawn_agents():
    for sprite in agent_sprites.values():
        sprite.queue_free()
    agent_sprites.clear()
    for agent_id in GameState.agents:
        _spawn_agent(agent_id)

func _spawn_agent(agent_id):
    var data = GameState.agents[agent_id]
    var scene = preload("res://scenes/World/AgentSprite.tscn")
    var sprite = scene.instantiate()
    sprite.name = agent_id
    sprite.agent_id = agent_id
    var loc_id = data.get("location", "square")
    var base_pos = LOCATION_POSITIONS.get(loc_id, Vector2(640, 360))
    sprite.position = base_pos + Vector2(randf_range(-30, 30), randf_range(-30, 30))
    _agents_container.add_child(sprite)
    agent_sprites[agent_id] = sprite

func move_agent(agent_id, location_id):
    if not agent_sprites.has(agent_id):
        _spawn_agent(agent_id)
    var sprite = agent_sprites[agent_id]
    var target = LOCATION_POSITIONS.get(location_id, Vector2(640, 360))
    target += Vector2(randf_range(-30, 30), randf_range(-30, 30))
    sprite.move_to(target)

func update_positions():
    for agent_id in GameState.agents:
        var data = GameState.agents[agent_id]
        var loc_id = data.get("location", "square")
        if agent_sprites.has(agent_id):
            var sprite = agent_sprites[agent_id]
            var target = LOCATION_POSITIONS.get(loc_id, Vector2(640, 360))
            target += Vector2(randf_range(-20, 20), randf_range(-20, 20))
            sprite.move_to(target)
