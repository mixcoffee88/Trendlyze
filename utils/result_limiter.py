from config import settings

import re, logging

logger = logging.getLogger(__name__)


class ResultLimiter:
    def __init__(self):
        self.is_crawling_limit = settings.IS_CRAWLING_LIMIT
        self.max_count = settings.CRAWLING_LIMIT
        self.count_by_cat = {}  # catCd별 개수
        self.total_count = 0  # fallback용 전체 개수
        self.results = []  # 수집된 결과를 저장할 리스트

        logger.info(
            f"ResultLimiter initialized with is_crawling_limit={self.is_crawling_limit}, max_count={self.max_count}"
        )

    def append(self, item: dict) -> bool:
        if not self.is_crawling_limit:
            logger.info(
                f"Crawling limit is disabled, appending item without checks.{item}"
            )
            self.results.append(item)
            return True

        meta = item.get("metaData", {})
        cat_cd = meta.get("catCd")

        if cat_cd:
            current_count = self.count_by_cat.get(cat_cd, 0)
            if current_count >= self.max_count:
                return False
            self.count_by_cat[cat_cd] = current_count + 1
        else:
            if self.total_count >= self.max_count:
                return False
            self.total_count += 1

        self.results.append(item)
        return True

    def is_exceeded(self, cat_cd: str = None) -> bool:
        if not self.is_crawling_limit:
            return False
        if cat_cd:
            return self.count_by_cat.get(cat_cd, 0) >= self.max_count
        return self.total_count >= self.max_count
