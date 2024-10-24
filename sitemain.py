from flask import Flask, request, jsonify, send_file
import requests
import os
from io import BytesIO
import json
import zipfile

app = Flask(__name__)

# Настройки
REFRESH_TOKEN = 'OQigtzF32QoAAAAAAAAAASFHVSGh-EGBSsBoVZn2YgKZ7ZBL0rzMIYOWXnVUuyMF'
APP_KEY = 'p86rppkc8d7fslf'
APP_SECRET = '5sx8vbxpfmxdd8b'
TOKEN_URL = "https://api.dropbox.com/oauth2/token"  
CACHE_DIR = '/tmp/cache'  # Используем временную папку для кэширования
os.makedirs(CACHE_DIR, exist_ok=True)

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

# Кэширование файла
def cache_file(file_content, file_name):
    local_path = os.path.join(CACHE_DIR, file_name)
    with open(local_path, 'wb') as f:
        f.write(file_content.getbuffer())  # Сохраняем поток данных в файл
    return local_path

# Проверка наличия файла в кэше
def is_file_cached(file_name):
    local_path = os.path.join(CACHE_DIR, file_name)
    return os.path.exists(local_path), local_path

# Эндпоинт для получения файла с кэшированием
@app.route('/get-file/<path:file_name>', methods=['GET'])
def get_file(file_name):
    # Проверяем, есть ли файл в кэше
    cached, local_path = is_file_cached(file_name)
    
    if cached:
        return send_file(local_path)  # Возвращаем файл из кэша
    else:
        # Если файла нет в кэше, загружаем его с Dropbox
        dropbox_path = f'/{file_name}'  # Предполагаем, что путь в Dropbox такой же
        try:
            file_content = download_from_dropbox(dropbox_path)
            local_path = cache_file(file_content, file_name)  # Сохраняем в кэш
            return send_file(local_path)  # Возвращаем файл
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
