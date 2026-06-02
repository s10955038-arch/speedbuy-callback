from flask import Flask, request
from datetime import datetime
import requests
import json

app = Flask(__name__)

# ========== 設定區 ==========
# Discord Bot Token（用你原本的 Bot Token）
DISCORD_BOT_TOKEN = "MTUxMTM0Nzc0MTcxOTAwNzQ2NA.G4lxjw.4CBVhMoyzxAqNHm2ZDGxdqetFMwgwoKRAQLR74"

# Discord Webhook URL（備用，發送到指定頻道）
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511316917699219600/63Gv56ImNzDNuU_EtgzpL_p7Eup6f9gKasqY0EakYbCTmKGDAarjYy-yoJ1gZSBLhcDa"
# ===========================

def send_to_discord(channel_id, content, embed=None):
    """直接用 Bot Token 發送訊息到 Discord（不需要 Bot 登入）"""
    if not DISCORD_BOT_TOKEN:
        print("❌ 未設定 DISCORD_BOT_TOKEN")
        return False
    
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
            return True
        else:
            print(f"❌ 發送失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 發送訊息失敗: {e}")
        return False

def send_to_webhook(content, embed=None):
    """發送到指定頻道（使用 Webhook）"""
    if not DISCORD_WEBHOOK_URL:
        return
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ 已發送 Webhook 通知")
    except Exception as e:
        print(f"❌ 發送 Webhook 失敗: {e}")

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
    
    if response_id == "1" or payment_no:
        print(f"✅ 訂單 {data_id} 付款成功！")
        
        if classif == "E":
            payment_type = "7-11 ibon"
        elif classif == "F":
            payment_type = "全家 FamiPort"
        else:
            payment_type = "超商代碼"
        
        embed = {
            "title": "✅ 付款成功通知",
            "description": f"訂單 **{data_id}** 已完成付款！",
            "color": 0x00ff00,
            "fields": [
                {"name": "💵 總金額", "value": f"{amount} 元", "inline": True},
                {"name": "🏪 付款方式", "value": payment_type, "inline": True},
                {"name": "🔢 超商代碼", "value": payment_no or "無", "inline": True},
                {"name": "🆔 訂單編號", "value": data_id, "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. 發送到 Webhook 指定頻道
        send_to_webhook("", embed)
        
        # 2. 從訂單 ID 解析頻道 ID，發送到當前頻道
        if data_id.startswith("ABA"):
            parts = data_id.split("_")
            if len(parts) >= 2:
                channel_id = parts[0].replace("ABA", "")
                print(f"✅ 解析到頻道 ID: {channel_id}")
                # 用 Bot Token 直接發送（不需要 Bot 登入）
                send_to_discord(channel_id, "", embed)
            else:
                print(f"⚠️ 訂單 ID 格式不正確: {data_id}")
        else:
            print(f"⚠️ 不是 ABA 開頭的訂單: {data_id}")
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("啟動速買配回傳接收伺服器...")
    app.run(host='0.0.0.0', port=5000, debug=False)
