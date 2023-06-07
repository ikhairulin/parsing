"""Сохраняем страницы интернета в Notion"""

from httpx._exceptions import HTTPStatusError
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from httpcore import ReadTimeout
import logging.config

from sql_commit import TableMaster
from notion_libs import Notion_page, Article_parser
from settings import logger_config
from environ import CHROME_FAVS_PATH, debug_list

logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')

np = Notion_page()
t = TableMaster('notion')


def main():

    links_list = Article_parser.get_urls_by_bookmarks(CHROME_FAVS_PATH, 'mirf')
    console_log.info(f'Список ссылок содержит {len(links_list)} позиций')
    db_links_set = t.get_data_set('article_id')

    counter = 0

    for url in links_list:
        hash_url = Article_parser.hash_string(url)
        if hash_url in db_links_set:
            counter += 1
            continue
        elif url in debug_list:
            continue

        console_log.info(f'Из них уже есть в базе {counter} шт.')
        console_log.info(f'Обрабатываю страницу {url}')
        ap = Article_parser(url)

        blocks = ap.parsing_data()
        # pprint(blocks['header'])

        np.create_page(blocks['header'])

        for block in enumerate(blocks['body']):
            block_num, block_value = block
            blocks_qty = len(blocks["body"]) - 1

            try:
                np.match_block(block_value)
            except HTTPStatusError:
                np.match_block(block_value)
                console_log.info('HTTPStatusError')
            except HTTPResponseError:
                np.match_block(block_value)
                console_log.info('HTTPResponseError')
            except RequestTimeoutError:
                np.match_block(block_value)
                console_log.info('RequestTimeoutError')
            except TimeoutError:
                np.match_block(block_value)
                console_log.info('TimeoutError')
            except ReadTimeout:
                np.match_block(block_value)
                console_log.info('ReadTimeout')
            except ConnectionResetError:
                np.match_block(block_value)
                console_log.info('ConnectionResetError')

            finally:
                np.random_wait(0, 1)
                console_log.info(f'Блок {block_num} из {blocks_qty} '
                                 f'- {block_value}')

        if np.add_url_property(url):
            console_log.info('Success')
            t.commit_notion_data(blocks['header'])
            counter += 1

        counter = 1
        if counter == 1:
            break


if __name__ == "__main__":

    main()
