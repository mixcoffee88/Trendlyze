import logging, argparse
from crawler.CrawlingManager import CrawlingManager
from llm.classify_duplicates import classify_duplicates, deduplicate_by_link
from llm.analyze_article import analyze_article
from llm.extract_cluster_topic import extract_cluster_topic
from llm.cluster_by_category_e5 import SummaryClusterer

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()
level = logging.DEBUG if args.debug else logging.INFO


# 로거 설정
logging.basicConfig(
    level=level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trendlyze.log", encoding="utf-8"),
    ],
)


def main():
    try:
        manager = CrawlingManager()
        clusterer = SummaryClusterer(manager)
        try:
            logging.info("WEB SITE URL 크롤링을 실행합니다.")
            manager.execCrawlingWebSite()
            results = manager.merge_get_json_files(manager.uuid)
            results = deduplicate_by_link(results)
            # # deduplicate_by_link
            manager.saveResults("dedup", results)
            results = analyze_article(results)
            manager.saveResults("analyze", results)
            logging.info("WEB SITE URL 크롤링이 종료되었습니다.")

            logging.info("SummaryClusterer 실행합니다.")
            # results = clusterer.run()
            logging.info("SummaryClusterer 종료되었습니다.")
            results = manager.s3.loadJsonFromS3(
                "crawl/20250528/f9d05846fe4c47c19ff34fe40c1ebe50/clustered_result.json"
            )
            results = extract_cluster_topic(results)
            manager.saveResults("final", results)
        except Exception as e:
            logging.error(f"❌ 크롤링 실패: {e}")
    finally:
        manager.close()
        logging.info("드라이버 초기화 완료")


if __name__ == "__main__":
    main()
