import os
import requests
import time
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

# Токены и ключи для Backblaze B2
B2_ACCOUNT_ID = 'e902e40d0449'
BUCKET_ID = '2ee970b25e84c05d90240419'  # ID
B2_APPLICATION_KEY_ID = '005e902e40d04490000000001'  # keyID
B2_APPLICATION_KEY = 'K005LC5NiXBqf0HbQLts9m8U+yHJSKo'  # applicationKey
B2_BUCKET_NAME = 'Revalstone'  # Имя bucket

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = "https://f005.backblazeb2.com"
UPLOAD_FOLDER = 'episode_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла 500 MB

CACHE_LIFETIME = 60 * 60 * 24  # 24 часа

@app.route('/')
def index():
    return "Welcome to Revalstone!"

# Функция для авторизации в Backblaze B2 и получения URL для загрузки файлов
def get_b2_auth_data():
    global B2_DOWNLOAD_URL
    try:
        auth_response = requests.get(B2_AUTH_URL, auth=(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY))
        auth_response.raise_for_status()
        
        auth_data = auth_response.json()
        B2_DOWNLOAD_URL = auth_data['downloadUrl']
        return auth_data['authorizationToken']
    except Exception as e:
        print(f"Ошибка при авторизации в Backblaze B2: {str(e)}")
        raise

# Функция проверки кэша
def is_file_cached(file_path):
    local_path = os.path.join(UPLOAD_FOLDER, file_path)
    return os.path.exists(local_path) and time.time() - os.path.getmtime(local_path) < CACHE_LIFETIME

# Функция скачивания файлов с Backblaze B2
def download_from_backblaze(file_path, local_path):
    try:
        auth_token = get_b2_auth_data()
        download_url = f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_NAME}/{file_path}"
        
        headers = {"Authorization": auth_token}
        response = requests.get(download_url, headers=headers, timeout=60)

        print(f"Response от Backblaze B2: {response.status_code}")
        
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"Ошибка при скачивании из Backblaze B2: {response.status_code} - {response.content.decode()}")
            return False
    except Exception as e:
        print(f"Ошибка при скачивании из Backblaze B2: {str(e)}")
        return False

# Маршрут для скачивания архива (Render + Vercel)
@app.route('/download_archive', methods=['GET'])
def download_archive():
    try:
        season_number = request.args.get('season_number')
        episode_number = request.args.get('episode_number')

        if not season_number or not episode_number:
            return jsonify({"error": "Не указаны параметры season_number или episode_number"}), 400

        file_path = f"archives/season_{season_number}_episode_{episode_number}.zip"
        local_path = os.path.join(UPLOAD_FOLDER, file_path)

        if not is_file_cached(file_path):
            if not download_from_backblaze(file_path, local_path):
                return jsonify({"error": "Не удалось скачать файл"}), 500

        return send_file(local_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500

# Маршрут для скачивания списка эпизодов (Render + Vercel)
@app.route('/download_episodes_list', methods=['GET'])
def download_episodes_list():
    try:
        season_number = request.args.get('season_number')

        if not season_number:
            return jsonify({"error": "Не указан параметр season_number"}), 400

        file_path = f"episodes_list/season_{season_number}.json"
        local_path = os.path.join(UPLOAD_FOLDER, file_path)

        if not is_file_cached(file_path):
            if not download_from_backblaze(file_path, local_path):
                return jsonify({"error": "Не удалось скачать файл"}), 500

        return send_file(local_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500

# Запуск сервера
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
