from langchain_aws import ChatBedrockConverse
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from collections import defaultdict
import json, time, os, platform, re, logging, copy
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 1. Bedrock 모델 초기화
chat = ChatBedrockConverse(
    model_id="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="ap-northeast-2",
    temperature=0.3,
    top_p=0.9,
)

# 2. 출력 스키마 정의
schemas = [
    ResponseSchema(name="topic", description="이 기사 클러스터의 대표 주제. 1문장"),
    ResponseSchema(
        name="reason", description="대표 주제를 선택한 이유와 공통점 요약 (300자 이내)"
    ),
]

parser = StructuredOutputParser.from_response_schemas(schemas)
format_instructions = parser.get_format_instructions()

# 3. 프롬프트 템플릿
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 수많은 산업 기사를 분석해 공통 주제를 추출하는 전문 AI입니다.",
        ),
        (
            "user",
            """
        다음 기사들은 같은 클러스터로 묶인 관련 기사들입니다.
        공통된 주제를 하나의 문장으로 요약하고, 그렇게 판단한 이유를 300자 이내로 요약하세요.

        <기사 목록>
        {joined_contents}

        {format_instructions}
    """,
        ),
    ]
)


def group_articles_by_category_and_cluster(resultss):
    cluster_articles = {}

    for category, articles in resultss.items():
        cluster_map = defaultdict(list)
        for article in articles:
            cluster_id = article.get("cluster")
            if cluster_id is not None:
                cluster_map[cluster_id].append(article)
        cluster_articles[category] = dict(cluster_map)

    return cluster_articles


# 4. 분석 함수 정의
def extract_cluster_topic(results: list) -> dict:
    chain = prompt | chat | parser
    cluster_articles = group_articles_by_category_and_cluster(results)

    cluster_topics = []

    for category, cluster_map in cluster_articles.items():
        for cluster_id, articles in cluster_map.items():
            contents = [
                f"제목: {item.get('title')}\n요약: {item.get('analyze', {}).get('summary', '')}"
                for item in articles
                if item.get("analyze", {}).get("summary")
            ]
            joined_contents = "\n\n".join(contents)

            if not joined_contents.strip():
                continue  # 분석할 내용이 없으면 skip

            try:
                result = chain.invoke(
                    {
                        "joined_contents": joined_contents,
                        "format_instructions": format_instructions,
                    }
                )
                result["articles"] = articles
                cluster_topics.append(
                    {
                        "category": category,
                        "cluster_id": cluster_id,
                        "topic": result.get("topic"),
                        "reason": result.get("reason"),
                        "articles": articles,
                    }
                )

                logger.info(f"[{category} / 클러스터 {cluster_id}] ✔ 주제 추출 완료")
            except Exception as e:
                logger.error(
                    f"[{category} / 클러스터 {cluster_id}] ❌ LLM 호출 실패: {str(e)}"
                )
                cluster_topics.append(
                    {
                        "category": category,
                        "cluster_id": cluster_id,
                        "topic": "ERROR",
                        "reason": str(e),
                        "articles": articles,
                    }
                )

    return cluster_topics
