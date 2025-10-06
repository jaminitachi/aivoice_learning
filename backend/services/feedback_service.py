"""
피드백 생성 서비스

사용자의 대화 내용을 분석하여 영어 학습 피드백을 제공합니다.
Grok LLM을 사용하여 문법 개선 및 자연스러운 표현을 제안합니다.
"""

from typing import List, Dict, Any, Optional
import json
from services.llm_service import get_grok_client


# 실시간 단일 문장 평가 프롬프트
REALTIME_EVALUATION_PROMPT = """You are an expert English teacher. Analyze the following student's English sentence from a SPOKEN CONVERSATION.

Student's sentence: "{user_text}"

Evaluate the sentence for:

1. **Grammar Issue** (문법 문제): 
   - ONLY if there's an actual grammar error (wrong tense, subject-verb agreement, wrong article, etc.)
   - Example: "I want go school" → wrong (missing "to")
   - Example: "She don't like it" → wrong (should be "doesn't")
   
2. **Naturalness Issue** (자연스러움 문제):
   - Grammatically correct but sounds awkward/unnatural to native speakers
   - Better native-like alternatives exist
   - Example: "I think that is good" → correct but "I think it's good" sounds more natural

CRITICAL RULES FOR SPOKEN CONVERSATION:
- **DO NOT flag conversational/colloquial expressions as grammar errors**
- Short answers like "Absolutely, pork" or "Sure, coffee" are NATURAL in conversation
- Fragment answers in response to questions are ACCEPTABLE (e.g., "Because I love it" as a standalone answer)
- Ellipsis (omitting subject/verb when context is clear) is NORMAL in spoken English
- Only flag ACTUAL errors that would confuse meaning or sound wrong to native speakers

IMPORTANT: 
- Be LENIENT with spoken conversation style
- Only report issues if they actually harm clarity or sound wrong
- If the sentence is natural for spoken conversation, set has_issues to false
- Provide explanations in Korean

Respond in JSON format:
{{
  "has_issues": true/false,
  "user_sentence": "{user_text}",
  "grammar_issue": {{
    "has_issue": true/false,
    "corrected": "corrected version (only if has_issue is true)",
    "explanation": "Korean explanation (only if has_issue is true)"
  }},
  "naturalness_issue": {{
    "has_issue": true/false,
    "suggestion": "more natural expression (only if has_issue is true)",
    "explanation": "Korean explanation (only if has_issue is true)"
  }}
}}"""


async def evaluate_user_message_realtime(user_text: str) -> Optional[Dict[str, Any]]:
    """
    사용자 메시지를 실시간으로 평가 (매 턴마다 호출)
    
    문법 오류나 개선 가능한 표현이 있는 경우만 반환합니다.
    완벽한 문장은 None 반환.
    
    Args:
        user_text: 사용자가 말한 문장
    
    Returns:
        피드백 데이터 또는 None (개선할 것이 없으면)
        {
            "user_sentence": "원본 문장",
            "grammar_issue": {
                "has_issue": bool,
                "corrected": str,
                "explanation": str
            },
            "naturalness_issue": {
                "has_issue": bool,
                "suggestion": str,
                "explanation": str
            }
        }
    """
    try:
        client = get_grok_client()
        
        prompt = REALTIME_EVALUATION_PROMPT.format(user_text=user_text)
        
        response = await client.chat.completions.create(
            model="x-ai/grok-4-fast",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert English teacher. Respond only in valid JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=500,
            extra_body={
                "reasoning": {
                    "enabled": True
                }
            }
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 파싱
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        evaluation = json.loads(result_text)
        
        # 개선할 것이 있는 경우만 반환
        if evaluation.get("has_issues", False):
            return evaluation
        
        return None
        
    except Exception as e:
        print(f"⚠️  실시간 평가 오류: {e}")
        return None


async def generate_overall_assessment(feedback_items: List[Dict]) -> Dict[str, Any]:
    """
    전반적 평가 생성 - 피드백 리스트를 분석하여 사용자의 주요 약점 파악
    
    Args:
        feedback_items: 실시간으로 수집된 피드백 항목들 (문장별 통합 구조)
    
    Returns:
        전반적 평가 데이터
    """
    try:
        client = get_grok_client()
        
        # 피드백 항목들을 상세하게 포맷팅
        feedback_details = []
        grammar_count = 0
        naturalness_count = 0
        
        for item in feedback_items:
            user_sentence = item.get("user_sentence", "")
            grammar_issue = item.get("grammar_issue", {})
            naturalness_issue = item.get("naturalness_issue", {})
            
            issues = []
            
            if grammar_issue.get("has_issue", False):
                grammar_count += 1
                issues.append(f"문법: '{grammar_issue.get('corrected', '')}' ({grammar_issue.get('explanation', '')})")
            
            if naturalness_issue.get("has_issue", False):
                naturalness_count += 1
                issues.append(f"자연스러움: '{naturalness_issue.get('suggestion', '')}' ({naturalness_issue.get('explanation', '')})")
            
            if issues:
                feedback_details.append(f"  - \"{user_sentence}\" → {', '.join(issues)}")
        
        feedback_summary = "\n".join(feedback_details) if feedback_details else "  (모두 완벽한 문장!)"
        
        prompt = f"""You are an expert English teacher analyzing a student's conversation performance.

**Collected Feedback Details:**

Total Issues Found:
- Grammar issues: {grammar_count}개
- Naturalness issues: {naturalness_count}개

Detailed Feedback:
{feedback_summary}

**Task:** 
Analyze the patterns in the feedback above and identify the student's **main weaknesses**. 
Don't just say "몇 개의 문법 오류" or "몇 개의 표현이 부자연스럽다".

Instead, look for patterns like:
- Are there repeated tense errors? (시제 오류가 반복되는가?)
- Are there issues with articles (a/an/the)? (관사 사용 문제가 있는가?)
- Are there preposition mistakes? (전치사 실수가 있는가?)
- Is sentence structure awkward? (문장 구조가 어색한가?)
- Are there vocabulary choice issues? (어휘 선택 문제가 있는가?)
You don't have to follow this exactly. Please analyze the main weaknesses, focusing on aspects like grammar and naturalness.
Provide an insightful analysis in Korean:

1. **Strengths** (잘한 점): What did the student do well?
2. **Main Weaknesses** (주요 약점): Based on the patterns you see in the feedback, what are the specific areas this student needs to focus on? Be specific and analytical.
3. **Actionable Advice** (구체적 조언): Concrete steps to improve these weaknesses
4. **Encouragement** (격려): A warm, motivating message

Also provide scores (0-100):
- Grammar score: Based on severity and frequency of grammar errors
- Fluency score: Based on naturalness and expression issues

Respond in JSON format:
{{
  "strengths": "Korean description of strengths",
  "main_weaknesses": "Korean description of specific patterns and main weaknesses identified",
  "actionable_advice": "Korean description of concrete improvement steps",
  "encouragement": "Korean encouraging message",
  "scores": {{
    "grammar": integer (0-100),
    "fluency": integer (0-100)
  }}
}}"""
        
        response = await client.chat.completions.create(
            model="x-ai/grok-4-fast",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert English teacher who identifies learning patterns. Respond in valid JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1000,
            extra_body={
                "reasoning": {
                    "enabled": True
                }
            }
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 파싱
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        assessment = json.loads(result_text)
        return assessment
        
    except Exception as e:
        print(f"⚠️  전반적 평가 생성 오류: {e}")
        # 기본값 반환
        grammar_issues = sum(1 for item in feedback_items if item.get('grammar_issue', {}).get('has_issue', False))
        naturalness_issues = sum(1 for item in feedback_items if item.get('naturalness_issue', {}).get('has_issue', False))
        
        return {
            "strengths": "대화를 완료하셨습니다!",
            "main_weaknesses": "계속 연습하면 더 나아질 거예요.",
            "actionable_advice": "꾸준히 연습하세요.",
            "encouragement": "훌륭하게 해내셨어요! 계속 연습하세요!",
            "scores": {
                "grammar": max(0, 100 - grammar_issues * 10),
                "fluency": max(0, 100 - naturalness_issues * 10)
            }
        }

