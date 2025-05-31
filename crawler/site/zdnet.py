from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

from config import settings
from urllib.parse import urlparse
import json, time, os, platform, re, logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.crawling_manager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "ZDNET"
URL = "https://zdnet.co.kr/{catCd}"
VIEW_URL = "https://blog.daehong.com/{id}"
TARGET_LIST = [
    # {"catCd": "news/?lstcode=0000", "catNm": "뉴스 최신뉴스"},
    {"catCd": "news/?lstcode=0010", "catNm": "뉴스 방송/통신"},
    {"catCd": "news/?lstcode=0020", "catNm": "뉴스 컴퓨팅"},
    {"catCd": "news/?lstcode=0030", "catNm": "뉴스 홈&모바일"},
    {"catCd": "news/?lstcode=0040", "catNm": "뉴스 인터넷"},
    {"catCd": "news/?lstcode=0050", "catNm": "뉴스 반도체/디스플레이"},
    {"catCd": "news/?lstcode=0057", "catNm": "뉴스 카테크"},
    {"catCd": "news/?lstcode=0058", "catNm": "뉴스 헬스케어"},
    {"catCd": "news/?lstcode=0060", "catNm": "뉴스 게임"},
    {"catCd": "news/?lstcode=0045", "catNm": "뉴스 중기&스타트업"},
    {"catCd": "news/?lstcode=0055", "catNm": "뉴스 유통"},
    {"catCd": "news/?lstcode=0073", "catNm": "뉴스 금융"},
    {"catCd": "news/?lstcode=0070", "catNm": "뉴스 과학"},
    {"catCd": "news/?lstcode=0075", "catNm": "뉴스 디지털경제"},
    {"catCd": "news/?lstcode=0110", "catNm": "뉴스 취업/HR/교육"},
    {"catCd": "news/?lstcode=0100", "catNm": "뉴스 인터뷰"},
    {"catCd": "news/?lstcode=0090", "catNm": "뉴스 인사/부음"},
    {"catCd": "news/?lstcode=0120", "catNm": "뉴스 글로벌뉴스"},
    {"catCd": "special/launch_special_25th.php", "catNm": "창간특집", "pagePass": "Y"},
    {"catCd": "newskey/?lstcode=인공지능", "catNm": "인공지능"},
    {"catCd": "newskey/?lstcode=배터리", "catNm": "배터리"},
    {"catCd": "column/?lstcode=0100", "catNm": "칼럼/연재 전문가 칼럼"},
    {"catCd": "column/?lstcode=0200", "catNm": "칼럼/연재 데스크 칼럼"},
    {"catCd": "column/?lstcode=0300", "catNm": "칼럼/연재 기자 수첩"},
    {"catCd": "column/?lstcode=0400", "catNm": "칼럼/연재 기자 연재"},
    {"catCd": "photo/", "catNm": "포토/영상"},
]


def crawling(driver: CrawlingManager):

    limiter = ResultLimiter()
    for target in TARGET_LIST:
        logger.debug(f"{target['catNm']} 진행 시작")
        is_loop = True
        page_num = 0
        while is_loop:
            page_num += 1
            logger.debug(f"{target['catNm']} / {page_num} 진행 시작")
            if target.get("pagePass", "N") == "Y":
                full_url = URL.format(catCd=target["catCd"])
                is_loop = False
            else:
                base_url = target["catCd"]
                page_param = (
                    f"&page={page_num}" if "?" in base_url else f"?page={page_num}"
                )
                full_url = URL.format(catCd=base_url + page_param)
            logger.debug(full_url)
            driver.browser.get(full_url)
            WebDriverWait(driver.browser, 20).until(wait_ready_state())

            # news_box.big 제거
            driver.browser.execute_script(
                """
                const el = document.querySelector('div.news_box.big');
                if (el) el.remove();
            """
            )

            rows = driver.browser.find_elements(
                By.CSS_SELECTOR, "div.news_box > div.newsPost"
            )
            for row in rows:
                try:
                    href = row.find_element(
                        By.CSS_SELECTOR, "div.assetText > a"
                    ).get_attribute("href")
                    title = row.find_element(
                        By.CSS_SELECTOR, "div.assetText > a > h3"
                    ).text.strip()
                    date_span = row.find_element(
                        By.CSS_SELECTOR, "div.assetText > p.byline > span"
                    )
                    date_text = date_span.get_attribute("textContent").strip()
                    if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                        logger.debug(
                            f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                        )
                        is_loop = False
                        break

                    result_item = make_result(
                        SITE_NAME,
                        target,
                        title,
                        href,
                        replace_date(date_text),
                        driver.getIdx(),
                    )
                    if not limiter.append(result_item):
                        logger.debug(
                            f"🛑 디버그 모드: {target['catCd']} 수집 제한 도달, 중단"
                        )
                        is_loop = False
                        break
                except Exception as e:
                    logger.error(f"❌ 오류 발생: {e}")
                    continue
    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
