import os
import requests
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
B2_API_URL = None
B2_DOWNLOAD_URL = None
B2_AUTH_TOKEN = None

def authorize_b2():
    """Авторизация в Backblaze B2 и обновление глобальных переменных."""
    global B2_API_URL, B2_DOWNLOAD_URL, B2_AUTH_TOKEN
    try:
        response = requests.get(B2_AUTH_URL, auth=(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY))
        response.raise_for_status()
        auth_data = response.json()
        B2_API_URL = auth_data['apiUrl']
        B2_DOWNLOAD_URL = auth_data['downloadUrl']
        B2_AUTH_TOKEN = auth_data['authorizationToken']
    except requests.exceptions.RequestException as e:
        print(f"Ошибка авторизации в B2: {str(e)}")
        return None

@app.route('/')
def index():
    return "Welcome to Revalstone!"

def get_file_signed_url(file_path, valid_duration=3600):
    """Генерация временной ссылки для скачивания файла."""
    if not B2_AUTH_TOKEN:
        authorize_b2()
    if not B2_AUTH_TOKEN:
        return None
    
    headers = {"Authorization": B2_AUTH_TOKEN}
    data = {
        "bucketId": BUCKET_ID,
        "fileNamePrefix": file_path,
        "validDurationInSeconds": valid_duration
    }
    try:
        response = requests.post(f"{B2_API_URL}/b2api/v2/b2_get_download_authorization", headers=headers, json=data)
        response.raise_for_status()
        auth_data = response.json()
        return f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_NAME}/{file_path}?Authorization={auth_data['authorizationToken']}"
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении signed URL: {str(e)}")
        return None

@app.route('/download_archive', methods=['GET'])
def download_archive():
    """Маршрут для скачивания архива."""
    season_number = request.args.get('season_number')
    episode_number = request.args.get('episode_number')

    if not season_number or not episode_number:
        return jsonify({"error": "Не указаны параметры season_number или episode_number"}), 400

    file_path = f"episode_files/{season_number}/{episode_number}/{season_number}_{episode_number}.zip"
    signed_url = get_file_signed_url(file_path)
    if not signed_url:
        return jsonify({"error": "Не удалось получить ссылку для скачивания"}), 500

    return redirect(signed_url)

@app.route('/download_episodes_list', methods=['GET'])
def download_episodes_list():
    """Маршрут для скачивания списка эпизодов."""
    file_path = "episode_files/episodes_list.rpy"
    signed_url = get_file_signed_url(file_path)
    if not signed_url:
        return jsonify({"error": "Не удалось получить ссылку для скачивания"}), 500
    
    return redirect(signed_url)

if __name__ == '__main__':
    authorize_b2()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
