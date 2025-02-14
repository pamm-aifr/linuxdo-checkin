import os
import random
import time

from loguru import logger
from playwright.sync_api import sync_playwright
from tabulate import tabulate

USERNAME = os.environ.get("LINUXDO_USERNAME")
PASSWORD = os.environ.get("LINUXDO_PASSWORD")

HOME_URL = "https://linux.do/"


class LinuxDoBrowser:
    def __init__(self) -> None:
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True, timeout=30000)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.target_count = 10  # 设置的目标量
        self.page.goto(HOME_URL)

    def login(self):
        logger.info("Login")
        self.page.click(".login-button .d-button-label")
        time.sleep(2)
        self.page.fill("#login-account-name", USERNAME)
        time.sleep(2)
        self.page.fill("#login-account-password", PASSWORD)
        time.sleep(2)
        self.page.click("#login-button")
        time.sleep(10)
        user_ele = self.page.query_selector("#current-user")
        if not user_ele:
            logger.error("Login failed")
            return False
        else:
            logger.info("Login success")
            return True

    def click_topic(self):
        # 首先滚动页面加载帖子
        topics = self.scroll_down_until_loaded()
        for topic in self.page.query_selector_all("#list-area .title"):
            logger.info("Click topic: " + topic.get_attribute("href"))
            page = self.context.new_page()
            page.goto(HOME_URL + topic.get_attribute("href"))
            time.sleep(random.uniform(2, 5))
            # if random.random() < 0.02:  # 100 * 0.02 * 30 = 60
            #     self.click_like(page)
            # time.sleep(3)
            page.close()

    def run(self):
        if not self.login():
            return
        self.click_topic()
        self.print_connect_info()

    def scroll_down_until_loaded(self):
        """滚动到页面底部，直到加载的帖子数量达到目标数量"""
        loaded_count = 0
        while loaded_count < self.target_count:
            # 获取当前加载的帖子数量
            loaded_topics = self.page.query_selector_all("#list-area .title")
            loaded_count = len(loaded_topics)
            
            if loaded_count >= self.target_count:
                break  # 达到目标数量，停止滚动

            # 滚动到底部触发加载新内容
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(2, 4))  # 随机等待时间

        return loaded_topics[:self.target_count]  # 返回目标数量的帖子
    
    def click_like(self, page):
        logger.info("Click like")
        page.locator(".discourse-reactions-reaction-button").first.click()
        logger.info("Like success")

    def print_connect_info(self):
        logger.info("Print connect info")
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


if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Please set USERNAME and PASSWORD")
        exit(1)
    l = LinuxDoBrowser()
    l.run()
