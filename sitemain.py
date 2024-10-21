from flask import Flask, request, send_file
import requests
import os
from io import BytesIO

app = Flask(__name__)

REFRESH_TOKEN = 'OQigtzF32QoAAAAAAAAAASFHVSGh-EGBSsBoVZn2YgKZ7ZBL0rzMIYOWXnVUuyMF'

APP_KEY = 'p86rppkc8d7fslf'
APP_SECRET = '5sx8vbxpfmxdd8b'
TOKEN_URL = "https://api.dropbox.com/oauth2/token"  

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
        "Dropbox-API-Arg": '{"path": "%s"}' % dropbox_path,
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return BytesIO(response.content)  # Возвращаем файл как поток данных
    else:
        raise Exception(f"Ошибка при скачивании: {response.status_code} {response.text}")

# Маршрут для скачивания файла
@app.route('/download', methods=['GET'])
def download():
    file_path = request.args.get('file_path')
    if not file_path:
        return "Не указан путь к файлу", 400
    
    try:
        # Скачиваем файл с Dropbox
        file_content = download_from_dropbox(file_path)
        # Отправляем файл обратно клиенту как вложение
        return send_file(file_content, as_attachment=True, download_name=file_path.split("/")[-1])
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
