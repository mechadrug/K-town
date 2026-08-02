extends Control

# Agent inspector panel - shows selected agent details

@onready var _name_label: Label = /NameLabel
@onready var _role_label: Label = /RoleLabel
@onready var _mood_label: Label = /MoodLabel
@onready var _location_label: Label = /LocationLabel
@onready var _memory_list: ItemList = /MemoryList
@onready var _claims_list: ItemList = /ClaimsList
@onready var _chat_btn: Button = /ChatBtn
@onready var _close_btn: Button = /CloseBtn

var _agent_id: String = ""

func _ready():
    GameState.agent_selected.connect(_on_agent_selected)
    _close_btn.pressed.connect(_on_close)
    _chat_btn.pressed.connect(_on_chat)
    visible = false

func _on_agent_selected(agent_id: String):
    _agent_id = agent_id
    _refresh()
    visible = true

func _refresh():
    var agent = GameState.get_agent(_agent_id)
    if agent.is_empty():
        return
    _name_label.text = agent.get("name", "Unknown")
    _role_label.text = "Role: " + agent.get("role", "")
    _mood_label.text = "Mood: " + agent.get("mood", "")
    _location_label.text = "Location: " + agent.get("location_id", "")
    # Memory
    _memory_list.clear()
    for mem in agent.get("memory", []):
        _memory_list.add_item(str(mem))
    # Claims
    _claims_list.clear()
    for claim in agent.get("claims", []):
        _claims_list.add_item(str(claim.get("content", "")))

func _on_close():
    visible = false

func _on_chat():
    # Open chat panel for this agent
    var chat = get_node_or_null("/root/Main/UI/ChatPanel")
    if chat:
        chat.open_with(_agent_id)
