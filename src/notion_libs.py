from notion_client import Client
import requests
from bs4 import BeautifulSoup
import json
import re
import logging.config

import hashlib
import time
from random import randint

from alive_progress import alive_bar

from sql_commit import TableMaster
from settings import sites, logger_config, proxy_settings, user_agent

logging.config.dictConfig(logger_config)

console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')

table = TableMaster('no_db')

MAX_BLOCK_LENGTH = 2000
MAX_IMG_SIZE = 5000 * 1024


class Article_parser():
    def __init__(self, url):
        self.url = url
        self.domain = self.get_domain_name(self.url)
        self.sites_dict = sites
        self.blocks = {}
        self.unique_block_set = set()
        self.notion_tags = {
            "li": "bulleted_list_item",
            "blockquote": "quote",
            "code": "code",
            "h1": "heading_1",
            "h2": "heading_2",
            "h3": "heading_3",
            "img": "image",
            "ol": "bulleted_list_item",
            "paragraph": "paragraph",
            "pdf": "pdf",
            "q": "quote",
            "to_do": "to_do",
            "video": "video",
                }

        response = requests.get(self.url)
        html = response.content
        self.soup = BeautifulSoup(html, 'lxml')

    def get_article_header(self) -> None:
        title = self.extract_title(self.soup.title.string,
                                   sites[self.domain]['extract_title_pattern'])

        self.blocks['header'] = {'title': title,
                                 'url': self.url,
                                 'database_id': sites[self.domain]['db_id'],
                                 'domain': self.domain,
                                 'article_id': self.hash_string(self.url),
                                 }

    def parsing_data(self) -> None:

        self.get_article_header()

        self.blocks['body'] = []

        attr_type = sites[self.domain]['search_tag']
        raw_soup = self.soup.find(
                attrs={attr_type: sites[self.domain][attr_type]})

        raw_tags = raw_soup.find_all()
        tags_count = len(raw_tags)

        with alive_bar(tags_count) as bar:
            # for i in range(tags_count):
            for tag in raw_tags:
                if len(self.blocks["body"]):
                    file_log.debug(f'case {tag.name} - '
                                   f'content {self.blocks["body"][-1]} '
                                   f'attrs - {tag.attrs}')
                self.parse_tag(tag)
                bar()
        return self.blocks

    def parse_tag(self, tag: BeautifulSoup) -> None:

        match tag.name:
            case 'code':
                # Блок с кодом с habr
                text = str(tag)
                self.blocks['body'].append({'type': 'code',
                                            'content': text,
                                            })
            case 'img':
                # Общие блоки изображений
                try:
                    img_src = tag[sites[self.domain]['src']]
                except KeyError:
                    return
                if img_url := self.analyze_img_size(img_src):
                    self.blocks['body'].append({'type': 'image',
                                                'content': img_url,
                                                })
            case 'div' if sites[self.domain]['src'] in tag.attrs:
                # Изображения на dtf
                img_src = tag[sites[self.domain]['src']]
                if img_url := self.analyze_img_size(img_src):
                    self.blocks['body'].append({'type': 'image',
                                                'content': img_url,
                                                })
            case 'div' if 'data-index' in tag.attrs:
                # Изображения на блоке со свайпом на dtf
                img_src = tag['style']
                img_src = self.extract_dtf_url(img_src)
                if img_url := self.analyze_img_size(img_src):
                    self.blocks['body'].append({'type': 'image',
                                                'content': img_url,
                                                })
            case 'sg-spoiler':
                # Заголовок на спойлерном блоке на stopgame
                self.blocks['body'].append({'type': 'paragraph',
                                            'content': tag.attrs['title'],
                                            })
            case 'figcaption':
                # Текст на блоке под изображением на dtf
                text = tag.get_text()
                self.blocks['body'].append({'type': 'paragraph',
                                            'content': text.strip(),
                                            })
            case 'div' if 'data-video-mp4' in tag.attrs:
                # Короткое видео на dtf
                url = tag['data-video-mp4']
                self.blocks['body'].append({'type': 'video',
                                            'content': url,
                                            })
            case 'audio':
                # аудио файл со страницы
                url = tag['src']
                self.blocks['body'].append({'type': 'audio',
                                            'content': url,
                                            })

            case 'div' if tag.get('class') == ['highlight']:
                # Выделенный блок текста на mirf
                text = tag.get_text()
                print({'type': 'quote', 'content': text.strip()})

            case 'div' if ('class' in tag.attrs
                           and tag['class'] == ['block-number__digit']):
                # Выделенный заголовок на dtf
                if tag['class'] == ['block-number__digit']:
                    text = tag.get_text().strip()
                    self.blocks['body'].append({'type': 'heading_1',
                                                'content': text,
                                                })
                    self.unique_block_set.add(text)

            case 'h1' | 'h2' | 'h3' | 'li' | 'q':
                # Общие блоки выделенного текста
                text = self.delete_newlines(tag.get_text()).strip()
                block_type = self.notion_tags[str(tag.name)]
                self.blocks['body'].append({'type': block_type,
                                            'content': text,
                                            })
                self.unique_block_set.add(text)

            case 'h4' | 'h5' | 'h6':
                # Общие блоки обычного текста
                text_raw = self.delete_newlines(tag.get_text()).strip()
                self.blocks['body'].append({'type': 'paragraph',
                                            'content': text,
                                            })

            case 'blockquote' if quote_text_raw := tag('p'):
                # Общие блоки выделенного текста
                for p in quote_text_raw:
                    text = self.delete_newlines(p.get_text()).strip()
                    if not len(text):
                        return
                    self.blocks['body'].append({'type': 'quote',
                                                'content': text,
                                                })
                self.unique_block_set.add(text)

            case 'p' if not tag.find_parents('blockquote'):
                # Основной общий блок обычного текста
                text_raw = self.split_string(str(tag.get_text()))
                for text in text_raw:
                    if text in self.unique_block_set:
                        pass
                    else:
                        self.blocks['body'].append({'type': 'paragraph',
                                                    'len': len(text),
                                                    'content': text,
                                                    })
            case _:
                pass

    def analyze_img_size(self, img_url: str) -> str:
        """
        Отправляем GET-запрос по адресу изображения и проверяем его размер
        """
        clean_img_link, img_size = self.smell_img_link(img_url)

        if img_size > MAX_IMG_SIZE:
            # -> переписать через скачивание и декодирование файла
            console_log.error(f'Файл изображения по ссылке {clean_img_link} '
                              f'весит {round(img_size/1024, 2)}Кб')

        if img_size > sites[self.domain]['min_img_size']:
            return clean_img_link

    def smell_img_link(self, img_url: str) -> str:
        if self.bad_domain_check(img_url):
            return None, 0

        if (self.domain == 'stopgame.ru' and
                self.get_domain_name(img_url) == 'images.stopgame.ru'):
            img_url = self.transform_sg_img_link(img_url)

        if self.domain == 'dtf.ru':
            img_url = img_url + '.webp'

        if self.domain == 'mirf.ru':
            img_url = self.replace_mirf_img_url(img_url)
            print(f'Функция replace_mirf_img_url -> {img_url}')

        try:
            img_response = requests.get(img_url)

        except requests.exceptions.MissingSchema:
            img_url = sites[self.domain]['prefix'] + img_url
            img_response = requests.get(img_url)

        except requests.exceptions.ReadTimeout:
            proxies = proxy_settings
            img_response = requests.get(
                            img_url,
                            stream=True,
                            proxies=proxies,
                            headers={'User-Agent': user_agent,
                                     'referer': img_url})
        finally:
            img_size = len(img_response.content)

        return img_url, img_size

    @staticmethod
    def get_domain_name(url: str) -> str:
        pattern = r'https?://(?:www\.)?([^\s/]+)'
        domain = re.search(pattern, url).group(1)
        return domain

    def bad_domain_check(self, url: str) -> bool:
        bad_domain_set = {'yandex', }
        img_domain = self.get_domain_name(url)
        if set(img_domain.split('.')) & bad_domain_set:
            return True

    @staticmethod
    def transform_sg_img_link(link: str) -> str:
        split_link = link.split("/")
        new_link = "/".join(split_link[:-3] + [split_link[-1]])
        return new_link

    @staticmethod
    def delete_newlines(string: str) -> str:
        return string.replace('\n', ' ')

    @staticmethod
    def split_string(string: str) -> str:
        string = string.replace('\n', ' ')
        if len(string) <= MAX_BLOCK_LENGTH:
            yield string
        else:
            while len(string) > MAX_BLOCK_LENGTH:
                split_index = string.rfind(".", 0, MAX_BLOCK_LENGTH)
                if split_index == -1:
                    split_index = MAX_BLOCK_LENGTH
                yield string[:split_index+1]
                string = string[split_index+1:]
            yield string

    @staticmethod
    def extract_dtf_url(string: str) -> str:
        pattern = r'url\((.*?)\)'
        match = re.search(pattern, string)
        if match:
            raw_link = match.group(1)
            img_link = raw_link[:raw_link.index('-/resize')]
            return img_link
        else:
            return None

    @staticmethod
    def replace_mirf_img_url(url: str) -> None:
        return re.sub(r'-\d+x\d+\.', '.', url)

    @staticmethod
    def get_file_size(url: str) -> None:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 200:
            return int(response.headers.get('content-length', 0))
        else:
            return None

    @staticmethod
    def collect_urls_by_file(file_path: str, param: str) -> list:
        with open(file_path, 'r', encoding='UTF-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            text_beacon = soup.find(text=param)
            links_dir_by_param = text_beacon.find_parent('dt').find('dl')
            raw_soup = links_dir_by_param.find_all('a')
            link_list = [link.get('href') for link in raw_soup]
            return link_list

    @staticmethod
    def get_urls_by_bookmarks(file_path: str, query: str) -> list:
        with open(file_path, 'r', encoding='UTF-8') as f:
            json_data = json.loads(f.read())
        urls = []
        for child in json_data['roots']['bookmark_bar']['children']:
            if 'children' in child:
                for grandchild in child['children']:
                    if grandchild.get('type') == 'folder' and grandchild.get(
                            'name') == query:
                        for great_grandchild in grandchild['children']:
                            if great_grandchild.get('type') == 'url':
                                urls.append(great_grandchild['url'])
        return urls

    @staticmethod
    def hash_string(string: str) -> str:
        """
        Создаем объект хеша SHA-256
        Кодируем строку в байты
        возвращаем хеш в виде шестнадцатеричной строки
        """
        hash_object = hashlib.md5()
        hash_object.update(string.encode('utf-8'))
        return hash_object.hexdigest()

    def extract_title(self, string: str, pattern: str) -> str:
        pattern = r'(.*?)[—].*'
        match = re.match(pattern, string)
        if match:
            return match.group(1).rstrip()
        else:
            return string


class Notion_page():
    def __init__(self):
        self.notion_token = table.get_login_data('notion')['add_inf']
        self.client = Client(auth=self.notion_token)
        self.page_id = "fcd9bb2d-0c25-48a1-bf11-a475d44313a1"
        self.database_id = '77a7aaf6d2e84eb693601f64a24183bb'

    def match_block(self, block: dict) -> None:

        match block['type']:
            case 'heading_1' | 'heading_2' | 'heading_3' | 'paragraph':
                self.write_text(text=block['content'], type=block['type'])
            case 'bulleted_list_item' | 'numbered_list_item':
                self.write_text(text=block['content'], type=block['type'])
            case 'quote':
                self.add_quote(text=block['content'], type=block['type'])
            case 'image':
                self.add_media(media_url=block['content'], type=block['type'])
            case 'video' | 'audio':
                self.add_media_as_embed(url=block['content'])
            case 'code':
                pass

    def create_page(self, article_properties: dict) -> None:
        title = article_properties['title']
        self.database_id = article_properties['database_id']
        new_page = {
            "title": [{"text": {"content": title}}]
        }
        self.client.pages.create(
            parent={"database_id": self.database_id}, properties=new_page)
        result = self.client.databases.query(
            **{
                "database_id": self.database_id,
                "filter": {
                    "property": "title",
                    "title": {
                        "equals": title}
                }
            }
        )
        page_id = result["results"][0]["id"]
        console_log.info(f'Создаю страницу {page_id} '
                         f'в базе {self.database_id}')
        self.page_id = page_id

    def write_text(self, text: str, type: str = 'paragraph') -> None:
        file_log.info(f'Добавляю текстовый блок "{text[:20]}" '
                      f'на странице {self.page_id}')
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "parent": {"page_id": self.page_id},
                "type": type,
                type: {
                    "rich_text": [{"type": "text",
                                   "text": {"content": text}},
                                    #   {"type": "text",
                                    #    "text": {"content": text},
                                    #    "href": "https://example.com"}
                                  ],
                       }
                       }]
        )

    def add_rich_text(self, text: str) -> None:
        file_log.info(f'Добавляю текстовый блок "{text[:20]}" '
                      f'на странице {self.page_id}')
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "parent": {"page_id": self.page_id},
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Обычный текст "
                            }
                        },
                        {
                            "type": "text",
                            "text": {
                                "content": "жирный текст",
                                "link": {
                                    "url": "https://example.com"
                                },
                                "annotations": {
                                    "bold": True
                                }
                            }
                        },
                        {
                            "type": "text",
                            "text": {
                                "content": " еще обычный текст"
                            }
                        }
                    ]
                }
            }]
        )

    def add_quote(self, text: str, type: str = 'quote') -> None:
        file_log.info(f'Добавляю цитатный блок "{text[:20]}" '
                      f'на странице {self.page_id}')
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "parent": {"page_id": self.page_id},
                "type": type,
                type: {
                    "rich_text": [{"type": "text",
                                   "text": {"content": text,
                                            "link": None},
                                   }],
                    "color": "default"
                }
            }]
        )

    def add_media(self, media_url: str, type: str) -> None:
        file_log.info(f'Добавляю медиа блок {media_url} '
                      f'на странице {self.page_id}')
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "parent": {"page_id": self.page_id},
                "type": type,
                type: {
                    "type": "external",
                    "external": {"url": media_url}
                }
            }]
        )

    def add_media_as_embed(self, url: str) -> None:
        file_log.info(f'Добавляю медиа-файл по ссылке {url} как вложение')
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "type": "embed",
                "embed": {
                    "url": url,
                }
            }]
        )

    def read_text(self, page_id: str) -> None:
        response = self.client.blocks.children.list(block_id=page_id)
        return response['results']

    def add_url_property(self, url: str) -> bool:
        # Обновляем свойство "url" на странице
        properties = {
            'URL': {
                'url': url
            }
        }
        self.client.pages.update(page_id=self.page_id, properties=properties)
        return True

    def upload_file_to_page(self, file_path: str) -> None:
        self.client.blocks.children.append(
            block_id=self.page_id,
            children=[{
                "object": "block",
                "parent": {"page_id": self.page_id},
                "type": 'file',
                'file': {
                    "type": "external",
                    "external": {"url": file_path}
                }
            }]
        )

    def random_wait(self, min: int, max: int) -> None:
        "Customize random wait time"
        seconds = randint(min, max)
        time.sleep(seconds)


def main():
    pass

    # notion_page_id = "fcd9bb2d-0c25-48a1-bf11-a475d44313a1"
    # database_id = '77a7aaf6d2e84eb693601f64a24183bb'
    np = Notion_page()

    text = "## Строка"

    np.write_text(text)


if __name__ == '__main__':
    main()
