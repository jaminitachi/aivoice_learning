"""
데이터베이스 통계를 조회하는 스크립트

사용법:
    python view_statistics.py
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json


def view_detailed_statistics():
    """상세 통계 조회 및 출력"""
    
    db_path = Path(__file__).parent / "aivoice_beta.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일을 찾을 수 없습니다.")
        print(f"   경로: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"\n{'='*70}")
    print(f"📊 AI 영어 회화 베타 서비스 - 통계 대시보드")
    print(f"{'='*70}\n")
    
    # 1. 전체 세션 통계
    print("📈 세션 통계")
    print("-" * 70)
    
    cursor.execute("SELECT COUNT(*) as total FROM sessions")
    total_sessions = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as completed FROM sessions WHERE is_completed = 1")
    completed_sessions = cursor.fetchone()["completed"]
    
    cursor.execute("SELECT COUNT(*) as blocked FROM sessions WHERE is_blocked = 1")
    blocked_sessions = cursor.fetchone()["blocked"]
    
    print(f"  총 세션 수: {total_sessions}개")
    print(f"  완료된 세션: {completed_sessions}개")
    print(f"  차단된 세션: {blocked_sessions}개")
    print(f"  완료율: {round(completed_sessions / total_sessions * 100, 2) if total_sessions > 0 else 0}%")
    
    # 2. 사전 등록 통계
    print(f"\n💌 사전 등록 통계")
    print("-" * 70)
    
    cursor.execute("SELECT COUNT(*) as total FROM pre_registrations")
    total_registrations = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as email FROM pre_registrations WHERE notify_email = 1")
    email_notifications = cursor.fetchone()["email"]
    
    cursor.execute("SELECT COUNT(*) as sms FROM pre_registrations WHERE notify_sms = 1")
    sms_notifications = cursor.fetchone()["sms"]
    
    print(f"  총 사전 등록 수: {total_registrations}명")
    print(f"  이메일 알림 동의: {email_notifications}명")
    print(f"  SMS 알림 동의: {sms_notifications}명")
    print(f"  등록 전환율: {round(total_registrations / completed_sessions * 100, 2) if completed_sessions > 0 else 0}%")
    
    # 3. 캐릭터별 통계
    print(f"\n🎭 캐릭터별 인기도")
    print("-" * 70)
    
    cursor.execute("""
        SELECT character_id, COUNT(*) as count
        FROM sessions
        GROUP BY character_id
        ORDER BY count DESC
    """)
    character_stats = cursor.fetchall()
    
    if character_stats:
        for idx, row in enumerate(character_stats, 1):
            char_id = row["character_id"]
            count = row["count"]
            percentage = round(count / total_sessions * 100, 1) if total_sessions > 0 else 0
            bar = "█" * int(percentage / 2)
            print(f"  {idx}. {char_id:15s} {count:3d}회 ({percentage:5.1f}%) {bar}")
    else:
        print("  데이터 없음")
    
    # 4. 대화 턴 수 분석
    print(f"\n📊 대화 턴 수 분석")
    print("-" * 70)
    
    cursor.execute("""
        SELECT AVG(turn_count) as avg_turns, 
               MAX(turn_count) as max_turns,
               MIN(turn_count) as min_turns
        FROM sessions
        WHERE turn_count > 0
    """)
    turn_stats = cursor.fetchone()
    
    if turn_stats and turn_stats["avg_turns"]:
        print(f"  평균 대화 턴 수: {round(turn_stats['avg_turns'], 1)}턴")
        print(f"  최대 턴 수: {turn_stats['max_turns']}턴")
        print(f"  최소 턴 수: {turn_stats['min_turns']}턴")
    else:
        print("  데이터 없음")
    
    # 5. 대화 시간 분석
    print(f"\n⏱️  대화 시간 분석")
    print("-" * 70)
    
    cursor.execute("""
        SELECT 
            AVG(CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 AS INTEGER)) as avg_duration,
            MAX(CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 AS INTEGER)) as max_duration,
            MIN(CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 AS INTEGER)) as min_duration
        FROM sessions
        WHERE end_time IS NOT NULL
    """)
    duration_stats = cursor.fetchone()
    
    if duration_stats and duration_stats["avg_duration"]:
        print(f"  평균 대화 시간: {round(duration_stats['avg_duration'], 1)}분")
        print(f"  최대 대화 시간: {duration_stats['max_duration']}분")
        print(f"  최소 대화 시간: {duration_stats['min_duration']}분")
    else:
        print("  데이터 없음")
    
    # 6. 최근 활동
    print(f"\n🕒 최근 활동 (최근 5건)")
    print("-" * 70)
    
    cursor.execute("""
        SELECT session_id, character_id, turn_count, start_time, is_completed
        FROM sessions
        ORDER BY start_time DESC
        LIMIT 5
    """)
    recent_sessions = cursor.fetchall()
    
    if recent_sessions:
        for session in recent_sessions:
            session_id = session["session_id"][:12]
            char_id = session["character_id"]
            turns = session["turn_count"]
            start = session["start_time"][:19]
            status = "✅ 완료" if session["is_completed"] else "🔄 진행 중"
            print(f"  [{start}] {char_id:10s} | {turns:2d}턴 | {status} | ID: {session_id}...")
    else:
        print("  데이터 없음")
    
    # 7. 최근 사전 등록자
    print(f"\n💌 최근 사전 등록자 (최근 5건)")
    print("-" * 70)
    
    cursor.execute("""
        SELECT name, email, created_at
        FROM pre_registrations
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_registrations = cursor.fetchall()
    
    if recent_registrations:
        for reg in recent_registrations:
            name = reg["name"]
            email = reg["email"]
            created = reg["created_at"][:19]
            print(f"  [{created}] {name} ({email})")
    else:
        print("  데이터 없음")
    
    print(f"\n{'='*70}")
    print(f"📅 조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    conn.close()


if __name__ == "__main__":
    view_detailed_statistics()

