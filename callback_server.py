from flask import Flask, request, Response, jsonify
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import json
import threading
import time
import os

app = Flask(__name__)

# ========== 設定區 ==========
DISCORD_BOT_TOKEN = "MTUxMTM0Nzc0MTcxOTAwNzQ2NA.GiVg9D.1zTAlLGoHRfriINY-4CTDJkjzgbB-fvdClRDC8"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511948231721091187/7kqK_eHheCGnsDDMXyi3bzJQWXB670C4aOOTaqTS_0Zsh3O4ZzhgpQ4buPCBpL1KA2zG"
SPEEDBUY_MERCHANT_ID = "19989"
SPEEDBUY_PARAM_CODE = "1"
DATA_FILE = "/tmp/orders.json"

def load_orders():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if "orders" not in data:
                    data["orders"] = {}
                return data
        except:
            return {"orders": {}}
    return {"orders": {}}

def save_orders(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"儲存失敗: {e}")
        return False

def send_to_webhook(embed):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        print("✅ 已發送 Webhook")
    except Exception as e:
        print(f"❌ Webhook失敗: {e}")

def send_to_discord(channel_id, embed):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        requests.post(url, headers=headers, json={"embeds": [embed]}, timeout=10)
        print(f"✅ 已發送到頻道 {channel_id}")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def check_order_payment(order_id):
    url = f"https://ssl.smse.com.tw/ezpos/roturl.asp?Dcvc={SPEEDBUY_MERCHANT_ID}&Rvg2c={SPEEDBUY_PARAM_CODE}&Data_id={order_id}&types=xml"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            status = root.findtext("Status", "")
            amount = root.findtext("Amount", "")
            payment_no = root.findtext("Payment_no", "")
            print(f"[查詢] 訂單 {order_id} Status={status}")
            if status == "1":
                return {"paid": True, "amount": amount, "payment_no": payment_no}
        return {"paid": False}
    except Exception as e:
        print(f"[查詢] 錯誤: {e}")
        return {"paid": False, "error": str(e)}

def scan_pending_orders():
    print(f"[{datetime.now()}] ========== 開始掃描待付款訂單 ==========")
    data = load_orders()
    pending = {oid: info for oid, info in data.get("orders", {}).items() if info.get("status") == "pending"}
    print(f"找到 {len(pending)} 筆待付款訂單")
    
    for oid, info in pending.items():
        print(f"檢查訂單: {oid}")
        result = check_order_payment(oid)
        if result.get("paid"):
            print(f"✅ 訂單 {oid} 已付款！")
            data["orders"][oid]["status"] = "paid"
            
            embed = {
                "title": "✅ 付款成功通知",
                "description": f"訂單 **{oid}** 已完成付款！",
                "color": 0x00ff00,
                "fields": [
                    {"name": "💵 總金額", "value": f"{result['amount']} 元", "inline": True},
                    {"name": "🔢 超商代碼", "value": result.get('payment_no', '無'), "inline": True}
                ],
                "timestamp": datetime.now().isoformat()
            }
            send_to_webhook(embed)
            
            if info.get("channel_id"):
                send_to_discord(info.get("channel_id"), embed)
        else:
            print(f"⏳ 訂單 {oid} 尚未付款")
        time.sleep(1)
    
    save_orders(data)
    print(f"[{datetime.now()}] ========== 掃描完成 ==========")

def start_order_scanner():
    def scanner_loop():
        print("🚀 啟動訂單主動查詢服務（每5分鐘掃描一次）")
        time.sleep(10)
        while True:
            try:
                scan_pending_orders()
            except Exception as e:
                print(f"掃描失敗: {e}")
            time.sleep(300)
    threading.Thread(target=scanner_loop, daemon=True).start()

@app.route('/speedbuy_callback', methods=['POST', 'GET'])
def callback():
    data = request.form if request.method == 'POST' else request.args
    print(f"收到回傳: {dict(data)}")
    
    if data.get('Response_id') == '1' or data.get('Payment_no'):
        oid = data.get('Data_id')
        if oid:
            orders = load_orders()
            if oid in orders.get("orders", {}):
                orders["orders"][oid]["status"] = "paid"
                save_orders(orders)
                print(f"✅ 已更新訂單 {oid} 為 paid")
                
                embed = {
                    "title": "✅ 付款成功通知",
                    "description": f"訂單 **{oid}** 已完成付款！",
                    "color": 0x00ff00,
                    "fields": [
                        {"name": "💵 總金額", "value": f"{data.get('Amount', '')} 元", "inline": True},
                        {"name": "🔢 超商代碼", "value": data.get('Payment_no', '無'), "inline": True}
                    ],
                    "timestamp": datetime.now().isoformat()
                }
                send_to_webhook(embed)
                
                channel_id = oid.split("_")[0].replace("ABA", "") if "_" in oid else None
                if channel_id:
                    send_to_discord(channel_id, embed)
    
    return Response('<Roturlstatus>OK</Roturlstatus>', mimetype='text/html')

@app.route('/update_order_status', methods=['POST'])
def update_order():
    d = request.get_json()
    oid = d.get('order_id')
    if oid:
        data = load_orders()
        data["orders"][oid] = {
            "order_id": oid,
            "amount": d.get('amount'),
            "payment_no": d.get('payment_no'),
            "channel_id": d.get('channel_id'),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            **d.get('order_info', {})
        }
        save_orders(data)
        print(f"✅ 已儲存訂單: {oid}")
        return jsonify({"success": True, "order_id": oid})
    return jsonify({"error": "missing order_id"}), 400

@app.route('/pending_orders', methods=['GET'])
def pending():
    data = load_orders()
    pending = {oid: info for oid, info in data.get("orders", {}).items() if info.get("status") == "pending"}
    return jsonify({"count": len(pending), "orders": pending})

@app.route('/force_check', methods=['GET'])
def force():
    threading.Thread(target=scan_pending_orders).start()
    return jsonify({"status": "scanning_started"})

@app.route('/health', methods=['GET'])
def health():
    data = load_orders()
    pending_count = len([o for o in data.get("orders", {}).values() if o.get("status") == "pending"])
    return jsonify({"status": "ok", "pending_orders": pending_count, "data_file": DATA_FILE})

@app.route('/')
def index():
    return """
    <h1>SpeedBuy Callback Server</h1>
    <p>✅ 主動查詢每5分鐘執行一次</p>
    <p>📊 <a href='/health'>健康檢查</a></p>
    <p>📋 <a href='/pending_orders'>待付款訂單</a></p>
    <p>🔧 <a href='/force_check'>手動觸發掃描</a></p>
    """

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 啟動速買配整合伺服器...")
    print(f"📁 資料檔案: {DATA_FILE}")
    print("✅ 支援主動回傳接收")
    print("✅ 支援主動查詢掃描（每5分鐘）")
    print("=" * 60)
    
    if not os.path.exists(DATA_FILE):
        save_orders({"orders": {}})
        print("📝 已建立新的訂單資料檔")
    
    start_order_scanner()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
