from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import hashlib
import logging
from functools import wraps

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hotel_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 配置
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    ADMIN_PASSWORD_HASH = hashlib.sha256(
        os.environ.get('ADMIN_PASSWORD', 'admin123').encode()
    ).hexdigest()
    DATABASE = 'hotel.db'
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# 權限裝飾器
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        password = request.args.get('password') or request.headers.get('X-API-Key')
        if not password:
            return jsonify({"status": "error", "message": "需要管理員權限"}), 401
        
        # 驗證密碼哈希
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != Config.ADMIN_PASSWORD_HASH:
            return jsonify({"status": "error", "message": "權限不足"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# 資料庫初始化
def init_db():
    conn = sqlite3.connect(Config.DATABASE)
    c = conn.cursor()
    
    # 創建房間表
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            capacity INTEGER DEFAULT 2,
            amenities TEXT DEFAULT '[]',
            images TEXT DEFAULT '[]',
            available INTEGER DEFAULT 1,
            featured INTEGER DEFAULT 0,
            rating REAL DEFAULT 4.5,
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
            guest_phone TEXT,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            guests INTEGER DEFAULT 1,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            payment_method TEXT DEFAULT 'credit_card',
            special_requests TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE
        )
    ''')
    
    # 創建用戶表（擴展功能）
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 插入範例資料
    c.execute('SELECT COUNT(*) FROM rooms')
    if c.fetchone()[0] == 0:
        sample_rooms = [
            ('豪華海景雙人房', 4200, '180度海景陽台，免費早餐與下午茶', 2, 
             '["wifi", "breakfast", "sea_view", "bathtub"]', 
             '["room1.jpg", "room2.jpg"]', 1, 1, 4.8),
            ('行政套房', 6800, '獨立客廳與辦公區，行政酒廊權益', 2,
             '["wifi", "breakfast", "executive_lounge", "workspace"]',
             '["suite1.jpg"]', 1, 1, 4.9),
            ('家庭連通房', 8500, '兩間相連客房，適合家庭入住', 4,
             '["wifi", "breakfast", "family", "connecting"]',
             '["family1.jpg"]', 1, 0, 4.7),
            ('標準雙床房', 2800, '兩張單人床，簡約舒適設計', 2,
             '["wifi", "tv", "desk"]',
             '["standard1.jpg"]', 1, 0, 4.3),
            ('商務單人房', 2200, '高效工作空間，快速網路', 1,
             '["wifi", "workspace", "coffee"]',
             '["business1.jpg"]', 1, 0, 4.4),
            ('總統套房', 18800, '私人管家服務，專屬露台與按摩浴缸', 2,
             '["wifi", "butler", "jacuzzi", "terrace", "luxury"]',
             '["president1.jpg", "president2.jpg"]', 1, 1, 5.0)
        ]
        c.executemany('''
            INSERT INTO rooms (name, price, description, capacity, amenities, images, available, featured, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_rooms)
        
        # 插入範例訂單
        sample_bookings = [
            (1, '陳大明', 'chen@example.com', '0912345678', 
             '2024-01-15', '2024-01-18', 2, 12600, 'confirmed'),
            (3, '林小美', 'lin@example.com', '0922333444',
             '2024-01-20', '2024-01-25', 4, 42500, 'confirmed'),
            (5, '王建國', 'wang@example.com', '0933555777',
             '2024-02-01', '2024-02-03', 1, 4400, 'pending')
        ]
        c.executemany('''
            INSERT INTO bookings (room_id, guest_name, guest_email, guest_phone, 
                                 check_in, check_out, guests, total_price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_bookings)
    
    conn.commit()
    conn.close()
    logger.info("資料庫初始化完成")

# 初始化資料庫
init_db()

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# 工具函數
def calculate_total_price(room_price, check_in, check_out):
    """計算住宿總價格"""
    try:
        start = datetime.strptime(check_in, '%Y-%m-%d')
        end = datetime.strptime(check_out, '%Y-%m-%d')
        nights = (end - start).days
        return room_price * max(1, nights)  # 至少一晚
    except:
        return room_price

def validate_date_range(check_in, check_out):
    """驗證日期範圍有效性"""
    try:
        start = datetime.strptime(check_in, '%Y-%m-%d')
        end = datetime.strptime(check_out, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if start < today:
            return False, "入住日期不能是過去日期"
        if start >= end:
            return False, "退房日期必須晚於入住日期"
        if (end - start).days > 30:
            return False, "住宿天數不能超過30天"
        
        return True, ""
    except ValueError:
        return False, "日期格式錯誤，請使用 YYYY-MM-DD"

# API 路由
@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "飯店管理系統 API",
        "version": "5.0",
        "documentation": {
            "rooms": {
                "GET /api/rooms": "取得所有房型（支援篩選）",
                "GET /api/rooms/<id>": "取得特定房型詳情",
                "GET /api/rooms/available": "查詢可訂房型",
                "POST /api/rooms": "新增房型 (需管理員權限)",
                "PUT /api/rooms/<id>": "更新房型 (需管理員權限)",
                "DELETE /api/rooms/<id>": "刪除房型 (需管理員權限)"
            },
            "bookings": {
                "GET /api/bookings": "取得所有訂單",
                "GET /api/bookings/<id>": "取得特定訂單",
                "POST /api/bookings": "創建新訂單",
                "PUT /api/bookings/<id>/status": "更新訂單狀態",
                "GET /api/bookings/check-availability": "檢查房型可用性"
            },
            "system": {
                "GET /api/stats": "取得統計資料",
                "GET /api/health": "系統健康檢查",
                "GET /api/search": "搜尋房型與訂單"
            }
        },
        "admin_password": "admin123 (開發環境)"
    })

@app.route('/api/health')
def health():
    try:
        conn = get_db_connection()
        room_count = conn.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]
        booking_count = conn.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "rooms": room_count,
                "bookings": booking_count,
                "file": os.path.exists(Config.DATABASE)
            },
            "system": {
                "python_version": os.sys.version,
                "platform": os.sys.platform
            }
        })
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# 房間相關 API
@app.route('/api/rooms')
def get_rooms():
    """取得所有房型，支援篩選"""
    try:
        # 查詢參數
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        capacity = request.args.get('capacity', type=int)
        featured = request.args.get('featured', type=int)
        available = request.args.get('available', 1, type=int)
        sort_by = request.args.get('sort_by', 'price')  # price, rating, name
        sort_order = request.args.get('sort_order', 'asc')  # asc, desc
        
        # 分頁參數
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page
        
        # 構建查詢
        query = 'SELECT * FROM rooms WHERE 1=1'
        params = []
        
        if min_price is not None:
            query += ' AND price >= ?'
            params.append(min_price)
        if max_price is not None:
            query += ' AND price <= ?'
            params.append(max_price)
        if capacity is not None:
            query += ' AND capacity >= ?'
            params.append(capacity)
        if featured is not None:
            query += ' AND featured = ?'
            params.append(featured)
        if available is not None:
            query += ' AND available = ?'
            params.append(available)
        
        # 排序
        valid_sort_columns = ['price', 'rating', 'name', 'created_at']
        sort_by = sort_by if sort_by in valid_sort_columns else 'price'
        sort_order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
        query += f' ORDER BY {sort_by} {sort_order}'
        
        # 分頁
        query += ' LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        
        conn = get_db_connection()
        rooms = conn.execute(query, params).fetchall()
        
        # 總數查詢（不分頁）
        count_query = 'SELECT COUNT(*) FROM rooms WHERE 1=1'
        count_params = params[:-2] if len(params) > 2 else []
        total = conn.execute(count_query, count_params).fetchone()[0]
        
        conn.close()
        
        rooms_list = []
        for room in rooms:
            room_dict = dict(room)
            # 解析 JSON 欄位
            room_dict['amenities'] = eval(room_dict.get('amenities', '[]'))
            room_dict['images'] = eval(room_dict.get('images', '[]'))
            rooms_list.append(room_dict)
        
        return jsonify({
            "status": "success",
            "data": rooms_list,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            },
            "filters": {
                "min_price": min_price,
                "max_price": max_price,
                "capacity": capacity,
                "featured": featured,
                "available": available
            }
        })
        
    except Exception as e:
        logger.error(f"取得房間列表失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/rooms/<int:room_id>')
def get_room(room_id):
    """取得特定房型詳情"""
    try:
        conn = get_db_connection()
        room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        conn.close()
        
        if room is None:
            return jsonify({"status": "error", "message": "房間不存在"}), 404
        
        room_dict = dict(room)
        room_dict['amenities'] = eval(room_dict.get('amenities', '[]'))
        room_dict['images'] = eval(room_dict.get('images', '[]'))
        
        return jsonify({"status": "success", "data": room_dict})
        
    except Exception as e:
        logger.error(f"取得房間詳情失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/rooms/available')
def get_available_rooms():
    """查詢可訂房型（根據日期）"""
    try:
        check_in = request.args.get('check_in')
        check_out = request.args.get('check_out')
        guests = request.args.get('guests', type=int, default=1)
        
        if not check_in or not check_out:
            return jsonify({"status": "error", "message": "需要 check_in 和 check_out 參數"}), 400
        
        # 驗證日期
        valid, message = validate_date_range(check_in, check_out)
        if not valid:
            return jsonify({"status": "error", "message": message}), 400
        
        conn = get_db_connection()
        
        # 查詢在指定日期已有訂單的房間
        busy_rooms = conn.execute('''
            SELECT DISTINCT room_id 
            FROM bookings 
            WHERE status IN ('confirmed', 'checked_in')
            AND (
                (check_in <= ? AND check_out > ?) OR
                (check_in < ? AND check_out >= ?) OR
                (check_in >= ? AND check_out <= ?)
            )
        ''', (check_out, check_in, check_out, check_in, check_in, check_out)).fetchall()
        
        busy_room_ids = [str(r['room_id']) for r in busy_rooms]
        
        # 查詢可用房間
        query = '''
            SELECT * FROM rooms 
            WHERE available = 1 
            AND capacity >= ?
        '''
        params = [guests]
        
        if busy_room_ids:
            query += f' AND id NOT IN ({",".join(["?"] * len(busy_room_ids))})'
            params.extend(busy_room_ids)
        
        rooms = conn.execute(query, params).fetchall()
        conn.close()
        
        rooms_list = []
        for room in rooms:
            room_dict = dict(room)
            room_dict['amenities'] = eval(room_dict.get('amenities', '[]'))
            room_dict['images'] = eval(room_dict.get('images', '[]'))
            
            # 計算總價
            total_price = calculate_total_price(
                room_dict['price'], check_in, check_out
            )
            room_dict['total_price'] = total_price
            room_dict['check_in'] = check_in
            room_dict['check_out'] = check_out
            
            rooms_list.append(room_dict)
        
        return jsonify({
            "status": "success",
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "count": len(rooms_list),
            "data": rooms_list
        })
        
    except Exception as e:
        logger.error(f"查詢可用房間失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/rooms', methods=['POST'])
@require_admin
def add_room():
    """新增房型"""
    try:
        data = request.get_json()
        
        # 驗證必要欄位
        required_fields = ['name', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"缺少必要欄位: {field}"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rooms (
                name, price, description, capacity, 
                amenities, images, available, featured, rating
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['price'],
            data.get('description', ''),
            data.get('capacity', 2),
            str(data.get('amenities', [])),
            str(data.get('images', [])),
            data.get('available', 1),
            data.get('featured', 0),
            data.get('rating', 4.5)
        ))
        
        conn.commit()
        room_id = cursor.lastrowid
        
        new_room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        conn.close()
        
        room_dict = dict(new_room)
        room_dict['amenities'] = eval(room_dict.get('amenities', '[]'))
        room_dict['images'] = eval(room_dict.get('images', '[]'))
        
        logger.info(f"新增房型: ID={room_id}, 名稱={data['name']}")
        
        return jsonify({
            "status": "success",
            "message": "房間新增成功",
            "data": room_dict
        }), 201
        
    except Exception as e:
        logger.error(f"新增房型失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 訂單相關 API
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    """創建新訂單"""
    try:
        data = request.get_json()
        
        # 驗證必要欄位
        required_fields = ['room_id', 'guest_name', 'guest_email', 'check_in', 'check_out']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"缺少必要欄位: {field}"}), 400
        
        # 驗證日期
        valid, message = validate_date_range(data['check_in'], data['check_out'])
        if not valid:
            return jsonify({"status": "error", "message": message}), 400
        
        conn = get_db_connection()
        
        # 檢查房間可用性
        room = conn.execute('''
            SELECT * FROM rooms 
            WHERE id = ? AND available = 1
        ''', (data['room_id'],)).fetchone()
        
        if room is None:
            conn.close()
            return jsonify({"status": "error", "message": "房間不存在或不可預訂"}), 400
        
        # 檢查日期是否衝突
        conflict = conn.execute('''
            SELECT COUNT(*) FROM bookings 
            WHERE room_id = ? 
            AND status IN ('confirmed', 'checked_in')
            AND (
                (check_in <= ? AND check_out > ?) OR
                (check_in < ? AND check_out >= ?)
            )
        ''', (
            data['room_id'],
            data['check_out'], data['check_in'],
            data['check_out'], data['check_in']
        )).fetchone()[0]
        
        if conflict > 0:
            conn.close()
            return jsonify({"status": "error", "message": "該日期房間已被預訂"}), 400
        
        # 計算總價
        total_price = calculate_total_price(
            room['price'], data['check_in'], data['check_out']
        )
        
        # 創建訂單
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bookings (
                room_id, guest_name, guest_email, guest_phone,
                check_in, check_out, guests, total_price,
                status, payment_method, special_requests
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['room_id'],
            data['guest_name'],
            data['guest_email'],
            data.get('guest_phone', ''),
            data['check_in'],
            data['check_out'],
            data.get('guests', 1),
            total_price,
            data.get('status', 'confirmed'),
            data.get('payment_method', 'credit_card'),
            data.get('special_requests', '')
        ))
        
        conn.commit()
        booking_id = cursor.lastrowid
        
        # 取得完整訂單資料
        new_booking = conn.execute('''
            SELECT b.*, r.name as room_name, r.price as room_price 
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.id = ?
        ''', (booking_id,)).fetchone()
        
        conn.close()
        
        logger.info(f"新訂單創建: ID={booking_id}, 房間={data['room_id']}, 客戶={data['guest_name']}")
        
        return jsonify({
            "status": "success",
            "message": "訂單創建成功",
            "data": dict(new_booking)
        }), 201
        
    except Exception as e:
        logger.error(f"創建訂單失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/bookings')
def get_bookings():
    """取得所有訂單（支援篩選）"""
    try:
        # 查詢參數
        status = request.args.get('status')
        guest_email = request.args.get('guest_email')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 分頁參數
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page
        
        # 構建查詢
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
        if guest_email:
            query += ' AND b.guest_email LIKE ?'
            params.append(f'%{guest_email}%')
        if start_date:
            query += ' AND b.check_in >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND b.check_out <= ?'
            params.append(end_date)
        
        query += ' ORDER BY b.created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        
        conn = get_db_connection()
        bookings = conn.execute(query, params).fetchall()
        
        # 總數查詢
        count_query = query.replace(
            'SELECT b.*, r.name as room_name, r.price as room_price', 
            'SELECT COUNT(*)'
        ).split('ORDER BY')[0]
        total = conn.execute(count_query, params[:-2]).fetchone()[0]
        
        conn.close()
        
        bookings_list = [dict(booking) for booking in bookings]
        
        return jsonify({
            "status": "success",
            "data": bookings_list,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            },
            "filters": {
                "status": status,
                "guest_email": guest_email,
                "start_date": start_date,
                "end_date": end_date
            }
        })
        
    except Exception as e:
        logger.error(f"取得訂單列表失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/bookings/check-availability')
def check_availability():
    """檢查房型可用性"""
    try:
        room_id = request.args.get('room_id', type=int)
        check_in = request.args.get('check_in')
        check_out = request.args.get('check_out')
        
        if not all([room_id, check_in, check_out]):
            return jsonify({"status": "error", "message": "缺少必要參數"}), 400
        
        # 驗證日期
        valid, message = validate_date_range(check_in, check_out)
        if not valid:
            return jsonify({"status": "error", "message": message}), 400
        
        conn = get_db_connection()
        
        # 檢查房間是否存在且可用
        room = conn.execute('''
            SELECT * FROM rooms 
            WHERE id = ? AND available = 1
        ''', (room_id,)).fetchone()
        
        if room is None:
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "房間不存在或不可預訂",
                "available": False
            }), 400
        
        # 檢查日期衝突
        conflict = conn.execute('''
            SELECT COUNT(*) FROM bookings 
            WHERE room_id = ? 
            AND status IN ('confirmed', 'checked_in')
            AND (
                (check_in <= ? AND check_out > ?) OR
                (check_in < ? AND check_out >= ?)
            )
        ''', (room_id, check_out, check_in, check_out, check_in)).fetchone()[0]
        
        conn.close()
        
        available = conflict == 0
        
        return jsonify({
            "status": "success",
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "available": available,
            "message": "可預訂" if available else "該日期已被預訂"
        })
        
    except Exception as e:
        logger.error(f"檢查可用性失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 統計資料 API
@app.route('/api/stats')
def get_stats():
    """取得統計資料"""
    try:
        conn = get_db_connection()
        
        # 房間統計
        room_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_rooms,
                SUM(CASE WHEN available = 1 THEN 1 ELSE 0 END) as available_rooms,
                SUM(CASE WHEN featured = 1 THEN 1 ELSE 0 END) as featured_rooms,
                AVG(price) as avg_price,
                MAX(price) as max_price,
                MIN(price) as min_price,
                AVG(rating) as avg_rating
            FROM rooms
        ''').fetchone()
        
        # 訂單統計
        booking_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_bookings,
                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_bookings,
                SUM(CASE WHEN status = 'checked_in' THEN 1 ELSE 0 END) as checked_in_bookings,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_bookings,
                SUM(total_price) as total_revenue,
                AVG(total_price) as avg_booking_price,
                MIN(created_at) as first_booking,
                MAX(created_at) as last_booking
            FROM bookings
        ''').fetchone()
        
        # 近期訂單
        recent_bookings = conn.execute('''
            SELECT b.*, r.name as room_name
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            ORDER BY b.created_at DESC
            LIMIT 5
        ''').fetchall()
        
        # 熱門房型
        popular_rooms = conn.execute('''
            SELECT r.id, r.name, r.price, COUNT(b.id) as booking_count,
                   SUM(b.total_price) as revenue
            FROM rooms r
            LEFT JOIN bookings b ON r.id = b.room_id
            GROUP BY r.id
            ORDER BY booking_count DESC
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "rooms": dict(room_stats),
            "bookings": dict(booking_stats),
            "recent_bookings": [dict(b) for b in recent_bookings],
            "popular_rooms": [dict(r) for r in popular_rooms]
        })
        
    except Exception as e:
        logger.error(f"取得統計資料失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 搜尋 API
@app.route('/api/search')
def search():
    """搜尋房型與訂單"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "需要搜尋關鍵字"}), 400
        
        conn = get_db_connection()
        
        # 搜尋房型
        rooms = conn.execute('''
            SELECT * FROM rooms 
            WHERE name LIKE ? OR description LIKE ?
            ORDER BY featured DESC, price ASC
            LIMIT 10
        ''', (f'%{query}%', f'%{query}%')).fetchall()
        
        # 搜尋訂單
        bookings = conn.execute('''
            SELECT b.*, r.name as room_name
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.guest_name LIKE ? OR b.guest_email LIKE ? 
            OR b.id = ?
            ORDER BY b.created_at DESC
            LIMIT 10
        ''', (f'%{query}%', f'%{query}%', query if query.isdigit() else 0)).fetchall()
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "query": query,
            "rooms": [dict(r) for r in rooms],
            "bookings": [dict(b) for b in bookings],
            "counts": {
                "rooms": len(rooms),
                "bookings": len(bookings)
            }
        })
        
    except Exception as e:
        logger.error(f"搜尋失敗: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "找不到請求的資源"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"伺服器錯誤: {error}")
    return jsonify({"status": "error", "message": "伺服器內部錯誤"}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("飯店管理系統 API 啟動")
    print("=" * 50)
    print(f"資料庫: {Config.DATABASE}")
    print(f"管理員密碼: admin123")
    print(f"API 文檔: http://127.0.0.1:{Config.PORT}/")
    print(f"健康檢查: http://127.0.0.1:{Config.PORT}/api/health")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=Config.DEBUG
    )
