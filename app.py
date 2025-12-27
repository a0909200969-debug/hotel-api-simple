from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

# 資料庫初始化
def init_db():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    # 創建房間表
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            available INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 創建訂單表
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            guest_name TEXT NOT NULL,
            guest_email TEXT NOT NULL,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        )
    ''')
    
    # 插入範例資料（如果表是空的）
    c.execute('SELECT COUNT(*) FROM rooms')
    if c.fetchone()[0] == 0:
        sample_rooms = [
            ('豪華雙人房', 3500, '海景陽台、免費早餐'),
            ('標準單人房', 1800, '市景、辦公桌'),
            ('家庭套房', 5500, '兩房一廳、小廚房'),
            ('總統套房', 12000, '私人管家、按摩浴缸'),
            ('經濟雙床房', 2200, '兩張單人床、簡約風格')
        ]
        c.executemany('INSERT INTO rooms (name, price, description) VALUES (?, ?, ?)', sample_rooms)
    
    conn.commit()
    conn.close()

# 初始化資料庫
init_db()

# 資料庫連接函數
def get_db_connection():
    conn = sqlite3.connect('hotel.db')
    conn.row_factory = sqlite3.Row  # 以字典形式返回結果
    return conn

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "飯店房型管理 API (SQLite 資料庫版)",
        "version": "4.0",
        "endpoints": {
            "GET /api/rooms": "取得所有房型",
            "GET /api/rooms/<id>": "取得特定房型",
            "POST /api/rooms": "新增房型 (需密碼)",
            "PUT /api/rooms/<id>": "更新房型 (需密碼)",
            "DELETE /api/rooms/<id>": "刪除房型 (需密碼)",
            "GET /api/bookings": "取得所有訂單",
            "POST /api/bookings": "創建新訂單",
            "GET /api/stats": "取得統計資料"
        }
    })

@app.route('/api/health')
def health():
    conn = get_db_connection()
    room_count = conn.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]
    booking_count = conn.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
    conn.close()
    
    return jsonify({
        "status": "healthy",
        "room_count": room_count,
        "booking_count": booking_count,
        "database": "hotel.db"
    })

# 房間相關 API
@app.route('/api/rooms')
def get_rooms():
    conn = get_db_connection()
    rooms = conn.execute('SELECT * FROM rooms ORDER BY price').fetchall()
    conn.close()
    
    rooms_list = [dict(room) for room in rooms]
    return jsonify({
        "status": "success",
        "count": len(rooms_list),
        "data": rooms_list
    })

@app.route('/api/rooms/<int:room_id>')
def get_room(room_id):
    conn = get_db_connection()
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    conn.close()
    
    if room is None:
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    return jsonify({"status": "success", "data": dict(room)})

@app.route('/api/rooms', methods=['POST'])
def add_room():
    # 檢查管理員密碼
    password = request.args.get('password', '')
    if password != 'admin123':
        return jsonify({"status": "error", "message": "權限不足"}), 401
    
    data = request.get_json()
    
    # 驗證必要欄位
    required_fields = ['name', 'price']
    for field in required_fields:
        if field not in data:
            return jsonify({"status": "error", "message": f"缺少必要欄位: {field}"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO rooms (name, price, description, available)
            VALUES (?, ?, ?, ?)
        ''', (
            data['name'],
            data['price'],
            data.get('description', ''),
            data.get('available', 1)
        ))
        conn.commit()
        room_id = cursor.lastrowid
        
        # 取得新增的房間資料
        new_room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "房間新增成功",
            "data": dict(new_room)
        }), 201
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# 訂單相關 API
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.get_json()
    
    # 驗證必要欄位
    required_fields = ['room_id', 'guest_name', 'guest_email', 'check_in', 'check_out']
    for field in required_fields:
        if field not in data:
            return jsonify({"status": "error", "message": f"缺少必要欄位: {field}"}), 400
    
    conn = get_db_connection()
    
    try:
        # 檢查房間是否存在且可用
        room = conn.execute('SELECT * FROM rooms WHERE id = ? AND available = 1', 
                          (data['room_id'],)).fetchone()
        if room is None:
            conn.close()
            return jsonify({"status": "error", "message": "房間不存在或不可預訂"}), 400
        
        # 計算總價（簡化：天數 × 價格）
        # 實際應該計算天數差異，這裡簡化
        total_price = room['price']
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bookings (room_id, guest_name, guest_email, check_in, check_out, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['room_id'],
            data['guest_name'],
            data['guest_email'],
            data['check_in'],
            data['check_out'],
            total_price
        ))
        conn.commit()
        booking_id = cursor.lastrowid
        
        new_booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "訂單創建成功",
            "data": dict(new_booking)
        }), 201
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/bookings')
def get_bookings():
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT b.*, r.name as room_name, r.price as room_price 
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        ORDER BY b.created_at DESC
    ''').fetchall()
    conn.close()
    
    bookings_list = [dict(booking) for booking in bookings]
    return jsonify({
        "status": "success",
        "count": len(bookings_list),
        "data": bookings_list
    })

# 統計資料
@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    
    # 房間統計
    room_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_rooms,
            SUM(CASE WHEN available = 1 THEN 1 ELSE 0 END) as available_rooms,
            AVG(price) as avg_price,
            MAX(price) as max_price,
            MIN(price) as min_price
        FROM rooms
    ''').fetchone()
    
    # 訂單統計
    booking_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_bookings,
            SUM(total_price) as total_revenue,
            AVG(total_price) as avg_booking_price
        FROM bookings
    ''').fetchone()
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "rooms": dict(room_stats),
        "bookings": dict(booking_stats)
    })

if __name__ == '__main__':
    # 確保資料庫檔案存在
    if not os.path.exists('hotel.db'):
        init_db()
    
    print("飯店管理 API 啟動中...")
    print("資料庫: hotel.db")
    print("API 文檔: http://127.0.0.1:5000/")
    app.run(debug=True, port=5000)
