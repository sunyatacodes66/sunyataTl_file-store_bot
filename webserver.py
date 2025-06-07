from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os

load_dotenv()

app = Flask(__name__)

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI")
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.telegram_bot_db
user_verifications_col = db.user_verifications

@app.route('/verify')
def verify_user():
    user_id = request.args.get('uid')
    file_id = request.args.get('file_id')
    code = request.args.get('code')

    if not user_id or not file_id or not code:
        return jsonify({"error": "🚫 Missing uid, file_id or code"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "❌ Invalid user ID"}), 400

    # Verify the code matches the stored verification code for the file
    file_doc = db.files.find_one({"file_id": file_id})
    if not file_doc:
        return jsonify({"error": "❌ File not found"}), 404

    stored_code = file_doc.get("verification_code")
    if stored_code != code:
        return jsonify({"error": "❌ Invalid verification code"}), 403

    now = datetime.utcnow()
    expires = now + timedelta(hours=12)

    user_verifications_col.update_one(
        {"user_id": user_id, "file_id": file_id},
        {"$set": {
            "verified_at": now,
            "expires_at": expires
        }},
        upsert=True
    )

    return '''
    <html>
        <head><title>✅ Verified</title></head>
        <body style="text-align:center; font-family: Arial, sans-serif; margin-top: 50px;">
            <h2>✅ Verification Successful!</h2>
            <p>🎉 You can now return to the Telegram bot and click <strong>"Retry"</strong> to download your file.</p>
            <br>
            <a href="https://t.me/Mahiraa3_bot" style="text-decoration:none; font-size:18px;">👉 Return to Bot</a>
        </body>
    </html>
    '''

@app.route('/health')
def health_check():
    return jsonify({
        'status': '✅ healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
