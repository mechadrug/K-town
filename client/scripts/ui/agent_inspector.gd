extends Control

@onready var _name_label = $NameLabel
@onready var _role_label = $RoleLabel
@onready var _mood_label = $MoodLabel
@onready var _location_label = $LocationLabel
@onready var _memory_list = $MemoryList
@onready var _claims_list = $ClaimsList
@onready var _chat_btn = $ChatBtn
@onready var _close_btn = $CloseBtn

var _agent_id = ""

func _ready():
    GameState.agent_selected.connect(_on_agent_selected)
    _close_btn.pressed.connect(_on_close)
    _chat_btn.pressed.connect(_on_chat)
    visible = false

func _on_agent_selected(agent_id):
    _agent_id = agent_id
    _refresh()
    visible = true

func _refresh():
    var agent = GameState.get_agent(_agent_id)
    if agent.is_empty():
        visible = false
        return
    _name_label.text = agent.get("name", "Unknown")
    _role_label.text = "Role: " + agent.get("role", "")
    _mood_label.text = "Mood: " + agent.get("mood", "")
    _location_label.text = "Location: " + agent.get("location", "")
    _memory_list.clear()
    for mem in agent.get("memory", []):
        _memory_list.add_item(str(mem))
    _claims_list.clear()
    for claim in agent.get("claims", []):
        _claims_list.add_item(str(claim.get("content", "")))

func _on_close():
    visible = false

func _on_chat():
    var chat = get_node_or_null("/root/Main/UI/ChatPanel")
    if chat:
        chat.open_with(_agent_id)
