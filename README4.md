1. EventBridge
2. Lambda
3. EC2
- ✅ 1. Hub Instance (제어 + 모니터링 + Node 생성)

| 항목     | 추천 인스턴스                         |
| ------ | ------------------------------- |
| **역할** | SQS 할당, DynamoDB 감시, Node 생성/종료 |
| **추천** | `t3.small` 또는 `t3a.small`       |
| **이유** |                                 |

* 약간의 CPU와 메모리가 필요 (감시 루프 + EC2 생성 등)
* spot 가능, 운영시간 매우 짧음
* 동시 처리 많지 않음 (비용 효율 중심)
```
☑ EBS는 gp3, 8GB 정도면 충분

```

- ✅ 2. Node Instance (실제 크롤링 실행, 브라우저 포함)
| 항목              | 추천 인스턴스                            |
| --------------- | ---------------------------------- |
| **역할**          | Selenium 실행, S3 업로드, EFS 접근        |
| **추천 (x86 기반)** | `t3.small`, `t3.medium` *(기본 추천)*  |
| **ARM 호환 시**    | `t4g.small`, `t4g.medium` *(더 저렴)* |
| **이유**          |                                    |
크롬 실행 시 최소 2vCPU / 2GB RAM 필요
headless=new + --disable-gpu 설정 시도 효율적
Spot 인스턴스 사용 강력 추천
```
💡 크롬 구동 전 free -m 체크해서 메모리 부족 대비
Node 수는 **사이트 수 / 병렬 수량(예: 10~20)**로 조정
```
- ✅ 결론: 추천 조합

| 역할   | 인스턴스                   | 비고              |
| ---- | ---------------------- | --------------- |
| Hub  | `t3.small` (on-demand) | 감시/제어 중심        |
| Node | `t3.small` (spot)      | 병렬 실행, 10\~20대  |


4. SSM
* AWS SSM(Systems Manager)은 EC2 인스턴스를 관리, 제어, 자동화할 수 있는 서비스입니다. 그중에서도 크롤링 오케스트레이터 구조에서 주로 사용하는 기능은 다음과 같습니다:
- ✅ SSM 주요 기능 요약

| 기능                  | 설명                      | 예시                      |
| ------------------- | ----------------------- | ----------------------- |
| **SendCommand**     | EC2에 명령어 전송 (SSH 없이)    | `pkill chrome` 실행       |
| **RunCommand**      | 여러 인스턴스에 스크립트 실행        | 업데이트, 패치, 진단 등          |
| **Session Manager** | SSH 없이 웹 콘솔/CLI로 EC2 접속 | `aws ssm start-session` |
| **Inventory**       | EC2 구성 정보 수집            | 소프트웨어 목록 자동 수집          |
| **Automation**      | EC2 관리 작업 자동화           | 백업, 롤백, 재부팅 등           |

- 🧠 Trendlyze에서의 사용 예시
- 🔸 무한 대기 감지 → 크롤러 강제 종료
```python
ssm.send_command(
    InstanceIds=["i-04abcde..."],
    DocumentName="AWS-RunShellScript",
    Parameters={
        "commands": ["pkill -f 'chrome'"]
    }
)
```
* 🔸 Node EC2에서 자가 종료
```python
aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --instance-ids "i-xxxxx" \
  --parameters 'commands=["shutdown -h now"]'
```
* 🔐 사용 조건
1. EC2 인스턴스에 SSM Agent 설치되어 있어야 함
* 최신 Amazon Linux, Ubuntu는 기본 설치되어 있음
2. IAM Role 필요 (예: AmazonSSMManagedInstanceCore)
```json
{
  "Effect": "Allow",
  "Action": [
    "ssm:SendCommand",
    "ssm:DescribeInstanceInformation"
  ],
  "Resource": "*"
}
```
* ✅ 장점
- 🔐 SSH 없이 보안성 향상
- 🛠 상태 모니터링 없이 원격 명령 가능
- ☁ CloudWatch와 통합 가능 (로그 수집)
