from flask import Flask, request
from datetime import datetime
import requests
import json

app = Flask(__name__)

# ========== 設定區 ==========
# Discord Webhook URL（發送到指定頻道）
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1511316917699219600/63Gv56ImNzDNuU_EtgzpL_p7Eup6f9gKasqY0EakYbCTmKGDAarjYy-yoJ1gZSBLhcDa"

# 注意：不需要 DISCORD_BOT_TOKEN 了！
# ===========================

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

def get_order_data(order_id):
    """從訂單 ID 獲取訂單資料"""
    try:
        with open("shop_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            orders = data.get("orders", {})
            if order_id in orders:
                return orders[order_id]
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
    
    if response_id == "1" or payment_no:
        print(f"✅ 訂單 {data_id} 付款成功！")
        
        if classif == "E":
            payment_type = "7-11 ibon"
        elif classif == "F":
            payment_type = "全家 FamiPort"
        else:
            payment_type = "超商代碼"
        
        order_data = get_order_data(data_id)
        product_amount = order_data.get("amount", 0) if order_data else 0
        fee = order_data.get("fee", 35) if order_data else 35
        
        embed = {
            "title": "✅ 付款成功通知",
            "description": f"訂單 **{data_id}** 已完成付款！",
            "color": 0x00ff00,
            "fields": [
                {"name": "💰 商品金額", "value": f"{product_amount} 元", "inline": True},
                {"name": "💸 手續費", "value": f"{fee} 元", "inline": True},
                {"name": "💵 總金額", "value": f"{amount} 元", "inline": True},
                {"name": "🏪 付款方式", "value": payment_type, "inline": True},
                {"name": "🔢 超商代碼", "value": payment_no or "無", "inline": True},
                {"name": "🆔 訂單編號", "value": data_id, "inline": True}
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "阿巴商城 自動下單系統"}
        }
        
        # 只發送到 Webhook 指定頻道
        send_to_webhook("", embed)
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("=" * 50)
    print("啟動速買配回傳接收伺服器...")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
