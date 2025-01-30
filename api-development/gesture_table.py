from flask import Flask, jsonify, request

app = Flask(__name__)

# Example gesture list
gestures = [
    {"id": 1, "name": "fistClose", "action": "select"},
    {"id": 2, "name": "pinchMoveUp", "action": "scrollUp"}
]

@app.route("/gestures", methods=["GET"])
def get_gestures():
    return jsonify(gestures)

@app.route("/gestures", methods=["POST"])
def add_gesture():
    data = request.get_json()
    new_id = max([g["id"] for g in gestures]) + 1 if gestures else 1
    new_gesture = {"id": new_id, "name": data["name"], "action": data["action"]}
    gestures.append(new_gesture)
    return jsonify({"status": "success", "gesture": new_gesture}), 201

@app.route("/gestures/<int:gesture_id>", methods=["DELETE"])
def delete_gesture(gesture_id):
    global gestures
    gestures = [g for g in gestures if g["id"] != gesture_id]
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5001)
