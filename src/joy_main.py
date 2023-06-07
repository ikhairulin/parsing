"""Парсинг картинок и фотографий с сайта https://joyreactor.cc/"""
import logging.config

from sql_commit import TableMaster
from exceldb import ExcelMaster
from joy_libs import JoyMaster, JoyPost
from settings import logger_config

START_URL = 'https://joyreactor.cc/'

logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')

joy = JoyMaster()
table = TableMaster('joyreactor')
xl = ExcelMaster()


def start_session() -> None:
    joy.open_page(START_URL)
    joy.authorization()
    joy.open_page(joy.fav_url)


def error_checking(posts_list, post_soup, db_tags_dict, session_num, counters):

    counter = 0
    debug_list = counters.get('debug_list')

    saved_data = table.get_data_set('post_id')

    for post_num in posts_list:
        counters['all'] += 1

        if post_num in debug_list:
            continue

        if post_num in saved_data:
            counter += 1
            counters['db_counter'] += 1

            fav_flag = table.check_post_data(post_num)
            if fav_flag['unbutton'] == 1:
                joy.unbutton_favs(post_num)
            else:
                continue

        else:
            joy.find_post_on_page(post_num)
            post = JoyPost(post_num,
                           post_soup,
                           db_tags_dict,
                           session_num,
                           )
            post_data: dict = post.analyze_post()

            try:
                if len(post_data['message']):
                    # Если возникли ошибки в результате анализа поста
                    debug_list.append(post_num)
                    joy.collect_wrong_post_links(post_data)
                    table.commit_joy_data(post_data)
                    counters['error_counter'] += 1
                    continue

                if joy.prepare_imgs_and_save(post_data) == len(
                            post_data['img_links']):
                    joy.unbutton_favs(post_num)
                    post_data['check_file'] = 1
                    post_data['fav_button'] = 1
                    counter -= 1

                else:
                    post_data['message'] = 'Изображения не прошли проверку'
                    debug_list.append(post_num)
                    joy.collect_wrong_post_links(post_data)

            except UnboundLocalError:
                counters['error_counter'] += 1
                continue

            table.commit_joy_data(post_data)

    if counter != len(posts_list):
        console_log.info(f'На странице {len(posts_list)} постов '
                         f'из них в базе {counters["db_counter"]}')
        joy.refresh_page()
    else:
        joy.click_button_by_class_name(button_value='next')

    return counters


def main():

    start_session()

    counters = {'all': 0, 'error_counter': 0,
                'db_counter': 0, 'debug_list': []}

    db_tags_dict = xl.load_excel_tags_database()

    session_num = table.get_session_num()

    while joy.check_elem_exists_by_css_selector('a.next'):
        posts_raw_data = joy.get_posts_list()

        counters = error_checking(posts_raw_data['posts_list'],
                                  posts_raw_data['soup'],
                                  db_tags_dict,
                                  session_num,
                                  counters)

    console_log.info('\nПрограмма завершила свою работу. \n'
                     f'Обработано {counters["all"]} постов. \n'
                     f'В том числе {counters["db_counter"]} уже есть в базе '
                     f'и {counters["error_counter"]} пропущено из-за ошибок')


if __name__ == "__main__":

    main()
