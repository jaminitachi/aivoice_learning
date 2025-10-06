"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, Home } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { API_ENDPOINTS } from "@/utils/config";

// --- 타입 정의 ---
interface Character {
  id: string;
  name: string;
  description: string;
  tags: string[];
  creator: string;
  imageUrl: string;
  interactions?: string;
  // 상세 정보 필드를 추가합니다. 실제 데이터가 없으므로 임시 데이터를 사용합니다.
  age?: number;
  height?: number;
  weight?: string;
}

interface ProfilePageProps {
  params: {
    characterId: string;
  };
}

// --- 메인 컴포넌트 ---
export default function CharacterProfilePage({ params }: ProfilePageProps) {
  const { characterId } = params;
  const [character, setCharacter] = useState<Character | null>(null);

  useEffect(() => {
    const fetchCharacterInfo = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.CHARACTERS);
        const characters: Character[] = await response.json();
        const currentChar = characters.find((c) => c.id === characterId);
        if (currentChar) {
          // 임시로 상세 정보를 추가합니다.
          setCharacter({
            ...currentChar,
            age: 23,
            height: 173,
            weight: "비밀",
          });
        }
      } catch (error) {
        console.error("Failed to fetch character info:", error);
      }
    };
    fetchCharacterInfo();
  }, [characterId]);

  if (!character) {
    return (
      <div className="flex justify-center items-center h-screen bg-black text-white">
        <p>캐릭터 정보를 불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className="bg-black">
      <div className="w-full max-w-[390px] mx-auto relative bg-[#1c1c1c] text-white min-h-screen">
        {/* 헤더 */}
        <header className="sticky top-0 z-10 flex justify-between items-center mx-auto pt-2 pb-2 bg-[#1c1c1c] border-b border-gray-700">
          <Link href="/" className="p-2">
            <ChevronLeft size={24} />
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2">
              <Home size={22} />
            </Link>
          </div>
        </header>

        {/* 메인 콘텐츠 */}
        <main>
          {/* 캐릭터 이미지 */}
          <div className="relative w-full max-h-[60vh] rounded-b-3xl overflow-hidden">
            <Image
              width={390}
              height={390}
              src={character.imageUrl}
              alt={character.name}
              style={{ objectFit: "cover" }}
              priority
            />
            <div className="absolute top-4 right-4 bg-black/60 text-white text-sm px-3 py-1.5 rounded-lg">
              <span>{character.creator}</span>
            </div>
          </div>

          {/* 캐릭터 정보 */}
          <div className="p-4 space-y-4">
            <h1 className="text-3xl font-bold">{character.name}</h1>
            <p className="text-gray-300 text-lg">{character.description}</p>
            <div className="flex flex-wrap gap-2">
              {character.tags.map((tag) => (
                <span
                  key={tag}
                  className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          {/* 구분선 */}
          <hr className="border-gray-700 mx-4" />
        </main>

        {/* 하단 고정 버튼 */}
        <footer className="absolute bottom-0 left-0 right-0 z-10 bg-gradient-to-t from-black via-black/80 to-transparent p-4">
          <Link href={`/conversation-ws/${characterId}`}>
            <button className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold p-3 rounded-lg transition-colors">
              회화 시작하기
            </button>
          </Link>
        </footer>
      </div>
    </div>
  );
}
