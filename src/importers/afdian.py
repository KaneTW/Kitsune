from ..internals.utils.download import download_file, DownloaderException
from ..lib.post import afdian_post_exists, handle_post_import, delete_post_flags
from ..lib.artist import delete_artist_cache_keys, update_artist
from ..lib.autoimport import encrypt_and_save_session_for_auto_import, kill_key
from ..internals.database.database import get_conn, get_raw_conn, return_conn
from ..internals.utils.proxy import get_proxy
from ..internals.utils.scrapper import create_scrapper_session
from ..internals.utils.logger import log
from ..internals.cache.redis import delete_keys
from setproctitle import setthreadtitle
import json
import config
from os.path import join, splitext
from random import randrange
import time
import uuid
import requests
import datetime
from random import random
import sys
sys.setrecursionlimit(100000)


userAgent = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) discord/0.0.269 Chrome/91.0.4472.164 Electron/13.6.6 Safari/537.36'


def test_key_for_auto_import(
    import_id,
    key,
    contributor_id,
    allowed_to_auto_import,
    key_id,
    proxies
):
    try:
        scraper = create_scrapper_session().get(
            'https://afdian.net/api/my/profile',
            cookies={'auth_token': key},
            headers={'user-agent': userAgent},
            proxies=proxies
        )
        data = scraper.json()
        scraper.raise_for_status()
    except requests.HTTPError as e:
        if (e.response.status_code == 401):
            if (key_id):
                kill_key(key_id)
        return

    if data['ec'] != 200:
        log(import_id, f"Failed to add afdian key, ec {data['ec']}")


    if (allowed_to_auto_import):
        try:
            encrypt_and_save_session_for_auto_import(
                'afdian',
                key,
                contributor_id=contributor_id,
            )
            log(import_id, 'Your key was successfully enrolled in auto-import!', to_client=True)
        except:
            log(import_id, 'An error occured while saving your key for auto-import.', 'exception')


def import_subscribers(import_id, key, proxies):
    try:
        scraper = create_scrapper_session().get(
            f'https://afdian.net/api/my/sponsoring?need_sponsor_info=1',
            cookies={'auth_token': key},
            headers={'user-agent': userAgent},
            proxies=proxies
        )
        subscriber_data = scraper.json()
        scraper.raise_for_status()
    except requests.HTTPError:
        log(import_id, f"Status code {scraper.status_code} when contacting Afdian API.", 'exception')
        return
    except Exception:
        log(import_id, 'Error connecting to cloudscraper. Please try again.', 'exception')
        return

    if subscriber_data['ec'] != 200:
        log(import_id, f"ec {subscriber_data['ec']} when importing Afdian subscribers", 'exception')
        return

    for subscriber in subscriber_data['data']['sponsoring']:
        process_subscriber(subscriber['user']['user_id'], import_id, key, proxies)



def process_subscriber(user_id, import_id, key, proxies, before=None):
    log(import_id, f'Starting importing {user_id}', to_client=True)

    try:
        scraper = create_scrapper_session().get(
            'https://afdian.net/api/post/get-list?user_id=' +
            user_id +
            '&type=old' +
            (('&publish_sn=' + str(before)) if before is not None else '') +
            '&per_page=10&group_id=&all=1&is_public=&plan_id=&title=&name=',
            headers={'user-agent': userAgent},
            cookies={'auth_token': key},
            proxies=proxies
        )
        scraper_data = scraper.json()
        scraper.raise_for_status()
    except requests.HTTPError:
        log(import_id, f"Status code {scraper.status_code} when contacting Afdian API.", 'exception')
        return False
    except Exception:
        log(import_id, 'Error connecting to cloudscraper. Please try again.', 'exception')
        return False

    if scraper_data['ec'] != 200:
        log(import_id, f"ec {scraper_data['ec']} when importing Afdian subscriber {user_id}", 'exception')
        return False

    while True:
        for post in scraper_data['data']['list']:
            try:
                post_id = post['post_id']

                log(import_id, f"Starting import: {post_id} from user {user_id}")


                post_model = {
                    'id': post_id,
                    '"user"': user_id,
                    'service': 'afdian',
                    'title': post['title'],
                    'content': post['content'],
                    'embed': {},
                    'shared_file': False,
                    'added': datetime.datetime.now(),
                    'published': datetime.datetime.fromtimestamp(post['publish_time']),
                    'file': {},
                    'attachments': []
                }


                if('pics' in post and len(post['pics']) > 0):
                    for pic in post['pics']:
                        reported_filename, hash_filename, _ = download_file(
                            pic,
                            'afdian',
                            user_id,
                            post_id,
                        )
                        post_model['attachments'].append({
                            'name': reported_filename,
                            'path': hash_filename
                        })

                handle_post_import(post_model)
                delete_post_flags('afdian', user_id, post_id)


                log(import_id, f"Finished importing {post_id} from user {user_id}", to_client=False)
            except:
                log(import_id, f"Error while importing {post_id} from user {user_id}", 'exception', True)
                continue

        if scraper_data['data']['has_more']:
            before = scraper_data['data']['list'][-1]['publish_sn']
            time.sleep(randrange(500, 1250) / 1000)
            try:
                scraper = create_scrapper_session().get(
                        'https://afdian.net/api/post/get-list?user_id=' +
                        user_id +
                        '&type=old' +
                        (('&publish_sn=' + str(before)) if before is not None else '') +
                        '&per_page=10&group_id=&all=1&is_public=&plan_id=&title=&name=',
                        headers={'user-agent': userAgent},
                        cookies={'auth_token': key},
                        proxies=proxies
                )
                scraper_data = scraper.json()
                scraper.raise_for_status()
            except requests.HTTPError:
                log(import_id, f"Status code {scraper.status_code} when contacting Afdian API.", 'exception')
                return False
            except Exception:
                log(import_id, 'Error connecting to cloudscraper. Please try again.', 'exception')
                return False
            if scraper_data['ec'] != 200:
                log(import_id, f"ec {scraper_data['ec']} when importing Afdian subscriber {user_id}", 'exception')
                return False
        else:
            log(import_id, "Finished scanning for posts.")
            delete_artist_cache_keys('afdian', user_id)
            update_artist('afdian', user_id)

            return True


def import_posts(import_id, key, contributor_id, allowed_to_auto_import, key_id):
    setthreadtitle(f'KI{import_id}')
    while True:
        proxies = get_proxy()
        try:
            requests.get('https://google.com', proxies=proxies, timeout=10)
            break
        except requests.ConnectionError:
            try:
                config.proxies.remove(proxies['http'])
            except ValueError:
                pass
            proxies = get_proxy()

    test_key_for_auto_import(import_id, key, contributor_id, allowed_to_auto_import, key_id, proxies)
    import_subscribers(import_id, key, proxies)

