# SPOT realtime image v1.0.21 deployment gate report

> Updated: 2026-08-25
> Candidate version: `1.0.21`
> Build commit: `5971fc4fbdeec07ef65681a945319f0ae12d55cb`
> Classification: `PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY`
> Verdict: `15M_GATE_PASS_120M_TOOLING_HOLD_V1020_RESTORED`

## 1. Candidate identity

| Item | Evidence |
|---|---|
| Installer | `smart-factory-logger-v2 Setup 1.0.21.exe` |
| Installer SHA-256 | `01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A` |
| Authenticode | `NotSigned` |
| Backend bundle SHA-256 | `B818383DF7B035DC73C86E57F0080489B287C958086C8E2C426639C0622CB094` |
| Backend files verified | `1385 / 1385` |
| Extracted `app.asar` SHA-256 | `50734BC222DF943A2DC6605E35EDEA0AD600C909A0A32E4ADEFF2A2A0952C048` |
| Config SHA-256 | `6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E` |

The candidate remains unsigned and is restricted to the owner-controlled internal
canary. Production promotion and external distribution are not allowed.

## 2. Target install gates

| Gate | Result |
|---|---|
| Preinstall kit identity | `PASS` |
| Existing target baseline | `PASS`, v1.0.20, one backend, port 8000 owner matched |
| Rollback installer | `CORRECTED`, v1.0.20 `cd8cfa6...` SHA-256 matched |
| Installed app version/commit | `PASS`, v1.0.21 / `5971fc4...` |
| Installed `app.asar` | `PASS` |
| Installed backend bundle | `PASS`, 1,385 files |
| Config unchanged | `PASS` |
| Operator-live route | `PASS`, HTTP 200 / `image/jpeg` / `operator_live` |

Rollback is fixed to the exact pre-deploy baseline, v1.0.20
`cd8cfa649203494cf087206cf656dc2197107ea1`, using
`C:\Users\user\Desktop\SmartFactory\v1020_cd8cfa6_internal_private_server_deploy_20260821_R3\smart-factory-logger-v2 Setup 1.0.20.exe`
with SHA-256
`F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19`.

## 3. Physical SPOT 15-minute gate

The complete 2026-08-21 19:13-19:28 KST interval passed.

| Check | Result |
|---|---|
| Completion-driven image requests | `2928 / 2928`, failures `0` |
| Average / maximum response | `34.5 ms / 1323 ms` |
| Total SPOT transport | `4908 / 4908`, failures `0` |
| Average total SPOT rate | `5.4533/s`, limit `6/s` |
| Average image upstream rate | `2.6578/s` |
| Pool wait / exhaustion / reuse violation | `0 / 0 / 0` |
| Minimum source-port reuse interval | `75.0 s` |
| Image refresh failure / cache anomaly | `0 / 0` |
| Backend restart | none, PID unchanged |
| Config drift | none |
| Operator visual confirmation | continuous refresh for the full interval; no screen error |

The QA artifact contained 100 `recent_image_errors`, but every listed line was dated
2026-06-29. The script selected recently modified log files and then read the first 100
matching lines from the whole files; it did not filter each line to the observation
window. This is a false positive for the 2026-08-21 canary interval. The artifact's
`blockers` list was empty, current image/transport failure counters were zero, all 2,928
active probes succeeded, and the operator confirmed the complete interval. The first-100
cap remains a log-review coverage limitation and must not be reused as proof for the
120-minute interval.

## 4. 15-minute evidence identity

| File | SHA-256 |
|---|---|
| `spot-15m.json` | `464BF0A540133C5165B7E550430EDA9EDAA07FA866481B43FAD2B0392016A4F8` |
| `spot-config-image-before-15m.json` | `7E7486908045EF4898F44CA474816C647EAC1C5619EAADA6B3DA6445E5C87342` |
| `spot-config-image-after-15m.json` | `1859E0E79C7D24348132B93B8D2EBFA50FBD0166762F7A4F1A16B41C15A6D100` |
| `health-before-15m.json` | `12653336422E897764C47069F7CAE5F2C876B8B27591CDF7D52AB6ED6F982021` |
| `health-after-15m.json` | `9CD044E41D5A42AA72F94275B18AC1CBDB786AA44C5BCD0E836CF6772B883322` |
| `backend-integrity-after-install.json` | `6D077E7944C5670A6990862209C6D7A10935E13B01D920AF3D270538A5147058` |
| `postinstall-bundle-gate.json` | `E42CF3126CD5CC42F38918D0E64CF9C302A860FB00DD8B8030B676EF20147994` |
| `preinstall-summary.json` | `06F076A09D7D659B88A92959769CD1528802EC08E3C0A13F35A6A8329FF32138` |
| `health-before.json` | `2E16E28BD695B5D9125EF11822E4E10DA2D422E0D1781EE72A623D1EE0A97063` |

The operator confirmation is human attestation, not machine-generated evidence. The
120-minute kit binds it separately from the hashed server artifacts.

## 5. 120-minute canary contract

The 120-minute canary uses the passive diagnostic core from
`077b6b1c45b7bf6023d89ba13ecaa54d22acbe70`, bound to the v1.0.21 product and the
15-minute evidence above. It stops on a new `spot_image ConnectTimeout`, keeps a 75-second
post-trigger packet tail, and adds a 30-second console progress display based only on the
local clock and Windows process state. The progress display adds no SPOT or backend HTTP
requests.

Runtime hard failures require rollback. Incomplete packet coverage is an evidence
`HOLD`, not an automatic runtime failure. Missing managed-switch evidence yields
`PASS_WITH_SWITCH_LIMITATION` only when all app, packet, source-port, and operator gates
pass. No result from this unsigned canary automatically permits production promotion.

The corrected schema-v2 field kit was built and independently re-verified from a clean
tooling commit. It binds rollback to the v1.0.20 baseline evidence, calculates request
rates over the installed-state preflight/postflight timestamp window, and classifies a
collector failure without a separate runtime hard gate as `EVIDENCE_HOLD`. The previous
schema-v1 `92395058...` kit is incident evidence only and must not be executed again.

| Kit item | Identity |
|---|---|
| Schema | `spot-realtime-image-v1021-canary-kit-v2` |
| Tooling source commit | `fc29620a9ea0c24ecc8e10a6f7378b2928ed08ea` |
| Diagnostic core source commit | `077b6b1c45b7bf6023d89ba13ecaa54d22acbe70` |
| Package files | `12` |
| ZIP | `SmartFactoryLogger_SPOT_Realtime_Image_v1021_Canary_fc29620a_20260825_001911Z.zip` |
| ZIP length | `76,395` bytes |
| ZIP SHA-256 | `1D9A62D6F13C093A7DF1DC297691265B85A221F0DEAD66093890A95DB6D9755C` |
| Rollback identity | v1.0.20 / `cd8cfa649203494cf087206cf656dc2197107ea1` |
| Counter rate window | `installed-state-preflight-to-postflight` |
| Collector-only failure policy | `evidence-hold` |
| Extracted verifier | `PASS` |
| Analyzer / monitor / collectors / controller self-tests | `PASS` |
| Trigger integration | `PASS`, detection latency `6 ms` in the local fixture |

## 6. Current status

| Gate | Status |
|---|---|
| Target preinstall | `PASS` |
| v1.0.21 installation identity | `PASS` |
| Actual SPOT 15-minute smoke | `PASS` |
| Corrected commit-bound 120-minute kit | `BUILD_AND_VERIFY_PASS`, schema v2 / `fc29620a...` |
| Actual SPOT 120-minute canary | `INVALID_TOOLING_RUN`, stopped after 6.237 seconds |
| Request-rate comparison | `15M_PASS`, first 120M calculation invalid |
| old-ACK/RST risk proxy comparison | `PENDING` |
| source-port pool comparison | `15M_PASS`, `120M_PENDING` |
| Production promotion | `NOT_ALLOWED` |

The first server attempt did not execute a 120-minute observation. The collector stopped
after 6.237 seconds, while the product pre/post counter snapshots spanned 59.4678 seconds.
The controller divided the 332-request counter delta by the collector duration and
reported a false `53.2307/s`; the aligned installed-state window is `5.5829/s`. It also
classified the collector tooling failure as a runtime rollback and pointed at v1.0.16
instead of the actual v1.0.20 pre-deploy baseline. v1.0.20 `cd8cfa6...` was subsequently
restored and validated with unchanged config, one backend/port owner, live SPOT
connectivity, and operator-confirmed image refresh.

The next action is to transfer the corrected ZIP and SHA-256 file to the server, reinstall
the same v1.0.21 product identity, repeat the short identity/visual gate, and only then run
a fresh 120-minute observation. The invalid attempt is retained as incident evidence and
must not be counted as a candidate failure or a successful canary.
