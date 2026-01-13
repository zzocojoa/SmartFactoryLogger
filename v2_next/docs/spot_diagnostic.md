# SPOT 카메라 네트워크 진단 가이드 (PowerShell)

이 가이드는 로컬 서버(192.168.0.7)에서 SPOT 카메라와의 연결 상태를
터미널(PowerShell)을 통해 진단하는 방법을 설명합니다.

아래 명령어를 PowerShell 창에 복사하여 순서대로 실행하세요.

> **중요**: 먼저 `SmartFactory_v1.0.0.exe` 파일이 있는 폴더로 이동해야 합니다.
> 예: `cd C:\SmartFactory` 또는 `cd C:\Users\User\Desktop\SmartFactoryLogger`

---

## 1. 설정된 카메라 IP 확인

먼저 `config.ini` 파일에서 현재 설정된 SPOT 카메라의 IP 주소를 확인합니다.

```powershell
# config.ini 내용 중 [SPOT] 섹션 확인
Get-Content config.ini | Select-String "SPOT" -Context 0,5
```

```powershell
- 결과
PS C:\Users\user\AppData\Roaming\SmartFactoryLogger> Get-Content config.ini | Select-String "SPOT" -Context 0,5
>>

> [SPOT]
  ip = 10.1.10.50
  refreshinterval = 1.0
  imageurl = http://10.1.10.50/image.jpg
  crosshairx = 0.5
  crosshairy = 0.5
> spot = 500
  temp_f =
  temp_b =
  billet =
  billet_temp =
  at_temp =
> spot = False
  temp_f = False
  temp_b = False
  billet = False
  billet_temp = False
  at_temp = False
```

> **참고**: 만약 `config.ini`가 없다면 기본값은 **10.1.10.50**입니다.

---

## 2. Ping 테스트 (기본 연결 확인)

카메라 장비까지 신호가 도달하는지 확인합니다. (IP주소는 위에서 확인한 값으로
변경하세요)

```powershell
# 예: 10.1.10.50으로 Ping 테스트
Test-NetConnection 10.1.10.50
```

```powershell
- 결과
PS C:\Users\user\AppData\Roaming\SmartFactoryLogger> Test-NetConnection 10.1.10.50
>>


ComputerName           : 10.1.10.50
RemoteAddress          : 10.1.10.50
InterfaceAlias         : 이더넷 2
SourceAddress          : 10.1.10.25
PingSucceeded          : True
PingReplyDetails (RTT) : 0 ms
```

- **PingSucceeded: True** → 연결 정상 🟢
- **PingSucceeded: False** → 연결 끊김 🔴 (랜선, 전원, 네트워크 설정 확인 필요)

---

## 3. 포트 테스트 (웹 서버 확인)

카메라의 웹 서버(80번 포트)가 열려 있는지 확인합니다.

```powershell
# 포트 80 접속 테스트
Test-NetConnection 10.1.10.50 -Port 80
```

```powershell
- 결과
PS C:\Users\user\AppData\Roaming\SmartFactoryLogger> Test-NetConnection 10.1.10.50 -Port 80
>>


ComputerName     : 10.1.10.50
RemoteAddress    : 10.1.10.50
RemotePort       : 80
InterfaceAlias   : 이더넷 2
SourceAddress    : 10.1.10.25
TcpTestSucceeded : True
```

- **TcpTestSucceeded: True** → 서비스 정상 🟢
- **TcpTestSucceeded: False** → 포트 닫힘/방화벽 문제 🔴

---

## 4. 이미지 다운로드 속도 측정

실제로 이미지를 가져오는데 걸리는 시간을 측정합니다.

```powershell
# 카메라 직접 접속 속도 (1회)
$ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "Direct Camera Latency: $([Math]::Round($ms,1)) ms"
```

```powershell
- 결과
PS C:\Users\user\AppData\Roaming\SmartFactoryLogger> $ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "Direct Camera Latency: $([Math]::Round($ms,1)) ms"
Direct Camera Latency: 25.4 ms
```

- **100ms 미만**: 매우 좋음 🟢
- **500ms 이상**: 네트워크 느림 🟡
- **에러 발생**: 이미지 주소 틀림 또는 인증 필요 🔴

---

## 5. 백엔드 프록시 테스트 (로컬호스트)

백엔드 서버를 통해 이미지를 잘 가져오는지 확인합니다. (프리페칭 동작 확인)

```powershell
# 백엔드 프록시 속도 (1회)
$ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:8000/api/spot/proxy_image?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "Backend Proxy Latency: $([Math]::Round($ms,1)) ms"
```

```powershell
- 결과
PS C:\Users\user\AppData\Roaming\SmartFactoryLogger> $ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:8000/api/spot/proxy_image?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "Backend Proxy Latency: $([Math]::Round($ms,1)) ms"
Backend Proxy Latency: 79 ms
```

- **10ms 미만**: 프리페칭 정상 동작 중 (캐시 적중) 🟢 (이상적)
- **수백 ms**: 프리페칭 미동작 또는 Cache Miss 🟡
