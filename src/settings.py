import os
from collections import defaultdict

from environ import PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS
# from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sites = {
    'dtf.ru': {
        'search_tag': 'class',
        'class': "l-entry__content",
        'src': 'data-image-src',
        'img_search_list': ['div', 'img'],
        'db_id': 'ff910737baa74f5099b1f788bb4ce87c',
        'min_img_size': 0,
        'extract_title_pattern': r'(.*?)[—].*',
        'video_class': 'andropov_video',
        'video_src': 'data-video-mp4',
        },
    'pikabu.ru': {
        'search_tag': 'class',
        'class': "page-story__story",
        'src': 'data-src',
        'img_search_list': ['img'],
        'db_id': '60a83bb7b7114da38baf329789e3cd06',
        'min_img_size': 0,
        },
    'stopgame.ru': {
        'search_tag': 'class',
        # 'class': "_content_1dglt_8",
        # 'class': "_content_9gj8w_8",
        # 'class': "_content_1a9w5_8",
        'class': "_content_15hl6_8",
        'src': 'src',
        'img_search_list': ['img'],
        'tag_search': '_tags__wrapper_9gj8w_1',
        'db_id': 'ff910737baa74f5099b1f788bb4ce87c',
        'min_img_size': 0,
        'extract_title_pattern': r'^(.*?)\s*\|\s*[^\s]*$',
         },
    'lurkmore.wtf': {
        'search_tag': 'class',
        'class': "mw-parser-output",
        'src': 'src',
        'prefix': 'https://lurkmore.wtf',
        'img_search_list': ['img'],
        'exception_class': 'navigation',
        'db_id': 'ff910737baa74f5099b1f788bb4ce87c',
        'min_img_size': 0,
        },
    'habr.com': {
        'search_tag': 'class',
        'class': "tm-article-presenter__content",
        'src': 'data-src',
        'img_search_list': ['img'],
        'db_id': '7413f327360d4889851900dad5535076',
        'min_img_size': 0,
        },
    'rpgnuke.ru': {
        'search_tag': 'class',
        'class': "article-inner",
        'src': 'data-src',
        'img_search_list': ['img'],
        'db_id': 'ff910737baa74f5099b1f788bb4ce87c',
        'min_img_size': 0,
        },
    'dragonlance.ru': {

    },
    'mirf.ru': {
        'search_tag': 'class',
        'id': 'wtr-content',
        'class': 'content',
        'src': 'src',
        'prefix': 'https://www.mirf.ru/',
        'img_search_list': ['img'],
        'db_id': 'ff910737baa74f5099b1f788bb4ce87c',
        'min_img_size': 10 * 1024,
        'extract_title_pattern': r'(.+?)\s*\|.+',
        },
    'fallout.ru': {
        'search_tag': 'width',
        'width': "720",
        'src': 'src',
        'prefix': 'http://www.fallout.ru',
        'min_img_size': 0,
    },
    'igromania.ru': {
        'search_tag': 'class',
        'class': 'universal_content clearfix',
        'src': 'src',
        'prefix': '',
        'min_img_size': 0,
    },
    'pbs.twimg.com': defaultdict(str, {})
    }

db_path = {
           'auth': os.path.join(BASE_DIR, 'db', 'auth_data.db'),
           'joyreactor': os.path.join(BASE_DIR, 'db', 'joy_log.db'),
           'twitter':  os.path.join(BASE_DIR, 'db', 'tweet_log.db'),
           'notion': os.path.join(BASE_DIR, 'db', 'notion_log.db'),
           'excel': os.path.join(BASE_DIR, 'db', 'joy_tags.xlsx'),
           'no_db': '',
           }


user_agent = ('Mozilla/5.0 (Windows NT 6.1; WOW64)'
              'AppleWebKit/537.36 (KHTML, like Gecko)'
              'Chrome/110.0.0.0 Safari/537.36')

logger_config = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'std_format': {
            'format': ('{levelname} {asctime}. Функция {funcName}(). '
                       'строка {lineno} -> {message}'),
            'datefmt': '%Y-%m-%d %H:%M',
            'style': '{',
        },
        'console_format': {
            'format': ('{levelname} - Функция {funcName}(). '
                       'строка {lineno} -> {message}'),
            'style': '{',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'console_format'
        },
        'text_file': {
            'class': 'logging.FileHandler',
            # 'class': 'logging.RotatingFileHandler',
            'level': 'DEBUG',
            'filename': 'text_log.log',
            'encoding': 'UTF-8',
            'mode': 'a',
            'formatter': 'std_format',
            # 'maxBytes': '1*1024*1024',
        }
                 },
    'loggers': {
        'console_log': {
            'level': 'DEBUG',
            'handlers': ['console', 'text_file']
            # 'propagate': False
        },
        'file_log': {
            'level': 'DEBUG',
            'handlers': ['text_file']

        }

    }}


proxy_settings = {
    'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}'
}

manifest_json = """
{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Chrome Proxy",
    "permissions": [
        "proxy",
        "tabs",
        "unlimitedStorage",
        "storage",
        "<all_urls>",
        "webRequest",
        "webRequestBlocking"
    ],
    "background": {
        "scripts": ["background.js"]
    },
    "minimum_chrome_version":"76.0.0"
}
"""

background_js = """
let config = {
        mode: "fixed_servers",
        rules: {
        singleProxy: {
            scheme: "http",
            host: "%s",
            port: parseInt(%s)
        },
        bypassList: ["localhost"]
        }
    };
chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
function callbackFn(details) {
    return {
        authCredentials: {
            username: "%s",
            password: "%s"
        }
    };
}
chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {urls: ["<all_urls>"]},
            ['blocking']
);
""" % (PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)
