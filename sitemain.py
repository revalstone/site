from flask import Flask, request, jsonify
import requests
import os
from io import BytesIO
import json

app = Flask(__name__)

# Настройки
REFRESH_TOKEN = 'OQigtzF32QoAAAAAAAAAASFHVSGh-EGBSsBoVZn2YgKZ7ZBL0rzMIYOWXnVUuyMF'
APP_KEY = 'p86rppkc8d7fslf'
APP_SECRET = '5sx8vbxpfmxdd8b'
TOKEN_URL = "https://api.dropbox.com/oauth2/token"  
UPLOAD_FOLDER = 'episode_files'  # Папка для загруженных файлов
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Нет файла", 400
    
    file = request.files['file']
    # Создайте нужную папку, если она не существует
    directory = 'episode_files'  # Укажите путь к директории
    os.makedirs(directory, exist_ok=True)

    # Сохраните файл
    file.save(os.path.join(directory, file.filename))
    return "Файл успешно загружен", 200


@app.route('/list_files', methods=['GET'])
def list_files():
    directory = 'episode_files'  # Укажите путь к директории, где находятся файлы
    files = os.listdir(directory)
    return jsonify(files)

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
def download_from_dropbox(dropbox_path):
    access_token = get_access_token()  # Получаем новый токен
    url = "https://content.dropboxapi.com/2/files/download"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return BytesIO(response.content)  # Возвращаем файл как поток данных
    else:
        raise Exception(f"Ошибка при скачивании: {response.status_code} {response.text}")

# Функция для загрузки файлов на сервер
def upload_file(file_stream, filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    with open(file_path, 'wb') as f:
        f.write(file_stream.read())
    print(f"Файл успешно загружен: {filename}")  # Логирование

# Функция для рекурсивной загрузки папок и файлов с Dropbox на сервер
def download_and_upload_files(cloud_folder_path):
    list_files_url = "https://api.dropboxapi.com/2/files/list_folder"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    data = json.dumps({"path": cloud_folder_path})

    response = requests.post(list_files_url, headers=headers, data=data)

    if response.status_code == 200:
        files = response.json().get("entries", [])
        for file in files:
            if file[".tag"] == "file":
                cloud_file_path = file["path_lower"]
                # Скачиваем файл
                file_content = download_from_dropbox(cloud_file_path)
                
                # Загружаем файл на сервер
                upload_file(file_content, file["name"])  # Имя файла
                
            elif file[".tag"] == "folder":
                # Рекурсивно обрабатываем подкаталоги
                download_and_upload_files(file["path_lower"])
    else:
        print(f"Ошибка при получении содержимого папки: {response.status_code} - {response.text}")

# Проверка наличия загруженных файлов
def check_uploaded_files(file_names):
    uploaded_files = []
    for file_name in file_names:
        if os.path.exists(os.path.join(UPLOAD_FOLDER, file_name)):
            uploaded_files.append(file_name)
            print(f"Файл найден: {file_name}")
        else:
            print(f"Файл не найден: {file_name}")
    return uploaded_files

# Эндпоинт для загрузки папки
@app.route('/download_and_upload', methods=['POST'])
def handle_download_and_upload():
    cloud_folder_path = request.json.get("cloud_folder_path")
    if not cloud_folder_path:
        return "Не указан путь к папке", 400

    download_and_upload_files(cloud_folder_path)

    return jsonify({"message": "Загрузка завершена!"}), 200

if __name__ == '__main__':
    app.run(debug=True)
