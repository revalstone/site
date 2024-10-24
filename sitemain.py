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
UPLOAD_FOLDER = 'episode_files'  # Папка для загруженных файлов
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DROPBOX_TOKEN = None  # Определяется при запуске

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

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

# Функция для скачивания файла с Dropbox
def download_from_dropbox(file_path, local_path):
    url = "https://content.dropboxapi.com/2/files/download"
    headers = {
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
        "Dropbox-API-Arg": json.dumps({"path": file_path})
    }
    response = requests.post(url, headers=headers)
    
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        return True
    else:
        print(f"Ошибка при скачивании из Dropbox: {response.status_code} - {response.text}")
        return False

@app.route('/delete', methods=['POST'])
def delete_file():
    data = request.json
    file_name = data.get("file_name")

    if not file_name:
        return jsonify({"error": "Имя файла не указано"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"message": f"Файл {file_name} успешно удален"}), 200
        else:
            return jsonify({"error": "Файл не найден"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Нет файла", 400
    
    file = request.files['file']
    
    # Путь для сохранения ZIP-файла
    zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(zip_path)

    # Получаем имя папки для распаковки
    extract_folder = os.path.join(UPLOAD_FOLDER, os.path.splitext(file.filename)[0])

    # Создаем папку для распаковки, если она не существует
    os.makedirs(extract_folder, exist_ok=True)

    # Распакуйте ZIP-файл
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_folder)
    
    # Удалите ZIP-файл после распаковки
    os.remove(zip_path)

    return "Файл успешно загружен и распакован", 200

@app.route('/list_files', methods=['GET'])
def list_files():
    directory = UPLOAD_FOLDER  # Укажите путь к директории, где находятся файлы
    files = os.listdir(directory)
    return jsonify(files)

@app.route('/download_archive/<string:archive_name>', methods=['GET'])
def download_archive(archive_name):
    """Возвращает запрошенный ZIP-архив или загружает его с Dropbox, если он отсутствует."""
    archive_path = os.path.join(UPLOAD_FOLDER, archive_name)

    # Проверка наличия архива на сервере
    if not os.path.exists(archive_path):
        # Путь к архиву на Dropbox
        dropbox_path = f"/episode_files/{archive_name}"

        # Попытка скачать архив с Dropbox
        if download_from_dropbox(dropbox_path, archive_path):
            print(f"Архив {archive_name} успешно скачан с Dropbox.")
        else:
            return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Dropbox"}), 404

    # Если файл существует, отправляем его клиенту
    return send_file(archive_path, as_attachment=True)

if __name__ == '__main__':
    # Получаем новый access_token перед запуском сервера
    DROPBOX_TOKEN = get_access_token()

    # Запускаем сервер
    app.run(debug=True)
