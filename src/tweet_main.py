"""Парсинг изображений из моего избранного с сайта https://twitter.com/"""
import logging.config

from sql_commit import TableMaster
from exceldb import ExcelMaster
from tweet_libs import TweetMaster, Tweet
from settings import logger_config


logging.config.dictConfig(logger_config)
console_log = logging.getLogger('console_log')
file_log = logging.getLogger('file_log')


tweet = TweetMaster()
db = TableMaster('twitter')
xl = ExcelMaster()


def main():

    session_num = db.get_session_num()

    authors_dict = xl.load_twitter_authors_database()

    tweet.authorization()

    tweet.random_wait(2, 3)
    tweet.open_page(tweet.fav_url)
    tweet.wait(5)
    tweet.scroll_twitter_page()

    while not tweet.check_elem_exists_by_css_selector(
                    'div.css-1dbjc4n r-o52ifk'):

        tweets_raw = tweet.get_tweet_soup()
        for tweet_raw_data in tweets_raw:
            # if not tweet_raw_data:
            #     continue
            p = Tweet(tweet_raw_data,
                      authors_dict,
                      session_num,
                      )

            tweet_data = p.analyze_tweet()
            if not tweet_data:
                continue

            if db.post_data_exists(tweet_data['tweet_num']):
                continue

            tweet.find_post_on_page(tweet_data)

            if tweet.prepare_imgs_and_save(
                            tweet_data) == len(tweet_data['img_links']):
                if not tweet.unbutton_favs(tweet_data):
                    continue
                else:
                    tweet_data['check_file'] = 1
                    tweet_data['fav_button'] = 1

                    db.commit_tweet_data(tweet_data)


if __name__ == "__main__":

    try:
        main()

    finally:
        tweet.exit()
