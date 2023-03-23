from src.internals.database import database
from src.internals.cache import redis
from src.internals.database.database import get_cursor, get_conn, return_conn, get_raw_conn
from src.internals.utils.utils import get_hash_of_file
from src.internals.utils.download import perform_copy, make_thumbnail
from src.lib.files import write_file_log


import shutil
import config
import subprocess
import os
import os.path
import tempfile
import magic
import mimetypes
import pathlib
import datetime
import re

database.init()
redis.init()


conn = get_raw_conn()

cursor = conn.cursor()
cursor.execute("SELECT DISTINCT id, content_urls.user, service, url FROM content_urls EXCEPT SELECT post, fpr.user, service, remote_path as url FROM file_post_relationships as fpr, file_server_relationships as fsr WHERE fpr.file_id=fsr.file_id;")

result = cursor.fetchall()
cursor.close()
conn.commit()

for row in result:
    if 'mega.nz' not in row['url']:
        continue
    print(f"Processing {row}")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM file_server_relationships WHERE remote_path=%s;", [row['url']])
    matches = cursor.fetchall()
    cursor.close()
    conn.commit()

    if len(matches) > 0:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO file_post_relationships (file_id, filename, service, \"user\", post, contributor_id, inline) SELECT %(file_id)s, filename, %(service)s, %(user)s, %(post)s, contributor_id, inline FROM file_post_relationships WHERE file_id=%(file_id) LIMIT 1;"
                , {'file_id': matches[0]['file_id'], 'service': row['service'], 'user': row['user'], 'post': row['id']})
        cursor.close()
        conn.commit()
        print(f"Wrote duplicate file_id {matches[0]['file_id']} for {row['service']}/{row['user']}/{row['id']}")


    path = tempfile.mkdtemp()
    if 'mega.nz' in row['url']:
        subprocess.run(["mega-get", row['url'], path]).check_returncode()

    for file in os.listdir(path):
        file_hash = get_hash_of_file(os.path.join(path, file))
        fname = pathlib.Path(os.path.join(path, file))
        mtime = datetime.datetime.fromtimestamp(fname.stat().st_mtime)
        ctime = datetime.datetime.fromtimestamp(fname.stat().st_ctime)
        mime = magic.from_file(os.path.join(path, file), mime=True)
        extension = re.sub('^.jpe$', '.jpg', mimetypes.guess_extension(mime or  'application/octet-stream', strict=False) or '.bin')
        if extension == '.bin':
            print("Fucked up ", row)
        hash_filename = os.path.join(file_hash[0:2], file_hash[2:4], file_hash + extension)


        write_file_log(
            file_hash,
            mtime,
            ctime,
            mime,
            extension,
            file,
            row['service'],
            row['user'],
            row['id'],
            False,
            row['url'],
            fname.stat().st_size
            )
        perform_copy(
            str(fname),
            os.path.join(config.data_download_path, 'data', hash_filename))
        make_thumbnail(str(fname), os.path.join('data', hash_filename))
    shutil.rmtree(path)
    print(f"Fetched {row['url']}")









