from flask import Flask, request, Response, jsonify
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import json
import threading
import time
import os
import re

app = Flask(__name__)

# ========== 設定區 ==========
DISCORD_BOT_TOKEN = "MTUxMTM0Nzc0MTcxOTAwNzQ2NA.GiVg9D.1zTAlLGoHRfriINY-4CTDJkjzgbB-fvdClRDC8"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511948231721091187/7kqK_eHheCGnsDDMXyi3bzJQWXB670C4aOOTaqTS_0Zsh3O4ZzhgpQ4buPCBpL1KA2zG"

# 速買配設定
SPEEDBUY_MERCHANT_ID = "19989"
SPEEDBUY_PARAM_CODE = "1"

# 資料庫檔案（Render 的 /tmp 目錄可寫入）
DATA_FILE = os.environ.get('DATA_FILE', '/tmp/orders.json')
# ===========================

def load_orders():
    """載入訂單資料"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "orders" not in data:
                    data["orders"] = {}
                return data
        except:
            return {"orders": {}}
    return {"orders": {}}

def save_orders(data):
    """儲存訂單資料"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"儲存失敗: {e}")
        return False

def send_to_discord(channel_id, content, embed=None):
    """發送訊息到 Discord（使用 Bot Token）"""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        print(f"發送到頻道 {channel_id} 結果: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"發送失敗: {e}")
        return False

def send_to_webhook(content, embed=None):
    """發送到 Discord Webhook"""
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        print("✅ 已發送 Webhook 通知")
    except Exception as e:
        print(f"❌ 發送 Webhook 失敗: {e}")

def send_payment_notification(order_id, amount, payment_no, channel_id=None):
    """發送付款成功通知（統一介面）"""
    embed = {
        "title": "✅ 付款成功通知",
        "description": f"訂單 **{order_id}** 已完成付款！",
        "color": 0x00ff00,
        "fields": [
            {"name": "💵 總金額", "value": f"{amount} 元", "inline": True},
            {"name": "🔢 超商代碼", "value": payment_no or "無", "inline": True},
            {"name": "🆔 訂單編號", "value": order_id, "inline": True}
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    # 發送到 Webhook（監控頻道）
    send_to_webhook("", embed)
    
    # 如果知道頻道 ID，也發送到原下單頻道
    if channel_id:
        send_to_discord(channel_id, "", embed)

def check_order_payment(order_id):
    """主動查詢訂單是否已付款（根據速買配 API 規格）"""
    url = f"https://ssl.smse.com.tw/ezpos/roturl.asp?Dcvc={SPEEDBUY_MERCHANT_ID}&Rvg2c={SPEEDBUY_PARAM_CODE}&Data_id={order_id}&types=xml"
    
    print(f"[查詢] 訂單: {order_id}")
    print(f"[查詢] URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"[查詢] 回應狀態: {response.status_code}")
        print(f"[查詢] 回應內容: {response.text[:200]}")
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            status = root.findtext("Status", "")
            amount = root.findtext("Amount", "")
            payment_no = root.findtext("Payment_no", "")
            
            print(f"[查詢] Status={status}, Amount={amount}, Payment_no={payment_no}")
            
            if status == "1":
                return {"paid": True, "amount": amount, "payment_no": payment_no}
            else:
                return {"paid": False}
        else:
            return {"paid": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"[查詢] 錯誤: {e}")
        return {"paid": False, "error": str(e)}

def extract_channel_id_from_order_id(order_id):
    """從訂單 ID 中提取頻道 ID"""
    if "_" in order_id:
        return order_id.split("_")[0].replace("ABA", "")
    return None

def process_callback_notification(data):
    """處理速買配主動回傳的付款通知"""
    data_id = data.get('Data_id', '')
    amount = data.get('Amount', '')
    payment_no = data.get('Payment_no', '')
    response_id = data.get('Response_id', '')
    
    print(f"處理回傳訂單: {data_id}")
    
    if response_id == "1" or payment_no:
        print(f"✅ 回傳通知：訂單 {data_id} 付款成功！")
        
        # 更新本地訂單狀態
        orders_data = load_orders()
        if data_id in orders_data.get("orders", {}):
            orders_data["orders"][data_id]["status"] = "paid"
            save_orders(orders_data)
            print(f"✅ 已更新訂單 {data_id} 狀態為 paid")
        
        # 提取頻道 ID
        channel_id = extract_channel_id_from_order_id(data_id)
        
        # 發送通知
        send_payment_notification(data_id, amount, payment_no, channel_id)

def scan_pending_orders():
    """主動掃描所有待付款訂單"""
    print(f"[{datetime.now()}] ========== 開始掃描待付款訂單 ==========")
    
    orders_data = load_orders()
    orders = orders_data.get("orders", {})
    pending_orders = {oid: info for oid, info in orders.items() if info.get("status") == "pending"}
    
    print(f"找到 {len(pending_orders)} 筆待付款訂單")
    
    if len(pending_orders) == 0:
        print("沒有待付款訂單，結束掃描")
        return
    
    updated_count = 0
    
    for order_id, order_info in pending_orders.items():
        print(f"檢查訂單: {order_id}")
        result = check_order_payment(order_id)
        
        if result.get("paid"):
            print(f"✅ 主動查詢發現訂單 {order_id} 已付款！")
            
            # 更新訂單狀態
            orders[order_id]["status"] = "paid"
            updated_count += 1
            
            # 發送通知
            send_payment_notification(
                order_id,
                result["amount"],
                result["payment_no"],
                order_info.get("channel_id")
            )
        else:
            error_msg = result.get("error", "")
            if error_msg:
                print(f"⚠️ 查詢失敗: {error_msg}")
            else:
                print(f"⏳ 訂單 {order_id} 尚未付款")
        
        time.sleep(1)  # 避免請求過於頻繁
    
    if updated_count > 0:
        save_orders(orders_data)
        print(f"✅ 已更新 {updated_count} 筆訂單狀態")
    
    print(f"[{datetime.now()}] ========== 掃描完成 ==========")

def start_order_scanner():
    """啟動定時掃描器（在背景執行）"""
    def scanner_loop():
        print("🚀 啟動訂單主動查詢服務（每5分鐘掃描一次）")
        time.sleep(10)  # 啟動後先等10秒
        while True:
            try:
                scan_pending_orders()
            except Exception as e:
                print(f"掃描失敗: {e}")
            time.sleep(300)  # 5分鐘
    
    scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
    scanner_thread.start()
    print("✅ 主動查詢執行緒已啟動")

# ========== API 路由 ==========

@app.route('/speedbuy_callback', methods=['POST', 'GET'])
def speedbuy_callback():
    """接收速買配回傳（速買配會呼叫這個網址）"""
    if request.method == 'GET':
        data = request.args
    else:
        data = request.form
    
    print("=" * 50)
    print(f"收到速買配回傳 - {datetime.now()}")
    for key, value in data.items():
        print(f"  {key}: {value}")
    print("=" * 50)
    
    # 先立即回傳 OK（速買配要求1秒內回應）
    response = Response('<Roturlstatus>OK</Roturlstatus>', mimetype='text/html')
    
    # 在背景執行通知處理（不影響回傳速度）
    thread = threading.Thread(target=process_callback_notification, args=(data,))
    thread.daemon = True
    thread.start()
    
    return response

@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    """讓 Discord Bot 下單後呼叫，儲存訂單資訊"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        amount = data.get('amount')
        payment_no = data.get('payment_no')
        channel_id = data.get('channel_id')
        order_info = data.get('order_info', {})
        
        if not order_id:
            return jsonify({"error": "missing order_id"}), 400
        
        orders_data = load_orders()
        orders_data["orders"][order_id] = {
            "order_id": order_id,
            "amount": amount,
            "payment_no": payment_no,
            "channel_id": channel_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            **order_info
        }
        
        save_orders(orders_data)
        print(f"✅ 已儲存訂單: {order_id}")
        
        return jsonify({"success": True, "order_id": order_id})
    
    except Exception as e:
        print(f"儲存訂單失敗: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/pending_orders', methods=['GET'])
def get_pending_orders():
    """取得所有待付款訂單（API）"""
    orders_data = load_orders()
    pending = {oid: info for oid, info in orders_data.get("orders", {}).items() 
               if info.get("status") == "pending"}
    return jsonify({"count": len(pending), "orders": pending})

@app.route('/force_check', methods=['GET'])
def force_check():
    """強制檢查所有 pending 訂單（手動觸發）"""
    print("🔥 手動觸發主動查詢！")
    threading.Thread(target=scan_pending_orders).start()
    return jsonify({"status": "scanning_started", "message": "主動查詢已開始，請查看 Logs"})

@app.route('/check_one', methods=['GET'])
def check_one():
    """檢查單一訂單（測試用）"""
    order_id = request.args.get('order_id')
    if not order_id:
        return jsonify({"error": "請提供 order_id 參數"}), 400
    
    result = check_order_payment(order_id)
    return jsonify({"order_id": order_id, "result": result})

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查"""
    orders_data = load_orders()
    pending_count = len([o for o in orders_data.get("orders", {}).values() if o.get("status") == "pending"])
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "pending_orders": pending_count,
        "data_file": DATA_FILE
    })

@app.route('/')
def index():
    return """
    <h1>SpeedBuy Callback Server with Active Query</h1>
    <p>✅ 回傳接收服務運行中</p>
    <p>✅ 主動查詢服務運行中（每5分鐘）</p>
    <p>📊 <a href='/health'>健康檢查</a></p>
    <hr>
    <h3>測試端點</h3>
    <ul>
        <li><a href='/force_check'>手動觸發掃描</a></li>
        <li><a href='/pending_orders'>查看待付款訂單</a></li>
        <li><a href='/check_one?order_id=ABA1512667668518273174_202606061202569536'>測試單一訂單查詢</a></li>
    </ul>
    """

# ========== 主程式 ==========
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 啟動速買配整合伺服器...")
    print(f"📁 資料檔案: {DATA_FILE}")
    print("✅ 支援主動回傳接收")
    print("✅ 支援主動查詢掃描（每5分鐘）")
    print("=" * 60)
    
    # 確保資料檔案存在
    if not os.path.exists(DATA_FILE):
        save_orders({"orders": {}})
        print("📝 已建立新的訂單資料檔")
    
    # 啟動定時掃描器
    start_order_scanner()
    
    # 取得 Render 設定的 PORT
    port = int(os.environ.get('PORT', 5000))
    
    # 啟動 Flask 伺服器
    app.run(host='0.0.0.0', port=port, debug=False)
    # 啟動 Flask 伺服器
    app.run(host='0.0.0.0', port=port, debug=False)
