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
    try:
        response = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": APP_KEY,
            "client_secret": APP_SECRET,
        })
        response.raise_for_status()  # Если ответ не 200, вызовет исключение
        return response.json()["access_token"]
    except Exception as e:
        print(f"Ошибка при получении токена доступа: {str(e)}")
        raise

# Маршрут для скачивания архива
@app.route('/download_archive', methods=['GET'])
def download_archive():
    try:
        season_number = request.args.get('season_number')
        episode_number = request.args.get('episode_number')

        if not season_number or not episode_number:
            return jsonify({"error": "Необходимо указать номера сезона и эпизода"}), 400

        # Имя архива
        archive_name = f"e{episode_number}s{season_number}.zip"
        archive_path = os.path.join(UPLOAD_FOLDER, archive_name)

        # Логирование пути к архиву
        print(f"Проверка архива: {archive_path}")

        # Если файл отсутствует на сервере, скачиваем его с Dropbox
        if not os.path.exists(archive_path):
            dropbox_path = f"/episode_files/e{episode_number}s{season_number}"
            print(f"Попытка скачать архив с Dropbox по пути: {dropbox_path}")  # Логирование пути для скачивания
            if download_from_dropbox(dropbox_path, archive_path):
                print(f"Архив {archive_name} успешно скачан с Dropbox.")
            else:
                return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Dropbox"}), 404

        return send_file(archive_path, as_attachment=True)

    except Exception as e:
        print(f"Ошибка при обработке запроса /download_archive: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


# Функция для скачивания файла с Dropbox
def download_from_dropbox(file_path, local_path):
    try:
        access_token = get_access_token()
        url = "https://content.dropboxapi.com/2/files/download"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Dropbox-API-Arg": json.dumps({"path": file_path})
        }
        response = requests.post(url, headers=headers)
        print(f"Response от Dropbox: {response.status_code} - {response.text}")

        response.raise_for_status()  # Если ответ не 200, вызовет исключение

        with open(local_path, 'wb') as f:
            f.write(response.content)
        print(f"Файл {file_path} успешно скачан с Dropbox.")
        return True
    except Exception as e:
        print(f"Ошибка при скачивании из Dropbox: {str(e)}")
        return False

# Маршрут для загрузки файла на сервер
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
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
    except Exception as e:
        print(f"Ошибка при загрузке файла: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# Маршрут для удаления файла
@app.route('/delete', methods=['POST'])
def delete_file():
    try:
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
    except Exception as e:
        print(f"Ошибка при удалении файла: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@app.route('/list_files', methods=['GET'])
def list_files():
    directory = UPLOAD_FOLDER  # Укажите путь к директории, где находятся файлы
    files = os.listdir(directory)
    return jsonify(files)
# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)
