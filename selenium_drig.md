✅ 전제 조건 요약
사이트 수: 80개

Selenium Grid 사용 예정

모든 요청은 단일 고정 IP에서 나가야 함 (즉, NAT 또는 프록시 필수)

Driver는 사이트별로 생성 필요 여부 검토 중

배포 전략, 프로그램 구조 고민 중

✅ 최적의 시스템 구조
📦 아키텍처
[ 사용자 / 스케줄러 ]
        |
     EC2: Hub (t3.micro)
        |
  ┌────────────┬────────────┬────────────┐
  │            │            │            │
Node-1       Node-2       Node-3       ...  (EC2 or Docker)
  │            │            │
 Chrome       Chrome       Chrome      (Headless)
  │            │            │
모두 NAT 인스턴스를 통해 고정 Public IP 사용
🧩 고정 IP 유지 방식
모든 Node는 Private Subnet에 두고
NAT Instance (t3.micro) 하나를 통해 외부로 통신 → 고정 Elastic IP

🛠 프로그램 구조 (Python 기준)

crawler/
├── main.py                 # 병렬 분배 및 실행
├── grid_client.py          # Selenium RemoteDriver 관리
├── dispatcher.py           # 사이트 → Node 분배 로직
├── base_crawler.py         # 크롤러 Base 클래스
├── sites/
│   ├── zdnet.py            # 각 사이트 크롤러
│   ├── mobiinside.py
│   └── ...
└── state_manager.py        # DynamoDB 상태관리

🔁 실행 플로우
from dispatcher import dispatch_sites

if __name__ == "__main__":
    sites = load_site_list()
    dispatch_sites(sites)  # 병렬 분산 실행

2. dispatcher.py: 사이트를 Node에 분배
from concurrent.futures import ThreadPoolExecutor
from grid_client import create_driver
from state_manager import update_state

def run_site(site):
    update_state(site, "RUNNING")
    driver = create_driver()  # RemoteWebDriver 생성
    try:
        crawler = get_site_crawler(site)
        crawler(driver).run()
        update_state(site, "COMPLETED")
    except Exception:
        update_state(site, "FAILED")

def dispatch_sites(sites):
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(run_site, sites)

3. grid_client.py: 사이트별 driver 생성
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def create_driver():
    options = Options()
    options.add_argument("--headless")
    return webdriver.Remote(
        command_executor="http://<hub-private-ip>:4444/wd/hub",
        options=options
    )
✅ Driver는 사이트별로 독립 생성해야 합니다.
각 사이트는 독립 브라우저 세션이 필요

사이트 별 로딩/타이밍 차이 대응

이후 에러 복구/재시작도 쉬움

🚀 배포 전략
1. Hub/Node 배포 (Docker or EC2 Script)
docker-compose.yml 기반으로 각 EC2에 배포 자동화

또는 cloud-init / SSM / Ansible로 설치 자동화

2. 크롤러 소스 배포
방법 1: Git pull + main.py 실행

방법 2: cron or EventBridge로 주기적 실행

방법 3: Airflow, Step Functions 연동 (고급 스케줄링)

✨ 핵심 요약
| 항목               | 설계안                                                  |
| ---------------- | ---------------------------------------------------- |
| **Driver 생성 방식** | 사이트마다 새 RemoteWebDriver 생성 (Node는 Grid에서 분배됨)        |
| **배포 방식**        | Grid 구성은 Docker 또는 cloud-init로 자동화, 크롤러는 git pull 기반 |
| **고정 IP 사용**     | 모든 Node는 NAT 인스턴스를 통해 1개의 Elastic IP 사용              |
| **확장성**          | Node EC2 수 늘리면 병렬성 확장 가능 (AutoScaling도 가능)           |
| **오류 복구**        | DynamoDB 상태값 기반으로 Watchdog 구현 (지금 방식 유지 가능)          |
