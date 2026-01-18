################################################################
### Backend for the Node1 (Flask + Paho-mqtt + Flask-SocketIO)
################################################################

import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, FirstNodeState # Import model + db
import json
import time
import os

app = Flask(__name__)
CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",   # use eventlet backend
    transports=["websocket"] # force websocket transport
)

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(base_dir, ".env"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "test")
# -------- PostgreSQL Connection URI -------------
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all() # make sur tables exist

# ----------- DB Helpers -------------
def get_state(key, default=None):
    with app.app_context():
        record = FirstNodeState.query.filter_by(key=key).first()
        return record.value if record else default

def set_state(key, value, ts=None):
    with app.app_context():
        record = FirstNodeState.query.filter_by(key=key).first()
        if not record:
            record = FirstNodeState(key=key, value=str(value), ts=ts)
            db.session.add(record)
        else:
            record.value = str(value)
            if ts:
                record.ts = ts
            db.session.merge(record)   # handles insert/update safely
        db.session.commit()

# ---------- MQTT Configurations ------------
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "test")
MQTT_PASS = os.getenv("MQTT_PASS", "test")
timeout = 60

# ------------ MQTT Topics creation ---------
PIR_TOPIC = "home/node1/motion"
LED1_TOPIC = "home/node1/led1"
LED2_TOPIC = "home/node1/led2"

# ------------  MQTT Callbacks -------------
def on_connect(client, userdata, flags, rc, properties):
    with app.app_context():
        print(f"MQTT connected, rc={rc}")
        client.subscribe([(PIR_TOPIC, 0)])

def on_message(client, userdata, message):
    with app.app_context():
        payload = message.payload.decode("UTF-8", errors="ignore")
        print(f"MQTT <- {message.topic, payload}")

    if message.topic == PIR_TOPIC:
        try:
            j_payload = json.loads(payload)
            motion_text = j_payload.get("motion", payload)
        except Exception:
            motion_text = payload
        
        if "no motion" in motion_text.lower():
            set_state("motion", "no_motion")
        else:
            ts = time.time()
            set_state("motion", "motion", ts=ts)
            set_state("last_motion_ts", ts)

        socketio.emit(
            "motion", {
                "motion": get_state("motion"),
                "payload": motion_text,
                "ts": get_state("last_motion_ts")
            }
        )
# MQTT Client Setup
mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

print("Connecting to MQTT Broker ...")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, timeout)
mqtt_client.loop_start()

# ------ SocketIO handlers -------
@socketio.on("connect")
def on_connect_socket():
    print("Frontend/Reactjs Web Client connected!")
    states = {r.key: r.value for r in FirstNodeState.query.all()}
    socketio.emit("state", states, to=request.sid)
    socketio.server.enter_room(request.sid, "all_clients")

@socketio.on('disconnect')
def handle_disconnect_socket():
    print('Frontend/Reactjs Web Client disconnected')

# ------- RESTful APIs
@app.route("/api/status", methods=["GET"])
def api_status():
    states = {r.key: r.value for r in FirstNodeState.query.all()}
    return jsonify(states)

@app.route("/api/led1", methods=["POST"])
def api_led1():
    body = request.get_json(force=True)
    state_val = body.get("state")
    if state_val not in ["on", "off"]:
        return jsonify({"error": "state must be 'on' or 'off'"}), 400
    mqtt_client.publish(LED1_TOPIC, state_val)
    set_state("led1", state_val)
    socketio.emit("led_update", {"led1": state_val})
    return jsonify({"led1": state_val})

@app.route("/api/led2", methods=["POST"])
def api_led2():
    body = request.get_json(force=True)
    try:
        level = int(body.get("level", -1))
    except:
        return jsonify({"error": "level must be integer 0 ... 5"}), 400
    if not (0 <= level <= 5):
        return jsonify({"error": "level must be 0..5"}), 400
    mqtt_client.publish(LED2_TOPIC, str(level))
    set_state("led2", level)
    socketio.emit("led_update", {"led2": level})
    return jsonify({"led2": level})

# ---- Run
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)