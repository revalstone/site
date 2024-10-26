import os
import requests
import zipfile
import json
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

# Токены и ключи для Backblaze B2
B2_API_URL = "https://api.backblazeb2.com"  # URL API
B2_APPLICATION_KEY_ID = '005e902e40d04490000000001'  # keyID
B2_APPLICATION_KEY = 'K005LC5NiXBqf0HbQLts9m8U+yHJSKo'  # applicationKey
B2_BUCKET_NAME = 'Revalstone'  # Имя bucket

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = None
UPLOAD_FOLDER = 'episode_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла

@app.route('/')
def index():
    return "Welcome to Revalstone!"

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

def get_b2_auth_data():
    try:
        auth_url = f"{B2_API_URL}/b2_authorize_account"
        response = requests.get(auth_url, auth=(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY))
        response.raise_for_status()
        
        data = response.json()
        authorization_token = data['authorizationToken']
        download_url = data['downloadUrl']
        
        # Получаем ID ведра
        bucket_info = requests.get(
            f"{B2_API_URL}/b2_list_buckets",
            headers={"Authorization": authorization_token},
            params={"accountId": data["accountId"]}
        )
        bucket_info.raise_for_status()
        
        # Ищем ID ведра по имени
        bucket_id = next(
            (bucket["bucketId"] for bucket in bucket_info.json()["buckets"] if bucket["bucketName"] == B2_BUCKET_NAME),
            None
        )
        
        if not bucket_id:
            raise Exception("Bucket ID не найден для ведра с указанным именем.")
        
        return authorization_token, bucket_id, download_url
    
    except Exception as e:
        print(f"Ошибка при аутентификации в Backblaze B2: {str(e)}")
        return None, None, None

# Функция для скачивания файла с Backblaze B2
def download_from_backblaze(file_path, local_path):
    try:
        auth_token, _, download_url = get_b2_auth_data()
        if not auth_token:
            print("Не удалось получить авторизационный токен.")
            return False

        download_url = f"{download_url}/file/{B2_BUCKET_NAME}/{file_path}"
        headers = {"Authorization": auth_token}
        
        response = requests.get(download_url, headers=headers, timeout=60)
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

# Функция для удаления файла с Backblaze B2
def delete_from_backblaze(file_path):
    try:
        auth_token, bucket_id, _ = get_b2_auth_data()
        if not auth_token or not bucket_id:
            print("Не удалось получить авторизационный токен или bucket ID.")
            return False

        delete_url = f"{B2_API_URL}/b2_delete_file_version"
        data = {
            "fileName": file_path,
            "fileId": f"{bucket_id}/{file_path}"
        }
        headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json"
        }
        
        response = requests.post(delete_url, json=data, headers=headers, timeout=60)
        if response.status_code == 200:
            print(f"Файл {file_path} удален успешно.")
            return True
        else:
            print(f"Ошибка при удалении файла с Backblaze B2: {response.status_code} - {response.content.decode()}")
            return False

    except Exception as e:
        print(f"Ошибка при удалении файла с Backblaze B2: {str(e)}")
        return False

# Flask endpoint для удаления файла
@app.route('/delete_file', methods=['POST'])
def delete_file():
    file_path = request.json.get("file_path")
    if not file_path:
        return jsonify({"error": "File path is required"}), 400

    # Удаляем локальный файл, если он существует
    full_path = os.path.join("path/to/files", file_path)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            print(f"Локальный файл {full_path} удален.")
        except Exception as e:
            print(f"Ошибка при удалении локального файла: {str(e)}")
            return jsonify({"error": "Failed to delete local file"}), 500
    
    # Удаляем файл на Backblaze B2
    if not delete_from_backblaze(file_path):
        return jsonify({"error": "Failed to delete file from Backblaze B2"}), 500

    return jsonify({"status": "File deleted"}), 200

# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)
