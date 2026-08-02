extends Node2D

# Agent sprite - visual representation of an agent

@export var agent_id: String = ""

var _mood = "neutral"
var _selected = false
var _tween = null

@onready var _circle = $Circle
@onready var _name_label = $NameLabel
@onready var _mood_indicator = $MoodIndicator
@onready var _area = $Area2D

signal clicked(agent_id)

func _ready():
    _area.input_event.connect(_on_input_event)
    _update_appearance()

func _on_input_event(viewport, event, shape_idx):
    if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
        clicked.emit(agent_id)

func set_mood(mood):
    _mood = mood
    _update_appearance()

func set_selected(selected):
    _selected = selected
    _update_appearance()

func set_name(name):
    _name_label.text = name

func _update_appearance():
    match _mood:
        "happy": _circle.modulate = Color(0.3, 0.9, 0.3)
        "sad": _circle.modulate = Color(0.3, 0.3, 0.9)
        "angry": _circle.modulate = Color(0.9, 0.3, 0.3)
        "anxious": _circle.modulate = Color(0.9, 0.9, 0.3)
        _: _circle.modulate = Color(0.7, 0.7, 0.7)
    if _selected:
        _circle.modulate = _circle.modulate.lightened(0.3)
        _circle.scale = Vector2(1.2, 1.2)
    else:
        _circle.scale = Vector2(1.0, 1.0)

func move_to(target):
    if _tween and _tween.is_running():
        _tween.kill()
    _tween = create_tween()
    _tween.tween_property(self, "position", target, 0.8).set_ease(Tween.EASE_OUT)
