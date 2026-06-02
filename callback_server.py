from flask import Flask, request
from datetime import datetime
import requests
import json

app = Flask(__name__)

# ========== 設定區 ==========
# Discord Webhook URL（發送到指定頻道）
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511316917699219600/63Gv56ImNzDNuU_EtgzpL_p7Eup6f9gKasqY0EakYbCTmKGDAarjYy-yoJ1gZSBLhcDa"

# Discord Bot Token（發送到使用者下單的當前頻道）
DISCORD_BOT_TOKEN = "MTUxMTIxMjU0NjA1MTI4MDk0Ng.GhbwC4.Zc3V7nnQDCaV8T5FJ070bna5vnWHNncvrpaj1E"  # 請改成你的 Discord Bot Token
# ===========================

def send_to_webhook(content, embed=None):
    """發送到指定頻道（使用 Webhook）"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ 未設定 DISCORD_WEBHOOK_URL")
        return
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ 已發送 Webhook 通知到指定頻道")
    except Exception as e:
        print(f"❌ 發送 Webhook 失敗: {e}")

def send_to_channel(channel_id, content, embed=None):
    """發送到指定頻道 ID（使用 Bot Token）"""
    if not DISCORD_BOT_TOKEN:
        print("❌ 未設定 DISCORD_BOT_TOKEN")
        return
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"✅ 已發送通知到頻道 {channel_id}")
        else:
            print(f"❌ 發送失敗: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ 發送訊息失敗: {e}")

def get_channel_id_from_order(order_id):
    """從訂單 ID 獲取原本下單的頻道 ID"""
    try:
        with open("shop_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            orders = data.get("orders", {})
            if order_id in orders:
                return orders[order_id].get("channel_id")
    except Exception as e:
        print(f"讀取訂單資料失敗: {e}")
    return None

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
    
    classif = data.get('Classif', '')
    data_id = data.get('Data_id', '')
    payment_no = data.get('Payment_no', '')
    amount = data.get('Amount', '')
    response_id = data.get('Response_id', '')
    process_date = data.get('Process_date', '')
    
    # 判斷付款是否成功
    if response_id == "1" or payment_no:
        print(f"✅ 訂單 {data_id} 付款成功！")
        
        # 判斷付款方式
        if classif == "E":
            payment_type = "7-11 ibon"
        elif classif == "F":
            payment_type = "全家 FamiPort"
        elif classif == "D":
            payment_type = "CVS代碼繳費"
        else:
            payment_type = "超商代碼"
        
        # 建立成功通知 Embed
        embed = {
            "title": "✅ 付款成功通知",
            "description": f"訂單 **{data_id}** 已完成付款！",
            "color": 0x00ff00,
            "fields": [
                {"name": "💰 付款金額", "value": f"{amount} 元", "inline": True},
                {"name": "🏪 付款方式", "value": payment_type, "inline": True},
                {"name": "📅 付款時間", "value": process_date or datetime.now().strftime("%Y/%m/%d %H:%M:%S"), "inline": False},
                {"name": "🔢 超商代碼", "value": payment_no or "無", "inline": True},
                {"name": "🆔 訂單編號", "value": data_id, "inline": True}
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "阿巴商城 自動下單系統"}
        }
        
        # ========== 1. 發送到使用者下單的頻道（當前頻道）==========
        channel_id = get_channel_id_from_order(data_id)
        if channel_id:
            send_to_channel(channel_id, "", embed)
        else:
            print(f"⚠️ 找不到訂單 {data_id} 對應的頻道 ID")
        
        # ========== 2. 發送到指定頻道（Webhook）==========
        send_to_webhook("", embed)
        
    else:
        print(f"❌ 訂單 {data_id} 失敗或處理中")
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("=" * 50)
    print("啟動速買配回傳接收伺服器...")
    print("接收網址: /speedbuy_callback")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
