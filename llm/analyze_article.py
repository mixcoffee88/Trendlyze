from langchain_aws import ChatBedrockConverse
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# thinking_params = {"thinking": {"type": "enabled", "budget_tokens": 2000}}
# 1) Bedrock Converse 챗 모델 초기화
chat = ChatBedrockConverse(
    # ✅ Claude 계열 모델 (2025년 5월 기준)
    # model_id="apac.anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku X
    # model_id="apac.anthropic.claude-3-sonnet-20240229-v1:0",  # Claude 3 Sonnet X
    # model_id="apac.anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet
    model_id="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",  # Claude 3.5 Sonnet v2(테스트 모델) O
    # model_id="apac.anthropic.claude-3-7-sonnet-20250219-v1:0",  # Claude 3.7 Sonnet
    # model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",  # Claude Sonnet 4
    # # ✅ Amazon Nova 계열 (Amazon 자체 모델)
    # model_id="apac.amazon.nova-lite-v1:0",  # Amazon Nova Lite
    # model_id="apac.amazon.nova-micro-v1:0",  # Amazon Nova Micro
    # model_id="apac.amazon.nova-pro-v1:0",  # Amazon Nova Pro
    # # 메타(Meta), 미스트랄(Mistral), 코히어(Cohere), AI21 등
    # model_id="meta.llama3-8b-instruct-v1:0",  # Meta LLaMA3 8B X
    # model_id="meta.llama3-70b-instruct-v1:0",  # Meta LLaMA3 70B X
    # model_id="mistral.mistral-7b-instruct-v0:2",  # Mistral 7B Instruct X
    # model_id="mistral.mixtral-8x7b-instruct-v0:1",  # Mixtral 8x7B Instruct X
    # model_id="cohere.command-r-plus-v1:0",  # Cohere Command R+ X
    # model_id="ai21.j2-ultra-v1",  # AI21 Jurassic-2 Ultra X
    region_name="ap-northeast-2",
    temperature=0.2,
    top_p=0.8,
    # stop_sequences=["```", "\n\n"],
    # additional_model_request_fields=thinking_params,
)

# 2) 출력 스키마 정의
schemas = [
    ResponseSchema(name="sentiment_score", description="0~100 정수"),
    ResponseSchema(
        name="positive_keywords", description="최대 5개 긍정적인 단어나 문구 리스트"
    ),
    ResponseSchema(
        name="negative_keywords", description="최대 5개 부정적인 단어나 문구 리스트"
    ),
    ResponseSchema(
        name="frequent_keywords", description="최대 5개 출현빈도 높은 단어 리스트"
    ),
    ResponseSchema(name="summary", description="500자 이내 요약"),
    ResponseSchema(name="brief_summary", description="100자 이내의 핵심 한 문장 요약"),
    ResponseSchema(name="category", description="커머스, 컨슈머, 콘텐츠 중 하나"),
]

# 파서 구성
parser = StructuredOutputParser.from_response_schemas(schemas)
format_instructions = parser.get_format_instructions()

# 3) 시스템 프롬프트 파일 읽기
prompt_path = Path("prompts") / "system_prompt.txt"
system_prompt = prompt_path.read_text(encoding="utf-8")

# 4) 프롬프트 템플릿 구성
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            system_prompt,
        ),
        (
            "user",
            """
                다음 본문을 분석하고, 다음 항목을 JSON 형식으로 작성하십시오:

                <본문>
                {content}

                {format_instructions}
            """,
        ),
    ]
)


# 5) 분석 함수 정의
def analyze_article(results) -> dict:
    chain = prompt | chat | parser
    # limit = 0
    for result in results:
        # if limit > 2:
        #     break
        content = result.get("content", "")
        if content != "":
            try:
                analyze = chain.invoke(
                    {"content": content, "format_instructions": format_instructions}
                )
                result["analyze"] = analyze
                print(analyze)
            except Exception as e:
                result["analyze_error"] = str(e)

        # limit += 1

    return results
