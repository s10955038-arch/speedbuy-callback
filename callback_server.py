from flask import Flask, request, Response, jsonify
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import json
import threading
import time
import os
import urllib3

# 忽略 SSL 警告（因為使用 verify=False）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    """發送 Discord Webhook（強制指定 Discord IP）"""
    print(f"🔧 [Webhook] 準備發送通知")
    
    payload = {"embeds": [embed]}
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=15,
                verify=False
            )
            print(f"🔧 [Webhook] 嘗試 {attempt+1}/{max_retries} - 狀態碼: {response.status_code}")
            
            if response.status_code == 204:
                print("✅ 已發送 Webhook")
                return True
            else:
                print(f"⚠️ 回應異常: {response.status_code} - {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            print(f"⚠️ 請求超時 (嘗試 {attempt+1}/{max_retries})")
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ 連線錯誤 (嘗試 {attempt+1}/{max_retries}): {str(e)[:100]}")
        except Exception as e:
            print(f"⚠️ 發送異常 (嘗試 {attempt+1}/{max_retries}): {type(e).__name__} - {str(e)[:100]}")
        
        if attempt < max_retries - 1:
            print(f"🔧 等待 {retry_delay} 秒後重試...")
            time.sleep(retry_delay)
    
    print("❌ Webhook 發送失敗，已重試 3 次")
    return False

def send_to_discord(channel_id, embed):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json={"embeds": [embed]}, timeout=10)
        print(f"✅ 已發送到頻道 {channel_id}，狀態: {response.status_code}")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def check_order_payment(order_id):
    """查詢訂單是否已付款（跳過 SSL 驗證）"""
    url = f"https://ssl.smse.com.tw/ezpos/roturl.asp?Dcvc={SPEEDBUY_MERCHANT_ID}&Rvg2c={SPEEDBUY_PARAM_CODE}&Data_id={order_id}&types=xml"
    try:
        r = requests.get(url, timeout=10, verify=False)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            status = root.findtext("Status", "")
            amount = root.findtext("Amount", "")
            payment_no = root.findtext("Payment_no", "")
            
            print(f"[查詢] 訂單 {order_id} Status={status}, Amount={amount}")
            
            if status == "1" and amount and int(amount) > 0:
                print(f"[查詢] ✅ 訂單已付款！金額: {amount}")
                return {"paid": True, "amount": amount, "payment_no": payment_no}
            else:
                print(f"[查詢] ⏳ 訂單未付款或金額為0")
                return {"paid": False}
        return {"paid": False}
    except Exception as e:
        print(f"[查詢] 錯誤: {e}")
        return {"paid": False, "error": str(e)}

def scan_pending_orders():
    """掃描所有待付款訂單"""
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
                    {"name": "🆔 訂單編號", "value": oid, "inline": False},
                    {"name": "💵 總金額", "value": f"{result['amount']} 元", "inline": True},
                    {"name": "🔢 超商代碼", "value": result.get('payment_no', '無'), "inline": True}
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            # 發送 Webhook
            send_to_webhook(embed)
            
            if info.get("channel_id"):
                send_to_discord(info.get("channel_id"), embed)
        else:
            error_msg = result.get("error", "")
            if error_msg:
                print(f"⚠️ 查詢失敗: {error_msg}")
            else:
                print(f"⏳ 訂單 {oid} 尚未付款")
        time.sleep(1)
    
    save_orders(data)
    print(f"[{datetime.now()}] ========== 掃描完成 ==========")

def start_order_scanner():
    """啟動定時掃描器"""
    def scanner_loop():
        print("🚀 啟動訂單主動查詢服務（每5分鐘掃描一次）")
        print("✅ 主動查詢執行緒已啟動")
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
    """接收速買配回傳"""
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
                        {"name": "🆔 訂單編號", "value": oid, "inline": False},
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
    """儲存訂單（由 Discord Bot 呼叫）"""
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
    """查詢待付款訂單"""
    data = load_orders()
    pending = {oid: info for oid, info in data.get("orders", {}).items() if info.get("status") == "pending"}
    return jsonify({"count": len(pending), "orders": pending})

@app.route('/force_check', methods=['GET'])
def force():
    """手動觸發掃描"""
    print("🔥 手動觸發掃描！")
    scan_pending_orders()
    return jsonify({"status": "scanning_started", "message": "主動查詢已開始，請查看 Logs"})

@app.route('/check_one', methods=['GET'])
def check_one():
    """測試單一訂單查詢"""
    oid = request.args.get('order_id')
    if not oid:
        return jsonify({"error": "請提供 order_id 參數"}), 400
    result = check_order_payment(oid)
    return jsonify({"order_id": oid, "result": result})

@app.route('/health', methods=['GET'])
def health():
    """健康檢查"""
    data = load_orders()
    pending_count = len([o for o in data.get("orders", {}).values() if o.get("status") == "pending"])
    return jsonify({"status": "ok", "pending_orders": pending_count, "data_file": DATA_FILE})

@app.route('/')
def index():
    """首頁"""
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
    </ul>
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
