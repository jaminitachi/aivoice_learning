"""
데이터베이스 관리 모듈

PostgreSQL을 사용하여 세션 추적 및 사전 등록 정보를 저장합니다.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, List, Dict
import json
import os


class Database:
    """PostgreSQL 데이터베이스 관리 클래스"""
    
    def __init__(self):
        """
        데이터베이스 초기화
        
        환경변수 DATABASE_URL을 사용하여 Railway PostgreSQL에 연결합니다.
        """
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("❌ DATABASE_URL 환경변수가 설정되지 않았습니다!")
        
        print(f"✅ PostgreSQL 연결 준비: {self.database_url[:30]}...")
        self.init_database()
    
    def get_connection(self):
        """데이터베이스 연결 생성"""
        conn = psycopg2.connect(self.database_url)
        return conn
    
    def init_database(self):
        """데이터베이스 테이블 생성"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 세션 추적 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                character_id TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                turn_count INTEGER DEFAULT 0,
                is_completed BOOLEAN DEFAULT FALSE,
                is_blocked BOOLEAN DEFAULT FALSE,
                conversation_history TEXT,
                feedback_data TEXT,
                user_ip TEXT,
                user_agent TEXT,
                fingerprint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 사전 등록 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pre_registrations (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                notify_email BOOLEAN DEFAULT TRUE,
                notify_sms BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        """)
        
        # 사용자 활동 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                activity_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"✅ PostgreSQL 데이터베이스 초기화 완료")
    
    # --- 세션 관련 메서드 ---
    
    def create_session(
        self, 
        session_id: str, 
        character_id: str,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        fingerprint: Optional[str] = None
    ) -> bool:
        """
        새로운 세션 생성
        
        Args:
            session_id: 세션 ID
            character_id: 캐릭터 ID
            user_ip: 사용자 IP 주소
            user_agent: 사용자 User-Agent
            fingerprint: 브라우저 지문
        
        Returns:
            성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sessions 
                (session_id, character_id, start_time, user_ip, user_agent, fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session_id, character_id, datetime.now(), user_ip, user_agent, fingerprint))
            
            conn.commit()
            conn.close()
            
            print(f"📝 세션 DB 저장: {session_id} (캐릭터: {character_id}, FP: {fingerprint[:8] if fingerprint else 'None'}...)")
            return True
        except Exception as e:
            print(f"⚠️  세션 생성 오류: {e}")
            return False
    
    def update_session_turn(self, session_id: str, turn_count: int) -> bool:
        """
        세션 턴 수 업데이트
        
        Args:
            session_id: 세션 ID
            turn_count: 현재 턴 수
        
        Returns:
            성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sessions 
                SET turn_count = %s
                WHERE session_id = %s
            """, (turn_count, session_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️  턴 수 업데이트 오류: {e}")
            return False
    
    def complete_session(
        self, 
        session_id: str, 
        conversation_history: List[Dict],
        feedback_data: Optional[Dict] = None
    ) -> bool:
        """
        세션 완료 처리
        
        Args:
            session_id: 세션 ID
            conversation_history: 대화 히스토리
            feedback_data: 피드백 데이터
        
        Returns:
            성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sessions 
                SET end_time = %s,
                    is_completed = TRUE,
                    is_blocked = TRUE,
                    conversation_history = %s,
                    feedback_data = %s
                WHERE session_id = %s
            """, (
                datetime.now(),
                json.dumps(conversation_history, ensure_ascii=False),
                json.dumps(feedback_data, ensure_ascii=False) if feedback_data else None,
                session_id
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ 세션 완료 DB 저장: {session_id}")
            return True
        except Exception as e:
            print(f"⚠️  세션 완료 처리 오류: {e}")
            return False
    
    def is_session_blocked(self, session_id: str) -> bool:
        """
        세션 차단 여부 확인
        
        Args:
            session_id: 세션 ID
        
        Returns:
            차단 여부 (True: 차단됨, False: 활성)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT is_blocked 
                FROM sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return bool(result["is_blocked"])
            return False
        except Exception as e:
            print(f"⚠️  세션 차단 확인 오류: {e}")
            return False
    
    def check_user_ever_completed(
        self, 
        user_ip: Optional[str], 
        fingerprint: Optional[str]
    ) -> bool:
        """
        사용자가 이전에 대화를 완료한 적이 있는지 확인 (영구 차단)
        
        Args:
            user_ip: 사용자 IP 주소 (참고용, 차단에는 사용 안 함)
            fingerprint: 브라우저 지문
        
        Returns:
            True: 이미 완료한 적 있음 (차단), False: 처음이거나 미완료 (허용)
        
        설명:
            - fingerprint만 사용하여 차단 (IP는 공유될 수 있으므로 사용 안 함)
            - is_completed = TRUE인 세션만 체크
            - 캐릭터 구분 없이 아무 캐릭터나 1번이라도 대화했으면 전체 차단
            - 영구 차단 (날짜 제한 없음)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # fingerprint가 없으면 체크 불가 (허용)
            if not fingerprint:
                print(f"⚠️  Fingerprint 없음 - 기본 허용 (IP만으로는 차단하지 않음)")
                conn.close()
                return False
            
            # ✅ Fingerprint만으로 체크 (IP는 사용하지 않음)
            query = """
                SELECT session_id, character_id, end_time, user_ip
                FROM sessions
                WHERE fingerprint = %s
                AND is_completed = TRUE
                ORDER BY end_time DESC
                LIMIT 1
            """
            
            cursor.execute(query, (fingerprint,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # 완료된 세션이 있으면 차단
                completed_character = result["character_id"]
                previous_ip = result["user_ip"]
                print(f"🚫 영구 차단: 이미 '{completed_character}' 캐릭터와 대화 완료")
                print(f"   - 현재 FP: {fingerprint[:16]}...")
                print(f"   - 이전 IP: {previous_ip}, 현재 IP: {user_ip}")
                if previous_ip != user_ip:
                    print(f"   ℹ️  IP는 다르지만 Fingerprint가 일치하여 차단")
                return True
            else:
                # 완료된 세션이 없으면 허용
                print(f"✅ 접근 허용: 첫 대화")
                print(f"   - FP: {fingerprint[:16]}...")
                print(f"   - IP: {user_ip}")
                return False
                
        except Exception as e:
            print(f"⚠️  사용자 완료 확인 오류: {e}")
            # 오류 발생 시 안전하게 허용 (서비스 중단 방지)
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        세션 정보 조회
        
        Args:
            session_id: 세션 ID
        
        Returns:
            세션 정보 딕셔너리 또는 None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return dict(result)
            return None
        except Exception as e:
            print(f"⚠️  세션 조회 오류: {e}")
            return None
    
    # --- 사전 등록 관련 메서드 ---
    
    def create_pre_registration(
        self,
        session_id: str,
        name: str,
        email: str,
        phone: Optional[str] = None,
        notify_email: bool = True,
        notify_sms: bool = False
    ) -> bool:
        """
        사전 등록 정보 저장
        
        Args:
            session_id: 세션 ID
            name: 이름
            email: 이메일
            phone: 전화번호 (선택)
            notify_email: 이메일 알림 수신 여부
            notify_sms: SMS 알림 수신 여부
        
        Returns:
            성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO pre_registrations 
                (session_id, name, email, phone, notify_email, notify_sms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session_id, name, email, phone, notify_email, notify_sms))
            
            conn.commit()
            conn.close()
            
            print(f"✅ 사전 등록 저장: {name} ({email})")
            return True
        except Exception as e:
            print(f"⚠️  사전 등록 저장 오류: {e}")
            return False
    
    def get_all_pre_registrations(self) -> List[Dict]:
        """
        모든 사전 등록 정보 조회
        
        Returns:
            사전 등록 리스트
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT pr.*, s.character_id, s.turn_count
                FROM pre_registrations pr
                LEFT JOIN sessions s ON pr.session_id = s.session_id
                ORDER BY pr.created_at DESC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in results]
        except Exception as e:
            print(f"⚠️  사전 등록 조회 오류: {e}")
            return []
    
    # --- 활동 로그 관련 메서드 ---
    
    def log_activity(
        self,
        session_id: str,
        activity_type: str,
        activity_data: Optional[Dict] = None
    ) -> bool:
        """
        사용자 활동 로그 기록
        
        Args:
            session_id: 세션 ID
            activity_type: 활동 유형 (e.g., 'start', 'turn', 'complete', 'feedback_view')
            activity_data: 활동 관련 데이터
        
        Returns:
            성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO activity_logs 
                (session_id, activity_type, activity_data)
                VALUES (%s, %s, %s)
            """, (
                session_id,
                activity_type,
                json.dumps(activity_data, ensure_ascii=False) if activity_data else None
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️  활동 로그 기록 오류: {e}")
            return False
    
    # --- 통계 조회 메서드 ---
    
    def get_statistics(self) -> Dict:
        """
        전체 통계 조회
        
        Returns:
            통계 데이터
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 총 세션 수
            cursor.execute("SELECT COUNT(*) as total FROM sessions")
            total_sessions = cursor.fetchone()["total"]
            
            # 완료된 세션 수
            cursor.execute("SELECT COUNT(*) as completed FROM sessions WHERE is_completed = TRUE")
            completed_sessions = cursor.fetchone()["completed"]
            
            # 사전 등록 수
            cursor.execute("SELECT COUNT(*) as total FROM pre_registrations")
            total_registrations = cursor.fetchone()["total"]
            
            # 캐릭터별 통계
            cursor.execute("""
                SELECT character_id, COUNT(*) as count
                FROM sessions
                GROUP BY character_id
            """)
            character_stats = {row["character_id"]: row["count"] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "completion_rate": round(completed_sessions / total_sessions * 100, 2) if total_sessions > 0 else 0,
                "total_registrations": total_registrations,
                "character_stats": character_stats
            }
        except Exception as e:
            print(f"⚠️  통계 조회 오류: {e}")
            return {}


# 전역 데이터베이스 인스턴스
db = Database()
