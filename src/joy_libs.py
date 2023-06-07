from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup
import requests
import os
import pickle

import logging.config

from parsing import Parsing
from sql_commit import TableMaster
from settings import BASE_DIR, user_agent, logger_config
from environ import JOY_FAV_URL, JOY_DIR

logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')


class JoyMaster(Parsing):
    def __init__(self):
        super().__init__(use_proxy=False)
        self.start_url = 'https://joyreactor.cc/'
        self.login_url = 'https://joyreactor.cc/login'
        self.fav_url = JOY_FAV_URL
        self.cookie_path = os.path.join(BASE_DIR, 'cookies', 'joy_cookies')

    def authorization(self):

        # проверить авторизацию
        if self.check_elem_exists_by_id('logout'):
            self.load_cookies()

        else:
            # авторизуемся и получаем куки
            self.driver.get(self.login_url)
            self.wait(1)

            db = TableMaster('joyreactor')

            auth_data = db.get_login_data('joyreactor')
            username = auth_data['login']
            password = auth_data['password']

            console_log.info('Проходим авторизацию...')
            email_input = self.driver.find_element(By.ID, 'signin_username')
            email_input.clear()
            email_input.send_keys(username)
            pass_input = self.driver.find_element(By.ID, 'signin_password')
            pass_input.clear()
            pass_input.send_keys(password)
            self.wait(1)

            pass_input.send_keys(Keys.ENTER)

            self.wait(1)

            # сохраняем cookies в файл
            if not os.path.isfile(self.cookie_path):
                pickle.dump(self.driver.get_cookies(), open(
                            self.cookie_path, "wb"))
                self.wait(2)

    def find_post_on_page(self, post_num):
        """Переходит к нужному посту на странице
        """
        postContainer = "postContainer" + str(post_num)
        element = self.driver.find_element(By.ID, postContainer)
        self.actions.move_to_element(element).perform()

    def load_cookies(self):
        """Загружает куки из файла
        """
        if os.path.isfile(self.cookie_path):
            self.driver.get(self.start_url)
            self.wait(4)
            for cookie in pickle.load(open(self.cookie_path, 'rb')):
                self.driver.add_cookie(cookie)
            console_log.info('Загружаю cookies')
            self.wait(3)
            self.driver.refresh()
            self.wait(3)

    def check_login_button_exists(self) -> bool:
        """Проверяет наличие кнопки 'Выход' на странице"""
        return len(self.driver.find_elements(By.ID, 'logout')) > 0

    def get_posts_list(self) -> list:
        """Вытаскивает из html-кода страницы список номеров постов
        для анализа. Возвращает словарь со списком постов и суп страницы.
        """
        page_code = self.driver.page_source

        current_page_url: str = self.driver.current_url

        console_log.info(f'Собираю информацию о постах '
                         f'на странице {current_page_url}')

        soup = BeautifulSoup(page_code, 'lxml')
        posts_raw = soup.find('div', id='post_list').findAll(
                                        class_="postContainer")
        posts_id_nums: list = []
        for i in posts_raw:
            posts_id_nums.append(i.get('id')[13:])
        file_log.info(f'Номера постов на странице {posts_id_nums}')
        posts_raw_data = {'posts_list': posts_id_nums, 'soup': soup}
        return posts_raw_data

    def prepare_imgs_and_save(self, post_data: dict) -> int:
        """Сохраняет изображения из поста в соответствующую папку"""
        tag_category = post_data.get('tag_category')
        img_links = post_data.get('img_links')
        post_num = post_data.get('post_num')

        self.make_dirs(alpha_dir=JOY_DIR,
                       tag_category=tag_category)

        if len(img_links) > 1:
            self.make_dirs(alpha_dir=JOY_DIR,
                           tag_category=tag_category,
                           post_num=post_num)
            file_dir = os.path.join(tag_category, str(post_num))
        else:
            file_dir = tag_category

        counter = 0

        for img_link in img_links:
            filename = self.get_filename(img_link)
            save_path = os.path.join(JOY_DIR, file_dir,
                                     filename)
            self.save_file('https:' + img_link, save_path)
            file_log.info(f'Сохраняю файл {filename} в папку {file_dir}')
            if self.check_saved_img(save_path):
                counter += 1

        console_log.info(f'Сохранил {counter} файлов в папку {file_dir}')
        return counter

    def unbutton_favs(self, post_num) -> None:
        '''Нажимает кнопку избранное'''
        button_xpath = (f'//*[@id="postContainer{post_num}"]/descendant::'
                        'span[@class="favorite_link favorite"]')
        element = self.driver.find_element(By.XPATH, button_xpath)
        self.actions.move_to_element(element).perform()

        self.driver.find_element(By.XPATH, button_xpath).click()
        console_log.warning(f'''Снимаю метку с поста {post_num}
                             ''')
        self.random_wait(0, 1)

    def collect_wrong_post_links(self, post_data) -> None:
        '''Записывает данные проблемных постов для последующего анализа
        '''
        console_log.warning(post_data['message'])
        wrong_links_file = os.path.join(JOY_DIR, 'wrong_post_list.txt')

        with open(wrong_links_file, 'a', encoding='UTF-8') as saved_text:
            saved_text.write(
                f"Пост по ссылке {post_data['post_url']}\n"
                f"Тэги {post_data['post_tags']}\n"
                f"Приоритетный тэг {post_data['biggest_tag']} "
                f"категории {post_data['tag_category']}\n"
                f"Ссылок на файлы {post_data['imgs_qty']}\n"
                f"Текст {post_data['text_lenth']} символов\n"
                f"Текст -> {post_data['text']}\n"
                f"Вероятная причина -> {post_data['message']}\n\n")


class JoyPost():
    def __init__(self,
                 post_num: int,
                 soup,
                 db_tags_dict: dict,
                 session_num: int):
        self.post_num = post_num
        self.soup = soup
        self.db_tags_dict = db_tags_dict
        self.session_num = session_num
        self.user_agent = user_agent
        self.post_tags_list = []
        self.post_url = 'https://joyreactor.cc/post/' + str(self.post_num)
        self.postContainer = "postContainer" + str(self.post_num)
        self.message = ''

    def define_priority_tag(self) -> tuple[str, str]:
        '''
        Из тэгов поста определяет приоритетный
        Возвращает его и категорию тэга
        '''
        file_log.debug('Выбираю приоритетный тэг.')
        self.post_tags_list = self.get_tag_list()
        post_tags_dict = self.compare_tags(self.db_tags_dict)
        max_num = 0
        biggest_tag = ''
        tag_category = ''

        for key, value in post_tags_dict.items():
            if value[1] > max_num:
                max_num = value[1]
                biggest_tag = key
                tag_category = value[0]
            if tag_category is None:
                tag_category = 'Other'
        console_log.info(f'Приоритетный тэг поста {self.post_num} - '
                         f'{biggest_tag} в категории {tag_category}')
        return biggest_tag, tag_category

    def get_tag_list(self) -> list[str]:
        """Получаем из поста список тэгов
        """
        tags_raw_data = self.soup.find('div', id=self.postContainer).find(
                                    'h2', class_="taglist").findAll('b')
        for i in tags_raw_data:
            self.post_tags_list.append(i.get_text()[:-1])
        file_log.info(f'Список тэгов поста {self.post_tags_list}')
        return self.post_tags_list

    def compare_tags(self, db_tags_dict: dict) -> dict:
        """Сопоставляет список тэгов из поста с тэгами из базы
        Убирает лишние незначительные тэги
        Возвращает отсортированный словарь с тэгами поста
        """
        file_log.debug('Сравниваю тэги поста с базой.')
        post_tags_dict = {}
        for tag in self.post_tags_list:
            try:
                post_tags_dict[tag] = db_tags_dict[tag]
            except KeyError:
                continue
        return post_tags_dict

    def get_post_author_nickname(self) -> str:
        post_author_nickname = self.soup.find(
                                'div', id=self.postContainer).find(
                                'div', class_="uhead_nick").get_text()
        file_log.debug(f'Никнэйм автора поста - {post_author_nickname}')
        return post_author_nickname

    def get_imgs_links(self) -> list[str]:

        try:
            imgs_raw_data = self.soup.find(
                                    'div', id=self.postContainer).find(
                                    'div', class_="post_content").findAll(
                                    'img')
        except AttributeError:
            self.message = 'Не могу найти ссылки на изображения'
            return None
        else:
            imgs_links_list = []
            counter_img = 0
            for k in imgs_raw_data:
                img_link = k.get("src")
                img_link_full = self.check_link(img_link)
                if img_link_full:
                    img_link = img_link_full
                imgs_links_list.append(img_link)
                counter_img += 1
                file_log.debug(f'Ссылка на {counter_img} файл - {img_link}')

            file_log.debug(f'Пост содержит {len(imgs_links_list)} изображений')

            if imgs_links_list:
                return imgs_links_list
            else:
                return []

    def check_link(self, link: str) -> str:
        """Проверяет возможность скачать увеличенную версию картинки
        и пропускает зацензуренные посты
        """
        forbidden = ['/images/censorship/ru.png',
                     '/images/censorship/copywrite.jpg',
                     ]
        if link in forbidden:
            console_log.error('Пост заблокирован. '
                              'Доступ только через расширение')
            self.message = 'Пост заблокирован'
            return None

        src1 = link
        src2 = (src1[:src1.find('post') + 5] + "full"
                + src1[src1.find('post') + 4:])
        link = 'https:' + src2
        response = requests.get(link, stream=True,
                                headers={
                                        'User-Agent': self.user_agent,
                                        'referer': link,
                                        }
                                )
        if response.status_code == 200:
            return src2
        else:
            return None

    def get_post_text(self) -> str:
        try:
            text_raw_data = self.soup.find(
                                'div', id=self.postContainer).find(
                                'div', class_="post_content").findAll(
                                'div')
        except AttributeError:
            return ''
        else:
            text_list = []
            for f in text_raw_data:
                text_list.append(f.text)
            return text_list[0]

    def analyze_post(self) -> dict:
        """Основная функция с логикой обработки поста"""
        console_log.info(f'\nАнализирую пост №{self.post_num} '
                         f'по адресу {self.post_url}')
        post_author_nickname: str = self.get_post_author_nickname()
        imgs_links_list: list = self.get_imgs_links()
        biggest_tag_data: tuple = self.define_priority_tag()
        text = self.get_post_text()

        try:
            text_lenth = len(text)
            if text_lenth > 120:
                self.message = 'Пост содержит текст более 120 символов'
        except TypeError:
            text_lenth = 0

        try:
            imgs_qty = len(imgs_links_list)
        except TypeError:
            imgs_qty = 0

        post_data = {
                     'post_num': self.post_num,
                     'post_url': self.post_url,
                     'post_author': post_author_nickname,
                     'post_tags': self.post_tags_list,
                     'img_links': imgs_links_list,
                     'imgs_qty': imgs_qty,
                     'biggest_tag': biggest_tag_data[0],
                     'tag_category': biggest_tag_data[1],
                     'check_file': 0,
                     'fav_button': 0,
                     'session_num': self.session_num,
                     'text': text[:120],
                     'text_lenth': text_lenth,
                     'message': self.message,
                     }

        return post_data


def main():
    pass


if __name__ == '__main__':
    main()
