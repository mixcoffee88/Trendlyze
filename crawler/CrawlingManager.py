import json, time, os, platform, logging, requests, trafilatura, importlib, uuid, argparse, re, random

from config import settings
from collections import Counter
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoAlertPresentException, TimeoutException

from models.elements import InputField, ActionButton
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from utils.common import wait_ready_state
from datetime import datetime
from aws.S3Uploader import S3Uploader

# ─── 로깅 설정 ──────────────────────────
logger = logging.getLogger(__name__)


# -------- 사용자 정의 타임아웃 예외 --------
class TimeoutError(Exception):
    pass


def handler(signum, frame):
    raise TimeoutError()


# ===== 크롤링 매니저 클래스 =====
class CrawlingManager:
    def __init__(self):
        # 크롬 브라우저 실행 환경(옵션) 설정 및 인스턴스 생성
        logger.debug(f"✅ CHROME_DRIVER_PATH: {settings.CHROME_DRIVER_PATH}")
        logger.debug(f"✅ BINARY_PATH: {settings.CHROME_BINARY_PATH}")
        logger.debug(
            f"✅ os.path.exists(chrome): {os.path.exists(settings.CHROME_BINARY_PATH)}"
        )
        logger.debug(
            f"✅ os.path.exists(driver): {os.path.exists(settings.CHROME_DRIVER_PATH)}"
        )

        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = str(settings.CHROME_BINARY_PATH)

        # 디버깅(비헤드리스/헤드리스) 설정
        if not settings.HEADLESS_MODE:
            chrome_options.add_argument("--auto-open-devtools-for-tabs")
        else:
            # print("-")
            chrome_options.add_argument("--headless=new")

        # 다양한 최적화 및 보안, 환경 옵션 추가
        chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--enable-unsafe-swiftshader")  # ✅ 핵심
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7103.113 Safari/537.36"
        )
        chrome_options.add_argument("window-size=1392x1150")
        chrome_options.add_argument("disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-software-rasterizer")

        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-prompt-on-repost")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--metrics-recording-only")

        # chrome_options.add_argument("--disable-images")  # 이미지 로딩 비활성화
        # chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        # chrome_prefs = {"profile.managed_default_content_settings.images": 2}
        # chrome_options.experimental_options["prefs"] = chrome_prefs

        chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--enable-logging")
        # chrome_options.add_argument("--v=1")
        # chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option(
            "excludeSwitches",
            ["enable-logging", "enable-automation", "disable-popup-blocking"],
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # 알림, 팝업 등 차단 프리퍼런스
        chrome_prefs = {
            "profile.default_content_setting_values.popups": 2,  # 팝업 차단
            "profile.default_content_setting_values.notifications": 2,  # 알림 차단
            # "profile.default_content_setting_values.automatic_downloads": 1,  # 다운로드 허용
        }
        chrome_options.add_experimental_option("prefs", chrome_prefs)

        # OS별 크롬 프로필 디렉토리 경로 설정
        if settings.OS_NAME != "windows":
            chrome_options.add_argument("--user-data-dir=/tmp/chrome-profile")
        else:
            chrome_options.add_argument("--user-data-dir=C:/tmp/tmp/chrome-profile4")

        # caps = DesiredCapabilities.CHROME.copy()
        # caps["pageLoadStrategy"] = "eager"
        # chrome_options.set_capability("pageLoadStrategy", "eager")

        # 크롬 드라이버 실행
        service = Service(str(settings.CHROME_DRIVER_PATH))
        browser = webdriver.Chrome(service=service, options=chrome_options)

        self.browser = browser

        # 유니크 식별용 UUID 생성
        # self.uuid = str(uuid.uuid4()).replace("-", "")
        # self.uuid = "f9d05846fe4c47c19ff34fe40c1ebe50"
        self.timestamp = datetime.now().strftime("%Y%m%d")
        self.s3 = S3Uploader()
        self.idx = 0  # 크롤링 인덱스 초기화

    def getIdx(self):
        rtnIdx = self.idx
        self.idx += 1
        return rtnIdx

    # ------- 로그인 메서드 -------
    def login(
        self, url: str, id: InputField, pwd: InputField, action: ActionButton, wait=None
    ) -> bool:
        """
        사이트 로그인 자동화.
        """
        try:
            self.browser.get(url)
            logger.debug(f"✅ {url} 페이지 로드 중...")
            if wait:
                # 조건이 있으면 명시적으로 대기
                try:
                    WebDriverWait(self.browser, 10).until(wait)
                    logger.debug(f"✅ 페이지 로딩 완료 (wait 조건 충족)")
                except Exception as e:
                    logger.error(f"❌ wait 조건 실패: {e}")
            else:
                time.sleep(2)

            # 로그인 입력 (ID, PW)
            self.browser.find_element(id.attr, id.attrValue).send_keys(id.value)
            logger.debug(f"✅ ID 입력 완료: {id.value}")
            pwd_input = self.browser.find_element(pwd.attr, pwd.attrValue)
            pwd_input.send_keys(pwd.value)
            logger.debug(f"✅ PWD 입력 완료: {pwd.value}")

            # 엔터 또는 버튼 클릭으로 로그인
            if pwd.afterEnter:
                pwd_input.send_keys(Keys.ENTER)
            else:
                actionEl = self.browser.find_element(action.attr, action.attrValue)
                actionEl.click()

            logger.debug(f"✅ 로그인 버튼 클릭 완료")
            # 로그인 후 특정 요소 등장 대기(필요시)
            if action.wait:
                try:
                    WebDriverWait(self.browser, 10).until(action.wait)
                    logger.debug(f"✅ 로그인 후 요소 대기 완료")
                except Exception as e:
                    logger.error(f"⚠️ 로그인 후 대기 실패: {e}")
                    return False

            # 추가적인 후처리 콜백(옵션)
            if action.waitAfterAction:
                isLoginComplate = action.waitAfterAction(self.browser)
                if not isLoginComplate:
                    logger.error("❌ 로그인 확인 실패 (후처리 결과 False)")
                    return False
            # time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"[로그인 중 예외 발생] {e}")
            return False

    # ------- 불필요한 탭 닫기 -------
    def closeExtraTabs(self):
        tabs = self.browser.window_handles
        main_tab = tabs[0]

        for tab in tabs:
            if tab != main_tab:
                try:
                    self.browser.switch_to.window(tab)
                    self.browser.close()
                except Exception as e:
                    logger.warning(f"❗탭 닫기 중 오류 발생: {e}")

        # 마지막에 반드시 첫 번째 탭으로 복귀
        try:
            self.browser.switch_to.window(main_tab)
        except Exception as e:
            logger.error(f"❌ 첫 번째 탭 복귀 실패: {e}")

    # ------- 브라우저 종료 -------
    def close(self):
        """
        브라우저 완전 종료
        """
        self.browser.quit()

    # ------- 상세 본문 크롤링 -------
    def crawing_content(self, results):
        """
        각 결과의 링크별로 본문 크롤링, 본문 추출 및 중복제거, 팝업/타임아웃 처리
        """
        logger.info("::::::상세 크롤링 시작::::::")
        timeout = 20  # 페이지 로딩 타임아웃 설정
        self.browser.set_page_load_timeout(timeout)  # 20초 초과 시

        start_time = time.time()
        origin_counts = Counter(item["metaData"]["origin"] for item in results)
        for origin, count in origin_counts.items():
            logger.debug(f"🗂 {origin}: {count}건")

        total = len(results)
        for idx, result in enumerate(results, start=1):
            logger.info(f"🔗 [{idx}/{total}] {result['link']} 크롤링 시작")
            time.sleep(
                random.uniform(4, 6)
            )  # 크롤링 차단을 피하기 위한 접근속도 제어위한 추가 시간
            link_start = time.time()
            domain = urlparse(result["link"]).netloc

            try:
                logger.info(f"[{idx}/{total}] {result['link']} 크롤링 시작")
                # 도메인 별로 크롤링 방식 다르게 처리(특정 도메인은 requests로만 처리)
                try:
                    logger.debug(f"[{idx}] ▶ driver.get() 시작: {result['link']}")

                    if "zdnet.co.kr" in domain:
                        time.sleep(1)
                        try:
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                            }
                            res = requests.get(
                                result["link"], headers=headers, timeout=timeout
                            )
                            res.raise_for_status()
                            logger.debug(
                                f"✅ requests로 페이지 불러오기 완료: {result['link']}"
                            )
                            html = res.text
                        except Exception as e:
                            logger.warning(f"❌ requests 실패: {result['link']} → {e}")
                            return ""
                    else:
                        # Selenium을 활용한 브라우저 이동 및 대기
                        self.browser.get(result["link"])
                        logger.debug(f"[{idx}] ✔ driver.get() 완료")

                        logger.debug(f"[{idx}] ▶ readyState 대기 시작")
                        try:
                            WebDriverWait(self.browser, 10).until(wait_ready_state())
                            logger.debug(f"[{idx}] ✔ readyState 완료")

                        except TimeoutException:
                            logger.warning(
                                f"⚠️ readyState 미완료 → 강제 진행: {result['link']}"
                            )

                        time.sleep(1)
                        # alert 팝업 닫기(있을 경우)
                        try:
                            alert = self.browser.switch_to.alert
                            alert.dismiss()
                            logger.warning("⚠️ 팝업 alert 닫음")
                        except NoAlertPresentException:
                            pass  # 정상

                        logger.debug(f"HTML 호출 완료")
                        time.sleep(2)  # JS 로딩 대기 보강
                        html = self.browser.page_source
                        # logger.info(html)
                        logger.info(f"[{idx}/{total}] {result['link']} HTML 호출 완료")

                except TimeoutException:
                    logger.warning(f"⚠️ 페이지 로딩 타임아웃: {result['link']}")
                    continue

                # parsing_html = self.preprocess_html_for_extraction(domain, html)

                # 본문 추출 시도 (1차: trafilatura)
                content = trafilatura.extract(
                    html,
                    with_metadata=False,
                    include_comments=False,
                    include_tables=True,
                    favor_recall=True,
                    output_format="txt",
                    include_links=False,
                )
                # content = self.postprocess_extracted_content(domain, content)
                logger.debug(f'{result["link"]} trafilatura 전환 완료')

                # Fallback: trafilatura 실패 시 BeautifulSoup
                if not content or len(content) < 300:
                    logger.debug(f'{result["link"]} Fallback : BeautifulSoup 전환 진행')
                    soup = BeautifulSoup(html, "html.parser")
                    content = soup.get_text(" ", strip=True)
                    logger.debug(f'{result["link"]} Fallback : BeautifulSoup 전환 완료')

                # 너무 짧은 본문은 None 처리
                if len(content) < 200:
                    content = ""

                result["content"] = content or ""  # None 방지
                logger.debug(f"✅ 크롤링 완료: {result['link']}")
                self.closeExtraTabs()

            except Exception as e:
                result["content"] = ""
                logger.error(
                    f"❌ 크롤링 실패: {result['link']} → {type(e).__name__}: {e}"
                )

            link_elapsed = time.time() - link_start
            logger.info(f"⏱️ {result['link']} 처리 시간: {link_elapsed:.2f}초")

        empty_count = sum(1 for r in results if not r.get("content"))
        logger.info(f"📭 본문 미수집 건수: {empty_count}건 / 전체 {len(results)}건")

        elapsed_time = time.time() - start_time
        logger.info(f"\n⏱️ 총 소요 시간: {elapsed_time:.2f}초")
        logger.info("::::::상세 크롤링 종료::::::")
        return results

    # ------- site 폴더 내 모든 crawling() 실행 -------
    def execCrawlingWebSite(self):
        # logger.info(f"{settings.PROJECT_ROOT}")
        """
        site 디렉터리의 모든 .py 파일에서 crawling(self.browser) 함수가 있으면 실행
        """
        site_path = os.path.join(settings.PROJECT_ROOT, "crawler", "site")
        for fname in os.listdir(site_path):
            if fname.endswith(".py"):
                module_name = f"crawler.site.{fname[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "crawling"):
                    logger.info(f"실행: {module_name}.crawling()")
                    try:
                        # if fname[:-3] == "zdnet":
                        #     module.crawling(self)
                        module.crawling(self)
                    except Exception as e:
                        logger.error(f"에러: {e}")

    # ------- 크롤링 본문 결과 저장 -------
    def saveResults(self, module_name, results):
        if not results:
            logger.warning("저장할 결과가 없습니다.")
            return

        file_full_path = os.path.join(
            settings.CRAWL_DATA_DIR,
            self.timestamp,
            self.uuid,
            f"{module_name.replace(' ', '_')}_result.json",
        )
        self.saveFile(file_full_path, results)

    def saveFile(self, file_full_path, results):
        """
        결과 리스트를 지정 파일 경로에 JSON 포맷으로 저장
        """
        try:
            if not results:
                logger.warning("저장할 결과가 없습니다.")
                return

            self.s3.saveFileToS3(file_full_path, results)
            logger.info(f"✅ 결과 저장 완료: {file_full_path}")
        except Exception as e:
            logger.error(f"❌ 결과 저장 실패: {file_full_path} → {e}")
            logger.error(f"❌ 결과 저장 실패: {results}")
            raise

    def merge_get_json_files(self, uuid):
        file_full_path = os.path.join(settings.CRAWL_DATA_DIR, self.timestamp, uuid)

        # merged = S3Uploader.loadAllJsonFromPrefix(file_full_path)
        # # 폴더 내 모든 .json 파일 가져오기
        # for fname in os.listdir(file_full_path):
        #     if fname.endswith(".json"):
        #         file_path = os.path.join(file_full_path, fname)
        #         with open(file_path, encoding="utf-8") as f:
        #             data = json.load(f)
        #             if isinstance(data, list):
        #                 merged.extend(data)  # 리스트면 병합
        #             else:
        #                 merged.append(data)  # dict/object면 그냥 append

        try:
            merged = self.s3.loadAllJsonFromPrefix(file_full_path)
            logger.info(f"🔗 merged: {merged}")
            # 중복 제거
            # logger.info(f"🔗 병합된 데이터 개수: {len(merged)}개")
            # merged = self.deduplicate_by_link(merged)
            # logger.info(f"✅ 중복 제거 완료: {len(merged)}개 항목")
            # 순서 보정
            merged = sorted(merged, key=lambda x: x["idx"])
            self.saveResults("merge", merged)
            return merged
        except Exception as e:
            logger.error(f"❌ 중복 제거 실패: {e}")
            return []

    def preprocess_html_for_extraction(self, domain: str, html: str):
        """
        HTML 문자열에서 .entry-content .contents_style 클래스를 찾아 해당 내용을 반환하고,
        내부의 footer 태그를 제거합니다.
        """
        logger.info(f"in {domain}")
        try:
            soup = BeautifulSoup(html, "html.parser")
            content_html = soup
            if domain == "blog.daehong.com":
                content_html = soup.select_one(".entry-content .contents_style")
                self.remove_tags_by_selector(content_html, ".related-articles")
                self.remove_tags_by_selector(content_html, ".another_category")
                self.remove_tag_and_prev_siblings(
                    content_html, ".entry-content > .contents_style > hr"
                )
            elif domain == "ditoday.com":
                # content_html = soup.select_one(".entry-content")
                self.remove_tag_and_next_siblings(content_html, ".copyright")
                self.remove_tag_with_text(
                    content_html, "컨슈머 모먼트 리포트 보러 가기", "p"
                )
            elif "brandbrief.co.kr" in domain:
                container = content_html.select_one("#article-view-content-div")
                if container:
                    last_p = container.find_all("p")[-1]
                    last_strong = last_p.find_all("strong")[-1]
                    last_strong.decompose()

            elif domain == "mobiinside.co.kr":
                logger.info("mobiinside.co.kr 처리")
                # self.remove_tag_and_next_siblings(content_html, ".post-content > hr")
                self.remove_tag_and_next_siblings(content_html, ".td-post-content > hr")
            # footer 태그 제거 (공통 처리)
            footers = content_html.find_all("footer")
            for footer in footers:
                footer.decompose()

            # logger.info(f"out 1 {content_html}")
            return str(content_html)
        except Exception as e:
            logger.error(f"❌ HTML 파싱 중 오류 발생: {e}")
            # logger.info(f"out 2 {html}")

        return html

    def postprocess_extracted_content(self, domain: str, content: str):
        """본문 추출 이후 추가 텍스트 가공 및 정제(후처리)."""
        # 특정 패턴 제거 ("연합뉴스********입니다")
        content = str(content)
        match = re.search(r"연합뉴스.*?입니다\.", content)
        if match:
            content = content[: match.start()]

        prefix = content[:50]
        match = re.search(r"^\((.{1,10})\)\s{0,5}.{1,10}기자\s*=\s*", prefix)
        if match:
            content = content[match.end() :]

        suffix = content[-50:]
        match = re.search(r"\[[^\[\]]{1,20}\s.{1,10}\s(기자|특파원)\]", suffix)
        if match:
            content = content[: -30 + match.start()]

        suffix = content[-50:]  # 끝 50자 정도만 검사
        match = re.search(r"제일기획\s.{2,10}\s프로\s*\(.*?CD팀\)", suffix)

        if match:
            content = content[: -50 + match.start()]

        # 마지막에 위치한 이메일 주소 제거
        content = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+$", "", content.strip())

        return content

    def remove_tags_by_selector(self, soup, selector):
        """
        주어진 셀렉터로 선택된 모든 태그를 제거합니다.
        """
        remove_tags = soup.select(selector)
        # print(f"[DEBUG] 선택된 태그 수: {len(remove_tags)}")
        for remove_tag in remove_tags:
            # logger.info(f"{selector} 태그 제거: {remove_tag.name}")
            remove_tag.decompose()

    def remove_tag_and_prev_siblings(self, soup, selector, is_first=True):
        # <hr> 포함 이전 요소 제거
        # remove_tag = soup.select_one(selector)
        tags = soup.select(selector)
        if not tags:
            return

        remove_tag = tags[0] if is_first else tags[-1]
        if remove_tag:
            for prev in list(remove_tag.find_previous_siblings()):
                # logger.info(f"이전 요소 제거: {prev.name}")
                if hasattr(prev, "decompose"):
                    prev.decompose()
            remove_tag.decompose()

    def remove_tag_and_next_siblings(self, soup, selector, is_last=True):
        # <hr> 포함 이전 요소 제거
        tags = soup.select(selector)
        if not tags:
            return
        logger.info(f"선택된 태그 수: {len(tags)}")
        remove_tag = tags[-1] if is_last else tags[0]
        if remove_tag:
            for prev in list(remove_tag.find_next_siblings()):
                logger.info(f"이전 요소 제거: {prev.name}")
                if hasattr(prev, "decompose"):
                    prev.decompose()
            remove_tag.decompose()

    def remove_tag_with_text(self, soup, target_text: str, tag_name: str = "p"):
        """
        특정 텍스트를 포함한 요소의 가장 가까운 상위 태그(tag_name)를 제거합니다.

        :param soup: BeautifulSoup 파싱 객체
        :param target_text: 기준이 되는 텍스트 문자열
        :param tag_name: 제거할 상위 태그 이름 (예: 'p', 'div')
        :return: 수정된 soup 객체
        """
        target_el = soup.find(string=lambda t: t and target_text in t)

        if target_el:
            container = target_el.find_parent(tag_name)
            if container:
                container.decompose()
                logger.info(f"✅ '{target_text}' 포함 <{tag_name}> 태그 제거 완료")

        return soup
