extends Node2D

# Town map - manages locations and agent sprites

# Location positions on the map (pixel coordinates)
const LOCATION_POSITIONS = {
    "square": Vector2(640, 360),
    "cafe": Vector2(320, 240),
    "park": Vector2(960, 480)
}

var agent_sprites: Dictionary = {}  # id -> AgentSprite node
var location_nodes: Dictionary = {}  # id -> Location node

@onready var _locations_container: Node2D = 
@onready var _agents_container: Node2D = 

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
    # Clear existing
    for sprite in agent_sprites.values():
        sprite.queue_free()
    agent_sprites.clear()
    # Spawn from GameState
    for agent_id in GameState.agents:
        _spawn_agent(agent_id)

func _spawn_agent(agent_id: String):
    var data = GameState.agents[agent_id]
    var scene = preload("res://scenes/World/AgentSprite.tscn")
    var sprite = scene.instantiate()
    sprite.name = agent_id
    sprite.agent_id = agent_id
    var loc_id = data.get("location_id", "square")
    var base_pos = LOCATION_POSITIONS.get(loc_id, Vector2(640, 360))
    sprite.position = base_pos + Vector2(randf_range(-30, 30), randf_range(-30, 30))
    _agents_container.add_child(sprite)
    agent_sprites[agent_id] = sprite

func move_agent(agent_id: String, location_id: String):
    if not agent_sprites.has(agent_id):
        _spawn_agent(agent_id)
    var sprite = agent_sprites[agent_id]
    var target_pos = LOCATION_POSITIONS.get(location_id, Vector2(640, 360))
    target_pos += Vector2(randf_range(-30, 30), randf_range(-30, 30))
    sprite.move_to(target_pos)

func update_positions():
    for agent_id in GameState.agents:
        var data = GameState.agents[agent_id]
        var loc_id = data.get("location_id", "square")
        if agent_sprites.has(agent_id):
            var sprite = agent_sprites[agent_id]
            var target = LOCATION_POSITIONS.get(loc_id, Vector2(640, 360))
            target += Vector2(randf_range(-20, 20), randf_range(-20, 20))
            sprite.move_to(target)
