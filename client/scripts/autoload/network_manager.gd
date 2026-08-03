extends Node

# Network manager singleton - manages WebSocket connection to Go server

const SERVER_URL: String = "ws://localhost:8090/ws"
const RECONNECT_DELAY: float = 3.0

var _ws: WebSocketPeer = null
var _connected: bool = false
var _reconnect_timer: float = 0.0

signal connected()
signal disconnected()
signal message_received(data: Dictionary)
signal connection_error(msg: String)

func _ready():
    _connect()

func _process(delta: float):
    if _connected and _ws:
        _ws.poll()
        var state = _ws.get_ready_state()
        while state == WebSocketPeer.STATE_OPEN:
            if _ws.get_available_packet_count() > 0:
                var raw = _ws.get_packet().get_string_from_utf8()
                var json = JSON.new()
                var err = json.parse(raw)
                if err == OK:
                    message_received.emit(json.data)
                else:
                    connection_error.emit("JSON parse error: " + json.get_error_message())
            _ws.poll()
            state = _ws.get_ready_state()
        if state == WebSocketPeer.STATE_CLOSED:
            _handle_disconnect()
    elif not _connected:
        _reconnect_timer -= delta
        if _reconnect_timer <= 0.0:
            _connect()

func _connect():
    _ws = WebSocketPeer.new()
    var err = _ws.connect_to_url(SERVER_URL)
    if err != OK:
        connection_error.emit("Failed to connect to " + SERVER_URL)
        _reconnect_timer = RECONNECT_DELAY
        return
    print("[NetworkManager] Connecting to " + SERVER_URL)

func _handle_disconnect():
    _connected = false
    _ws = null
    disconnected.emit()
    connection_error.emit("Disconnected from server")
    _reconnect_timer = RECONNECT_DELAY

func _exit_tree():
    if _ws:
        _ws.close()

func _ws_poll_result():
    if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN and not _connected:
        _connected = true
        connected.emit()
        print("[NetworkManager] Connected to server")

func send_action(action: Dictionary):
    if _connected and _ws:
        var raw = JSON.stringify(action)
        _ws.send_text(raw)

func is_connected() -> bool:
    return _connected
