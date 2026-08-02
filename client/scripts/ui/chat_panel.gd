extends Control

@onready var _messages_list = $MessagesList
@onready var _input_field = $InputField
@onready var _send_btn = $SendBtn
@onready var _close_btn = $CloseBtn
@onready var _title_label = $TitleLabel

var _target_agent_id = ""

func _ready():
    _send_btn.pressed.connect(_on_send)
    _close_btn.pressed.connect(_on_close)
    _input_field.text_submitted.connect(_on_text_submitted)
    visible = false

func open_with(agent_id):
    _target_agent_id = agent_id
    var agent = GameState.get_agent(agent_id)
    _title_label.text = "Chat with " + agent.get("name", "Agent")
    visible = true

func _on_send():
    var text = _input_field.text.strip_edges()
    if text == "" or _target_agent_id == "":
        return
    _add_message("You", text)
    NetworkManager.send_action({
        "type": "player_chat",
        "agent_id": "player_0",
        "target_agent_id": _target_agent_id,
        "message": text
    })
    _input_field.text = ""

func _on_text_submitted(text):
    _on_send()

func _add_message(sender, text):
    _messages_list.add_item(sender + ": " + text)

func _on_close():
    visible = false
    _target_agent_id = ""
