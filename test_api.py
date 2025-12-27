import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_endpoint(endpoint, method='GET', data=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url)
        elif method == 'POST':
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=json.dumps(data), headers=headers)
        
        print(f"\n{method} {endpoint}")
        print(f"狀態碼: {response.status_code}")
        if response.text:
            print(f"回應: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response
    except Exception as e:
        print(f"錯誤: {e}")
        return None

if __name__ == '__main__':
    print("=== API 測試開始 ===")
    
    # 測試首頁
    test_endpoint('/')
    
    # 測試健康檢查
    test_endpoint('/api/health')
    
    # 測試取得所有房間
    test_endpoint('/api/rooms')
    
    # 測試取得特定房間
    test_endpoint('/api/rooms/1')
    
    # 測試統計資料
    test_endpoint('/api/stats')
    
    print("\n=== API 測試完成 ===")
