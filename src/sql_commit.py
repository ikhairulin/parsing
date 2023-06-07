import sqlite3
import json

import logging.config
import pickle

from settings import db_path, logger_config

logging.config.dictConfig(logger_config)

console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')


class SQLite():
    def __init__(self, path=db_path['auth']):
        self.path = path

    def __enter__(self):
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        return self.conn.cursor()

    def __exit__(self, type, value, traceback):
        self.conn.commit()
        self.conn.close()


class TableMaster():

    def __init__(self, domain):
        self.domain = domain.lower()
        self.db_auth_path = db_path['auth']
        self.db_excel_path = db_path['excel']
        self.db_log_path = db_path[domain]

    def create_joy_db(self):
        with SQLite(path=self.db_log_path) as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS data (
                post_id TEXT NOT NULL PRIMARY KEY,
                post_url TEXT NOT NULL,
                post_author TEXT,
                post_tags TEXT,
                imgs_qty INT,
                biggest_tag TEXT,
                tag_category TEXT,
                check_file BIT,
                unbutton BIT,
                session_num INT,
                session_date DATE DEFAULT CURRENT_DATE)
                ''')

    def create_tweet_db(self):
        with SQLite(path=self.db_log_path) as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS data (
                post_id INT NOT NULL PRIMARY KEY,
                post_url TEXT NOT NULL,
                post_author TEXT,
                post_tags TEXT,
                img_links TEXT,
                imgs_qty INT,
                tag_dir TEXT,
                check_file BIT,
                unbutton BIT,
                session_num INT,
                session_date DATE DEFAULT CURRENT_DATE)
                ''')

    def create_notion_db(self):
        with SQLite(path=self.db_log_path) as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS data (
                article_id TEXT NOT NULL PRIMARY KEY,
                article_url TEXT NOT NULL,
                article_domain TEXT,
                article_title TEXT,
                session_date DATE DEFAULT CURRENT_DATE)
                ''')

    def migrate_data(self) -> None:
        """Переносит данные из одной таблицы в другую
        """
        old_file_path = str(input('Input path to the old file...  '))
        with SQLite(path=old_file_path) as cur:
            cur.execute("""SELECT * FROM data""")
            with SQLite(path=self.db_log_path) as alter_cur:
                for i in cur:
                    alter_cur.execute("""INSERT INTO data
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                            i[0], i[1], i[2], i[3], i[4],
                            i[5], i[6], i[7], i[8], i[9], i[10]))

    def commit_joy_data(self, post_data: dict) -> None:
        """Принимает словарь с данными по постам с джоя,
           и заносит его в базу
        """
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""INSERT INTO data
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))""", (
                post_data['post_num'],
                post_data['post_url'],
                post_data['post_author'],
                json.dumps(post_data['post_tags'], ensure_ascii=False),
                post_data['imgs_qty'],
                post_data['biggest_tag'],
                post_data['tag_category'],
                post_data['check_file'],
                post_data['fav_button'],
                post_data['session_num'],
                ))

    def commit_tweet_data(self, post_data: dict) -> None:
        """Принимает словарь с данными по твитам,
           и заносит его в базу
       """
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""INSERT OR IGNORE INTO data
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))""", (
                post_data['tweet_num'],
                post_data['tweet_url'],
                post_data['author'],
                json.dumps(post_data['tags'], ensure_ascii=False),
                json.dumps(post_data['img_links'], ensure_ascii=False),
                post_data['imgs_qty'],
                post_data['tag_dir'],
                post_data['check_file'],
                post_data['fav_button'],
                post_data['session_num'],
                ))

    def commit_notion_data(self, article_data: dict) -> None:
        """Принимает словарь с данными,
           и заносит его в базу
       """
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""INSERT OR IGNORE INTO data
                VALUES (?, ?, ?, ?, DATE('now'))""", (
                article_data['article_id'],
                article_data['url'],
                article_data['domain'],
                article_data['title'],
                ))

    def get_session_num(self) -> int:
        '''Вытаскивает из базы номер сессии по порядку'''
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""SELECT COALESCE(MAX(session_num) + 1, 1)
                        FROM data
                        """)
            for i in cur:
                session_num = i[0]
            console_log.info(f'Номер текущей сессии {session_num}')
            return session_num

    def post_data_exists(self, column_name, data_id):
        """Проверяет есть ли запрашиваемый пост в базе"""
        with SQLite(path=self.db_log_path) as cur:
            info = cur.execute(f'SELECT * FROM data WHERE {column_name}=?',
                               (data_id, )).fetchone()
            if info is None:
                return False
            else:
                file_log.warning(f'Пост номер {data_id} уже есть в базе')
                return True

    def get_data_set(self, column_name: str) -> set:
        """
        Возвращает множество (set) значений из ячеек выбранной колонки
        """
        with SQLite(path=self.db_log_path) as cur:
            info = cur.execute(f'SELECT {column_name} FROM data',
                               ).fetchall()
            data_list = []
            for item in info:
                data_list.append(item[0])
            return set(data_list)

    def check_post_data(self, post_num: str) -> dict:
        '''Вытаскивает из базы данные поста'''
        with SQLite(path=self.db_log_path) as cur:
            post_log_data = {}
            cur.execute("""SELECT post_id, unbutton
                        FROM data WHERE post_id = ?
                        """, (post_num, ))
            for i in cur:
                post_log_data['post_num'] = i[0]
                post_log_data['unbutton'] = i[1]
            return post_log_data

    def get_joypost_img_links(self, post_num: str) -> dict:
        '''Вытаскивает из базы данные поста'''
        with SQLite(path=self.db_log_path) as cur:
            post_log_data = {}
            cur.execute("""SELECT post_id, img_links, tag_category
                        FROM data WHERE post_id = ?
                        """, (post_num, ))
            for i in cur:
                post_log_data['post_num'] = i[0]
                post_log_data['img_links'] = i[1][1:-1].split(',')
                post_log_data['tag_category'] = i[2]
            return post_log_data

    def extract_all_data(self) -> dict:
        '''Вытаскивает из базы данные поста'''
        with SQLite(path=self.db_log_path) as cur:
            post_log_data = {}
            cur.execute("""SELECT * FROM data""")
            for i in cur:
                post_log_data[i[0]] = i[1]
                print(i[0], i[1])
            return post_log_data

    def get_login_data(self, domain: str) -> dict:
        with SQLite(path=self.db_auth_path) as cur:
            cur.execute(f"""SELECT login, password, add_inf FROM auth_data
                        WHERE name = '{domain}'""")
            for i in cur:
                auth_data = {'login': i[0],
                             'password': i[1],
                             'add_inf': i[2]}
        return auth_data

    def commit_auth_data(self) -> None:
        """Пополняет базу паролей
        """
        with SQLite(path=self.db_auth_path) as cur:
            cur.execute("""INSERT INTO auth_data
                VALUES (?, ?, ?, ?, ?)""", (
                'notion',  # name
                'hn.so/',  # url
                'ikha',  # login
                '',  # password
                "st_",  # add_inf
                ))

    def update_data(self) -> None:
        """Пополняет базу паролей
        """
        with SQLite(path=self.db_auth_path) as cur:
            cur.execute("""UPDATE auth_data
               SET add_inf = ''
               WHERE name = 'twitter'
               """)

    def delete_table(self) -> None:
        """Удаляет таблицу"""
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""DROP TABLE IF EXISTS data2""")

    def add_column(self) -> None:
        """Добавляет в базу столбцы
        """
        with SQLite(path=self.db_auth_path) as cur:
            cur.execute("""ALTER TABLE auth_data
                ADD add_inf TEXT""")

    def delete_entries(self, column=None, value=None) -> None:
        # with SQLite(path=self.db_log_path) as cur:
        with SQLite(path=self.db_auth_path) as cur:
            query = f"DELETE FROM auth_data WHERE {column} = '{value}' "
            cur.execute(query)
            print(f"Запись {value} удалена")

    def change_table(self) -> None:
        with SQLite(path=self.db_log_path) as cur:
            cur.execute("""
            ALTER TABLE data2 RENAME TO data""")
            print("Задача выполнена")

    @staticmethod
    def dump_data_to_pickle(data) -> None:
        with open('data.pickle', 'wb') as f:
            pickle.dump(data, f)


def main():
    pass
    # t = TableMaster('joyreactor')
    # data = (t.extract_all_data())
    # t.dump_data_to_pickle(data)
    # t.create_joy_db()
    # t.migrate_data()
    # t.change_table()


if __name__ == '__main__':
    main()
