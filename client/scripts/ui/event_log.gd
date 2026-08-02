extends Control

# Event log - scrollable list of world events

@onready var _log_list: ItemList = /LogList
@onready var _filter_option: OptionButton = /FilterOption

const MAX_ITEMS: int = 200

func _ready():
    GameState.state_updated.connect(_on_update)
    _filter_option.item_selected.connect(_on_filter_changed)

func _add_event(text: String, color: Color = Color.WHITE):
    _log_list.add_item(text)
    var idx = _log_list.item_count - 1
    _log_list.set_item_custom_fg_color(idx, color)
    # Trim old items
    while _log_list.item_count > MAX_ITEMS:
        _log_list.remove_item(0)
    _log_list.scroll_to_item(_log_list.item_count - 1)

func _on_update():
    # Called on any state update - could be refined to only events
    pass

func add_event_text(text: String, event_type: String = ""):
    var color = Color.WHITE
    match event_type:
        "move":
            color = Color(0.7, 0.9, 0.7)
        "chat":
            color = Color(0.7, 0.7, 0.9)
        "rumor":
            color = Color(0.9, 0.7, 0.7)
        "conflict":
            color = Color(0.9, 0.5, 0.3)
        _:
            color = Color(0.8, 0.8, 0.8)
    _add_event(text, color)

func _on_filter_changed(idx: int):
    # Filter implementation would go here
    pass
