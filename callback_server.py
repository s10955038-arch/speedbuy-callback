from flask import Flask, request
from datetime import datetime
import requests
import json

app = Flask(__name__)

# 設定你的 Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511316917699219600/63Gv56ImNzDNuU_EtgzpL_p7Eup6f9gKasqY0EakYbCTmKGDAarjYy-yoJ1gZSBLhcDa"

def send_to_webhook(content, embed=None):
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
    
    data_id = data.get('Data_id', '')
    payment_no = data.get('Payment_no', '')
    amount = data.get('Amount', '')
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
        
        send_to_webhook("", embed)
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("啟動速買配回傳接收伺服器...")
    app.run(host='0.0.0.0', port=5000, debug=False)
