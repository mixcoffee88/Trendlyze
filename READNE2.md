# ✅ Trendlyze: 단일 IP 기반 Selenium Grid 분산 크롤링 오케스트레이터 (with 무한대기 방지)
## 📌 목표
* 80개 사이트를 1일 1회 자동 분산 크롤링
* 각 Node는 하나의 사이트만 크롤링
* 모든 Node는 단일 IP로 외부 통신
* 크롤링이 무한 대기에 빠질 경우 감지하고 자동 복구
* 모든 크롤링 완료 후 자원 자동 종료

## 🔗 핵심 구성 요소 요약
| 구성 요소                    | 설명                                    |
| ------------------------ | ------------------------------------- |
| **NAT Instance**         | 모든 Node가 단일 IP를 통해 외부와 통신             |
| **S3**                   | 크롤러 코드 배포 (site\_crawler.zip)         |
| **EFS**                  | 크롬 프로필 공유용 user-data-dir (락 관리 포함)    |
| **SQS**                  | 사이트 작업 대기열                            |
| **DynamoDB**             | 사이트별 크롤러 상태 저장                        |
| **EventBridge + Lambda** | 1일 1회 Hub EC2 실행                      |
| **Hub EC2**              | 전체 제어 (SQS 분배, Node 생성, 상태 감시, 자원 종료) |

## 🧠 상세 동작 흐름
### 1️⃣ EventBridge → Lambda → Hub EC2 실행
* 매일 새벽 1시 등 일정 설정
* Lambda는 start-instances 또는 run-instances로 Hub EC2 시작
### 2️⃣ Hub EC2 부팅 시 cloud-init 또는 스크립트 자동 실행
* Docker로 Grid Hub 컨테이너 실행
* SQS에 80개 사이트 작업 등록
* Node EC2 n대 실행 (run_instances)
* 각 Node는 cloud-init으로 다음 작업 수행:
1.  EFS 마운트
2. S3에서 코드 다운로드
3. SQS에서 사이트 메시지 하나 소비
4. 크롤러 실행 → 상태 DynamoDB 보고
5. 크롤링 완료 후 shutdown -h now
### 3️⃣ Node 상태 관리 (DynamoDB)
* 테이블 예시:
```
{
  "Site": "zdnet",
  "run_status": "RUN",
  "site_status": "URL_CALL",
  "lastUpdateEpoch": 1716980721,
  "attemptCount": 1,
  "instance_id": "i-04abcde..."
}
```
| 필드                | 설명                             |
| ----------------- | ------------------------------ |
| `run_status`      | RUN / COMPLETED / FAILED       |
| `site_status`     | URL\_CALL / COMPLETED / FAILED |
| `lastUpdateEpoch` | 상태 갱신 시점 (epoch sec)           |
| `attemptCount`    | 재시도 횟수 (3회 제한)                 |
| `instance_id`     | Node EC2 ID (추적용)              |
### 4️⃣ 무한 대기 방지 로직 (Hub 감시 루프)
* Hub에서 30초마다 다음 감시 수행:
```python
for item in dynamodb.scan(TableName="TrendlyzeStatus"):
    if item['site_status'] == 'URL_CALL':
        if now() - item['lastUpdateEpoch'] > 120:  # 2분 초과
            # Node에서 크롤러 프로세스 종료
            send_ssm_kill_command(item['instance_id'])

            # 상태 FAILED로 갱신
            update_status(site, run="FAILED", site_status="FAILED")

            # 재시도 허용 시 SQS에 다시 등록
            if item['attemptCount'] < 3:
                sqs.send_message(site)
                increment_attempt(site)
```

### 5️⃣ 모든 Node 상태가 COMPLETED or FAILED 시
* Hub는 다음 수행:
```python
terminate_nodes(all_instance_ids)
shutdown -h now  # Hub 자체 종료
```

### ✅ 락 기반 EFS user-data-dir 구성
* --user-data-dir=/efs/profiles/zdnet
* 락 파일: /efs/locks/zdnet.lock
```python
with open(f"/efs/locks/{site}.lock", "w") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    run_chrome()

```

### 🔐 IAM 권한 요약
| 서비스      | 권한                                                                    |
| -------- | --------------------------------------------------------------------- |
| S3       | `s3:GetObject`                                                        |
| SQS      | `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`          |
| EC2      | `ec2:RunInstances`, `ec2:TerminateInstances`, `ec2:DescribeInstances` |
| SSM      | `ssm:SendCommand`, `ssm:DescribeInstanceInformation`                  |
| DynamoDB | `PutItem`, `UpdateItem`, `Scan`                                       |

### ✅ 기대 효과
* 사이트별 고립 처리로 충돌/에러 최소화
* 무한 대기 → 자동 복구 → 재시도 가능
* 완전 자동화된 1일 1회 크롤링 파이프라인
* 비용 최적화: Spot EC2 사용 + 종료 자동화
* 운영 개입 없이 안정적 크롤링 가능
