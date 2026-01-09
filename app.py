from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 管理員密碼（實際部署時應該使用環境變數）
ADMIN_PASSWORD = 'admin123'

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
            room_type TEXT DEFAULT 'standard',  -- standard, deluxe, suite, family
            capacity INTEGER DEFAULT 2,
            amenities TEXT DEFAULT '',  -- JSON格式存儲設施
            available INTEGER DEFAULT 1,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 創建訂單表
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            guest_name TEXT NOT NULL,
            guest_email TEXT NOT NULL,
            guest_phone TEXT,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            nights INTEGER NOT NULL,
            guests INTEGER DEFAULT 1,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',  -- confirmed, cancelled, checked_in, checked_out, completed
            special_requests TEXT,
            payment_status TEXT DEFAULT 'pending',  -- pending, paid, refunded
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        )
    ''')
    
    # 創建用戶表（用於擴展）
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',  -- user, admin
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 插入範例資料（如果表是空的）
    c.execute('SELECT COUNT(*) FROM rooms')
    if c.fetchone()[0] == 0:
        sample_rooms = [
            ('豪華海景雙人房', 3500, '180度海景陽台、免費早餐、迷你吧', 'deluxe', 2, '["wifi", "breakfast", "ocean_view", "minibar"]', 1, 'https://example.com/room1.jpg'),
            ('標準單人房', 1800, '市景、辦公桌、高速網路', 'standard', 1, '["wifi", "desk", "tv"]', 1, 'https://example.com/room2.jpg'),
            ('家庭套房', 5500, '兩房一廳、小廚房、兒童遊樂區', 'family', 4, '["wifi", "kitchen", "living_room", "children_area"]', 1, 'https://example.com/room3.jpg'),
            ('總統套房', 12000, '私人管家、按摩浴缸、專屬陽台', 'suite', 2, '["wifi", "butler", "jacuzzi", "private_balcony", "minibar"]', 1, 'https://example.com/room4.jpg'),
            ('經濟雙床房', 2200, '兩張單人床、簡約風格、市景', 'standard', 2, '["wifi", "tv", "city_view"]', 1, 'https://example.com/room5.jpg')
        ]
        c.executemany('''
            INSERT INTO rooms (name, price, description, room_type, capacity, amenities, available, image_url) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_rooms)
    
    conn.commit()
    conn.close()

# 初始化資料庫
init_db()

# 資料庫連接函數
def get_db_connection():
    conn = sqlite3.connect('hotel.db')
    conn.row_factory = sqlite3.Row
    return conn

# 權限檢查裝飾器
def admin_required(f):
    def decorated_function(*args, **kwargs):
        password = request.args.get('password') or request.headers.get('X-Admin-Password')
        if password != ADMIN_PASSWORD:
            return jsonify({"status": "error", "message": "權限不足，需要管理員密碼"}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 輸入驗證函數
def validate_room_data(data):
    errors = []
    
    if 'name' not in data or not data['name'].strip():
        errors.append("房間名稱是必填欄位")
    
    if 'price' not in data:
        errors.append("價格是必填欄位")
    elif not isinstance(data['price'], (int, float)) or data['price'] <= 0:
        errors.append("價格必須是正數")
    
    if 'capacity' in data and (not isinstance(data['capacity'], int) or data['capacity'] <= 0):
        errors.append("容納人數必須是正整數")
    
    return errors

# ==================== ROOMS CRUD API ====================

# CREATE - 新增房間
@app.route('/api/rooms', methods=['POST'])
@admin_required
def create_room():
    """新增房間 (需管理員權限)"""
    data = request.get_json()
    
    # 驗證輸入
    errors = validate_room_data(data)
    if errors:
        return jsonify({"status": "error", "messages": errors}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO rooms (name, price, description, room_type, capacity, amenities, available, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'].strip(),
            data['price'],
            data.get('description', ''),
            data.get('room_type', 'standard'),
            data.get('capacity', 2),
            data.get('amenities', '[]'),
            data.get('available', 1),
            data.get('image_url', '')
        ))
        
        conn.commit()
        room_id = cursor.lastrowid
        
        # 取得新增的房間
        new_room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        
        # 更新時間戳
        conn.execute('UPDATE rooms SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (room_id,))
        conn.commit()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "房間新增成功",
            "data": dict(new_room)
        }), 201
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"新增失敗: {str(e)}"}), 500

# READ - 取得所有房間
@app.route('/api/rooms')
def get_rooms():
    """取得所有房間（可篩選）"""
    # 獲取查詢參數
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    room_type = request.args.get('type')
    available_only = request.args.get('available', type=lambda v: v.lower() == 'true')
    
    conn = get_db_connection()
    
    # 動態構建查詢
    query = 'SELECT * FROM rooms WHERE 1=1'
    params = []
    
    if min_price is not None:
        query += ' AND price >= ?'
        params.append(min_price)
    
    if max_price is not None:
        query += ' AND price <= ?'
        params.append(max_price)
    
    if room_type:
        query += ' AND room_type = ?'
        params.append(room_type)
    
    if available_only:
        query += ' AND available = 1'
    
    # 排序
    sort_by = request.args.get('sort_by', 'price')
    sort_order = request.args.get('sort_order', 'asc')
    valid_sort_fields = ['price', 'capacity', 'created_at', 'name']
    
    if sort_by in valid_sort_fields:
        query += f' ORDER BY {sort_by} {sort_order.upper()}'
    else:
        query += ' ORDER BY price ASC'
    
    rooms = conn.execute(query, params).fetchall()
    conn.close()
    
    rooms_list = [dict(room) for room in rooms]
    
    return jsonify({
        "status": "success",
        "count": len(rooms_list),
        "data": rooms_list
    })

# READ - 取得單一房間
@app.route('/api/rooms/<int:room_id>')
def get_room(room_id):
    """取得特定房間詳細資訊"""
    conn = get_db_connection()
    
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    
    if room is None:
        conn.close()
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    # 獲取該房間的訂單數
    booking_count = conn.execute('SELECT COUNT(*) FROM bookings WHERE room_id = ?', (room_id,)).fetchone()[0]
    
    conn.close()
    
    room_data = dict(room)
    room_data['booking_count'] = booking_count
    
    return jsonify({
        "status": "success",
        "data": room_data
    })

# UPDATE - 更新房間
@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
@admin_required
def update_room(room_id):
    """更新房間資訊 (需管理員權限)"""
    data = request.get_json()
    
    conn = get_db_connection()
    
    # 檢查房間是否存在
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if room is None:
        conn.close()
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    # 構建更新語句
    update_fields = []
    update_values = []
    
    if 'name' in data:
        update_fields.append('name = ?')
        update_values.append(data['name'].strip())
    
    if 'price' in data:
        if not isinstance(data['price'], (int, float)) or data['price'] <= 0:
            conn.close()
            return jsonify({"status": "error", "message": "價格必須是正數"}), 400
        update_fields.append('price = ?')
        update_values.append(data['price'])
    
    if 'description' in data:
        update_fields.append('description = ?')
        update_values.append(data['description'])
    
    if 'room_type' in data:
        update_fields.append('room_type = ?')
        update_values.append(data['room_type'])
    
    if 'capacity' in data:
        update_fields.append('capacity = ?')
        update_values.append(data['capacity'])
    
    if 'amenities' in data:
        update_fields.append('amenities = ?')
        update_values.append(data.get('amenities', '[]'))
    
    if 'available' in data:
        update_fields.append('available = ?')
        update_values.append(1 if data['available'] else 0)
    
    if 'image_url' in data:
        update_fields.append('image_url = ?')
        update_values.append(data['image_url'])
    
    if not update_fields:
        conn.close()
        return jsonify({"status": "error", "message": "沒有提供更新資料"}), 400
    
    # 添加更新時間
    update_fields.append('updated_at = CURRENT_TIMESTAMP')
    
    # 執行更新
    update_values.append(room_id)
    update_query = f'UPDATE rooms SET {", ".join(update_fields)} WHERE id = ?'
    
    try:
        conn.execute(update_query, update_values)
        conn.commit()
        
        # 取得更新後的房間資料
        updated_room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "房間更新成功",
            "data": dict(updated_room)
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"更新失敗: {str(e)}"}), 500

# PARTIAL UPDATE - 部分更新房間
@app.route('/api/rooms/<int:room_id>', methods=['PATCH'])
@admin_required
def patch_room(room_id):
    """部分更新房間（例如只更新可用狀態）"""
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "沒有提供更新資料"}), 400
    
    conn = get_db_connection()
    
    # 檢查房間是否存在
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if room is None:
        conn.close()
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    # 只允許更新特定欄位
    allowed_fields = ['available', 'price', 'description']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        conn.close()
        return jsonify({"status": "error", "message": "沒有有效的更新欄位"}), 400
    
    # 執行更新
    try:
        for field, value in update_data.items():
            if field == 'available':
                value = 1 if value else 0
            conn.execute(f'UPDATE rooms SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                        (value, room_id))
        
        conn.commit()
        updated_room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "房間部分更新成功",
            "data": dict(updated_room)
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"更新失敗: {str(e)}"}), 500

# DELETE - 刪除房間
@app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
@admin_required
def delete_room(room_id):
    """刪除房間 (需管理員權限)"""
    conn = get_db_connection()
    
    # 檢查房間是否存在
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if room is None:
        conn.close()
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    # 檢查是否有關聯的訂單
    booking_count = conn.execute('SELECT COUNT(*) FROM bookings WHERE room_id = ?', (room_id,)).fetchone()[0]
    if booking_count > 0:
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "無法刪除，此房間有相關訂單",
            "booking_count": booking_count
        }), 400
    
    # 執行刪除
    try:
        conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "房間刪除成功",
            "deleted_room_id": room_id
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"刪除失敗: {str(e)}"}), 500

# ==================== BOOKINGS CRUD API ====================

# CREATE - 新增訂單
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    """創建新訂單"""
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
        
        # 計算住宿天數
        try:
            check_in_date = datetime.strptime(data['check_in'], '%Y-%m-%d')
            check_out_date = datetime.strptime(data['check_out'], '%Y-%m-%d')
            nights = (check_out_date - check_in_date).days
            
            if nights <= 0:
                return jsonify({"status": "error", "message": "退房日期必須晚於入住日期"}), 400
                
        except ValueError:
            return jsonify({"status": "error", "message": "日期格式錯誤，請使用 YYYY-MM-DD"}), 400
        
        # 檢查日期衝突
        conflicting = conn.execute('''
            SELECT COUNT(*) FROM bookings 
            WHERE room_id = ? 
            AND status NOT IN ('cancelled')
            AND NOT (check_out <= ? OR check_in >= ?)
        ''', (data['room_id'], data['check_in'], data['check_out'])).fetchone()[0]
        
        if conflicting > 0:
            conn.close()
            return jsonify({"status": "error", "message": "該日期區間已被預訂"}), 400
        
        # 計算總價
        total_price = nights * room['price']
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bookings (room_id, guest_name, guest_email, guest_phone, 
                                 check_in, check_out, nights, guests, total_price, 
                                 special_requests)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['room_id'],
            data['guest_name'],
            data['guest_email'],
            data.get('guest_phone', ''),
            data['check_in'],
            data['check_out'],
            nights,
            data.get('guests', 1),
            total_price,
            data.get('special_requests', '')
        ))
        
        conn.commit()
        booking_id = cursor.lastrowid
        
        # 取得新增的訂單
        new_booking = conn.execute('''
            SELECT b.*, r.name as room_name, r.price as room_price 
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.id = ?
        ''', (booking_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "訂單創建成功",
            "data": dict(new_booking)
        }), 201
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"創建訂單失敗: {str(e)}"}), 500

# READ - 取得所有訂單
@app.route('/api/bookings')
def get_bookings():
    """取得所有訂單（可篩選）"""
    # 獲取查詢參數
    status = request.args.get('status')
    room_id = request.args.get('room_id', type=int)
    guest_email = request.args.get('guest_email')
    
    conn = get_db_connection()
    
    query = '''
        SELECT b.*, r.name as room_name, r.price as room_price 
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE 1=1
    '''
    params = []
    
    if status:
        query += ' AND b.status = ?'
        params.append(status)
    
    if room_id:
        query += ' AND b.room_id = ?'
        params.append(room_id)
    
    if guest_email:
        query += ' AND b.guest_email = ?'
        params.append(guest_email)
    
    query += ' ORDER BY b.created_at DESC'
    
    bookings = conn.execute(query, params).fetchall()
    conn.close()
    
    bookings_list = [dict(booking) for booking in bookings]
    
    return jsonify({
        "status": "success",
        "count": len(bookings_list),
        "data": bookings_list
    })

# READ - 取得單一訂單
@app.route('/api/bookings/<int:booking_id>')
def get_booking(booking_id):
    """取得特定訂單詳細資訊"""
    conn = get_db_connection()
    
    booking = conn.execute('''
        SELECT b.*, r.name as room_name, r.price as room_price, 
               r.description as room_description, r.image_url as room_image
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()
    
    if booking is None:
        conn.close()
        return jsonify({"status": "error", "message": "訂單不存在"}), 404
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "data": dict(booking)
    })

# UPDATE - 更新訂單
@app.route('/api/bookings/<int:booking_id>', methods=['PUT'])
def update_booking(booking_id):
    """更新訂單資訊"""
    data = request.get_json()
    
    # 檢查訂單是否存在
    conn = get_db_connection()
    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
    
    if booking is None:
        conn.close()
        return jsonify({"status": "error", "message": "訂單不存在"}), 404
    
    # 只允許更新特定欄位
    allowed_fields = ['guest_name', 'guest_email', 'guest_phone', 'guests', 'special_requests']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        conn.close()
        return jsonify({"status": "error", "message": "沒有有效的更新欄位"}), 400
    
    try:
        for field, value in update_data.items():
            conn.execute(f'UPDATE bookings SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                        (value, booking_id))
        
        conn.commit()
        
        # 取得更新後的訂單
        updated_booking = conn.execute('''
            SELECT b.*, r.name as room_name, r.price as room_price 
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.id = ?
        ''', (booking_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "訂單更新成功",
            "data": dict(updated_booking)
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"更新失敗: {str(e)}"}), 500

# DELETE - 刪除訂單
@app.route('/api/bookings/<int:booking_id>', methods=['DELETE'])
@admin_required
def delete_booking(booking_id):
    """刪除訂單 (需管理員權限)"""
    conn = get_db_connection()
    
    # 檢查訂單是否存在
    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
    if booking is None:
        conn.close()
        return jsonify({"status": "error", "message": "訂單不存在"}), 404
    
    try:
        # 軟刪除：將狀態改為 cancelled
        conn.execute('''
            UPDATE bookings 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (booking_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "訂單已取消",
            "cancelled_booking_id": booking_id
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"刪除失敗: {str(e)}"}), 500

# ==================== 其他功能 API ====================

@app.route('/api/rooms/<int:room_id>/bookings')
def get_room_bookings(room_id):
    """取得特定房間的所有訂單"""
    conn = get_db_connection()
    
    # 檢查房間是否存在
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if room is None:
        conn.close()
        return jsonify({"status": "error", "message": "房間不存在"}), 404
    
    bookings = conn.execute('''
        SELECT * FROM bookings 
        WHERE room_id = ? 
        ORDER BY check_in DESC
    ''', (room_id,)).fetchall()
    
    conn.close()
    
    bookings_list = [dict(booking) for booking in bookings]
    
    return jsonify({
        "status": "success",
        "room": dict(room),
        "bookings": bookings_list,
        "count": len(bookings_list)
    })

@app.route('/api/bookings/guest/<string:email>')
def get_guest_bookings(email):
    """取得特定客人的所有訂單"""
    conn = get_db_connection()
    
    bookings = conn.execute('''
        SELECT b.*, r.name as room_name, r.price as room_price 
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE b.guest_email = ?
        ORDER BY b.created_at DESC
    ''', (email,)).fetchall()
    
    conn.close()
    
    bookings_list = [dict(booking) for booking in bookings]
    
    return jsonify({
        "status": "success",
        "guest_email": email,
        "bookings": bookings_list,
        "count": len(bookings_list)
    })

@app.route('/api/rooms/types')
def get_room_types():
    """取得所有房間類型"""
    conn = get_db_connection()
    
    room_types = conn.execute('''
        SELECT room_type, COUNT(*) as count, 
               AVG(price) as avg_price, MIN(price) as min_price, MAX(price) as max_price
        FROM rooms 
        GROUP BY room_type
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "data": [dict(room_type) for room_type in room_types]
    })

# ==================== 主程式 ====================

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "飯店房型管理 API (完整 CRUD 版)",
        "version": "5.0",
        "endpoints": {
            # 房間 CRUD
            "GET /api/rooms": "取得所有房型",
            "POST /api/rooms": "新增房型 (需密碼)",
            "GET /api/rooms/<id>": "取得特定房型",
            "PUT /api/rooms/<id>": "更新房型 (需密碼)",
            "PATCH /api/rooms/<id>": "部分更新房型 (需密碼)",
            "DELETE /api/rooms/<id>": "刪除房型 (需密碼)",
            
            # 訂單 CRUD
            "GET /api/bookings": "取得所有訂單",
            "POST /api/bookings": "創建新訂單",
            "GET /api/bookings/<id>": "取得特定訂單",
            "PUT /api/bookings/<id>": "更新訂單",
            "DELETE /api/bookings/<id>": "取消訂單 (需密碼)",
            
            # 其他功能
            "GET /api/rooms/<id>/bookings": "取得房間的所有訂單",
            "GET /api/bookings/guest/<email>": "取得客人的所有訂單",
            "GET /api/rooms/types": "取得房間類型統計",
            "GET /api/health": "系統健康檢查",
            "GET /api/stats": "取得統計資料"
        }
    })

@app.route('/api/health')
def health():
    conn = get_db_connection()
    
    try:
        room_count = conn.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]
        booking_count = conn.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
        available_rooms = conn.execute('SELECT COUNT(*) FROM rooms WHERE available = 1').fetchone()[0]
        
        # 檢查資料庫連接
        conn.execute('SELECT 1')
        
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "room_count": room_count,
            "available_rooms": available_rooms,
            "booking_count": booking_count,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 500

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
            MIN(price) as min_price,
            SUM(price * capacity) as total_capacity_value
        FROM rooms
    ''').fetchone()
    
    # 訂單統計
    booking_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_bookings,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_bookings,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_bookings,
            SUM(CASE WHEN status IN ('confirmed', 'checked_in', 'checked_out') THEN total_price ELSE 0 END) as total_revenue,
            AVG(total_price) as avg_booking_price,
            SUM(CASE WHEN status IN ('confirmed', 'checked_in', 'checked_out') THEN nights ELSE 0 END) as total_nights
        FROM bookings
    ''').fetchone()
    
    # 每月收入統計
    monthly_stats = conn.execute('''
        SELECT 
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as booking_count,
            SUM(total_price) as monthly_revenue
        FROM bookings
        WHERE status IN ('confirmed', 'checked_in', 'checked_out')
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month DESC
        LIMIT 6
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "rooms": dict(room_stats),
        "bookings": dict(booking_stats),
        "monthly_stats": [dict(stat) for stat in monthly_stats]
    })

if __name__ == '__main__':
    # 確保資料庫檔案存在
    if not os.path.exists('hotel.db'):
        init_db()
    
    print("飯店管理 API 啟動中...")
    print("資料庫: hotel.db")
    print("管理員密碼: admin123")
    print("API 文檔: http://127.0.0.1:5000/")
    print("\n主要端點:")
    print("- GET  /api/rooms - 取得所有房間")
    print("- POST /api/rooms?password=admin123 - 新增房間")
    print("- PUT  /api/rooms/<id>?password=admin123 - 更新房間")
    print("- DELETE /api/rooms/<id>?password=admin123 - 刪除房間")
    print("\n啟動成功！")
    
    app.run(debug=True, port=5000)
