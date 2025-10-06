"use client";

import { useState, useEffect } from "react";
import {
  ChevronLeft,
  CheckCircle,
  XCircle,
  Lightbulb,
  Award,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { API_ENDPOINTS } from "@/utils/config";

// --- 타입 정의 ---
interface GrammarIssue {
  has_issue: boolean;
  corrected?: string;
  explanation?: string;
}

interface NaturalnessIssue {
  has_issue: boolean;
  suggestion?: string;
  explanation?: string;
}

interface FeedbackItem {
  user_sentence: string;
  grammar_issue: GrammarIssue;
  naturalness_issue: NaturalnessIssue;
}

interface OverallAssessment {
  strengths: string;
  main_weaknesses: string;
  actionable_advice: string;
  encouragement: string;
  scores: {
    grammar: number;
    fluency: number;
  };
}

interface FeedbackData {
  feedback_items: FeedbackItem[];
  overall_assessment: OverallAssessment;
}

interface SessionInfo {
  session_id: string;
  character_id: string;
  turn_count: number;
  duration_seconds: number;
  start_time: string;
  end_time: string;
}

interface ConversationMessage {
  speaker: string;
  text: string;
  timestamp: string;
}

interface FeedbackPageProps {
  params: {
    sessionId: string;
  };
}

// --- 메인 컴포넌트 ---
export default function FeedbackPage({ params }: FeedbackPageProps) {
  const { sessionId } = params;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const [conversationHistory, setConversationHistory] = useState<
    ConversationMessage[]
  >([]);

  // 피드백 데이터 로드
  useEffect(() => {
    const fetchFeedback = async () => {
      try {
        setIsLoading(true);
        console.log("📊 피드백 요청 시작:", sessionId);

        const response = await fetch(API_ENDPOINTS.FEEDBACK(sessionId));
        console.log("📊 피드백 응답 상태:", response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("❌ 피드백 로드 실패:", response.status, errorText);
          throw new Error("피드백을 불러올 수 없습니다.");
        }

        const data = await response.json();
        console.log("✅ 피드백 데이터 수신 완료:", data);

        setSessionInfo(data.session_info);
        setFeedback(data.feedback);
        setConversationHistory(data.conversation_history);
      } catch (err) {
        console.error("❌ 피드백 로드 오류:", err);
        setError(err instanceof Error ? err.message : "알 수 없는 오류");
      } finally {
        setIsLoading(false);
      }
    };

    fetchFeedback();
  }, [sessionId]);

  // 시간 포맷팅
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}분 ${secs}초`;
  };

  // 점수에 따른 색상 반환
  const getScoreColor = (score: number): string => {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  // 로딩 중
  if (isLoading) {
    return (
      <div className="relative bg-black min-h-screen">
        {/* 배경 패턴 효과 */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>

        <div className="relative w-full max-w-[390px] mx-auto min-h-screen flex items-center justify-center text-white bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-white text-lg font-semibold">
              피드백을 생성하는 중...
            </p>
            <p className="text-purple-300 text-sm mt-2">잠시만 기다려주세요</p>
          </div>
        </div>
      </div>
    );
  }

  // 에러 발생
  if (error || !sessionInfo || !feedback) {
    return (
      <div className="relative bg-black min-h-screen">
        {/* 배경 패턴 효과 */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>

        <div className="relative w-full max-w-[390px] mx-auto min-h-screen flex items-center justify-center text-white bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900">
          <div className="text-center px-4">
            <XCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">오류 발생</h2>
            <p className="text-purple-200 mb-6">
              {error || "피드백을 불러올 수 없습니다."}
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-2xl font-bold shadow-lg shadow-purple-500/50 transition-all duration-300 hover:scale-105"
            >
              <ChevronLeft className="w-5 h-5" />
              홈으로 돌아가기
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative bg-black min-h-screen">
      {/* 배경 패턴 효과 */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>

      <div className="relative w-full max-w-[390px] mx-auto min-h-screen text-white bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900">
        {/* 헤더 - 글래스모피즘 효과 */}
        <header className="relative backdrop-blur-xl bg-white/5 border-b border-white/10 shadow-lg">
          <div className="flex items-center justify-between pt-2 pb-2 px-4">
            <Link
              href="/"
              className="p-2 rounded-full hover:bg-white/10 transition-all duration-300 hover:scale-110"
            >
              <ChevronLeft className="w-6 h-6" />
            </Link>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white to-purple-200 bg-clip-text text-transparent">
              영어 회화 피드백
            </h1>
            <div className="w-10"></div>
          </div>
        </header>

        {/* 메인 콘텐츠 */}
        <main className="px-4 py-6 space-y-4 pb-20">
          {/* 세션 정보 카드 */}
          <div className="backdrop-blur-lg bg-white/10 border border-white/20 rounded-2xl p-5 shadow-xl">
            <h2 className="text-base font-bold mb-4 flex items-center gap-2 text-white">
              <Clock className="w-5 h-5 text-purple-300" />
              대화 세션 정보
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                <p className="text-xs text-purple-200">총 대화 턴</p>
                <p className="text-xl font-bold text-white">
                  {sessionInfo.turn_count}턴
                </p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                <p className="text-xs text-purple-200">대화 시간</p>
                <p className="text-xl font-bold text-white">
                  {formatDuration(sessionInfo.duration_seconds)}
                </p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                <p className="text-xs text-purple-200">문법 점수</p>
                <p className="text-xl font-bold text-green-400">
                  {feedback.overall_assessment.scores.grammar}점
                </p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                <p className="text-xs text-purple-200">유창성 점수</p>
                <p className="text-xl font-bold text-green-400">
                  {feedback.overall_assessment.scores.fluency}점
                </p>
              </div>
            </div>
          </div>

          {/* 전반적 평가 */}
          <div className="backdrop-blur-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-400/30 rounded-2xl p-5 shadow-xl">
            <h2 className="text-base font-bold mb-4 flex items-center gap-2 text-white">
              <Award className="w-5 h-5 text-yellow-300" />
              전반적 평가
            </h2>
            <div className="space-y-3">
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="font-semibold text-green-300 mb-2">잘한 점</h3>
                <p className="text-purple-100 leading-relaxed text-sm">
                  {feedback.overall_assessment.strengths}
                </p>
              </div>
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="font-semibold text-orange-300 mb-2">
                  주요 약점
                </h3>
                <p className="text-purple-100 leading-relaxed text-sm">
                  {feedback.overall_assessment.main_weaknesses}
                </p>
              </div>
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="font-semibold text-blue-300 mb-2">
                  구체적인 학습 조언
                </h3>
                <p className="text-purple-100 leading-relaxed text-sm">
                  {feedback.overall_assessment.actionable_advice}
                </p>
              </div>
              <div className="bg-gradient-to-r from-purple-600/40 to-pink-600/40 rounded-xl p-4 border-l-4 border-purple-400">
                <p className="text-white font-medium text-sm">
                  {feedback.overall_assessment.encouragement}
                </p>
              </div>
            </div>
          </div>

          {/* 문장별 피드백 */}
          {feedback.feedback_items.length > 0 && (
            <div className="backdrop-blur-lg bg-white/10 border border-white/20 rounded-2xl p-5 shadow-xl">
              <h2 className="text-base font-bold mb-4 flex items-center gap-2 text-white">
                <Lightbulb className="w-5 h-5 text-yellow-300" />
                문장별 피드백
              </h2>
              <div className="space-y-4">
                {feedback.feedback_items.map((item, idx) => (
                  <div
                    key={idx}
                    className="bg-white/5 rounded-xl p-4 border border-white/10"
                  >
                    {/* 사용자 문장 */}
                    <div className="mb-3 pb-3 border-b border-white/10">
                      <p className="text-purple-200 text-xs mb-1">
                        당신의 문장:
                      </p>
                      <p className="text-white font-medium text-base">
                        "{item.user_sentence}"
                      </p>
                    </div>

                    {/* 문법 피드백 */}
                    {item.grammar_issue.has_issue && (
                      <div className="mb-3">
                        <div className="flex items-start gap-2 mb-2">
                          <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <p className="text-purple-200 text-xs">
                              문법 수정:
                            </p>
                            <p className="text-green-300 font-medium text-sm">
                              "{item.grammar_issue.corrected}"
                            </p>
                          </div>
                        </div>
                        <div className="bg-yellow-500/20 rounded-lg p-3 border-l-4 border-yellow-400">
                          <p className="text-xs text-yellow-100">
                            <span className="font-semibold">📚 문법 설명:</span>{" "}
                            {item.grammar_issue.explanation}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* 자연스러움 피드백 */}
                    {item.naturalness_issue.has_issue && (
                      <div>
                        <div className="flex items-start gap-2 mb-2">
                          <CheckCircle className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <p className="text-purple-200 text-xs">
                              더 자연스러운 표현:
                            </p>
                            <p className="text-blue-300 font-medium text-sm">
                              "{item.naturalness_issue.suggestion}"
                            </p>
                          </div>
                        </div>
                        <div className="bg-blue-500/20 rounded-lg p-3 border-l-4 border-blue-400">
                          <p className="text-xs text-blue-100">
                            <span className="font-semibold">💡 설명:</span>{" "}
                            {item.naturalness_issue.explanation}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* 피드백이 없는 경우 */}
                    {!item.grammar_issue.has_issue &&
                      !item.naturalness_issue.has_issue && (
                        <div className="bg-green-500/20 rounded-lg p-3 border-l-4 border-green-400">
                          <p className="text-xs text-green-100">
                            ✅ 완벽한 문장입니다!
                          </p>
                        </div>
                      )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 오류가 없는 경우 */}
          {feedback.feedback_items.length === 0 && (
            <div className="backdrop-blur-lg bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-400/30 rounded-2xl p-6 text-center shadow-xl">
              <CheckCircle className="w-16 h-16 text-green-300 mx-auto mb-4" />
              <h3 className="text-xl font-bold text-green-100 mb-2">
                완벽합니다! 🎉
              </h3>
              <p className="text-green-200">
                문법 오류나 개선할 표현이 없습니다. 훌륭한 영어 실력이에요!
              </p>
            </div>
          )}

          {/* 액션 버튼 */}
          <div className="flex flex-col gap-3 pt-4 pb-4">
            <Link
              href={`/pre-registration/${sessionId}`}
              className="px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-2xl shadow-lg shadow-purple-500/50 transition-all duration-300 hover:scale-105 text-center"
            >
              정식 오픈 알림 받기 🚀
            </Link>
            <Link
              href="/"
              className="px-8 py-3 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-medium rounded-2xl transition-all duration-300 hover:scale-105 text-center"
            >
              나중에 할게요
            </Link>
          </div>
        </main>
      </div>
    </div>
  );
}
