from flask import Flask, request
from datetime import datetime
import requests
import json

app = Flask(__name__)

# ========== 設定區 ==========
DISCORD_BOT_TOKEN = "MTUxMTM0Nzc0MTcxOTAwNzQ2NA.GiVg9D.1zTAlLGoHRfriINY-4CTDJkjzgbB-fvdClRDC8"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511316917699219600/63Gv56ImNzDNuU_EtgzpL_p7Eup6f9gKasqY0EakYbCTmKGDAarjYy-yoJ1gZSBLhcDa"
# ===========================

def send_to_discord(channel_id, content, embed=None):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    
    response = requests.post(url, headers=headers, json=data)
    print(f"發送結果: {response.status_code} - {response.text}")
    return response.status_code == 200

def send_to_webhook(content, embed=None):
    data = {"content": content}
    if embed:
        data["embeds"] = [embed]
    requests.post(DISCORD_WEBHOOK_URL, json=data)
    print("✅ 已發送 Webhook 通知")

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
    
    data_id = data.get('Data_id', '')
    amount = data.get('Amount', '')
    payment_no = data.get('Payment_no', '')
    response_id = data.get('Response_id', '')
    
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
        
        # 直接從訂單 ID 提取頻道 ID 並發送
        # 訂單 ID 格式: ABA1511331666717573130_202606021933144256
        if "_" in data_id:
            channel_id = data_id.split("_")[0].replace("ABA", "")
            print(f"📢 準備發送到頻道: {channel_id}")
            send_to_discord(channel_id, "", embed)
        else:
            print(f"⚠️ 訂單 ID 沒有底線: {data_id}")
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("啟動速買配回傳接收伺服器...")
    app.run(host='0.0.0.0', port=5000, debug=False)
