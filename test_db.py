import sqlite3

# 測試資料庫連接
conn = sqlite3.connect('hotel.db')
cursor = conn.cursor()

print("=== 房間表結構 ===")
cursor.execute("PRAGMA table_info(rooms)")
for col in cursor.fetchall():
    print(col)

print("\n=== 訂單表結構 ===")
cursor.execute("PRAGMA table_info(bookings)")
for col in cursor.fetchall():
    print(col)

print("\n=== 範例房間資料 ===")
cursor.execute("SELECT * FROM rooms")
rooms = cursor.fetchall()
for room in rooms:
    print(f"ID: {room[0]}, 名稱: {room[1]}, 價格: {room[2]}")

print("\n=== 房間數量 ===")
cursor.execute("SELECT COUNT(*) FROM rooms")
print(f"總房間數: {cursor.fetchone()[0]}")

conn.close()
print("\n資料庫測試完成！")
