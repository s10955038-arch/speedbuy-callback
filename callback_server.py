from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

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
        print(f"✅ 訂單 {data_id} 超商代碼: {payment_no}")
    else:
        print(f"❌ 訂單 {data_id} 失敗")
    
    return '<Roturlstatus>OK</Roturlstatus>'

@app.route('/')
def index():
    return "SpeedBuy Callback Server is Running!"

if __name__ == '__main__':
    print("啟動速買配回傳接收伺服器...")
    app.run(host='0.0.0.0', port=5000, debug=False)
