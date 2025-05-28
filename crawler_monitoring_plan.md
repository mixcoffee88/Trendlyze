# Trendlyze AWS 기반 크롤러 오류 복구 및 상태 모니터링 설계

## ✅ 핵심 개요

Trendlyze는 EC2에서 멀티프로세싱 방식으로 실행되는 병렬 크롤러 구조입니다. 이 시스템을 다음과 같은 문제를 해결하도록 설계합니다:

* 무한 대기 방지
* 타임아웃 자동 감지 및 재시도
* 상태 기록 및 외부 모니터링
* 크롤링 중복 방지
* 자동 장애 복구 및 비용 최소화

---

## 📦 AWS 구성 요소

| 구성 요소            | 용도                     | 비용 효율성        |
| ---------------- | ---------------------- | ------------- |
| DynamoDB         | 크롤러 상태값 저장 및 TTL 자동 삭제 | 💯 매우 효율적     |
| S3               | 크롤링 결과 저장 / 중복 여부 확인   | 💯 매우 효율적     |
| Lambda           | 외부 모니터링 Watchdog 역할    | ✅ 무료 티어 충분    |
| EventBridge      | 2분마다 Watchdog 호출       | ✅ 매우 저렴       |
| SSM (RunCommand) | EC2 크롤러 프로세스 재시작       | ✅ 유용하며 비용 없음  |
| CloudWatch Logs  | 로그 기록 및 추적             | ✅ 기본 무료 티어 충분 |

---

## 🧩 상태 저장 설계 (DynamoDB)

* **테이블 이름**: `CrawlerStateTable`
* **PK (Primary Key)**: `Site` (크롤링 대상 사이트 식별자)
* **속성 예시**:

  ```json
  {
    "Site": "zdnet",
    "state": "URL_CALL",
    "lastUpdateEpoch": 1716874800,
    "attemptCount": 2,
    "expireAt": 1716961200
  }
  ```
* **TTL 설정**: `expireAt` 필드 기준으로 하루 뒤 자동 삭제
* **상태값 종류**:

  * `RUNNING`: 크롤러 시작됨
  * `URL_CALL`: URL 호출 중
  * `CALL_DONE`: 호출 성공
  * `COMPLETED`: 정상 종료
  * `FAILED`: 재시도 3회 실패 후 종료

---

## 🕹️ EC2 내 크롤러 구조

* 모든 `site 크롤러`는 `BaseCrawler` 클래스를 상속받고 다음과 같은 상태 업데이트 수행

  ```python
  def update_state(site, state):
      table.update_item(...)
  ```
* 시작 시 `RUNNING`, URL 호출 시 `URL_CALL`, 완료 시 `COMPLETED`
* 각 상태 갱신 시 `lastUpdateEpoch`도 함께 갱신

---

## 🚦 중복 크롤링 방지

* 크롤러 실행 전 다음 2가지를 체크:

  1. **S3**: 이미 결과가 존재하는 경우 skip
  2. **DynamoDB**: 해당 사이트 상태가 `RUNNING`, `URL_CALL` 인 경우 실행 방지
* DynamoDB에 `ConditionExpression`을 활용한 락 구현

  ```python
  put_item(..., ConditionExpression="attribute_not_exists(Site)")
  ```

---

## 🔁 자동 재시도 및 모니터링

### 📍 내부 모니터링 (EC2 내부 루프)

* 메인 프로세스가 30초마다 DynamoDB를 확인
* `URL_CALL` 상태가 2분 이상 유지된 경우:

  * `process.terminate()`로 해당 프로세스 강제 종료
  * `attemptCount += 1`, 상태 `RUNNING`으로 갱신 후 재시작
  * 3회 실패 시 `FAILED`로 종료 및 로그 기록

### 📍 외부 모니터링 (Lambda + EventBridge)

* **EventBridge**: 2분마다 Lambda 호출
* **Lambda**: 다음 로직 수행

  1. DynamoDB에서 `URL_CALL` + 2분 초과 항목 조회
  2. 3회 미만이면 `attemptCount += 1`, 상태 갱신
  3. **SSM**을 이용해 EC2에서 해당 크롤러 재실행
  4. 3회 초과이면 `FAILED` 상태로 마감 및 SNS 알림(Optional)

---

## 📂 결과 저장 및 중복 확인 (S3)

* 크롤링 결과는 다음 형식으로 저장:

  * `s3://trendlyze-results/zdnet/20240528/result.json`
* 메인 프로세스는 크롤링 전 다음으로 확인:

  ```python
  s3.head_object(Bucket, Key) → 존재하면 skip
  ```
* 중복 방지 외에도 결과 보존 및 분석용

---

## 🔐 IAM 권한 설계

### EC2 Instance Role

* `dynamodb:*` on `CrawlerStateTable`
* `s3:*` on 결과 bucket
* `ssm:*` (SSM 사용 시)

### Lambda Execution Role

* `dynamodb:Scan,UpdateItem`
* `ssm:SendCommand` (EC2 크롤러 제어)
* `logs:*` (CloudWatch Logs 기록)

---

## 📈 모니터링 및 비용

| 구성 요소                | 예상 월 비용        | 비고                 |
| -------------------- | -------------- | ------------------ |
| DynamoDB             | \$0.5\~1       | 상태 로그 수천 건 기준      |
| Lambda + EventBridge | <\$0.1         | 2분 주기 기준           |
| CloudWatch Logs      | \~\$0          | 수 MB 기준 무료         |
| EC2                  | 인스턴스 스펙에 따라 결정 | t3.medium 권장       |
| S3                   | 저장량에 비례        | 크롤링 결과 보존 정책 적용 가능 |

---

## ✅ 결론

이 구조는 다음을 보장합니다:

* 크롤러 중복 실행 방지
* 무한대기 자동 감지 및 복구
* 3회 재시도 후 안전한 실패 처리
* 상태 기록 및 자동 로그 삭제 (TTL)
* AWS 기반 저비용, 고신뢰 자동화 크롤링 인프라

궁극적으로 Trendlyze의 크롤링 시스템을 운영자 개입 없이 **자가 복구 + 자동 상태 추적** 가능한 수준으로 끌어올릴 수 있습니다.
