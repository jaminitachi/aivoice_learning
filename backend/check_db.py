"""
SQLite 데이터베이스를 간단하게 확인하는 스크립트

사용법:
    python check_db.py
"""

import sqlite3
from pathlib import Path


def check_database():
    """데이터베이스 내용 확인"""
    
    db_path = Path(__file__).parent / "aivoice_beta.db"
    
    if not db_path.exists():
        print("❌ 데이터베이스 파일이 아직 생성되지 않았습니다.")
        print("   서버를 한 번 실행하면 자동으로 생성됩니다.")
        return
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"\n{'='*70}")
    print(f"📊 데이터베이스 내용 확인")
    print(f"{'='*70}\n")
    
    # 1. 모든 세션 조회
    cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT 10")
    sessions = cursor.fetchall()
    
    print(f"📝 세션 목록 (최근 10개):")
    print("-" * 70)
    if sessions:
        for session in sessions:
            session_id = session["session_id"][:12]
            char = session["character_id"]
            turns = session["turn_count"]
            completed = "✅" if session["is_completed"] else "🔄"
            blocked = "🚫" if session["is_blocked"] else "✅"
            print(f"  ID: {session_id}... | {char:10s} | {turns:2d}턴 | 완료:{completed} | 차단:{blocked}")
    else:
        print("  (데이터 없음)")
    
    # 2. 사전 등록자 조회
    print(f"\n💌 사전 등록자 목록:")
    print("-" * 70)
    cursor.execute("SELECT * FROM pre_registrations ORDER BY created_at DESC")
    registrations = cursor.fetchall()
    
    if registrations:
        for reg in registrations:
            name = reg["name"]
            email = reg["email"]
            phone = reg["phone"] or "(없음)"
            created = reg["created_at"][:19]
            print(f"  {name:10s} | {email:30s} | {phone:15s} | {created}")
    else:
        print("  (데이터 없음)")
    
    # 3. 간단한 통계
    print(f"\n📊 통계:")
    print("-" * 70)
    
    cursor.execute("SELECT COUNT(*) as cnt FROM sessions")
    total_sessions = cursor.fetchone()["cnt"]
    
    cursor.execute("SELECT COUNT(*) as cnt FROM sessions WHERE is_completed = 1")
    completed_sessions = cursor.fetchone()["cnt"]
    
    cursor.execute("SELECT COUNT(*) as cnt FROM pre_registrations")
    total_regs = cursor.fetchone()["cnt"]
    
    print(f"  총 세션: {total_sessions}개")
    print(f"  완료된 세션: {completed_sessions}개")
    print(f"  사전 등록: {total_regs}명")
    
    print(f"\n{'='*70}\n")
    
    conn.close()


if __name__ == "__main__":
    check_database()

