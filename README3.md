# ✅ Trendlyze: 단일 IP 기반 Selenium 분산 크롤링 오케스트레이터 (무한대기 방지 포함)

## 📌 목표
* 80개 사이트를 매일 자동 분산 크롤링
* Node 1개당 사이트 1개 크롤링
* 모든 외부 통신은 단일 IP (NAT Instance) 사용
* 무한 대기 상태 탐지 → 자동 종료 및 재시도
* 모든 크롤링 종료 시 전체 인프라 자동 종료

## 아키텍쳐 구조
```plaintext
📅 EventBridge (1일 1회) → Lambda → Hub EC2 기동

🏗 Hub EC2 (Controller)
 └─ 1. NAT Instance 시작 (run-instances)
 └─ 2. GIT PULL 후 S3 업로드
 └─ 3. SQS에 사이트 80개 푸시
 └─ 4. Node N개 run_instances 생성
 └─ 5. 상태 감시 (DynamoDB)
 └─ 6. 모든 Node 상태 COMPLETED or FAILED 시 종료 (shutdown -h now)

🧱 Node EC2 (Worker)
 └─ 1. cloud-init: EFS 마운트 → S3 코드 다운로드
 └─ 2. SQS 메시지 1건 수신 (site_id 포함)
 └─ 3. DynamoDB 상태 체크 → 실행 가능하면 크롤링 시작
 └─ 4. 크롤링 → 결과 S3 저장 → 상태 DynamoDB 보고
 └─ 5. EC2 종료 (shutdown -h now)
```

## 🔗 AWS 구성 요소 요약
| 구성 요소                    | 설명                                                                    |
| ------------------------ | --------------------------------------------------------------------- |
| **NAT Instance**         | 모든 Node가 단일 공용 IP로 외부와 통신                                             |
| **S3**                   | 크롤러 코드 배포 및 실행 파일 다운로드용                                               |
| **EFS**                  | `user-data-dir` 공유 디렉토리. 크롬 프로필 및 락 파일 관리                             |
| **SQS (Standard Queue)** | 사이트 작업 큐<br/>✔ `VisibilityTimeout = 300초`<br/>✔ `MaxReceiveCount = 6` |
| **DynamoDB**             | 사이트별 상태 저장 (`run_status`, `site_status`, `lastUpdateEpoch`)           |
| **EventBridge + Lambda** | 하루 한 번 Hub EC2 기동                                                     |
| **EC2 (Hub)**            | 전체 제어: 작업 큐 작성, Node 생성, 상태 모니터링, 종료                                  |
| **EC2 (Node)**           | 사이트 1개 담당, 상태 체크 후 크롤링 실행, 상태 기록, 자가 종료                               |

## 🧠 상세 동작 흐름
```plaintext
1. Node 부팅 시 cloud-init으로 아래 자동 수행:
   → EFS 마운트
   → S3 코드 다운로드
   → SQS 메시지 수신 (site_id)

2. DynamoDB 상태 조회:
   - 실행 중이면 → 메시지 삭제 없이 skip
   - 실행 가능하면:
     → run_status=RUN, site_status=URL_CALL 기록
     → 크롤링 실행
     → 결과 S3 저장
     → DynamoDB에 COMPLETED 기록
     → 메시지 삭제
     → shutdown -h now

```

## DynamoDB TTL 설정
* lastUpdateEpoch + 1일로 TTL 설정 시,
- 자동 정리 가능
- 이전 상태나 시도 기록이 1일 뒤 정리되어 재시도 여지 확보

## 🔁 Hub 무한 대기 방지 감시 로직
* Hub에서 30초 주기로 DynamoDB 상태 확인:
```python
for item in dynamodb.scan(...):
    if item['site_status'] == 'URL_CALL':
        if now() - item['lastUpdateEpoch'] > 120:
            send_ssm_kill_command(item['instance_id'])

            update_status(site=item['Site'],
                          run_status='FAILED',
                          site_status='FAILED')

            if item['attemptCount'] < 5:
                sqs.send_message(site=item['Site'])
                increment_attempt(site)
```

## 📁 DynamoDB 상태 구조 예시
```json
{
  "Site": "zdnet",
  "run_status": "RUN",
  "site_status": "URL_CALL",
  "lastUpdateEpoch": 1716980721,
  "attemptCount": 2,
  "instance_id": "i-04abcde..."
}
```
| 필드                | 설명                                |
| ----------------- | --------------------------------- |
| `run_status`      | `RUN`, `COMPLETED`, `FAILED`      |
| `site_status`     | `URL_CALL`, `COMPLETED`, `FAILED` |
| `lastUpdateEpoch` | 마지막 상태 갱신 시간 (epoch 단위)           |
| `attemptCount`    | 현재까지 시도 횟수 (6회까지 허용)              |
| `instance_id`     | EC2 추적 및 종료용 정보                   |

## 🔐 IAM 권한 요약
| 역할           | 필요한 권한                                                                                |
| ------------ | ------------------------------------------------------------------------------------- |
| **Hub EC2**  | `ec2:RunInstances`, `sqs:SendMessage`, `dynamodb:PutItem`, `ssm:SendCommand`          |
| **Node EC2** | `sqs:ReceiveMessage`, `s3:GetObject`, `dynamodb:UpdateItem`, `ec2:TerminateInstances` |
| **Lambda**   | `ec2:StartInstances`, `events:PutRule`, `events:PutTargets`                           |

## ✅ 기대 효과
* ✔ 사이트 단위 분리로 병렬성 극대화 + 충돌 최소화
* ✔ 무한 대기 자동 감지/복구
* ✔ DynamoDB 상태 기반 중복 실행 방지
* ✔ SQS 표준 큐로 유연한 메시지 처리
* ✔ 전체 워크플로우 100% 자동화
* ✔ EC2 자가 종료 + NAT 단일 IP 유지로 비용 최적화