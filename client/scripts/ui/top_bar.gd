extends Control

@onready var _day_label = $DayLabel
@onready var _time_label = $TimeLabel
@onready var _weather_label = $WeatherLabel
@onready var _pause_btn = $PauseBtn
@onready var _speed_btn = $SpeedBtn
@onready var _replay_btn = $ReplayBtn

func _ready():
    GameState.tick_changed.connect(_on_tick_changed)
    GameState.weather_changed.connect(_on_weather_changed)
    GameState.mode_changed.connect(_on_mode_changed)
    _pause_btn.pressed.connect(_on_pause)
    _speed_btn.pressed.connect(_on_speed)
    _replay_btn.pressed.connect(_on_replay)
    _update_labels(0, "clear")

func _on_tick_changed(tick):
    var day = int(tick / 24) + 1
    var hour = tick % 24
    _day_label.text = "Day " + str(day)
    _time_label.text = "%02d:00" % hour

func _on_weather_changed(weather):
    _weather_label.text = weather

func _on_mode_changed(mode):
    _replay_btn.text = "Live" if mode == "replay" else "Replay"

func _on_pause():
    if GameState.mode == "live":
        GameState.set_mode("paused")
    elif GameState.mode == "paused":
        GameState.set_mode("live")

func _on_speed():
    pass

func _on_replay():
    if GameState.mode == "replay":
        GameState.set_mode("live")
    else:
        GameState.set_mode("replay")

func _update_labels(tick, weather):
    _on_tick_changed(tick)
    _on_weather_changed(weather)
