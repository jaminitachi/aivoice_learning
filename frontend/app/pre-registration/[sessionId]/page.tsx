"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { API_ENDPOINTS } from "@/utils/config";
import { CheckCircle, Sparkles, Mail, Phone, User } from "lucide-react";

export default function PreRegistrationPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    notify_email: true,
    notify_sms: false,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(API_ENDPOINTS.PRE_REGISTRATION, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          ...formData,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "사전 등록에 실패했습니다.");
      }

      setIsSuccess(true);

      // 3초 후 홈으로 이동
      setTimeout(() => {
        router.push("/");
      }, 3000);
    } catch (err) {
      console.error("사전 등록 오류:", err);
      setError(
        err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  // 성공 화면
  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-600 via-pink-500 to-orange-400 p-4">
        <div className="max-w-md w-full bg-white/10 backdrop-blur-lg rounded-3xl p-8 text-center shadow-2xl">
          <div className="mb-6 flex justify-center">
            <div className="bg-green-500 rounded-full p-4 animate-bounce">
              <CheckCircle className="w-16 h-16 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white mb-4">등록 완료! </h1>
          <p className="text-white/90 text-lg mb-6">
            정식 오픈 시<br />
            가장 먼저 알려드리겠습니다!
          </p>
          <p className="text-white/70 text-sm">
            잠시 후 홈 화면으로 이동합니다...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-600 via-pink-500 to-orange-400 p-4">
      <div className="max-w-md w-full bg-white/10 backdrop-blur-lg rounded-3xl p-8 shadow-2xl">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="mb-4 flex justify-center">
            <Sparkles className="w-16 h-16 text-yellow-300 animate-pulse" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-3">체험 완료! 👏</h1>
          <p className="text-white/90 text-lg mb-2">
            AI 영어 회화, 어떠셨나요?
          </p>
          <p className="text-white/80 text-sm">
            정식 서비스 오픈 시<br />
            가장 먼저 알림을 받아보세요!
          </p>
        </div>

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 이름 */}
          <div>
            <label className="block text-white/90 text-sm font-medium mb-2">
              <User className="inline w-4 h-4 mr-1" />
              이름 <span className="text-red-300">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 bg-white/20 border border-white/30 rounded-xl text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50 transition"
              placeholder="홍길동"
            />
          </div>

          {/* 이메일 */}
          <div>
            <label className="block text-white/90 text-sm font-medium mb-2">
              <Mail className="inline w-4 h-4 mr-1" />
              이메일 <span className="text-red-300">*</span>
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 bg-white/20 border border-white/30 rounded-xl text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50 transition"
              placeholder="example@email.com"
            />
          </div>

          {/* 전화번호 (선택) */}
          <div>
            <label className="block text-white/90 text-sm font-medium mb-2">
              <Phone className="inline w-4 h-4 mr-1" />
              전화번호 <span className="text-white/50 text-xs">(선택)</span>
            </label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-white/20 border border-white/30 rounded-xl text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50 transition"
              placeholder="010-1234-5678"
            />
          </div>

          {/* 알림 수신 동의 */}
          <div className="space-y-2 pt-2">
            <label className="flex items-center space-x-2 text-white/90 cursor-pointer">
              <input
                type="checkbox"
                name="notify_email"
                checked={formData.notify_email}
                onChange={handleChange}
                className="w-4 h-4 rounded border-white/30 bg-white/20 text-purple-600 focus:ring-2 focus:ring-white/50"
              />
              <span className="text-sm">이메일로 알림 받기</span>
            </label>
            {formData.phone && (
              <label className="flex items-center space-x-2 text-white/90 cursor-pointer">
                <input
                  type="checkbox"
                  name="notify_sms"
                  checked={formData.notify_sms}
                  onChange={handleChange}
                  className="w-4 h-4 rounded border-white/30 bg-white/20 text-purple-600 focus:ring-2 focus:ring-white/50"
                />
                <span className="text-sm">SMS로 알림 받기</span>
              </label>
            )}
          </div>

          {/* 에러 메시지 */}
          {error && (
            <div className="bg-red-500/20 border border-red-300/50 rounded-xl p-3">
              <p className="text-red-100 text-sm">{error}</p>
            </div>
          )}

          {/* 제출 버튼 */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-4 bg-white text-purple-600 font-bold rounded-xl hover:bg-white/90 transition-all transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg"
          >
            {isSubmitting ? "등록 중..." : "알림 받기 🚀"}
          </button>

          {/* 건너뛰기 */}
          <button
            type="button"
            onClick={() => router.push("/")}
            className="w-full py-2 text-white/70 hover:text-white text-sm transition"
          >
            나중에 할게요
          </button>
        </form>

        {/* 개인정보 안내 */}
        <p className="text-white/60 text-xs text-center mt-6">
          입력하신 정보는 서비스 안내 목적으로만 사용되며,
          <br />
          제3자에게 제공되지 않습니다.
        </p>
      </div>
    </div>
  );
}
