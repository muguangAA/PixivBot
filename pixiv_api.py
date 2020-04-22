import os
import shutil
import threading
import time

from pixivpy3 import ByPassSniApi
from settings import settings

__back_api__ = None
__api_init_time__ = 0
__lock__ = threading.RLock()


def api():
    global __api_init_time__, __back_api__, __lock__
    if time.time() - __api_init_time__ <= 1800:
        return __back_api__

    __lock__.acquire()
    try:
        __back_api__ = ByPassSniApi()
        __back_api__.require_appapi_hosts()
        __back_api__.set_accept_language('zh-cn')
        __back_api__.login(settings["pixiv"]["username"], settings["pixiv"]["password"])
        __api_init_time__ = time.time()
    finally:
        __lock__.release()
    return __back_api__


def shuffle_illust(illusts):
    import random

    bookmarks = list(map(lambda illust: int(illust["total_bookmarks"]), illusts))
    sum_bm = sum(bookmarks)
    possibility = list(map(lambda x: x / sum_bm, bookmarks))
    for i in range(1, len(possibility)):
        possibility[i] = possibility[i] + possibility[i - 1]
    rand = random.random()
    for i in range(len(possibility)):
        if possibility[i] > rand:
            return illusts[i]
    return illusts[len(illusts) - 1]


def has_tag(illust, tag: str):
    tag = tag.lower()
    for x in illust["tags"]:
        tag_name: str = x["name"].lower()
        if tag in tag_name:
            return True
    return False


def download_illust(illust):
    import os

    download_dir: str = settings["illust"]["download_dir"]
    download_quantity: str = settings["illust"]["download_quantity"]
    download_replace: bool = settings["illust"]["download_replace"]
    domain = settings["illust"]["domain"]
    compress_oversize: bool = settings["illust"]["compress_oversize"]

    dirname = os.path.join(os.path.curdir, download_dir)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if download_quantity == "original":
        if len(illust["meta_pages"]) > 0:
            url: str = illust["meta_pages"][0]["image_urls"]["original"]
        else:
            url: str = illust["meta_single_page"]["original_image_url"]
    else:
        url: str = illust["image_urls"][download_quantity]

    filename = os.path.basename(url)
    fullpath = os.path.join(dirname, filename)

    if os.path.exists(fullpath):
        if download_replace:
            os.remove(fullpath)
        else:
            return fullpath

    if domain is not None:
        url = url.replace("i.pximg.net", domain)
        # r = requests.get(url, stream=True)
        # with open(fullpath, "wb") as f:
        #     for chunk in r.iter_content(chunk_size=32):
        #         f.write(chunk)
    api().download(url=url, path=dirname)

    if compress_oversize:
        compress_illust(fullpath)
    return fullpath


def compress_illust(fullpath):
    max_size: int = settings["illust"]["max_size"]

    from PIL import Image
    img = Image.open(fullpath)
    w, h = img.size
    if w > max_size or h > max_size:
        ratio = min(max_size/w, max_size/h)
        img_cp = img.resize((int(ratio*w),int(ratio*h)),Image.ANTIALIAS)
        img_cp.save(fullpath)


def illust_to_message(illust):
    from mirai import Plain, Image
    pattern: str = settings["illust"]["reply_pattern"]
    string = pattern.replace("$title", illust["title"]) \
        .replace("$tags", " ".join(map(lambda x: x["name"], illust["tags"]))) \
        .replace("$id", str(illust["id"]))
    message = [Plain(string)]

    if has_tag(illust, "R-18G") and settings["illust"]["r18g_img_escape"]:
        message.append(Plain(settings["illust"]["r18g_img_escape_message"]))
    elif has_tag(illust, "R-18") and settings["illust"]["r18_img_escape"]:
        message.append(Plain(settings["illust"]["r18_img_escape_message"]))
    else:
        filename = download_illust(illust)
        message.append(Image.fromFileSystem(filename))

    return message