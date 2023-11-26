"""
This module backups photos from the Russian social network called VK
or Вконтакте in Russian

Classes:
Tokens -- access to a file containing tokens
VKAPIClient -- access to VK API
Yandex -- access to Yandex Disc API
Google -- access to Google Drive API
"""

import os
import sys
import json
import logging
import requests
from configparser import ConfigParser
from datetime import datetime
from googleapiclient.errors import HttpError
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pydrive.files import ApiRequestError
from tqdm import tqdm
from urllib.parse import urlencode

# Set a config for the logging module
logging.basicConfig(level=logging.INFO, filename='vk.log',
                    filemode='w', encoding='utf-8',
                    format='%(asctime)s %(levelname)s %(message)s')


class Tokens:
    """This class provides the access to a token file
    for VK and YANDEX tokens

    The token file must consist of the following 4 lines in which
    you have to paste your OAuth tokens after the equal sign:
    [VK]
    token=your_oauth_vk_token
    [YANDEX]
    token=OAuth your_oauth_yandex_token
    """
    if 'tokens.ini' in os.listdir():
        tokens = ConfigParser()
        tokens.read('tokens.ini')
    else:
        logging.exception('Not found tokens.ini '
                          'in the current directory')
        sys.exit()


class VKAPIClient:
    """This class provides the access to the VK API for
    downloading photos
    """
    API_BASE_URL = 'https://api.vk.com/method'
    APP_ID = '51792163'
    OAUTH_BASE_URL = 'https://oauth.vk.com/authorize'

    def __init__(self, owner_id: int):
        self._token = Tokens.tokens['VK']['token']
        self.owner_id = owner_id
        self.folder_name = 'vk_photos'
        params = {
            'client_id': self.APP_ID,
            'redirect_uri': 'https://oauth.vk.com/blank.html',
            'display': 'page',
            'scope': 'status,photos,offline',
            'response_type': 'token',
            'expires_in': 0
        }
        # Get a VK API token using the following url string:
        oauth_url = f'{self.OAUTH_BASE_URL}?{urlencode(params)}'
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def _get_common_params(self):
        """Get the common parameters for API requests"""
        return {
            'access_token': self._token,
            'v': '5.131',
            'owner_id': self.owner_id
        }

    def _build_url(self, path: str):
        """Get a url for API requests"""
        return f'{self.API_BASE_URL}/{path}'

    def _get_profile_photos(self):
        """Get a JSON string of profile photos"""
        params = self._get_common_params()
        params.update({'album_id': 'profile', 'extended': 1, 'rev': 1,
                       'count': self.num})
        response = requests.get(self._build_url('photos.get'), params=params)
        if 200 <= response.status_code < 300:
            logging.info('Retrieved JSON string of profile photos')
            return response.json()
        else:
            logging.exception('Failed retrieving JSON string '
                              'of profile photos')

    def download_profile_photos(self, num=5):
        """Download the provided number of profile photos and
        save them in the JSON file
        """
        self.num = num
        try:
            self.download_photos = self._get_profile_photos()
        except ValueError:
            logging.exception('No number of photos provided')
        else:
            self.json_output = []
            self.desc = 'profile photos'
            self._get_url()
            logging.info(f'Downloaded profile photos in '
                         f'{os.path.join(os.getcwd(), self.folder_name)}')
            self.json_file_name = 'profile_photos.json'
            self._save_json()

    def _get_wall_photos(self):
        """Get a JSON string of wall photos"""
        params = self._get_common_params()
        params.update({'album_id': 'wall', 'extended': 1, 'rev': 1,
                       'count': 1000})
        response = requests.get(self._build_url('photos.get'), params=params)
        if 200 <= response.status_code < 300:
            logging.info('Retrieved JSON string of wall photos')
            return response.json()
        else:
            logging.exception('Failed retrieving JSON string '
                              'of profile photos')

    def download_wall_photos(self):
        """Download the provided number of wall photos and
        save them in the JSON file
        """
        self.download_photos = self._get_wall_photos()
        self.json_output = []
        self.desc = 'wall photos'
        self._get_url()
        logging.info(f'Downloaded wall photos in '
                     f'{os.path.join(os.getcwd(), self.folder_name)}')
        self.json_file_name = 'wall_photos.json'
        self._save_json()

    def _get_all_album_photos(self):
        """Get a JSON string of album photos"""
        params = self._get_common_params()
        response = requests.get(self._build_url('photos.getAlbums'),
                                params=params)
        if 200 <= response.status_code < 300:
            self.album_title_and_id = []
            items = response.json()['response']['items']
            if 200 <= response.status_code < 300:
                for item in items:
                    self.album_title_and_id.append((item['title'], item['id']))
                albums_info = []
                for album_id in self.album_title_and_id:
                    params.update({'album_id': album_id[1], 'extended': 1,
                                   'rev': 1, 'count': 1000})
                    response = requests.get(self._build_url('photos.get'),
                                            params=params)
                    if 200 <= response.status_code < 300:
                        albums_info.append(response.json())
                        logging.info('Retrieved JSON string of photo info '
                                     'in album photos')
                    else:
                        logging.exception('Failed retrieving JSON string of '
                                          'photo info in album photos')
            else:
                logging.exception('Failed retrieving JSON string of items in'
                                  ' album photos')
        else:
            logging.exception('Failed retrieving JSON string of album photos')
        return albums_info

    def _download_all_album_photos(self):
        """Download all album photos and save them in the JSON file"""
        albums = self._get_all_album_photos()
        i = 0
        # Create a while loop to show a specific album title
        # in the progress bar while downloading
        while i < len(albums):
            for album in albums:
                self.desc = (f'album photos with title '
                             f'{self.album_title_and_id[i][0]}')
                self.download_photos = album
                self._get_url()
                i += 1
        logging.info(f'Downloaded all album photos in '
                     f'{os.path.join(os.getcwd(), self.folder_name)}')
        self.json_file_name = 'album_photos.json'
        self._save_json()

    def _search_for_album_title(self):
        """Search the user's album titles for a specific one and
        if found then get an ID"""
        self._get_all_album_photos()
        for album in self.album_title_and_id:
            if album[0] == self.title:
                return album[1]
        logging.exception(f'No album found with title {self.title}')

    def _get_album_photos_by_title(self, title: str):
        """Get a JSON string of album photos with a specific title"""
        self.title = title
        album_id = self._search_for_album_title()
        params = self._get_common_params()
        params.update({'album_id': album_id, 'extended': 1, 'rev': 1,
                       'count': 1000})
        response = requests.get(self._build_url('photos.get'), params=params)
        if 200 <= response.status_code < 300:
            logging.info(f'Retrieved JSON string of album with title {title}')
            return response.json()
        else:
            logging.exception(f'Failed retrieving JSON string of album with '
                              f'title {title}')

    def download_album_photos(self, *args: str):
        """Download album photos with the provided title(s) and
        save them in the JSON file"""
        self.json_output = []
        if not args:
            logging.exception('No album titles provided. '
                              'Started downloading all albums')
            self._download_all_album_photos()
            return
        for arg in args:
            try:
                self.download_photos = self._get_album_photos_by_title(arg)
            except ValueError:
                logging.exception('No album title(s) provided')
            else:
                self.desc = f'album photos with title {arg}'
                self._get_url()
                self.json_file_name = 'album_photos.json'
                self._save_json()

    def _get_url(self):
        """Get a url for a photo with the maximum resolution"""
        try:
            for items in tqdm(self.download_photos['response']['items'],
                              desc=f'Downloading {self.desc}'):
                self.photo_id = items['id']
                self.likes = items['likes']['count']
                max_res = 0
                for item in items['sizes']:
                    self.date = datetime.fromtimestamp(items['date']).date()
                    cur_res = item['height'] * item['width']
                    if cur_res == 0:
                        self.url = items['sizes'][-1]['url']
                        self.res_type = item['type']
                    elif cur_res > max_res:
                        max_res = cur_res
                        self.url = item['url']
                        self.res_type = item['type']
                logging.info(f'Retrieved photo url with id {self.photo_id}')
                self._download()
        except KeyError:
            logging.exception('Photo not found')

    def _download(self):
        """Download a photo with the provided url and
        check for an existing file name in the folder
        """
        if not os.path.exists(f'{self.folder_name}'):
            os.mkdir(f'{self.folder_name}')
            logging.info(f'Created folder {self.folder_name}')
        folder = os.listdir(f'{self.folder_name}/')
        response = requests.get(self.url)
        if 200 <= response.status_code < 300:
            if f'{self.likes}.jpg' not in folder:
                with open(f'{self.folder_name}/{self.likes}.jpg', 'wb') \
                        as img:
                    img.write(response.content)
                file_name = self.likes
                logging.info(f'Downloaded photo {self.likes}.jpg')
            elif f'{self.date}.jpg' not in folder:
                with open(f'{self.folder_name}/{self.date}.jpg', 'wb') \
                        as img:
                    img.write(response.content)
                file_name = self.date
                logging.info(f'Downloaded photo {self.date}.jpg')
            else:
                with open(f'{self.folder_name}/{self.photo_id}.jpg', 'wb') \
                        as img:
                    img.write(response.content)
                file_name = self.photo_id
                logging.info(f'Downloaded photo {self.photo_id}.jpg')
            self.json_output.append({'file_name': f'{file_name}.jpg',
                                     'size': f'{self.res_type}'})
        else:
            logging.exception('Failed downloading photo with provided url')

    def _save_json(self):
        """Save the list of dictionaries with a photo info
        in the JSON file"""
        with open(self.json_file_name, 'w') as file:
            json.dump(self.json_output, file)
        logging.info(f'JSON file saved in '
                     f'{os.path.join(os.getcwd(), self.json_file_name)}')


class Yandex:
    """This class provides the access to the Yandex Disc API
    for uploading photos
    """
    API_BASE_URL = 'https://cloud-api.yandex.net/v1/disk'

    def __init__(self):
        self._token = Tokens.tokens['YANDEX']['token']
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def _get_common_headers(self):
        """Get the common parameters for API requests"""
        return {
            'Authorization': self._token
        }

    def _build_url(self, path: str):
        """Get a url for API requests"""
        return f'{self.API_BASE_URL}/{path}'

    def create_folder(self, folder_name: str):
        """Create a folder on Yandex Disc"""
        self.folder_name = folder_name
        params = {
            'path': f'{folder_name}'
        }
        response = requests.put(self._build_url('resources'),
                                headers=self._get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            logging.info(f'Folder {folder_name} created on Yandex Disc')
        else:
            logging.exception(f'Failed creating folder {folder_name} '
                              f'on Yandex Disc')

    def _get_url(self, file: str):
        """Get a url for uploading a specific photo"""
        params = {
            'path': f'{self.folder_name}/{file}'
        }
        response = requests.get(self._build_url('resources/upload'),
                                headers=self._get_common_headers(),
                                params=params)
        if 200 <= response.status_code < 300:
            logging.info(f'Retrieved url for uploading {file}')
            return response.json()['href']
        else:
            logging.exception('Failed retrieving url for uploading')

    def upload(self):
        """Upload a photo on Yandex Disc"""
        folder = os.listdir(self.folder_name)
        for file in tqdm(folder, desc='Uploading photos on Yandex Disc'):
            url = self._get_url(file)
            try:
                with open(f'{self.folder_name}/{file}', 'rb') as upload_file:
                    response = requests.put(url, files={'file': upload_file})
            except requests.exceptions.MissingSchema:
                logging.exception(f'Folder {self.folder_name} already exists '
                                  f'on Yandex Disc')
                break
            if 200 <= response.status_code < 300:
                logging.info(f'Photo {file} uploaded on Yandex Disc')
            else:
                logging.exception(f'Failed uploading photo {file} '
                                  f'on Yandex Disc')


class Google:
    """This class provides the access to Google Drive API
    for uploading photos
    """
    def __init__(self):
        auth = GoogleAuth()
        auth.LocalWebserverAuth()
        self.drive = GoogleDrive(auth)
        logging.info(f'Instance of class {self.__class__.__name__} created')

    def create_folder(self, folder_name: str):
        """Create a folder on Google Drive"""
        self.folder_name = folder_name
        metadata = {'title': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'}
        self.google_folder = self.drive.CreateFile(metadata)
        try:
            self.google_folder.Upload()
            logging.info(f'Folder {self.folder_name} created on Google Drive')
        except ApiRequestError and HttpError:
            logging.exception(f'Failed creating folder {self.folder_name} '
                              f'on Google Drive')

    def upload(self):
        """Upload a photo on Google Drive"""
        folder = os.listdir(self.folder_name)
        for file in tqdm(folder, desc='Uploading photos on Google Drive'):
            metadata = {'parents': [{'id': self.google_folder['id']}],
                        'title': file}
            google_file = self.drive.CreateFile(metadata)
            google_file.SetContentFile(f'{self.folder_name}/{file}')
            try:
                google_file.Upload()
                logging.info(f'Photo {file} uploaded on Google Drive')
            except ApiRequestError or HttpError:
                logging.exception(f'Failed uploading photo {file} '
                                  f'on Google Drive')


if __name__ == '__main__':
    vk = VKAPIClient(783464)
    vk.download_profile_photos(10)
    vk.download_album_photos('sweden', 'BK', 'Прованс')
    vk.download_wall_photos()
    yandex = Yandex()
    yandex.create_folder('vk_photos')
    yandex.upload()
    google = Google()
    google.create_folder('vk_photos')
    google.upload()
