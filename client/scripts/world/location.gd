extends Node2D

# Location node - represents a place in the town

@export var location_id: String = ""
@export var location_name: String = "Location"
@export var location_type: String = "generic"

var agent_ids: Array = []

@onready var _sprite: Sprite2D = 
@onready var _label: Label = 

func _ready():
    _label.text = location_name
    # Color by type
    match location_type:
        "square":
            _sprite.modulate = Color(0.8, 0.7, 0.5)
        "cafe":
            _sprite.modulate = Color(0.6, 0.4, 0.2)
        "park":
            _sprite.modulate = Color(0.4, 0.8, 0.4)
        _:
            _sprite.modulate = Color(0.7, 0.7, 0.7)

func add_agent(agent_id: String):
    if not agent_ids.has(agent_id):
        agent_ids.append(agent_id)

func remove_agent(agent_id: String):
    agent_ids.erase(agent_id)
