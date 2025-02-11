import os
import requests
import time
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv(override=True)

app = Flask(__name__)

# Токены и ключи для Backblaze B2
B2_ACCOUNT_ID = os.getenv('B2_ACCOUNT_ID')
BUCKET_ID = os.getenv('BUCKET_ID')  
B2_APPLICATION_KEY_ID = os.getenv('B2_APPLICATION_KEY_ID')
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY')
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME')

B2_AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"

# Кэш авторизации
auth_cache = {
    "token": None,
    "api_url": None,
    "download_url": None,
    "expires_at": 0  # Время истечения токена
}
# Кэш файла эпизодов
episodes_list_cache = {
    "url": None,
    "expires_at": 0  # Время истечения кэша
}
CACHE_LIFETIME = 60 * 60 * 24  # 24 часа
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Максимальный размер файла 500 MB

def authorize_b2():
    """Авторизуется в Backblaze B2 и кэширует токен"""
    global auth_cache
    if time.time() < auth_cache["expires_at"]:
        return auth_cache["token"], auth_cache["api_url"], auth_cache["download_url"]
    
    try:
        response = requests.get(B2_AUTH_URL, auth=(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY))
        response.raise_for_status()
        data = response.json()
        auth_cache["token"] = data['authorizationToken']
        auth_cache["api_url"] = data['apiUrl']
        auth_cache["download_url"] = data['downloadUrl']
        auth_cache["expires_at"] = time.time() + CACHE_LIFETIME
        print("✅ Успешная авторизация в B2")
        return auth_cache["token"], auth_cache["api_url"], auth_cache["download_url"]
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка авторизации B2: {e}")
        if response is not None:
            print(f"Ответ сервера: {response.text}")
        return None, None, None

def get_file_signed_url(file_path, valid_duration=86400):
    """Генерирует временную ссылку на файл"""
    token, api_url, download_url = authorize_b2()
    if not token:
        return None
    
    try:
        headers = {"Authorization": token}
        data = {
            "bucketId": BUCKET_ID,
            "fileNamePrefix": file_path,
            "validDurationInSeconds": valid_duration
        }
        print("🔗 Отправляем запрос на B2 для получения ссылки:", data)

        response = requests.post(
            f"{api_url}/b2api/v2/b2_get_download_authorization",  # <-- исправленный URL
            headers=headers, json=data
        )
        response.raise_for_status()
        auth_data = response.json()
        auth_token = auth_data["authorizationToken"]

        signed_url = f"{download_url}/file/{B2_BUCKET_NAME}/{file_path}?Authorization={auth_token}"
        print(f"✅ Успешно получена временная ссылка: {signed_url}")
        return signed_url
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка генерации URL: {e}")
        if response is not None:
            print(f"Ответ сервера: {response.text}")
        return None

@app.route('/download_episodes_list', methods=['GET'])
def download_episodes_list():
    global episodes_list_cache
    current_time = time.time()

    # Проверяем, есть ли актуальный кэш
    if episodes_list_cache["url"] and current_time < episodes_list_cache["expires_at"]:
        print("⚡ Используем кэшированную ссылку для episodes_list.rpy")
        return redirect(episodes_list_cache["url"])

    file_name = "episodes_list.rpyc"
    file_path = f"episode_files/{file_name}"
    
    signed_url = get_file_signed_url(file_path, valid_duration=86400)  # Срок действия 24 часа
    if not signed_url:
        return jsonify({"error": "Не удалось получить ссылку"}), 500

    # Кэшируем ссылку
    episodes_list_cache["url"] = signed_url
    episodes_list_cache["expires_at"] = current_time + 86400  # Действительна 24 часа

    print("✅ Получена новая подписанная ссылка для episodes_list.rpy (на 24 часа)")
    return redirect(signed_url)


@app.route('/download_archive', methods=['GET'])
def download_archive():
    """Маршрут для скачивания архива"""
    season = request.args.get('season_number')
    episode = request.args.get('episode_number')
    
    if not season or not episode:
        return jsonify({"error": "Не указаны параметры season_number или episode_number"}), 400
    
    archive_name = f"e{episode}s{season}.zip"
    file_path = f"episode_files/{season}/{episode}/{archive_name}"
    
    print(f"📌 Запрос на скачивание: season={season}, episode={episode}, file_path={file_path}")
    
    signed_url = get_file_signed_url(file_path)
    if not signed_url:
        return jsonify({"error": "Не удалось получить ссылку"}), 500
    
    return redirect(signed_url)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
