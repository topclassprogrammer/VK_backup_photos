import os
import json
import logging
import requests
import configparser
from datetime import datetime
from googleapiclient.errors import HttpError
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pydrive.files import ApiRequestError
from tqdm import tqdm
from urllib.parse import urlencode


class VKAPIClient:
    API_BASE_URL = 'https://api.vk.com/method'
    APP_ID = '51792163'
    OAUTH_BASE_URL = 'https://oauth.vk.com/authorize'

    def __init__(self, owner_id):
        self._token = tokens['VK']['token']
        self.owner_id = owner_id
        self.folder_name = 'vk'
        params = {
            'client_id': self.APP_ID,
            'redirect_uri': 'https://oauth.vk.com/blank.html',
            'display': 'page',
            'scope': 'status,photos,offline',
            'response_type': 'token',
            'expires_in': 0
        }
        oauth_url = f'{self.OAUTH_BASE_URL}?{urlencode(params)}'
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def _get_common_params(self):
        return {
            'access_token': self._token,
            'v': '5.131',
            'owner_id': self.owner_id
        }

    def _build_url(self, path):
        return f'{self.API_BASE_URL}/{path}'

    def _get_profile_photos(self, count):
        params = self._get_common_params()
        params.update({'album_id': 'profile', 'extended': 1, 'rev': 1, 'count': count})
        response = requests.get(self._build_url('photos.get'), params=params)
        logging.info(f'Retrieved JSON string of profile photos')
        return response.json()

    def download_profile_photos(self, count=5):
        try:
            self.photos_for_downloading = self._get_profile_photos(count)
        except ValueError:
            logging.error(f'No number of photos provided', exc_info=True)
        else:
            self.json_output = []
            self.desc = 'profile photos'
            self._get_url()
            logging.info(f"Downloaded profile photos in {os.path.join(os.getcwd(), self.folder_name)}")
            self.json_file_name = 'profile_photos.json'
            self._save_json()

    def _get_all_album_photos(self):
        params = self._get_common_params()
        response = requests.get(self._build_url('photos.getAlbums'), params=params)
        self.album_title_and_id = []
        items = response.json()['response']['items']
        for item in items:
            self.album_title_and_id.append((item['title'], item['id']))
        albums_info = []
        for album_id in self.album_title_and_id:
            params.update({'album_id': album_id[1], 'extended': 1, 'rev': 1})
            response = requests.get(self._build_url('photos.get'), params=params)
            albums_info.append(response.json())
        logging.info(f'Retrieved JSON string of album photos')
        return albums_info

    def _download_all_album_photos(self):
        albums = self._get_all_album_photos()
        self.desc = 'all album photos'
        for album in albums:
            self.photos_for_downloading = album
            self._get_url()
        logging.info(f"Downloaded all album photos in {os.path.join(os.getcwd(), self.folder_name)}")
        self.json_file_name = 'album_photos.json'
        self._save_json()

    def _search_for_album_title(self, title):
        self._get_all_album_photos()
        for album in self.album_title_and_id:
            if album[0] == title:
                return album[1]
        logging.error(f'No album title found called {title}', exc_info=True)

    def _get_album_photos_by_title(self, title):
        album_id = self._search_for_album_title(title)
        params = self._get_common_params()
        params.update({'album_id': album_id, 'extended': 1, 'rev': 1})
        response = requests.get(self._build_url('photos.get'), params=params)
        logging.info(f'Retrieved JSON string of album title called {title}')
        return response.json()
    
    def download_album_photos(self, *args):
        self.json_output = []
        if not args:
            logging.error('No album titles provided. Started downloading all albums', exc_info=True)
            self._download_all_album_photos()
            return
        for arg in args:
            try:
                self.photos_for_downloading = self._get_album_photos_by_title(arg)
            except ValueError:
                logging.error(f'No album title(s) provided', exc_info=True)
            else:
                self.desc = f'album photos with title {arg}'
                self._get_url()
                self.json_file_name = 'album_photos.json'
                self._save_json()

    def _get_url(self):
        try:
            for items in tqdm(self.photos_for_downloading['response']['items'], desc=f'Downloading {self.desc}', colour='#5D548C'):
                self.photo_id = items['id']
                self.likes = items['likes']['count']
                max_res = 0
                for item in items['sizes']:
                    self.date = datetime.fromtimestamp(items['date']).date()
                    self.res_type = item['type']
                    cur_res = item['height'] * item['width']
                    if cur_res == 0:
                        self.url = items['sizes'][-1]['url']
                    elif cur_res > max_res:
                        max_res = cur_res
                        self.url = item['url']
                logging.info(f'Retrieved photo url with id {self.photo_id}')
                self._download()
        except KeyError:
            logging.error(f'Photo not found', exc_info=True)

    def _download(self):
        if not os.path.exists(f'{self.folder_name}'):
            os.mkdir(f'{self.folder_name}')
            logging.info(f'Created folder {self.folder_name}')
        folder = os.listdir(f'{self.folder_name}/')
        response = requests.get(self.url)
        if f'{self.likes}.jpg' not in folder:
            with open(f'{self.folder_name}/{self.likes}.jpg', 'wb') as img:
                img.write(response.content)
            file_name = self.likes
            logging.info(f'Downloaded photo {self.likes}.jpg')
        elif f'{self.date}.jpg' not in folder:
            with open(f'{self.folder_name}/{self.date}.jpg', 'wb') as img:
                img.write(response.content)
            file_name = self.date
            logging.info(f'Downloaded photo {self.date}.jpg')
        else:
            with open(f'{self.folder_name}/{self.photo_id}.jpg', 'wb') as img:
                img.write(response.content)
            file_name = self.photo_id
            logging.info(f'Downloaded photo {self.photo_id}.jpg')
        self.json_output.append({'file_name': f'{file_name}.jpg', 'size': f'{self.res_type}'})
        return self.json_output

    def _save_json(self):
        with open(self.json_file_name, 'w') as file:
            json.dump(self.json_output, file)
        logging.info(f"JSON file saved in {os.path.join(os.getcwd(), self.json_file_name)}")


class Yandex:
    API_BASE_URL = "https://cloud-api.yandex.net/v1/disk"

    def __init__(self):
        self._token = tokens['YANDEX']['token']
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def _get_common_headers(self):
        return {
            "Authorization": self._token
        }

    def _build_url(self, path):
        return f'{self.API_BASE_URL}/{path}'

    def create_folder(self, folder_name):
        self.folder_name = folder_name
        params = {
            "path": f'{folder_name}'
        }
        response = requests.put(self._build_url("resources"),
                                headers=self._get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            logging.info(f"Folder {folder_name} created on Yandex Disc")
        else:
            logging.error(f"Failed creating folder {folder_name} on Yandex Disc", exc_info=True)

    def _get_url_for_uploading(self, file):
        params = {
            "path": f"{self.folder_name}/{file}"
        }
        response = requests.get(self._build_url("resources/upload"),
                                headers=self._get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            logging.info(f"Retrieved url for uploading {file}")
            return response.json()['href']
        else:
            logging.error(f"Failed receiving url for uploading", exc_info=True)

    def upload(self):
        folder = os.listdir(self.folder_name)
        for file in tqdm(folder, desc='Uploading photos on Yandex Disc', colour='#5D548C'):
            url = self._get_url_for_uploading(file)
            try:
                with open(f'{self.folder_name}/{file}', "rb") as upload_file:
                    response = requests.put(url, files={"file": upload_file})
            except requests.exceptions.MissingSchema:
                logging.error(f'Folder {self.folder_name} already exists on Yandex Disc')
                break
            if 200 <= response.status_code < 300:
                logging.info(f"Photo {file} uploaded on Yandex Disc")
            else:
                logging.error(f"Failed uploading photo {file} on Yandex Disc", exc_info=True)


class Google:
    def __init__(self):
        auth = GoogleAuth()
        auth.LocalWebserverAuth()
        self.drive = GoogleDrive(auth)
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def create_folder(self, folder_name):
        self.folder_name = folder_name
        metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        self.google_folder = self.drive.CreateFile(metadata)
        try:
            self.google_folder.Upload()
            logging.info(f"Folder {self.folder_name} created on Google Drive")
        except ApiRequestError and HttpError:
            logging.error(f"Failed creating folder {self.folder_name} on Google Drive", exc_info=True)

    def upload(self):
        folder = os.listdir(self.folder_name)
        for file in tqdm(folder, desc='Uploading photos on Google Drive', colour='#5D548C'):
            metadata = {"parents": [{"id": self.google_folder['id']}], "title": file}
            google_file = self.drive.CreateFile(metadata)
            google_file.SetContentFile(f'{self.folder_name}/{file}')
            try:
                google_file.Upload()
                logging.info(f"Photo {file} uploaded on Google Drive")
            except ApiRequestError or HttpError:
                logging.error(f"Failed uploading photo {file} on Google Drive", exc_info=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, filename="vk_backup_photos.log", filemode="w",
                        format="%(asctime)s %(levelname)s %(message)s", encoding='utf-8')
    tokens = configparser.ConfigParser()
    tokens.read("tokens.ini")
    vk = VKAPIClient(1568059)
    vk.download_profile_photos(10)
    vk.download_album_photos('Я, снова я...', 'наши подопечные')
    yandex = Yandex()
    yandex.create_folder('VK')
    yandex.upload()
    google = Google()
    google.create_folder('VK')
    google.upload()










