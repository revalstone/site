import os
import requests
import time
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

# Токены и ключи для Backblaze B2
B2_ACCOUNT_ID = 'e902e40d0449'
BUCKET_ID = '2ee970b25e84c05d90240419'  # ID
B2_APPLICATION_KEY_ID = '005e902e40d04490000000001'  # keyID
B2_APPLICATION_KEY = 'K005LC5NiXBqf0HbQLts9m8U+yHJSKo'  # applicationKey
B2_BUCKET_NAME = 'Revalstone'  # Имя bucket

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
B2_DOWNLOAD_URL = "https://f005.backblazeb2.com"
UPLOAD_FOLDER = 'episode_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла 500 MB

CACHE_LIFETIME = 60 * 60 * 24  # 24 часа

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

        # Создаем имя архива
        archive_name = f"e{episode_number}s{season_number}.zip"
        
        # Формируем путь к архиву с учетом структуры папок
        archive_path = os.path.join(UPLOAD_FOLDER, season_number, episode_number)
        os.makedirs(archive_path, exist_ok=True)  # Создаем папку, если она не существует
        archive_file_path = os.path.join(archive_path, archive_name)

        print(f"Проверка архива: {archive_file_path}")

        # Проверяем, существует ли архив
        if not os.path.exists(archive_file_path):
            # Путь к файлу на Backblaze B2 с учетом новой структуры папок
            b2_file_path = f"episode_files/{season_number}/{episode_number}/{archive_name}"
            print(f"Попытка скачать архив с Backblaze B2 по пути: {b2_file_path}")

            # Скачиваем архив, если он не найден локально
            if not download_from_backblaze(b2_file_path, archive_file_path):
                return jsonify({"error": "Архив не найден на сервере и не удалось скачать с Backblaze B2"}), 404

        # Проверяем, существует ли архив после загрузки
        if not os.path.exists(archive_file_path):
            return jsonify({"error": "Файл не найден после загрузки"}), 404

        # Отправляем файл клиенту
        return send_file(archive_file_path, as_attachment=True)

    except Exception as e:
        print(f"Ошибка при обработке запроса /download_archive: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500

@app.route('/download_episodes_list', methods=['GET'])
def download_episodes_list():
    try:
        file_name = "episodes_list.rpy"
        file_path = f"episode_files/{file_name}"

        # Путь для локального хранения на сервере Render
        local_file_path = os.path.join(UPLOAD_FOLDER, file_name)

        # Проверяем, существует ли файл локально и не устарел ли он
        if not is_file_cached(local_file_path):
            print(f"Файл {file_name} не найден или устарел, пытаемся скачать из Backblaze B2...")
            
            # Скачиваем файл, если его нет локально или он устарел
            if not download_from_backblaze(file_path, local_file_path):
                return jsonify({"error": "Файл не найден на сервере и не удалось скачать с Backblaze B2"}), 404

        # Отправляем файл клиенту
        return send_file(local_file_path, as_attachment=True)

    except Exception as e:
        print(f"Ошибка при обработке запроса /download_episodes_list: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера", "details": str(e)}), 500

def is_file_cached(file_path):
    """Проверка, кэширован ли файл и не истек ли срок его действия"""
    if os.path.exists(file_path):
        # Проверяем время последнего изменения файла
        file_age = time.time() - os.path.getmtime(file_path)
        if file_age < CACHE_LIFETIME:
            # Если файл недавно обновлялся, считаем его кэшированным
            return True
    return False

# Функция для скачивания файла с Backblaze B2
def download_from_backblaze(file_path, local_path):
    try:
        auth_token = get_b2_auth_data()
        download_url = f"{B2_DOWNLOAD_URL}/file/{B2_BUCKET_NAME}/{file_path}"
        
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


# Запуск сервера
if __name__ == '__main__':
    # Получаем порт из переменной окружения PORT
    port = int(os.environ.get("PORT", 5000))  # если переменная не установлена, используем порт 5000
    app.run(debug=True, host='0.0.0.0', port=port)
