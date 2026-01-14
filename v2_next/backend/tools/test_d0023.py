#!/usr/bin/env python
"""
D0023 (메인 압력) 레지스터 진단 스크립트
Melsec PLC의 D0023 응답 시간을 측정합니다.

사용법:
    python test_d0023.py [횟수]
    
예시:
    python test_d0023.py        # 기본 100000회 테스트
    python test_d0023.py 50     # 50회 테스트
    
결과:
    - 콘솔 출력
    - CSV 파일 실시간 저장 (test_d0023_YYYYMMDD_HHMMSS.csv)
"""

import csv
from datetime import datetime
import os
import socket
import sys
import time
from typing import Optional, Tuple

# 설정
EXTRUDER_IP = "192.168.10.10"
EXTRUDER_PORT = 12289
TIMEOUT = 5.0  # 최대 대기 시간 (초)
THRESHOLD = 0.3  # 경고 임계값 (초)


def recv_until(sock: socket.socket, terminator: bytes = b"\r\n", max_bytes: int = 1024) -> bytes:
    """응답을 종료 문자까지 수신"""
    data = bytearray()
    while len(data) < max_bytes:
        try:
            chunk = sock.recv(256)
        except socket.timeout:
            break
        if not chunk:
            break
        data.extend(chunk)
        if terminator in data:
            break
    return bytes(data)


def melsec_read(sock: socket.socket, addr: str, count: int) -> Tuple[Optional[int], float]:
    """
    Melsec ASCII 프로토콜로 레지스터 읽기
    Returns: (값 또는 None, 소요 시간)
    """
    cmd = f"01WRD{addr} {count:02}\r\n".encode()
    
    t_start = time.time()
    try:
        sock.sendall(cmd)
        raw = recv_until(sock)
        elapsed = time.time() - t_start
        
        if not raw:
            return None, elapsed
        
        resp_str = raw.decode("ascii", errors="replace").strip()
        if "OK" not in resp_str:
            return None, elapsed
        
        parts = resp_str.split("OK", 1)
        if len(parts) < 2:
            return None, elapsed
        
        hex_data = parts[1]
        if len(hex_data) >= 4:
            value = int(hex_data[:4], 16)
            return value, elapsed
        
        return None, elapsed
        
    except Exception as e:
        elapsed = time.time() - t_start
        print(f"  [ERROR] {type(e).__name__}: {e}")
        return None, elapsed


def run_test(test_count: int = 100000):
    """D0023 테스트 실행"""
    print("=" * 60)
    print(f"D0023 (메인 압력) 진단 테스트")
    print(f"대상: {EXTRUDER_IP}:{EXTRUDER_PORT}")
    print(f"테스트 횟수: {test_count}회")
    print(f"경고 임계값: {THRESHOLD}초")
    print("=" * 60)
    print()
    
    # CSV 파일 생성 (실시간 저장)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_filename = os.path.join(script_dir, f"test_d0023_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    print(f"[0] CSV 파일 생성: {csv_filename}")
    print("    ※ 다른 프로그램에서 읽기 전용으로 열 수 있습니다.")
    print()
    
    # CSV 파일 열기 (share_delete 모드로 다른 프로세스 읽기 허용)
    csv_file = open(csv_filename, 'w', newline='', encoding='utf-8-sig', buffering=1)
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['순번', '시간', '값(raw)', '값(bar)', '응답시간(s)', '상태'])
    csv_file.flush()
    
    # 연결
    print("[1] PLC 연결 중...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(TIMEOUT)
        sock.connect((EXTRUDER_IP, EXTRUDER_PORT))
        print(f"    ✅ 연결 성공")
    except Exception as e:
        print(f"    ❌ 연결 실패: {e}")
        csv_file.close()
        return
    
    print()
    print("[2] D0023 읽기 테스트 시작...")
    print("-" * 60)
    
    elapsed_list = []
    slow_count = 0
    error_count = 0
    
    try:
        for i in range(test_count):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            value, elapsed = melsec_read(sock, "D0023", 1)
            elapsed_list.append(elapsed)
            
            if value is not None:
                press = value / 10.0
                status = "느림" if elapsed > THRESHOLD else "정상"
                status_icon = "⚠️ 느림!" if elapsed > THRESHOLD else "✅"
                if elapsed > THRESHOLD:
                    slow_count += 1
                print(f"  [{i+1:3d}] 값: {press:6.1f} bar | 시간: {elapsed:.3f}s {status_icon}")
                
                # 실시간 CSV 저장
                csv_writer.writerow([i + 1, timestamp, value, press, round(elapsed, 4), status])
                csv_file.flush()
            else:
                error_count += 1
                print(f"  [{i+1:3d}] ❌ 읽기 실패 | 시간: {elapsed:.3f}s")
                
                # 실시간 CSV 저장
                csv_writer.writerow([i + 1, timestamp, '', '', round(elapsed, 4), '실패'])
                csv_file.flush()
            
            # 다음 테스트 전 짧은 대기
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n[!] 사용자에 의해 테스트 중단됨 (Ctrl+C)")
        test_count = len(elapsed_list)
    
    # 연결 종료
    sock.close()
    csv_file.close()
    
    # 결과 요약
    print("-" * 60)
    print()
    print("[3] 결과 요약")
    print("=" * 60)
    
    if elapsed_list:
        avg_time = sum(elapsed_list) / len(elapsed_list)
        max_time = max(elapsed_list)
        min_time = min(elapsed_list)
        
        print(f"  총 테스트:      {len(elapsed_list)}회")
        print(f"  성공:           {len(elapsed_list) - error_count}회")
        print(f"  실패:           {error_count}회")
        print(f"  느린 응답(>{THRESHOLD}s): {slow_count}회")
        print()
        print(f"  최소 응답 시간: {min_time:.3f}s")
        print(f"  최대 응답 시간: {max_time:.3f}s")
        print(f"  평균 응답 시간: {avg_time:.3f}s")
        print()
        
        if slow_count > 0:
            print("  ⚠️  주의: 느린 응답이 발견되었습니다!")
            print("      PLC 담당자에게 D0023 관련 프로그램 확인을 요청하세요.")
        else:
            print("  ✅ 모든 응답이 정상 범위 내입니다.")
    
    print("=" * 60)
    print()
    print(f"[4] CSV 파일 저장 완료: {csv_filename}")


if __name__ == "__main__":
    count = 100000
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print(f"잘못된 횟수: {sys.argv[1]}")
            print("사용법: python test_d0023.py [횟수]")
            input("\n아무 키나 누르면 종료합니다...")
            sys.exit(1)
    
    run_test(count)
    
    # 창이 바로 닫히지 않도록 대기
    print()
    input("아무 키나 누르면 종료합니다...")
