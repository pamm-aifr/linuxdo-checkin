"""
cron: 0 */6 * * *
new Env("Linux.Do 签到")
"""
import os
import random
import time
import functools
import sys
import requests
from loguru import logger
from playwright.sync_api import sync_playwright
from tabulate import tabulate


def retry_decorator(retries=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:  # 最后一次尝试
                        logger.error(f"函数 {func.__name__} 最终执行失败: {str(e)}")
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1}/{retries} 次尝试失败: {str(e)}")
                    time.sleep(1)
            return None

        return wrapper

    return decorator


os.environ.pop("DISPLAY", None)
os.environ.pop("DYLD_LIBRARY_PATH", None)

USERNAME = os.environ.get("LINUXDO_USERNAME")
PASSWORD = os.environ.get("LINUXDO_PASSWORD")
if not USERNAME:
    USERNAME = os.environ.get('USERNAME')
if not PASSWORD:
    PASSWORD = os.environ.get('PASSWORD')
GOTIFY_URL = os.environ.get("GOTIFY_URL")  # 新增环境变量
GOTIFY_TOKEN = os.environ.get("GOTIFY_TOKEN")  # 新增环境变量

HOME_URL = "https://linux.do/"
LOGIN_URL = "https://linux.do/login"
TARGET_TOPIC_COUNT = 3000


class LinuxDoBrowser:
    def __init__(self) -> None:
        self.pw = sync_playwright().start()
        self.browser = self.pw.firefox.launch(headless=True, timeout=30000)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(HOME_URL)
        self.browsed_topic_count = 0

    def login(self):
        logger.info("开始登录")
        # self.page.click(".login-button .d-button-label")
        self.page.goto(LOGIN_URL)
        time.sleep(2)
        self.page.fill("#login-account-name", USERNAME)
        time.sleep(2)
        self.page.fill("#login-account-password", PASSWORD)
        time.sleep(2)
        self.page.click("#login-button")
        time.sleep(10)
        user_ele = self.page.query_selector("#current-user")
        if not user_ele:
            logger.error("登录失败")
            return False
        else:
            logger.info("登录成功")
            return True

    # def click_topic(self):
    #     topic_list = self.page.query_selector_all("#list-area .title")
    #     logger.info(f"发现 {len(topic_list)} 个主题帖")
    #     for topic in topic_list:
    #         self.click_one_topic(topic.get_attribute("href"))

    def click_topic(self):
        while self.browsed_topic_count < TARGET_TOPIC_COUNT:
            topic_list = self.page.query_selector_all("#list-area .title")
            topic_count = len(topic_list)
            logger.info(f"发现 {topic_count} 个主题帖, 当前浏览了 {self.browsed_topic_count}/{TARGET_TOPIC_COUNT}")
            if topic_count == 0:
                logger.warning("未发现任何主题帖，刷新页面")
                self.page.reload()
                time.sleep(5) # 等待页面加载
                continue

            if topic_count < TARGET_TOPIC_COUNT:
                logger.info("当前页面主题不足, 向下滚动页面...")
                self.scroll_down()
                time.sleep(5) # 等待页面加载
                continue
                
            for topic in topic_list:
                if self.browsed_topic_count >= TARGET_TOPIC_COUNT:
                    logger.info(f"已达到目标主题数量 {TARGET_TOPIC_COUNT}, 停止浏览")
                    break
                self.click_one_topic(topic.get_attribute("href"))
                self.browsed_topic_count += 1


    def scroll_down(self):
        """向下滚动页面加载更多主题"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        logger.info("已滚动到页面底部")
        
    @retry_decorator()
    def click_one_topic(self, topic_url):
        page = self.context.new_page()
        page.goto(HOME_URL + topic_url)
        if random.random() < 0.3:  # 0.3 * 30 = 9
            self.click_like(page)
        self.browse_post(page)
        page.close()

    def browse_post(self, page):
        prev_url = None
        # 开始自动滚动，最多滚动2次
        for _ in range(2):
            # 随机滚动一段距离
            scroll_distance = random.randint(550, 650)  # 随机滚动 550-650 像素
            logger.info(f"向下滚动 {scroll_distance} 像素...")
            page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            logger.info(f"已加载页面: {page.url}")

            if random.random() < 0.03:  # 33 * 4 = 132
                logger.success("随机退出浏览")
                break

            # 检查是否到达页面底部
            at_bottom = page.evaluate("window.scrollY + window.innerHeight >= document.body.scrollHeight")
            current_url = page.url
            if current_url != prev_url:
                prev_url = current_url
            elif at_bottom and prev_url == current_url:
                logger.success("已到达页面底部，退出浏览")
                break

            # 动态随机等待
            wait_time = random.uniform(2, 4)  # 随机等待 2-4 秒
            logger.info(f"等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)

    def run(self):
        if not self.login():
            logger.error("登录失败，程序终止")
            sys.exit(1)  # 使用非零退出码终止整个程序
        self.click_topic()
        self.print_connect_info()
        self.send_gotify_notification()

    def click_like(self, page):
        try:
            # 专门查找未点赞的按钮
            like_button = page.locator('.discourse-reactions-reaction-button[title="点赞此帖子"]').first
            if like_button:
                logger.info("找到未点赞的帖子，准备点赞")
                like_button.click()
                logger.info("点赞成功")
                time.sleep(random.uniform(1, 2))
            else:
                logger.info("帖子可能已经点过赞了")
        except Exception as e:
            logger.error(f"点赞失败: {str(e)}")

    def print_connect_info(self):
        logger.info("获取连接信息")
        page = self.context.new_page()
        page.goto("https://connect.linux.do/")
        rows = page.query_selector_all("table tr")

        info = []

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                project = cells[0].text_content().strip()
                current = cells[1].text_content().strip()
                requirement = cells[2].text_content().strip()
                info.append([project, current, requirement])

        print("--------------Connect Info-----------------")
        print(tabulate(info, headers=["项目", "当前", "要求"], tablefmt="pretty"))

        page.close()

    def send_gotify_notification(self):
        """发送消息到Gotify"""
        if GOTIFY_URL and GOTIFY_TOKEN:
            try:
                response = requests.post(
                    f"{GOTIFY_URL}/message",
                    params={"token": GOTIFY_TOKEN},
                    json={
                        "title": "LINUX DO",
                        "message": f"✅每日签到成功完成",
                        "priority": 1
                    },
                    timeout=10
                )
                response.raise_for_status()
                logger.success("消息已推送至Gotify")
            except Exception as e:
                logger.error(f"Gotify推送失败: {str(e)}")
        else:
            logger.info("未配置Gotify环境变量，跳过通知发送")


if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Please set USERNAME and PASSWORD")
        exit(1)
    l = LinuxDoBrowser()
    l.run()
