extends Node2D

# Player controller - handles player input and movement

@export var move_speed: float = 200.0

var _current_location_id: String = ""
var _player_id: String = "player_0"

@onready var _sprite: Sprite2D = 

func _ready():
    # Register player in GameState
    GameState.set_agent(_player_id, {
        "id": _player_id,
        "name": "Player",
        "role": "human",
        "mood": "neutral",
        "location_id": "square",
        "memory": [],
        "claims": [],
        "relationships": {}
    })

func _process(delta: float):
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

func _input(event: InputEvent):
    if GameState.mode != "live":
        return
    if event is InputEventKey and event.pressed:
        if event.keycode == KEY_E:
            _interact()
        elif event.keycode == KEY_I:
            _make_introduction()

func _interact():
    # Find nearest location
    var nearest_id = ""
    var nearest_dist = INF
    for loc_id in GameState.locations:
        var loc_data = GameState.locations[loc_id]
        var loc_pos = loc_data.get("position", Vector2.ZERO)
        var dist = position.distance_to(loc_pos)
        if dist < nearest_dist and dist < 80.0:
            nearest_dist = dist
            nearest_id = loc_id
    if nearest_id != "":
        _current_location_id = nearest_id
        GameState.set_agent(_player_id, GameState.get_agent(_player_id))
        # Send location change to server
        NetworkManager.send_action({
            "type": "player_move",
            "agent_id": _player_id,
            "location_id": nearest_id
        })

func _make_introduction():
    # Player creates a knowledge claim at current location
    var location_name = "unknown"
    if _current_location_id != "":
        var loc_data = GameState.locations.get(_current_location_id, {})
        location_name = loc_data.get("name", "unknown")
    var claim_text = "I am visiting " + location_name
    NetworkManager.send_action({
        "type": "player_introduce",
        "agent_id": _player_id,
        "location_id": _current_location_id,
        "claim": claim_text
    })
