extends Node2D

@export var move_speed = 200.0

var _current_location_id = ""
var _player_id = "player_0"

@onready var _sprite = $Sprite

func _ready():
    GameState.set_agent(_player_id, {
        "id": _player_id,
        "name": "Player",
        "role": "human",
        "mood": "neutral",
        "location": "square",
        "memory": [],
        "claims": [],
        "relationships": {}
    })

func _process(delta):
    if GameState.mode != "live":
        return
    var input_dir = Vector2.ZERO
    if Input.is_action_pressed("ui_right"):
        input_dir.x += 1
    if Input.is_action_pressed("ui_left"):
        input_dir.x -= 1
    if Input.is_action_pressed("ui_up"):
        input_dir.y -= 1
    if Input.is_action_pressed("ui_down"):
        input_dir.y += 1
    if input_dir != Vector2.ZERO:
        position += input_dir.normalized() * move_speed * delta

func _input(event):
    if GameState.mode != "live":
        return
    if event is InputEventKey and event.pressed:
        if event.keycode == KEY_E:
            _interact()

func _interact():
    var nearest_id = ""
    var nearest_dist = 999999.0
    for loc_id in GameState.locations:
        var loc_data = GameState.locations[loc_id]
        var loc_pos = loc_data.get("position", Vector2.ZERO)
        var dist = position.distance_to(loc_pos)
        if dist < nearest_dist and dist < 80.0:
            nearest_dist = dist
            nearest_id = loc_id
    if nearest_id != "":
        _current_location_id = nearest_id
        NetworkManager.send_action({
            "type": "player_move",
            "agent_id": _player_id,
            "target": nearest_id
        })
