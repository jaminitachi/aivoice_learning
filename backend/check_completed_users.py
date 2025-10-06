#!/usr/bin/env python3
"""
완료된 세션 확인 스크립트
"""

import os
from database import db

print("\n" + "="*60)
print("📊 완료된 세션 확인")
print("="*60 + "\n")

try:
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # 완료된 세션 조회
    cursor.execute("""
        SELECT 
            session_id,
            character_id,
            turn_count,
            is_completed,
            is_blocked,
            user_ip,
            fingerprint,
            start_time,
            end_time
        FROM sessions
        WHERE is_completed = TRUE
        ORDER BY end_time DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    if not results:
        print("⚠️  완료된 세션이 없습니다!")
    else:
        print(f"✅ 완료된 세션: {len(results)}개\n")
        
        for idx, row in enumerate(results, 1):
            session_id, character_id, turn_count, is_completed, is_blocked, user_ip, fingerprint, start_time, end_time = row
            print(f"{idx}. 세션 ID: {session_id}")
            print(f"   캐릭터: {character_id}")
            print(f"   턴 수: {turn_count}")
            print(f"   완료 여부: {is_completed}")
            print(f"   차단 여부: {is_blocked}")
            print(f"   IP: {user_ip}")
            print(f"   Fingerprint: {fingerprint[:16] if fingerprint else 'None'}...")
            print(f"   시작: {start_time}")
            print(f"   종료: {end_time}")
            print()
    
    conn.close()
    
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

print("="*60)

