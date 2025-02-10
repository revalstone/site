import os
import requests
import time
from flask import Flask, request, send_file, jsonify, redirect
from io import BytesIO
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)
# Токены и ключи для Backblaze B2
B2_ACCOUNT_ID = os.getenv('B2_ACCOUNT_ID')
BUCKET_ID = os.getenv('BUCKET_ID')  # ID
B2_APPLICATION_KEY_ID = os.getenv('B2_APPLICATION_KEY_ID')  # keyID
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY')  # applicationKey
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME')  # Имя bucket

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = None

CACHE_LIFETIME = 60 * 60 * 24  # 24 часа

@app.route('/')
def index():
    return "Welcome to Revalstone!"

# Авторизация в Backblaze B2
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
        return None

# Функция для получения временной (signed) ссылки
def get_file_signed_url(file_path, valid_duration=3600):
    """
    Генерирует временную (signed) ссылку для скачивания файла с Backblaze B2.
    file_path – путь к файлу внутри бакета.
    valid_duration – время действия ссылки в секундах (по умолчанию 1 час).
    """
    try:
        # Получаем токен авторизации и downloadUrl (если требуется обновление)
        token = get_b2_auth_data()
        headers = {"Authorization": token}
        data = {
            "bucketId": BUCKET_ID,
            "fileNamePrefix": file_path,
            "validDurationInSeconds": valid_duration
        }
        response = requests.post(
            "https://api.backblazeb2.com/b2api/v2/b2_get_download_authorization",
            headers=headers, json=data
        )
        response.raise_for_status()
        auth_data = response.json()
        # Формируем signed URL:
        # Формат: {downloadUrl}/file/{bucketName}/{file_path}?Authorization={downloadAuthToken}
        signed_url = f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_NAME}/{file_path}?Authorization={auth_data['authorizationToken']}"
        return signed_url
    except Exception as e:
        print(f"Ошибка при генерации signed URL для {file_path}: {str(e)}")
        return None

# Функция скачивания файла в память (не сохраняем на диск)
def download_from_backblaze(file_path):
    try:
        auth_token = get_b2_auth_data()
        download_url = f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_NAME}/{file_path}"
        
        headers = {"Authorization": auth_token}
        response = requests.get(download_url, headers=headers, timeout=60)

        if response.status_code == 200:
            return BytesIO(response.content)  # Загружаем в память
        else:
            print(f"Ошибка при скачивании из Backblaze B2: {response.status_code} - {response.content.decode()}")
            return None
    except Exception as e:
        print(f"Ошибка при скачивании из Backblaze B2: {str(e)}")
        return None

# Маршрут для скачивания архива (Render + Vercel)
@app.route('/download_archive', methods=['GET'])
def download_archive():
    try:
        season_number = request.args.get('season_number')
        episode_number = request.args.get('episode_number')

        if not season_number or not episode_number:
            return jsonify({"error": "Не указаны параметры season_number или episode_number"}), 400

        # Путь к файлу в бакете
        file_path = f"{B2_BUCKET_NAME}/episode_files/{season_number}/{episode_number}/{season_number}_{episode_number}.zip"
        # Получаем временную ссылку
        signed_url = get_file_signed_url(file_path)
        if not signed_url:
            return jsonify({"error": "Не удалось получить ссылку для скачивания"}), 500

        # Перенаправляем пользователя на signed URL
        return redirect(signed_url)
    except Exception as e:
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500


# Маршрут для скачивания списка эпизодов (Render + Vercel)
@app.route('/download_episodes_list', methods=['GET'])
def download_episodes_list():
    try:
        season_number = request.args.get('season_number')
        if not season_number:
            return jsonify({"error": "Не указан параметр season_number"}), 400

        file_path = f"{B2_BUCKET_NAME}/episode_files/episodes_list.rpy"
        signed_url = get_file_signed_url(file_path)
        if not signed_url:
            return jsonify({"error": "Не удалось получить ссылку для скачивания"}), 500

        return redirect(signed_url)
    except Exception as e:
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500


token = get_b2_auth_data()


# Запуск сервера
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
