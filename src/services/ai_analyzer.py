"""Claude AI 분석 서비스"""
import os
from typing import Dict, Any, Optional


def generate_ai_analysis(signal_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Claude AI를 사용한 시그널 분석

    Args:
        signal_data: 시그널 데이터

    Returns:
        AI 분석 결과 딕셔너리 또는 None
    """
    try:
        from anthropic import Anthropic

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다. AI 분석을 건너뜁니다.")
            return None

        client = Anthropic(api_key=api_key)

        # 프롬프트 생성
        prompt = f"""당신은 주식 투자 전문 애널리스트입니다. 다음 데이터를 분석하여 한국어로 전문적인 투자 리포트를 작성해주세요.

**종목 정보:**
- 종목명: {signal_data.get('companyName', 'N/A')}
- 종목 코드: {signal_data.get('symbol', 'N/A')}
- 업종: {signal_data.get('sector', 'N/A')}

**시그널 분석:**
- 시그널 타입: {signal_data.get('signalType', 'N/A')}
- 예측 기간: {signal_data.get('period', 'N/A')}
- 예상 수익률: {signal_data.get('expectedReturn', 0):.2f}%
- KOSPI 대비: {signal_data.get('vsKospi', 0):.2f}%
- Surprise Z-Score: {signal_data.get('surpriseZ', 0):.2f}
- YoY 성장률: {signal_data.get('yoyGrowth', 0):.2f}%
- 신뢰도 점수: {signal_data.get('confidenceScore', 0):.1f}

다음 섹션으로 분석을 작성해주세요:
1. **시장 개요** (3-4문장): 현재 시장 상황과 해당 업종의 전반적인 상황
2. **투자 의견** (4-5문장): 종목에 대한 상세한 투자 의견 및 근거
3. **리스크 분석** (3-4문장): 주의해야 할 리스크 요인들
4. **기술적 분석** (3-4문장): 지표 해석 및 기술적 관점

각 섹션은 명확하게 구분하고 전문적이면서도 이해하기 쉽게 작성해주세요."""

        # Claude API 호출
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # 응답 파싱
        response_text = message.content[0].text

        # 섹션별로 분리 (간단한 파싱)
        sections = {
            'overview': '',
            'investment_opinion': '',
            'risk_analysis': '',
            'technical_analysis': ''
        }

        lines = response_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 섹션 제목 감지
            if '시장 개요' in line or 'market' in line.lower():
                current_section = 'overview'
                continue
            elif '투자 의견' in line or 'investment' in line.lower():
                current_section = 'investment_opinion'
                continue
            elif '리스크' in line or 'risk' in line.lower():
                current_section = 'risk_analysis'
                continue
            elif '기술적' in line or 'technical' in line.lower():
                current_section = 'technical_analysis'
                continue

            # 내용 추가
            if current_section and line:
                sections[current_section] += line + ' '

        # 빈 섹션 채우기 (파싱 실패 시)
        if not any(sections.values()):
            # 전체 텍스트를 4등분
            paragraphs = [p.strip() for p in response_text.split('\n\n') if p.strip()]
            if len(paragraphs) >= 4:
                sections['overview'] = paragraphs[0]
                sections['investment_opinion'] = paragraphs[1]
                sections['risk_analysis'] = paragraphs[2]
                sections['technical_analysis'] = paragraphs[3]
            else:
                # 기본 값
                sections['overview'] = response_text[:300]
                sections['investment_opinion'] = response_text[300:600] if len(response_text) > 300 else response_text
                sections['risk_analysis'] = response_text[600:900] if len(response_text) > 600 else "리스크를 주의 깊게 모니터링하고 있습니다."
                sections['technical_analysis'] = response_text[900:] if len(response_text) > 900 else "기술적 지표가 양호합니다."

        print("✅ Claude AI 분석 완료")
        return sections

    except ImportError:
        print("⚠️ anthropic 패키지가 설치되지 않았습니다.")
        return None
    except Exception as e:
        print(f"❌ AI 분석 실패: {e}")
        return None


def get_fallback_analysis(signal_data: Dict[str, Any]) -> Dict[str, str]:
    """AI 분석 실패 시 기본 분석 반환"""
    signal_type = signal_data.get('signalType', 'BUY')
    expected_return = signal_data.get('expectedReturn', 0)
    vs_kospi = signal_data.get('vsKospi', 0)
    sector = signal_data.get('sector', '업종')

    if signal_type == 'BUY':
        opinion = f"긍정적인 투자 기회로 판단됩니다. 예상 수익률 {expected_return:.1f}%로 KOSPI 대비 {vs_kospi:.1f}%p 우수한 성과가 기대됩니다."
        risk = "시장 변동성과 업종 특성을 고려한 위험 관리가 필요합니다."
    elif signal_type == 'HOLD':
        opinion = f"현재 시점에서는 관망이 적절합니다. 시장 상황을 주시하며 추가 진입 시점을 모색할 필요가 있습니다."
        risk = "단기적 변동성에 주의하며 장기 관점에서 접근해야 합니다."
    else:  # SELL
        opinion = f"현재 밸류에이션이 높아 차익 실현을 고려할 시점입니다. KOSPI 대비 상대적으로 약세가 예상됩니다."
        risk = "추가 하락 가능성을 고려하여 손절 라인을 설정하는 것이 중요합니다."

    return {
        'overview': f"{sector} 업종은 현재 시장에서 주목받고 있습니다. 최근 지표들이 양호한 흐름을 보이고 있으며, 투자자들의 관심이 높아지고 있습니다.",
        'investment_opinion': opinion,
        'risk_analysis': risk,
        'technical_analysis': f"Surprise Z-Score {signal_data.get('surpriseZ', 0):.2f}로 {signal_type} 시그널이 발생했습니다. YoY 성장률 {signal_data.get('yoyGrowth', 0):.1f}%를 기록하고 있으며, 기술적 지표들이 우호적인 모습을 보이고 있습니다."
    }
