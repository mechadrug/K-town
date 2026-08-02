extends Control

@onready var _timeline = $Timeline
@onready var _play_btn = $PlayBtn
@onready var _speed_btn = $SpeedBtn
@onready var _mode_btn = $ModeBtn
@onready var _tick_label = $TickLabel

var _playing = false
var _speed = 1.0
var _speeds = [0.5, 1.0, 2.0, 4.0]
var _speed_idx = 1

func _ready():
    GameState.tick_changed.connect(_on_tick_changed)
    GameState.mode_changed.connect(_on_mode_changed)
    _play_btn.pressed.connect(_on_play_toggle)
    _speed_btn.pressed.connect(_on_speed_cycle)
    _mode_btn.pressed.connect(_on_mode_toggle)
    _timeline.value_changed.connect(_on_timeline_scrub)
    visible = false

func _process(delta):
    if _playing and GameState.mode == "replay":
        GameState.current_view_tick += int(delta * _speed * 10)
        _tick_label.text = "Tick: " + str(GameState.current_view_tick)

func _on_tick_changed(tick):
    _timeline.max_value = float(tick)
    if GameState.mode == "live":
        _timeline.value = float(tick)
    _tick_label.text = "Tick: " + str(GameState.current_view_tick)

func _on_mode_changed(mode):
    visible = (mode == "replay")
    _mode_btn.text = "Live" if mode == "replay" else "Replay"

func _on_play_toggle():
    _playing = not _playing
    _play_btn.text = "Pause" if _playing else "Play"

func _on_speed_cycle():
    _speed_idx = (_speed_idx + 1) % _speeds.size()
    _speed = _speeds[_speed_idx]
    _speed_btn.text = str(_speed) + "x"

func _on_mode_toggle():
    if GameState.mode == "replay":
        GameState.set_mode("live")
    else:
        GameState.set_mode("replay")

func _on_timeline_scrub(value):
    GameState.current_view_tick = int(value)
    _tick_label.text = "Tick: " + str(GameState.current_view_tick)
