"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { API_ENDPOINTS } from "@/utils/config";
import { MessageCircle, Heart, Eye, Menu } from "lucide-react";
import { Swiper, SwiperSlide } from "swiper/react";
import { Pagination, Navigation, Autoplay } from "swiper/modules";
import "swiper/css";
import "swiper/css/pagination";
import "swiper/css/navigation";

// 백엔드에서 받아올 캐릭터 데이터의 타입을 정의합니다.
interface Character {
  id: string;
  name: string;
  description: string;
  tags: string[];
  creator: string;
  imageUrl: string;
  interactions?: number;
  likes?: number;
}

// Fingerprint 생성 함수
async function generateFingerprint(): Promise<string> {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.textBaseline = "top";
    ctx.font = "14px 'Arial'";
    ctx.fillText("Browser Fingerprint", 2, 2);
  }
  const canvasData = canvas.toDataURL();

  const fingerprint = {
    userAgent: navigator.userAgent,
    language: navigator.language,
    platform: navigator.platform,
    screenResolution: `${window.screen.width}x${window.screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    canvasFingerprint: canvasData.substring(0, 100),
  };

  const fingerprintString = JSON.stringify(fingerprint);
  const encoder = new TextEncoder();
  const data = encoder.encode(fingerprintString);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hashHex;
}

export default function CharacterSelection() {
  const router = useRouter();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 컴포넌트가 마운트되면 백엔드에서 캐릭터 목록을 가져옵니다.
    const fetchCharacters = async () => {
      try {
        console.log("캐릭터 데이터를 가져오는 중...");
        const response = await fetch(API_ENDPOINTS.CHARACTERS);
        console.log("응답 상태:", response.status);
        if (!response.ok) {
          throw new Error("캐릭터 목록을 불러오는 데 실패했습니다.");
        }
        const data: Character[] = await response.json();
        console.log("받은 캐릭터 데이터:", data);
        setCharacters(data);
      } catch (err) {
        console.error("에러 발생:", err);
        setError(
          err instanceof Error ? err.message : "알 수 없는 에러가 발생했습니다."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchCharacters();
  }, []); // 빈 배열을 전달하여 한 번만 실행되도록 합니다.

  // 캐릭터 클릭 핸들러
  const handleCharacterClick = async (characterId: string) => {
    try {
      // Fingerprint 생성
      const fingerprint = await generateFingerprint();

      // 사용자 IP는 백엔드에서 자동으로 감지하므로, 임시로 빈 문자열 전송
      // 실제로는 백엔드가 request IP를 사용함
      const response = await fetch(API_ENDPOINTS.CHECK_BLOCK, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fingerprint: fingerprint,
          user_ip: "", // 백엔드에서 실제 IP 추출
        }),
      });

      const data = await response.json();

      if (data.is_blocked) {
        // 차단된 경우 알림 표시
        alert(data.message);
      } else {
        // 차단되지 않은 경우 프로필 페이지로 이동
        router.push(`/chat/${characterId}`);
      }
    } catch (err) {
      console.error("차단 체크 오류:", err);
      // 오류 발생 시 일단 이동 (안전 장치)
      router.push(`/chat/${characterId}`);
    }
  };

  // 로딩 및 에러 UI 개선
  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center min-h-screen text-white">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
        <p className="text-lg">캐릭터를 불러오는 중...</p>
        <p className="text-sm text-gray-400 mt-2">잠시만 기다려주세요</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex justify-center items-center min-h-screen text-red-500">
        에러: {error}
      </div>
    );
  }

  // --- 애니메이션 캐릭터 그리드 레이아웃 ---
  return (
    <main className="min-h-screen flex flex-col items-center p-4">
      <div className="w-full max-w-[390px] h-full pb-4 bg-gray-600 rounded-3xl">
        <div className="p-4 font-nanum">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-extrabold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              캐픽
            </h1>
            <button className="text-white">
              <Menu size={24} />
            </button>
          </div>

          <Swiper
            modules={[Pagination, Navigation, Autoplay]}
            pagination={{ type: "fraction" }}
            navigation={true}
            loop={true}
            autoplay={{
              delay: 3000,
              disableOnInteraction: false,
            }}
            spaceBetween={16}
            slidesPerView={1}
            className="mb-8"
          >
            <SwiperSlide>
              <div
                className="relative h-32 rounded-lg bg-cover bg-center overflow-hidden p-4 flex flex-col justify-end items-start text-white"
                style={{ backgroundImage: "url('/images/cloud.png')" }}
              >
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
                <p className="relative z-10 text-xl font-bold">
                  캐릭터챗에 회화를 끼얹다.
                </p>
              </div>
            </SwiperSlide>
            <SwiperSlide>
              <div
                className="relative h-32 rounded-lg bg-cover bg-center overflow-hidden p-4 flex flex-col justify-end items-start text-white"
                style={{ backgroundImage: "url('/images/ocean.jpg')" }}
              >
                <div className="absolute inset-0 bg-black/50" />
                <p className="relative z-10 text-lg font-bold">
                  AI 꿀보이스와 함께하는 영어 회화
                </p>
              </div>
            </SwiperSlide>
          </Swiper>
        </div>

        <div className="grid grid-cols-2 gap-4 px-4">
          {characters.map((char) => (
            <div
              key={char.id}
              onClick={() => handleCharacterClick(char.id)}
              className="group rounded-2xl overflow-hidden bg-[#2d2d2d] hover:bg-gray-700 transition-colors cursor-pointer"
            >
              <div>
                {/* 캐릭터 이미지 */}
                <div className="relative w-full aspect-[3/4]">
                  <Image
                    src={char.imageUrl}
                    alt={char.name}
                    fill
                    sizes="(max-width: 640px) 50vw, 200px"
                    style={{ objectFit: "cover" }}
                    className="group-hover:scale-105 transition-transform duration-300"
                  />
                  <div className="absolute top-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full flex items-center gap-1">
                    <MessageCircle className="w-3 h-3" />
                    <span>
                      {char.interactions || Math.floor(Math.random() * 1000)}k
                    </span>
                  </div>
                </div>
                {/* 캐릭터 정보 */}
                <div className="p-3 text-white">
                  <h3 className="font-bold text-base truncate mb-1">
                    {char.name}
                  </h3>
                  <p className="text-sm text-gray-400 line-clamp-2 mb-2 h-[40px]">
                    {char.description}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {char.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
