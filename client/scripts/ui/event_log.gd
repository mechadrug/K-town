extends Control

@onready var _log_list = $LogList
@onready var _filter_option = $FilterOption

const MAX_ITEMS = 200

func _ready():
    GameState.state_updated.connect(_on_update)
    _filter_option.item_selected.connect(_on_filter_changed)

func _add_event(text, color = Color.WHITE):
    _log_list.add_item(text)
    var idx = _log_list.item_count - 1
    _log_list.set_item_custom_fg_color(idx, color)
    while _log_list.item_count > MAX_ITEMS:
        _log_list.remove_item(0)
    _log_list.scroll_to_item(_log_list.item_count - 1)

func _on_update():
    pass

func add_event_text(text, event_type = ""):
    var color = Color.WHITE
    match event_type:
        "move": color = Color(0.7, 0.9, 0.7)
        "chat": color = Color(0.7, 0.7, 0.9)
        "rumor": color = Color(0.9, 0.7, 0.7)
        _: color = Color(0.8, 0.8, 0.8)
    _add_event(text, color)

func _on_filter_changed(idx):
    pass
