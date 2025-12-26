from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

rooms_db = [
    {"id": 1, "name": "豪華雙人房", "price": 3500, "description": "海景陽台、免費早餐"},
    {"id": 2, "name": "標準單人房", "price": 1800, "description": "市景、辦公桌"},
    {"id": 3, "name": "家庭套房", "price": 5500, "description": "兩房一廳、小廚房"}
]

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "飯店房型 API",
        "version": "3.0"
    })

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "room_count": len(rooms_db)})

@app.route('/api/rooms')
def get_rooms():
    return jsonify({
        "status": "success",
        "data": rooms_db,
        "count": len(rooms_db)
    })

@app.route('/api/rooms', methods=['POST'])
def add_room():
    password = request.args.get('password', '')
    if password != 'admin123':
        return jsonify({"status": "error", "message": "密碼錯誤"}), 401
    
    data = request.get_json()
    new_id = max([r['id'] for r in rooms_db], default=0) + 1
    new_room = {
        "id": new_id,
        "name": data.get('name', ''),
        "price": data.get('price', 0),
        "description": data.get('description', '')
    }
    rooms_db.append(new_room)
    return jsonify({"status": "success", "data": new_room}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if data.get('password') == 'admin123':
        return jsonify({"status": "success", "is_admin": True})
    return jsonify({"status": "error", "is_admin": False})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
