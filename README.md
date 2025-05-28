# Trendlyze

📊 **Trendlyze**는 다양한 사업 부문의 웹사이트에서 데이터를 수집하고, 이를 AI 언어 모델(LLM)을 활용해 분석하여 트렌드 리포트를 자동 생성하는 Python 기반 크롤링 및 분석 도구입니다.

## 🔍 주요 기능

* ✅ 다양한 뉴스/블로그/리포트 사이트에서 트렌드 관련 컨텐츠 크롤링
* ✅ OCR + LLM 기반 요약 및 감성 분석 (한글/영문 지원)
* ✅ SentenceTransformer 기능 유사도 분석
* ✅ 키워드 추출, 카테고리 분류, 긍정지수 생성
* ✅ HTML 기능 시각화 및 카테고리별 리포트 출력

## 📂️ 프로젝트 구조

```
Trendlyze/
├── crawling/               # 사이트별 크롤러 모듈 및 manager
├── crawling/site           # 사이트별 크롤러 모듈
├── models/                 # 분석 모델 및 임브딩 처리
├── prompts/                # LLM 프롬프트 템플릿
├── utils/                  # 공통 유틸리티 함수
├── test.py                 # 기능 테스트용 스크립트
├── main.py                 # 크롤링 + 분석 전체 실행 진입점
├── requirements.txt        # Python 패키지 목록
└── README.md               # 이 파일
```

## 🚀 설치 및 실행 방법

### 1. 가상환경 설정

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 크론 드라이버 설정

* [ChromeDriver](https://chromedriver.chromium.org/downloads)를 설치한 후, `settings.py` 혹은 `.env`에서 건드 지정 필요

## 4. linux 서버에서 드라이버 권한 주기
chmod +x /home/ec2-user/CrawlBulk/driver/linux/chromedriver/chromedriver
chmod +x /home/ec2-user/CrawlBulk/driver/linux/chrome/chrome

### 5. 실행

```bash
python main.py
```

## 📦 주요 의존 라이브러리

* `selenium` – 웹 자동화 크롤러
* `PyMuPDF`, `pytesseract` – PDF 및 이미지 OCR
* `transformers`, `sentence-transformers` – LLM 및 벡터 임브딩
* `dateparser`, `justext`, `htmldate` – 날짜, 부문, HTML 정제
* `matplotlib`, `scikit-learn` – 시각화 및 통계 분석

## 📊 분석 예시 출력 (JSON)

```json
{
  "sentiment_score": 72,
  "positive_keywords": ["혁신", "확장", "성장"],
  "summary": "삼성전자는 AI 부문에서의 투자와 혁신을 강화하고 있다.",
  "category": "디지털/IT"
}
```

## 📁 참고 자료

* [OpenAI API Docs](https://platform.openai.com/docs)
* [Sentence Transformers](https://www.sbert.net/)
* [Korean News Dataset 참고](https://huggingface.co/datasets)

## 🤝 기억 방법

1. 이 저장소를 Fork합니다.
2. 기능 추가 또는 버그 수정 후 Pull Request를 생성합니다.
3. 새로운 사이트 크롤링 모듈은 `crawling/`에 추가해주세요.

## 📄 라이선스

MIT License

---

🧠 **Trendlyze는 인간처럼 생각하고 분류하는 AI 분석 툴을 지향합니다.**
트렌드를 빠른 시각으로 이해하고 싶은 모든 기획자, 마케팅 전문가, 전략가를 위해 만들어진 툴입니다.
