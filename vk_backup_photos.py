from urllib.parse import urlencode
import requests
from datetime import datetime
import os
import json
import configparser
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

APP_ID = '51792163'
OAUTH_BASE_URL = 'https://oauth.vk.com/authorize'
params = {
    'client_id': APP_ID,
    'redirect_uri': 'https://oauth.vk.com/blank.html',
    'display': 'page',
    'scope': 'status,photos,offline',
    'response_type': 'token',
    'expires_in': 0
}
oauth_url = f'{OAUTH_BASE_URL}?{urlencode(params)}'

tokens = configparser.ConfigParser()
tokens.read("tokens.ini")
VK_TOKEN = tokens['VK']['token']
YANDEX_TOKEN = tokens['YANDEX']['token']


class VKAPIClient:
    API_BASE_URL = 'https://api.vk.com/method'

    def __init__(self, token, owner_id):
        self.token = token
        self.owner_id = owner_id

    def get_common_params(self):
        return {
            'access_token': self.token,
            'v': '5.131',
            'owner_id': self.owner_id
        }

    def _build_url(self, path):
        return f'{self.API_BASE_URL}/{path}'

    def get_profile_photos_info(self, count):
        params = self.get_common_params()
        params.update({'album_id': 'profile', 'extended': 1, 'rev': 1, 'count': count})
        response = requests.get(self._build_url('photos.get'), params=params)
        return response.json()

    def download_profile_photos(self, count):
        self.photos_for_downloading = self.get_profile_photos_info(count)
        self.photo_info = []
        self.downloading()
        self.get_json_for_profile_photos()

    def get_albums_id(self, count):
        params = self.get_common_params()
        params.update({'count': count})
        albums_info = []
        response = requests.get(self._build_url('photos.getAlbums'), params=params)
        items = response.json()['response']['items']
        for item in items:
            albums_info.append(item['id'])
        return albums_info

    def get_album_photos_info(self, count):
        params = self.get_common_params()
        albums_id = self.get_albums_id(count)
        albums = []
        for album_id in albums_id:
            params.update({'album_id': album_id, 'extended': 1, 'rev': 1})
            response = requests.get(self._build_url('photos.get'), params=params)
            albums.append(response.json())
        return albums

    def download_album_photos(self, count):
        albums = self.get_album_photos_info(count)
        self.photo_info = []
        for album in albums:
            self.photos_for_downloading = album
            self.downloading()
        self.get_json_for_album_photos()

    def downloading(self):
        for items in self.photos_for_downloading['response']['items']:
            photo_id = items['id']
            likes = items['likes']['count']
            max_res = 0
            for item in items['sizes']:
                date = datetime.fromtimestamp(items['date']).date()
                res_type = item['type']
                cur_res = item['height'] * item['width']
                if cur_res == 0:
                    url = items['sizes'][-1]['url']
                elif cur_res > max_res:
                    max_res = cur_res
                    url = item['url']
            if not os.path.exists('vk'):
                os.mkdir('vk')
            folder = os.listdir('vk/')
            if f'{likes}.jpg' not in folder:
                with open(f'vk/{likes}.jpg', 'wb') as img:
                    response = requests.get(url)
                    img.write(response.content)
                    file_name = likes
            elif f'{date}.jpg' not in folder:
                with open(f'vk/{date}.jpg', 'wb') as img:
                    response = requests.get(url)
                    img.write(response.content)
                    file_name = date
            else:
                with open(f'vk/{photo_id}.jpg', 'wb') as img:
                    response = requests.get(url)
                    img.write(response.content)
                    file_name = photo_id
            self.photo_info.append({'file_name': f'{file_name}.jpg', 'size': f'{res_type}'})
        return self.photo_info

    def get_json_for_profile_photos(self):
        with open('profile_photos.json', 'w') as file:
            json.dump(self.photo_info, file)

    def get_json_for_album_photos(self):
        with open('album_photos.json', 'w') as file:
            json.dump(self.photo_info, file)


class Yandex:
    API_BASE_URL = "https://cloud-api.yandex.net/v1/disk"

    def __init__(self, token):
        self.token = token

    def get_common_headers(self):
        return {
            "Authorization": self.token
        }

    def _build_url(self, path):
        return f'{self.API_BASE_URL}/{path}'

    def create_folder(self, folder_name):
        self.folder = folder_name
        params = {
            "path": f'{folder_name}'
        }
        response = requests.put(self._build_url("resources"),
                                headers=self.get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            print(f"The folder {folder_name} has been successfully created on Yandex Disc")

    def get_url_for_uploading(self, file):
        params = {
            "path": f"{self.folder}/{file}"
        }
        response = requests.get(self._build_url("resources/upload"),
                                headers=self.get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            return response.json().get("href", "")

    def upload(self):
        folder = os.listdir('vk/')
        for file in folder:
            url = self.get_url_for_uploading(file)
            with open(f'vk/{file}', "rb") as upload_file:
                response = requests.put(url, files={"file": upload_file})
                if 200 <= response.status_code < 300:
                    print(f"The file {file} has been successfully uploaded on Yandex Disc")


class Google:
    def __init__(self):
        auth = GoogleAuth()
        auth.LocalWebserverAuth()
        self.drive = GoogleDrive(auth)

    def create_folder(self, folder_name):
        self.folder_name = folder_name
        folder_metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        self.google_folder = self.drive.CreateFile(folder_metadata)
        self.google_folder.Upload()

    def upload(self):
        folder = os.listdir('vk/')
        for file in folder:
            google_file = self.drive.CreateFile({"parents": [{"id": self.google_folder['id']}], "title": file})
            google_file.SetContentFile(f'vk/{file}')
            google_file.Upload()
            print(f"The file {file} has been successfully uploaded on Google Drive")


if __name__ == '__main__':
    vk_client = VKAPIClient(VK_TOKEN, 1568059)
    vk_client.download_profile_photos(8)
    vk_client.download_album_photos(3)
    yandex = Yandex(YANDEX_TOKEN)
    yandex.create_folder('VK')
    yandex.upload()
    google = Google()
    google.create_folder('VK')
    google.upload()


