from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException

from bs4 import BeautifulSoup
import os
import pickle
import re

import logging.config

from settings import BASE_DIR, logger_config
from environ import TWEET_FAV_URL, ART_CHANNELS, TWEET_DIR
from parsing import Parsing
from sql_commit import TableMaster

logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')


class TweetMaster(Parsing):
    def __init__(self):
        super().__init__(use_proxy=True)
        self.start_url = 'https://twitter.com'
        self.url_login = 'https://twitter.com/i/flow/login'
        self.fav_url = TWEET_FAV_URL
        self.authors_dict = {}
        self.post_class_id = ('css-1dbjc4n r-1iusvr4 '
                              'r-16y2uox r-1777fci r-kzbkwu')

    def authorization(self):

        db = TableMaster('twitter')

        auth_data = db.get_login_data()
        username = auth_data['login']
        password = auth_data['password']
        phone = auth_data['add_inf']

        twit_cookie = os.path.join('cookies', 'twit_cookies')
        path = os.path.join(BASE_DIR, twit_cookie)
        if os.path.isfile(path):
            self.driver.get(self.start_url)
            self.wait(5)
            for cookie in pickle.load(open(path, 'rb')):
                self.driver.add_cookie(cookie)
            console_log.info('Загружаю cookies')
            self.wait(5)
            self.driver.refresh()
            self.wait(5)

        else:
            self.driver.get(self.url_login)
            self.wait(5)

            # enter username
            self.random_wait(1, 3)
            login = self.driver.find_element(By.XPATH, "//input")
            login.send_keys(username)
            input('press any key')

            # click on the "next" button
            all_buttons = self.driver.find_elements(
                                    By.XPATH, "//div[@role='button']")
            all_buttons[-2].click()
            input('press any key')

            # enter phone_number
            phone_input = self.driver.find_element(By.CLASS_NAME, 'r-30o5oe')
            phone_input.send_keys(phone)
            input('press any key')
            all_buttons = self.driver.find_elements(
                                    By.XPATH, "//div[@role='button']")
            all_buttons[-1].click()
            self.wait(5)
            input('press any key')

            # enter password & login
            self.random_wait(1, 3)
            pass_input = self.driver.find_element(
                                    By.XPATH, "//input[@type='password']")
            pass_input.send_keys(password)
            input('press any key')

            # click on the "login" button
            all_buttons = self.driver.find_elements(
                                    By.XPATH, "//div[@role='button']")
            all_buttons[-1].click()
            input('press any key')

            # сохраняем cookies в файл
            pickle.dump(self.driver.get_cookies(), open(twit_cookie, "wb"))
            self.wait(3)

    def get_authors_list(self) -> list:
        """Вытаскивает из html-кода страницы список авторов.
        """
        page_code = self.driver.page_source
        current_page_url: str = self.driver.current_url
        console_log.info(f'Собираю список авторов в избранном '
                         f'на странице {current_page_url}')
        soup = BeautifulSoup(page_code, 'lxml')
        posts_raw = soup.findAll(class_='css-4rbku5 css-18t94o4 css-1dbjc4n '
                                 'r-1loqt21 r-1wbh5a2 r-dnmrzs r-1ny4l3l')
        authors = []
        for i in posts_raw:
            authors.append(i.getText())
            for i in range(len(authors)):
                if i % 2 != 0:
                    k = i
                    n = i - 1
                    self.authors_dict[authors[k]] = authors[n]
        return self.authors_dict

    def get_tweet_soup(self) -> BeautifulSoup:
        """Обрабатывает текущий html-код страницы.
        Возвращает Soup страницы со списком постов с загруженной страницы.
        """
        console_log.info('Собираю информацию о твитах')

        page_code = self.driver.page_source
        soup = BeautifulSoup(page_code, "lxml")
        tweets_raw = soup.find_all('div', class_=self.post_class_id)

        return tweets_raw

    def prepare_imgs_and_save(self, tweet_data: dict) -> int:
        """Сохраняет изображения из поста в соответствующую папку.
        """
        tag_dir = tweet_data['tag_dir']
        img_links = tweet_data['img_links']
        prefix = None

        if tweet_data['author'] in ART_CHANNELS:
            prefix = tweet_data['tag_dir']
            tag_dir = 'Misc_art'

        self.make_dirs(alpha_dir=TWEET_DIR,
                       tag_category=tag_dir)

        counter = 0

        for img_link in img_links:
            filename = self.get_filename(link=img_link, prefix=prefix)
            save_path = os.path.join(TWEET_DIR, tag_dir,
                                     filename)
            self.save_file(img_link, save_path)
            file_log.info(f'Сохраняю файл {filename} в папку {tag_dir}')
            if self.check_saved_img(save_path):
                counter += 1

        return counter

    def scroll_twitter_page(self) -> None:
        """Scroll page all the way down
        ## NEED TO REWRITE
        """
        scroll_script = 'document.body.scrollHeight'
        self.driver.execute_script(f"window.scrollTo(0, {scroll_script});")

    def find_post_on_page(self, tweet_data: dict) -> None:
        """Переходит к следующему посту на странице
        """
        element = self.driver.find_element(
                     By.XPATH, f'//a[contains(@href, "{tweet_data["href"]}")]')
        self.actions.move_to_element(element).perform()
        self.random_wait(0, 2)

    def unbutton_favs(self, tweet_data: dict) -> bool:
        """Найти кнопку "Отменить ретвит и нажать её
        """
        # Определяем элемент, от которого будем отталкиваться
        xpath_href_locator = f'//*[@href="{tweet_data["href"]}"]'
        parent_xpath = (xpath_href_locator +
                        f'/ancestor::div[@class="{self.post_class_id}"]')
        # Ищем родительский элемент по классу
        parent_element = self.find_element_with_xpath(self.driver,
                                                      parent_xpath)
        # Ищем элемент потомок по атрибуту data-testid
        cancel_button = self.find_element_with_xpath(
                            parent_element, './/div[@data-testid="unretweet"]')

        try:
            self.actions.move_to_element(cancel_button).perform()
            cancel_button.click()
            self.wait(2)
        except ElementClickInterceptedException:
            return False
        else:
            confirm_button = self.driver.find_element(
                                            By.XPATH,
                                            "//div[@role='menuitem']")
            confirm_button.click()
            console_log.warning(
                f'Снимаю ретвит c поста №{tweet_data["tweet_num"]} '
                f'автора {tweet_data["author"]}')
            return True

    # def find_element_with_xpath(self, parent_webdriver, element_xpath: str):
    #     """Находит с помощью XPATH на странице элемент и возвращает его
    #     """
    #     element = parent_webdriver.find_element(By.XPATH, element_xpath)
    #     return element


class Tweet():
    def __init__(self,
                 tweet_raw_data,
                 authors_dict: dict,
                 session_num: int):
        self.db_tags_dict = authors_dict
        self.session_num = session_num
        self.tweet_text = None
        self.tweet_raw_data = tweet_raw_data
        self.img_class_id = ('css-4rbku5 css-18t94o4 css-1dbjc4n '
                             'r-1loqt21 r-1pi2tsx r-1ny4l3l')

    def analyze_tweet(self) -> dict:
        """Основная функция с логикой обработки поста"""

        self.tweet_text = self.get_tweet_text(self.tweet_raw_data)

        tweet_img_data = self.tweet_raw_data.find_all('a',
                                                      class_=self.img_class_id)

        if not tweet_img_data:
            return

        tweet_card = {}
        imgs_links_list = []
        for tweet in tweet_img_data:
            tweet_href = tweet.get('href')

            tweet_url = 'https://twitter.com' + tweet_href
            tweet_num = self.get_tweet_num(tweet_href)
            tweet_author = self.get_author_name(tweet_href)
            tweet_src_list = tweet.find_all('img', alt=True)

            for tweet_src_raw in tweet_src_list:
                img_link = tweet_src_raw.get('src')
            imgs_links_list.append(self.get_img_link(img_link))

        tweet_card = {
            'tweet_num': tweet_num,
            'tweet_url': tweet_url,
            'author': tweet_author,
            'img_links': imgs_links_list,
            'text': None,
            'tags': None,
            'tag_dir': None,
            'session_num': self.session_num,
        }

        if (twt_text := self.convert_tweet_text(
                                                self.tweet_text,
                                                tweet_card['author'])):
            tweet_card['text'] = twt_text

        if len(tags := self.get_tags(self.tweet_text)) > 0:
            tweet_card['tags'] = tags

        tweet_card['tag_dir'] = self.get_priority_tag(tweet_card)

        tweet_href_locator = ('/' + tweet_card['author'] + '/status/' +
                              tweet_card['tweet_num'] + '/photo/1')

        tweet_card['href'] = tweet_href_locator

        try:
            tweet_card['imgs_qty'] = len(imgs_links_list)
        except TypeError:
            tweet_card['imgs_qty'] = None

        return tweet_card

    def get_tweet_text(self, tweet_raw_data: str) -> str:
        """Вытаскивает из href имя автора твита
        """
        string = tweet_raw_data.find_all('div', id=True)[1].get_text()
        return string

    def get_author_name(self, string: str) -> str:
        """Вытаскивает из href имя автора твита
        """
        author_name = string[1: string.find('/', 1)]
        return author_name

    def get_img_link(self, string: str) -> str:
        s = string
        img_raw_link = s[: s.find('?format')]
        extension = s[(s.find('?format=') + 8):(s.find('&name'))]
        img_clean_link = img_raw_link + '.' + extension
        return img_clean_link

    def get_tweet_num(self, string: str) -> str:
        s = string
        tweet_num = s[s.find('status/') + 7: s.find('/photo')]
        return tweet_num

    def get_tags(self, string: str) -> list:
        tags = re.findall(r'#\w+', string)
        return tags

    def convert_tweet_text(self, string: str, channel: str) -> str:
        match channel:
            case 'VideoArtGame':
                try:
                    artist_name = string.split('Artist: ')[1].strip('@')
                    return artist_name
                except IndexError:
                    return 'comic_art'
            case 'cómics clásicos' | 'CoolComicArt' | 'thatsgoodweb':
                return 'comic_art'
            case ('lavidaenvinetas' | 'Dungeonlust' | 'SavageComics'):
                return self.clean_text(string)
            case 'Sentinelcreativ':
                result = re.sub(r'https?://\S+', '', string)
                return result.strip()
            case _:
                return None

    def get_priority_tag(self, tweet_card: dict) -> str:
        try:
            tag_dir = self.db_tags_dict[tweet_card['author']]
        except KeyError:
            tag_dir = tweet_card['author']
        else:
            if tweet_card['author'] in ART_CHANNELS:
                tag_dir = tweet_card['text']
        finally:
            return tag_dir

    def clean_text(self, string: str) -> str:
        return re.sub(r'\n@.*', '', string)

    def compare_tags(self, db_tags_dict: dict) -> dict:
        'Сompare list of tags from analyzed post with tags_DB'
        file_log.debug('Сравниваю тэги поста с базой.')
        post_tags_dict = {}
        for tag in self.post_tags_list:
            try:
                post_tags_dict[tag] = db_tags_dict[tag]
            except KeyError:
                continue
        return post_tags_dict


def main():
    pass


if __name__ == '__main__':
    main()
