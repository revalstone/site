import os
import requests
import time
from flask import Flask, request, jsonify, redirect
from io import BytesIO
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)

# Токены и ключи для Backblaze B2
B2_ACCOUNT_ID = os.getenv('B2_ACCOUNT_ID')
BUCKET_ID = os.getenv('BUCKET_ID')
B2_APPLICATION_KEY_ID = os.getenv('B2_APPLICATION_KEY_ID')
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY')
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME')

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = None

# Кэш авторизации
auth_cache = {
    "token": None,
    "download_url": None,
    "expires_at": 0  # Время истечения токена
}
CACHE_LIFETIME = 60 * 60 * 24  # 24 часа

def authorize_b2():
    """Авторизуется в Backblaze B2 и кэширует токен"""
    global auth_cache
    if time.time() < auth_cache["expires_at"]:
        return auth_cache["token"], auth_cache["download_url"]
    
    try:
        response = requests.get(B2_AUTH_URL, auth=(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY))
        response.raise_for_status()
        data = response.json()
        auth_cache["token"] = data['authorizationToken']
        auth_cache["download_url"] = data['downloadUrl']
        auth_cache["expires_at"] = time.time() + CACHE_LIFETIME
        return auth_cache["token"], auth_cache["download_url"]
    except Exception as e:
        print(f"Ошибка авторизации: {e}")
        return None, None

def get_file_signed_url(file_path, valid_duration=3600):
    """Генерирует временную ссылку на файл"""
    token, download_url = authorize_b2()
    if not token:
        return None
    try:
        headers = {"Authorization": token}
        data = {
            "bucketId": BUCKET_ID,
            "fileNamePrefix": file_path,
            "validDurationInSeconds": valid_duration
        }
        response = requests.post(
            f"{download_url}/b2api/v2/b2_get_download_authorization",
            headers=headers, json=data
        )
        response.raise_for_status()
        auth_data = response.json()
        return f"{download_url}/file/{B2_BUCKET_NAME}/{file_path}?Authorization={auth_data['authorizationToken']}"
    except Exception as e:
        print(f"Ошибка генерации URL: {e}")
        return None

@app.route('/download_archive', methods=['GET'])
def download_archive():
    season = request.args.get('season_number')
    episode = request.args.get('episode_number')
    if not season or not episode:
        return jsonify({"error": "Не указаны параметры season_number или episode_number"}), 400
    file_path = f"episode_files/{season}/{episode}/{season}_{episode}.zip"
    signed_url = get_file_signed_url(file_path)
    if not signed_url:
        return jsonify({"error": "Не удалось получить ссылку"}), 500
    return redirect(signed_url)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
