extends Control

# Top bar - shows day/time/weather and control buttons

@onready var _day_label: Label = /DayLabel
@onready var _time_label: Label = /TimeLabel
@onready var _weather_label: Label = /WeatherLabel
@onready var _pause_btn: Button = /PauseBtn
@onready var _speed_btn: Button = /SpeedBtn
@onready var _replay_btn: Button = /ReplayBtn

func _ready():
    GameState.tick_changed.connect(_on_tick_changed)
    GameState.weather_changed.connect(_on_weather_changed)
    GameState.mode_changed.connect(_on_mode_changed)
    _pause_btn.pressed.connect(_on_pause)
    _speed_btn.pressed.connect(_on_speed)
    _replay_btn.pressed.connect(_on_replay)

func _on_tick_changed(tick: int):
    var day = tick / 24 + 1
    var hour = tick % 24
    _day_label.text = "Day " + str(day)
    _time_label.text = "%02d:00" % hour

func _on_weather_changed(weather: String):
    _weather_label.text = weather

func _on_mode_changed(mode: String):
    _replay_btn.text = "Live" if mode == "replay" else "Replay"

func _on_pause():
    GameState.set_mode("paused" if GameState.mode == "live" else "live")

func _on_speed():
    # Cycle speed: 1x -> 2x -> 4x -> 1x
    pass  # Speed handled by server tick rate

func _on_replay():
    if GameState.mode == "replay":
        GameState.set_mode("live")
    else:
        GameState.set_mode("replay")
