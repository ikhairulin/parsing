from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service

from urllib.parse import unquote
import requests
import zipfile
import re

import logging.config

from random import randint
import os
import time

from settings import (BASE_DIR, user_agent, logger_config,
                      manifest_json, background_js, proxy_settings)


logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')


class Parsing:
    def __init__(self, use_proxy=False):
        self.header = {
                       'User-Agent': user_agent,
        }
        self.user_agent = user_agent
        self.use_proxy = use_proxy
        self.driver = self.get_chromedriver()

        # Активизация эмуляции движения по странице
        self.actions = ActionChains(self.driver)

    def get_chromedriver(self):
        options = webdriver.ChromeOptions()
        options.add_argument(f'user-agent={self.user_agent}')

        # отключаем встроенные логи Selenium
        options.add_argument('--log-level=3')

        # disable webdrivermode
        options.add_argument('--disable-blink-features=AutomationControlled')

        # save sessions
        # options.add_argument(f'--user-data-dir={BASE_DIR}/User_data')
        # options.add_argument(f'--profile-directory={BASE_DIR}'
        #                      '/User_data/Profile 3')

        options.add_argument("--start-maximized")

        # работа в фоне
        # options.add_argument('--headless')

        if self.use_proxy:
            plugin_file = 'proxy_auth_plugin.zip'

            with zipfile.ZipFile(plugin_file, 'w') as zp:
                zp.writestr('manifest.json', manifest_json)
                zp.writestr('background.js', background_js)

            options.add_extension(plugin_file)

        # Адрес скачанного Chromedriver
        s = Service(os.path.join(BASE_DIR, 'chromedriver.exe'))

        driver = webdriver.Chrome(
            service=s,
            options=options
        )

        return driver

    def open_page(self, url: str) -> None:
        self.driver.get(url)
        console_log.info(f'Открываю страницу по адресу {url}')

    def scroll_page(self) -> None:
        scroll = self.driver.find_element(By.TAG_NAME, 'body')
        scroll.send_keys(Keys.PAGE_DOWN)
        time.sleep(1)

    def check_elem_exists_by_css_selector(self, query) -> bool:
        """Проверяет наличие элемента по CSS_SELECTOR на странице"""
        return len(self.driver.find_elements(By.CSS_SELECTOR, query)) > 0

    def check_elem_exists_by_id(self, query) -> bool:
        """Проверяет наличие элемента по ID на странице"""
        return len(self.driver.find_elements(By.ID, query)) > 0

    def find_element_with_xpath(self, parent_webdriver, element_xpath: str):
        """Находит с помощью XPATH на странице элемент и возвращает его
        """
        element = parent_webdriver.find_element(By.XPATH, element_xpath)
        return element

    def get_filename(self, link='', prefix=None) -> str:
        "Проверяет имя файла на наличие недопустимых для Windows символов"
        filename = unquote(link[link.rfind('/') + 1:])
        if prefix:
            filename = prefix + '_' + filename
        filename = re.sub(r'[/\:";*?<>|]', '', filename)
        file_log.info(f'Имя файла будет {filename}')
        return filename

    def make_dirs(self, alpha_dir=None,
                  tag_category=None, post_num=None) -> None:
        """Создает путь к рабочей папке для сохранения файла
        """

        if not os.path.exists((os.path.join(alpha_dir, tag_category))):
            os.makedirs(os.path.join(alpha_dir, tag_category), exist_ok=True)
            file_log.info(f'Создаю папку {tag_category}')

        if post_num:
            os.makedirs(os.path.join(alpha_dir, tag_category, post_num),
                        exist_ok=True)
            file_log.info(f'Создаю папку {post_num}')

    def check_saved_img(self, filepath: str) -> bool:
        try:
            with open(filepath, 'rb') as f:
                header = f.read(10)
                # Проверяем, является ли файл изображением
                # по характерным байтам в заголовке
                if header.startswith(
                    b'\xff\xd8') or header.startswith(
                        b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
                    # Проверяем целостность файла, сравнивая размер
                    # файла с длиной прочитанных байтов
                    file_log.info('Проверка пройдена. Это таки картиночка')
                    return os.path.getsize(filepath) == f.seek(0, 2)
        except IOError:
            pass
        file_log.warning('Проверка не пройдена.'
                         f'Что-то не так с файлом по адресу {filepath}')
        return False

    def save_file(self, img_link: str, save_path: str) -> None:
        if self.use_proxy:
            proxies = proxy_settings
        else:
            proxies = False
        file_log.debug('Сохраняю файл')
        response = requests.get(img_link,
                                stream=True,
                                proxies=proxies,
                                headers={
                                        'User-Agent': user_agent,
                                        'referer': img_link,
                                        }
                                )
        with open(save_path, "wb") as f:
            f.write(response.content)
        del response

    def click_button_by_class_name(self, button_value=None) -> None:
        '''Press target button on the page
        '''
        console_log.info('Нажимаю на кнопку <next>...')
        element = self.driver.find_element(By.CLASS_NAME, button_value)
        self.actions.move_to_element(element).perform()
        self.driver.find_element(By.CLASS_NAME, button_value).click()
        time.sleep(randint(0, 1))

    def random_wait(self, min: int, max: int) -> None:
        "Customize random wait time"
        seconds = randint(min, max)
        time.sleep(seconds)

    def wait(self, seconds: int) -> None:
        "Wait for a certain time"
        time.sleep(seconds)

    def refresh_page(self) -> None:
        console_log.info('Обновляю страницу')
        self.driver.refresh()

    def exit(self) -> None:
        self.driver.close()
        self.driver.quit()


def main():
    pass


if __name__ == '__main__':
    main()
