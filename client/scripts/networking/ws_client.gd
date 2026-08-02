extends Node

# WebSocket client node - attach to scene tree
# Connects to Go server and emits signals for state/events

const SERVER_URL: String = "ws://localhost:8080/ws"

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected: bool = false

signal state_received(state: Dictionary)
signal event_received(event: Dictionary)
signal connection_established()
signal connection_closed()
signal connection_error(msg: String)

func _ready():
    var err = _ws.connect_to_url(SERVER_URL)
    if err != OK:
        connection_error.emit("Failed to connect: " + str(err))

func _process(delta: float):
    if not _ws:
        return
    _ws.poll()
    var state = _ws.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN and not _connected:
        _connected = true
        connection_established.emit()
    elif state == WebSocketPeer.STATE_CLOSED and _connected:
        _connected = false
        connection_closed.emit()
        return
    if state == WebSocketPeer.STATE_OPEN:
        while _ws.get_available_packet_count() > 0:
            var raw = _ws.get_packet().get_string_from_utf8()
            _handle_message(raw)

func _handle_message(raw: String):
    var json = JSON.new()
    var err = json.parse(raw)
    if err != OK:
        connection_error.emit("Parse error: " + json.get_error_message())
        return
    var data = json.data
    if data.get("type") == "state":
        state_received.emit(data)
    elif data.get("type") == "event":
        event_received.emit(data)

func send_action(action: Dictionary):
    if _connected and _ws:
        _ws.send_text(JSON.stringify(action))

func _exit_tree():
    if _ws:
        _ws.close()
