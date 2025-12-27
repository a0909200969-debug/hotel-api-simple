# 🏨 飯店房型管理 API

這是一個使用 Flask + SQLite 建立的飯店房型與訂單管理系統。

## 📋 功能特色
- ✅ 房間管理（CRUD 操作）
- ✅ 訂單管理
- ✅ SQLite 資料庫
- ✅ RESTful API 設計
- ✅ CORS 支援
- ✅ 管理員權限控制
- ✅ 統計資料端點

## 🚀 快速開始

### 1. 安裝依賴
\\\ash
pip install -r requirements.txt
\\\

### 2. 運行應用程式
\\\ash
python app.py
\\\

### 3. 訪問 API
- 主頁：http://127.0.0.1:5000/
- API 文檔：http://127.0.0.1:5000/（顯示所有端點）

## 📊 資料庫結構

### rooms 表
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | INTEGER | 主鍵 |
| name | TEXT | 房間名稱 |
| price | INTEGER | 價格 |
| description | TEXT | 描述 |
| available | INTEGER | 是否可用 (1/0) |
| created_at | TIMESTAMP | 創建時間 |

### bookings 表
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | INTEGER | 主鍵 |
| room_id | INTEGER | 房間 ID |
| guest_name | TEXT | 客人姓名 |
| guest_email | TEXT | 客人郵箱 |
| check_in | DATE | 入住日期 |
| check_out | DATE | 退房日期 |
| total_price | INTEGER | 總價 |
| status | TEXT | 訂單狀態 |
| created_at | TIMESTAMP | 創建時間 |

## 📡 API 端點

### 房間管理
- \GET /api/rooms\ - 取得所有房型
- \GET /api/rooms/<id>\ - 取得特定房型
- \POST /api/rooms?password=admin123\ - 新增房型
- \PUT /api/rooms/<id>\ - 更新房型
- \DELETE /api/rooms/<id>\ - 刪除房型

### 訂單管理
- \GET /api/bookings\ - 取得所有訂單
- \POST /api/bookings\ - 創建新訂單

### 系統狀態
- \GET /\ - API 文檔
- \GET /api/health\ - 健康檢查
- \GET /api/stats\ - 統計資料

## 🧪 測試

### 資料庫測試
\\\ash
python test_db.py
\\\

### API 測試
1. 先啟動伺服器：\python app.py\
2. 在另一個終端執行：\python test_api.py\

## 🚀 部署

### Render / Railway / Heroku
這些平台支援從 GitHub 直接部署，只需連接你的倉庫。

### 本地部署
\\\ash
# 使用 gunicorn（生產環境）
gunicorn app:app -w 4 -b 0.0.0.0:5000
\\\

## 📝 注意事項
- 管理員密碼：\dmin123\
- 預設端口：5000
- 資料庫檔案：\hotel.db\（自動創建）

## 📄 授權
MIT License
