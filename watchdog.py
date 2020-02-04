from urllib.request import urlopen
import pandas as pd
import time
import logging, argparse
import threading
import copy
import signal, sys

from bs4 import BeautifulSoup
import multiprocessing
from multiprocessing.managers import BaseManager
from win10toast import ToastNotifier
from queue import LifoQueue

logger = logging.getLogger("global")
formatter = logging.Formatter('[%(asctime)s.%(msecs)03d][%(levelname)s:%(lineno)s] %(message)s',
                              datefmt='%y-%m-%d %H:%M:%S')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.setLevel(level=logging.INFO)
logger.addHandler(stream_handler)

runnable = True


class data_manager(BaseManager):
    pass


def load_board_contents(url, queue):
    html = urlopen(url)
    bs = BeautifulSoup(html, "html.parser")

    columns = bs.select('.board-list-table > thead > tr > th')
    columns = [column.text for column in columns]

    data = []
    entries = bs.select('.board-list-table > tbody > tr')[1:]
    for entry in entries:
        contents = entry.select('td')
        contents = [content.text.strip() for content in contents]
        data.append(contents)
    table = pd.DataFrame(data, columns=columns)
    logger.info("Successful get data from URL")
    queue.put(table.iloc[0])


# For multiprocessing
def load_board_helper(args):
    load_board_contents(args[0], args[1])


def request_loop(url, lifo_queue, sec=1.0):
    global runnable
    args = (url, lifo_queue)

    while runnable:
        load_board_helper(args)
        time.sleep(sec)


request_loop_thread = None
manager = None


def signal_handler(sig, frame):
    global request_loop_thread, manager, runnable

    logger.info("Ctrl+C pressed")
    if request_loop_thread is not None:
        runnable = False
        request_loop_thread.join()
    if manager is not None:
        manager.shutdown()
    sys.exit(0)


if __name__ == '__main__':

    multiprocessing.freeze_support()

    signal.signal(signal.SIGINT, signal_handler)

    logger.info("~~~ Watchdog(ver 0.1) ~~~")
    logger.info("* 개발자: BlaCkinkGJ")
    logger.info("* 버그 리포트: ss5kijun@gmail.com")

    URL = "https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN096"
    POINT = '제목'
    SECONDS = 1.0

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', metavar='<connect URL>', type=str, help="URL을 설정해주십시오.[기본값: 부산대 자유게시판]")
    parser.add_argument('-p', '--point', metavar='<column point>', type=str, help="출력하고자는 열 이름을 적으시오.[기본값: 제목]")
    parser.add_argument('-t', '--time', metavar='<time(seconds)>', type=float, help="출력 주기(초 단위)를 설정하시오.[기본값: 1.0]")

    args = parser.parse_args()

    if args.url is not None:
        URL = args.url
    if args.point is not None:
        POINT = args.point
    if args.time is not None:
        SECONDS = args.time

    logger.info("설정된 URL: {}".format(URL))
    logger.info("설정된 출력열: {}".format(POINT))
    logger.info("설정된 시간: {}초".format(SECONDS))

    data_manager.register('LifoQueue', LifoQueue)

    manager = data_manager()
    manager.start()

    lifo_queue = manager.LifoQueue()

    request_loop_thread = threading.Thread(target=request_loop, args=(URL, lifo_queue, SECONDS))
    request_loop_thread.start()

    toaster = ToastNotifier()

    prev_data = None

    while True:
        if lifo_queue.empty():
            time.sleep(0.1)
        else:
            data = lifo_queue.get()
            logger.info("===Receive Data===\n{}".format(data))
            logger.info("===Previous Data===\n{}".format(prev_data))
            logger.info("Updated State ==> {}".format(str(data) != str(prev_data)))
            if prev_data is not None and str(prev_data) != str(data):
                toaster.show_toast("URL WatchDog", "{}".format(data[POINT]), icon_path="python.ico")
                prev_data = copy.deepcopy(data)
            if prev_data is None:
                prev_data = copy.deepcopy(data)
