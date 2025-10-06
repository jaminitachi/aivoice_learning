"""
사전 등록자 정보를 CSV 파일로 내보내는 스크립트

사용법:
    python export_registrations.py
"""

import sqlite3
import csv
from datetime import datetime
from pathlib import Path


def export_to_csv():
    """사전 등록자 정보를 CSV로 내보내기"""
    
    # 데이터베이스 연결
    db_path = Path(__file__).parent / "aivoice_beta.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일을 찾을 수 없습니다.")
        print(f"   경로: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 사전 등록자 조회 (세션 정보 포함)
    cursor.execute("""
        SELECT 
            pr.id,
            pr.name,
            pr.email,
            pr.phone,
            pr.notify_email,
            pr.notify_sms,
            pr.created_at,
            pr.session_id,
            s.character_id,
            s.turn_count,
            s.start_time,
            s.end_time
        FROM pre_registrations pr
        LEFT JOIN sessions s ON pr.session_id = s.session_id
        ORDER BY pr.created_at DESC
    """)
    
    registrations = cursor.fetchall()
    
    if not registrations:
        print("⚠️  등록된 사용자가 없습니다.")
        conn.close()
        return
    
    # CSV 파일명 생성 (날짜 포함)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"pre_registrations_{timestamp}.csv"
    csv_path = Path(__file__).parent / csv_filename
    
    # CSV 파일로 저장
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        
        # 헤더
        writer.writerow([
            'ID',
            '이름',
            '이메일',
            '전화번호',
            '이메일알림',
            'SMS알림',
            '등록일시',
            '세션ID',
            '캐릭터',
            '대화턴수',
            '대화시작',
            '대화종료'
        ])
        
        # 데이터
        for reg in registrations:
            writer.writerow([
                reg['id'],
                reg['name'],
                reg['email'],
                reg['phone'] or '',
                '예' if reg['notify_email'] else '아니오',
                '예' if reg['notify_sms'] else '아니오',
                reg['created_at'],
                reg['session_id'],
                reg['character_id'] or '',
                reg['turn_count'] or '',
                reg['start_time'] or '',
                reg['end_time'] or ''
            ])
    
    conn.close()
    
    print(f"✅ 사전 등록자 정보가 CSV로 저장되었습니다!")
    print(f"   파일: {csv_path}")
    print(f"   총 {len(registrations)}명의 등록자")
    
    # 통계 출력
    email_count = sum(1 for r in registrations if r['notify_email'])
    sms_count = sum(1 for r in registrations if r['notify_sms'])
    
    print(f"\n📊 통계:")
    print(f"   이메일 알림 수신 동의: {email_count}명")
    print(f"   SMS 알림 수신 동의: {sms_count}명")


def show_statistics():
    """데이터베이스 통계 출력"""
    
    db_path = Path(__file__).parent / "aivoice_beta.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일을 찾을 수 없습니다.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 총 세션 수
    cursor.execute("SELECT COUNT(*) FROM sessions")
    total_sessions = cursor.fetchone()[0]
    
    # 완료된 세션 수
    cursor.execute("SELECT COUNT(*) FROM sessions WHERE is_completed = 1")
    completed_sessions = cursor.fetchone()[0]
    
    # 사전 등록 수
    cursor.execute("SELECT COUNT(*) FROM pre_registrations")
    total_registrations = cursor.fetchone()[0]
    
    # 캐릭터별 통계
    cursor.execute("""
        SELECT character_id, COUNT(*) as count
        FROM sessions
        GROUP BY character_id
        ORDER BY count DESC
    """)
    character_stats = cursor.fetchall()
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"📊 전체 통계")
    print(f"{'='*60}")
    print(f"총 세션 수: {total_sessions}개")
    print(f"완료된 세션: {completed_sessions}개")
    print(f"완료율: {round(completed_sessions / total_sessions * 100, 2) if total_sessions > 0 else 0}%")
    print(f"사전 등록 수: {total_registrations}명")
    print(f"등록 전환율: {round(total_registrations / completed_sessions * 100, 2) if completed_sessions > 0 else 0}%")
    
    print(f"\n캐릭터별 인기도:")
    for char_id, count in character_stats:
        print(f"  - {char_id}: {count}회")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    print("🚀 사전 등록자 정보 내보내기\n")
    
    # 통계 출력
    show_statistics()
    
    # CSV로 내보내기
    export_to_csv()

