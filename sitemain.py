import os
import requests
from flask import Flask, send_file, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = 'episode_files'  # Папка для хранения архивов на сервере
DROPBOX_TOKEN = 'ваш токен Dropbox'

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

@app.route('/download_archive/<string:archive_name>', methods=['GET'])
def download_archive(archive_name):
    """Возвращает запрошенный ZIP-архив или загружает его с Dropbox, если он отсутствует."""
    archive_path = os.path.join(UPLOAD_FOLDER, archive_name)

    # Проверка наличия архива на сервере
    if not os.path.exists(archive_path):
        # Путь к архиву на Dropbox
        dropbox_path = f"/{archive_name}"

        # Попытка скачать архив с Dropbox
        if download_from_dropbox(dropbox_path, archive_path):
            print(f"Архив {archive_name} успешно скачан с Dropbox.")
        else:
            return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Dropbox"}), 404

    # Если файл существует, отправляем его клиенту
    return send_file(archive_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
