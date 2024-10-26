import os
import requests
import zipfile
import json
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

# Установите ваши токены и ключи для Backblaze B2
B2_APPLICATION_KEY_ID = '005e902e40d04490000000001'  # keyID
B2_APPLICATION_KEY = 'K005LC5NiXBqf0HbQLts9m8U+yHJSKo'  # applicationKey
B2_BUCKET_ID = 'Revalstone'  # Имя bucket

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = None
UPLOAD_FOLDER = 'episode_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла

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

# Маршрут для скачивания архива
@app.route('/download_archive', methods=['GET'])
def download_archive():
    try:
        season_number = request.args.get('season_number')
        episode_number = request.args.get('episode_number')

        if not season_number or not episode_number:
            return jsonify({"error": "Необходимо указать номера сезона и эпизода"}), 400

        archive_name = f"e{episode_number}s{season_number}.zip"
        archive_path = os.path.join(UPLOAD_FOLDER, archive_name)

        print(f"Проверка архива: {archive_path}")

        if not os.path.exists(archive_path):
            # Путь к файлу на Backblaze B2
            b2_file_path = f"episode_files/{archive_name}"
            print(f"Попытка скачать архив с Backblaze B2 по пути: {b2_file_path}")

            if not download_from_backblaze(b2_file_path, archive_path):
                return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Backblaze B2"}), 404

        if not os.path.exists(archive_path):
            return jsonify({"error": "Файл не найден после загрузки"}), 404

        return send_file(archive_path, as_attachment=True)

    except Exception as e:
        print(f"Ошибка при обработке запроса /download_archive: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500

# Функция для скачивания файла с Backblaze B2
def download_from_backblaze(file_path, local_path):
    try:
        auth_token = get_b2_auth_data()
        download_url = f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_ID}/{file_path}"
        
        headers = {
            "Authorization": auth_token
        }
        response = requests.get(download_url, headers=headers, timeout=60)

        # Логирование статуса ответа
        print(f"Response от Backblaze B2: {response.status_code}")
        
        if response.status_code == 200:
            # Сохраняем содержимое файла на диск
            with open(local_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"Ошибка при скачивании из Backblaze B2: {response.status_code} - {response.content.decode()}")
            return False
    except Exception as e:
        print(f"Ошибка при скачивании из Backblaze B2: {str(e)}")
        return False

# Функция для удаления файла на Backblaze B2
def delete_from_backblaze(file_name):
    try:
        auth_token, api_url = get_b2_auth_data()  # Получаем токен авторизации и URL API
        
        # Получаем fileId, который нужен для удаления файла
        get_file_url = f"{api_url}/b2api/v2/b2_list_file_names"
        params = {
            "bucketId": B2_BUCKET_ID,
            "startFileName": file_name,
            "maxFileCount": 1
        }
        headers = {
            "Authorization": auth_token
        }
        response = requests.post(get_file_url, headers=headers, json=params)
        response_data = response.json()

        if "files" not in response_data or not response_data["files"]:
            print(f"Файл {file_name} не найден на Backblaze.")
            return False

        file_id = response_data["files"][0]["fileId"]

        # Удаляем файл с помощью API Backblaze
        delete_url = f"{api_url}/b2api/v2/b2_delete_file_version"
        delete_params = {
            "fileId": file_id,
            "fileName": file_name
        }
        delete_response = requests.post(delete_url, headers=headers, json=delete_params)

        if delete_response.status_code == 200:
            print(f"Файл {file_name} успешно удален с Backblaze B2.")
            return True
        else:
            print(f"Ошибка при удалении файла {file_name} с Backblaze B2: {delete_response.content.decode()}")
            return False
    except Exception as e:
        print(f"Ошибка при удалении файла с Backblaze B2: {str(e)}")
        return False

@app.route('/delete_file', methods=['POST'])
def delete_file():
    file_path = request.json.get("file_path")
    if not file_path:
        return jsonify({"error": "File path is required"}), 400

    # Удаление файла с Backblaze B2
    if delete_from_backblaze(file_path):
        return jsonify({"status": "File deleted"}), 200
    else:
        return jsonify({"error": "Failed to delete file"}), 500

# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)
