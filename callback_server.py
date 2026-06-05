from flask import Flask, request, Response
from datetime import datetime
import requests
import json
import threading

app = Flask(__name__)

# ========== 設定區 ==========
DISCORD_BOT_TOKEN = "MTUxMTM0Nzc0MTcxOTAwNzQ2NA.GiVg9D.1zTAlLGoHRfriINY-4CTDJkjzgbB-fvdClRDC8"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511948231721091187/7kqK_eHheCGnsDDMXyi3bzJQWXB670C4aOOTaqTS_0Zsh3O4ZzhgpQ4buPCBpL1KA2zG"
# ===========================

def send_to_discord(channel_id, content, embed=None):
    """發送訊息到 Discord"""
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
        print(f"發送結果: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"發送失敗: {e}")
        return False

def send_to_webhook(content, embed=None):
    """發送到 Webhook"""
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        print("✅ 已發送 Webhook 通知")
    except Exception as e:
        print(f"❌ 發送 Webhook 失敗: {e}")

def process_notification(data):
    """背景處理付款通知"""
    data_id = data.get('Data_id', '')
    amount = data.get('Amount', '')
    payment_no = data.get('Payment_no', '')
    response_id = data.get('Response_id', '')
    classif = data.get('Classif', '')
    
    print(f"處理訂單: {data_id}")
    
    if response_id == "1" or payment_no:
        print(f"✅ 訂單 {data_id} 付款成功！")
        
        embed = {
            "title": "✅ 付款成功通知",
            "description": f"訂單 **{data_id}** 已完成付款！",
            "color": 0x00ff00,
            "fields": [
                {"name": "💵 總金額", "value": f"{amount} 元", "inline": True},
                {"name": "🔢 超商代碼", "value": payment_no or "無", "inline": True},
                {"name": "🆔 訂單編號", "value": data_id, "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        # 發送到 Webhook
        send_to_webhook("", embed)
        
        # 從訂單 ID 提取頻道 ID
        if "_" in data_id:
            channel_id = data_id.split("_")[0].replace("ABA", "")
            print(f"📢 準備發送到頻道: {channel_id}")
            send_to_discord(channel_id, "", embed)

@app.route('/speedbuy_callback', methods=['POST', 'GET'])
def speedbuy_callback():
    if request.method == 'GET':
        data = request.args
    else:
        data = request.form
    
    print("=" * 50)
    print(f"收到速買配回傳 - {datetime.now()}")
    for key, value in data.items():
        print(f"  {key}: {value}")
    print("=" * 50)
    
    # 先立即回傳 OK（1秒內）
    response = Response('<Roturlstatus>OK</Roturlstatus>', mimetype='text/html')
    
    # 在背景執行通知（不影響回傳速度）
    thread = threading.Thread(target=process_notification, args=(data,))
    thread.daemon = True
    thread.start()
    
    return response

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("啟動速買配回傳接收伺服器...")
    app.run(host='0.0.0.0', port=5000, debug=False)
