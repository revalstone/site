import os
import requests
import zipfile
import json
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

REFRESH_TOKEN = 'OQigtzF32QoAAAAAAAAAASFHVSGh-EGBSsBoVZn2YgKZ7ZBL0rzMIYOWXnVUuyMF'
APP_KEY = 'p86rppkc8d7fslf'
APP_SECRET = '5sx8vbxpfmxdd8b'

TOKEN_URL = "https://api.dropbox.com/oauth2/token"
UPLOAD_FOLDER = 'episode_files'  # Папка для загруженных файлов на сервере
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла 500 MB

# Функция для получения нового access_token с помощью refresh_token
def get_access_token():
    response = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": APP_KEY,
        "client_secret": APP_SECRET,
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Ошибка обновления токена: {response.status_code} - {response.text}")

# Маршрут для скачивания архива
@app.route('/download_archive', methods=['GET'])
def download_archive():
    season_number = request.args.get('season_number')
    episode_number = request.args.get('episode_number')

    if not season_number or not episode_number:
        return jsonify({"error": "Необходимо указать номера сезона и эпизода"}), 400

    # Имя архива
    archive_name = f"e{episode_number}s{season_number}.zip"
    archive_path = os.path.join(UPLOAD_FOLDER, archive_name)

    # Если файл отсутствует на сервере, скачиваем его с Dropbox
    if not os.path.exists(archive_path):
        dropbox_path = f"/episode_files/{archive_name}"
        if download_from_dropbox(dropbox_path, archive_path):
            print(f"Архив {archive_name} успешно скачан с Dropbox.")
        else:
            return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Dropbox"}), 404

    return send_file(archive_path, as_attachment=True)

# Функция для скачивания файла с Dropbox
def download_from_dropbox(file_path, local_path):
    access_token = get_access_token()
    url = "https://content.dropboxapi.com/2/files/download"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Dropbox-API-Arg": json.dumps({"path": file_path})
    }
    response = requests.post(url, headers=headers)
    print(f"Response от Dropbox: {response.status_code} - {response.text}")

    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print(f"Файл {file_path} успешно скачан с Dropbox.")
        return True
    else:
        print(f"Ошибка при скачивании из Dropbox: {response.status_code} - {response.text}")
        return False

# Маршрут для загрузки файла на сервер
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Нет файла", 400
    
    file = request.files['file']
    
    # Путь для сохранения ZIP-файла
    zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(zip_path)

    # Распакуем файл, если это ZIP-архив
    extract_folder = os.path.join(UPLOAD_FOLDER, os.path.splitext(file.filename)[0])
    os.makedirs(extract_folder, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_folder)

    os.remove(zip_path)  # Удаляем архив после распаковки

    return "Файл успешно загружен и распакован", 200

# Маршрут для удаления файла
@app.route('/delete', methods=['POST'])
def delete_file():
    data = request.json
    file_name = data.get("file_name")

    if not file_name:
        return jsonify({"error": "Имя файла не указано"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"message": f"Файл {file_name} успешно удален"}), 200
    else:
        return jsonify({"error": "Файл не найден"}), 404

# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)
