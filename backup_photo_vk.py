import requests
from urllib.parse import parse_qs, urlparse
import os
from tqdm import tqdm
import json
import logging
import datetime
import uuid

# Логгер настройка
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получение токена VK
def get_vk_token():
    client_id = input("Вставьте ваш id приложения: ")
    redirect_uri = 'https://oauth.vk.com/blank.html'
    auth_url = f'https://oauth.vk.com/authorize?client_id={client_id}&display=page&redirect_uri={redirect_uri}&scope=photos&response_type=token&v=5.131'
    
    logger.info("Перейдите по ссылке для получения токена, скопировав всю адресную строку:")
    logger.info(auth_url)
    
    full_url = input("Вставьте полученный URL здесь: ").strip()
    parsed_url = urlparse(full_url)
    query_params = parse_qs(parsed_url.fragment)

    try:
        access_token = query_params.get('access_token')[0]
        return access_token.strip()
    except KeyError:
        logger.error("Не удалось найти access_token в полученном URL.")
        return None

# Получение списка альбомов
def get_albums(vk_user_id, access_token):
    url = "https://api.vk.com/method/photos.getAlbums"
    params = {
        'owner_id': vk_user_id,
        'need_system': 1,
        'access_token': access_token,
        'v': '5.131'
    }
    response = requests.get(url, params=params).json()

    if 'error' in response:
        logger.error(f"Произошла ошибка при получении альбомов: {response['error']['error_msg']}")
        raise Exception(response['error']['error_msg'])

    return [{'title': album['title'], 'id': album['id']} for album in response['response']['items']]

# Выбор альбома пользователем
def select_album(albums):
    print("\nДоступные альбомы:")
    for i, album in enumerate(albums):
        print(f"{i + 1}. {album['title']} (ID: {album['id']})")

    while True:
        choice = input("\nВыберите номер альбома: ")
        try:
            index = int(choice) - 1
            if 0 <= index < len(albums):
                return albums[index]['id']
            else:
                print("Неверный ввод. Попробуйте еще раз.")
        except ValueError:
            print("Неверный ввод. Введите число.")

# Получение списка фотографий
def get_photos(vk_user_id, access_token, album_id):
    url = "https://api.vk.com/method/photos.get"
    params = {
        'owner_id': vk_user_id,
        'album_id': album_id,
        'extended': 1,
        'photo_sizes': 1,
        'access_token': access_token,
        'v': '5.131'
    }
    response = requests.get(url, params=params).json()

    if 'error' in response:
        logger.error(f"Произошла ошибка при получении фотографий: {response['error']['error_msg']}")
        raise Exception(response['error']['error_msg'])

    photos = []
    for item in response['response']['items']:
        best_size = sorted(item['sizes'], key=lambda x: (x['width'] + x['height']), reverse=True)[0]
        photos.append({
            'url': best_size['url'],
            'likes_count': item.get('likes', {}).get('count', 0),
            'date': item['date'],
        })
    return photos[:5] #[:7]

# Загрузка файла на Яндекс диск
def upload_to_yandex_disk(ya_token, file_name, file_content):
    url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
    headers = {'Authorization': f'OAuth {ya_token}'}
    params = {'path': file_name, 'overwrite': 'true'}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        href = response.json()['href']
        put_response = requests.put(href, data=file_content)

        if put_response.status_code == 201:
            logger.info(f'Файл "{file_name}" успешно загружен.')
            return True
        else:
            logger.error(f'Ошибка при загрузке файла "{file_name}": {put_response.text}')
            return False
    else:
        logger.error(f'Не удалось получить ссылку для загрузки файла "{file_name}": {response.text}')
        return False

# Создание директории на Яндекс диске
def create_folder_on_yandex_disk(ya_token, folder_name):
    url = 'https://cloud-api.yandex.net/v1/disk/resources'
    headers = {'Authorization': f'OAuth {ya_token}'}
    params = {'path': folder_name}

    response = requests.put(url, headers=headers, params=params)
    if response.status_code == 201:
        logger.info(f"Папка '{folder_name}' создана успешно.")
        return True
    elif response.status_code == 409:
        logger.warning(f"Папка '{folder_name}' уже существует.")
        return True
    else:
        logger.error(f"Ошибка при создании папки {folder_name}: {response.text}")
        return False

# Проверка существования папки и создание на Яндекс диске
def check_and_create_folder(ya_token, folder_name):
    url = 'https://cloud-api.yandex.net/v1/disk/resources'
    headers = {'Authorization': f'OAuth {ya_token}'}
    params = {'path': folder_name}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        logger.info(f"Папка '{folder_name}' уже существует.")
        return True
    elif response.status_code == 404:
        logger.info(f"Папка '{folder_name}' не найдена. Создаю...")
        return create_folder_on_yandex_disk(ya_token, folder_name)
    else:
        logger.error(f"Ошибка при проверке папки '{folder_name}': {response.text}")
        return False

# Основная функция программы
def main():
    vk_user_id = input("Введите свой id пользователя VK: ")
    ya_token = input("Вставте сюда токен с Полигона Яндекс диска: ").strip() 
    access_token = input("Вставте сюда ваш токен VK или секретный ключ с приложения: ") #get_vk_token()  

    albums = get_albums(vk_user_id, access_token)
    album_id = select_album(albums)
    photos = get_photos(vk_user_id, access_token, album_id)

    folder_name = f'VK_Photos_{vk_user_id}'

    if not check_and_create_folder(ya_token, folder_name):
        return

    results = []
    for photo in tqdm(photos):
        date_str = datetime.datetime.fromtimestamp(photo['date']).strftime('%Y-%m-%d_%H-%M-%S')
        unique_id = str(uuid.uuid4()) # Использование уникального идентификатора в формате UUID для предотвращения удаления фото с одинаковыми именами
        file_name = f"{photo['likes_count']}_{date_str}_{unique_id}.jpg"
        full_file_name = f"{folder_name}/{file_name}"

        response = requests.get(photo['url'])
        if response.status_code == 200:
            if upload_to_yandex_disk(ya_token, full_file_name, response.content):
                result_item = {
                    "file_name": file_name,
                    "size": len(response.content),
                    #"likes_count": photo['likes_count'],
                    #"date": date_str,
                }
                results.append(result_item)
        else:
            logger.error(f"Ошибка при получении фото: {response.status_code}")

    with open('results.json', 'w') as f:
        json.dump(results, f, indent=4)

    logger.info("Фотографии успешно сохранены на Яндекс диске!")

if __name__ == "__main__":
    main()
