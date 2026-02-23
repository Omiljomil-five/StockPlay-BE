"""이메일 수정 + 리포트 고도화 테스트"""
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────
# 1. Config 테스트
# ──────────────────────────────────────────────
class TestConfig(unittest.TestCase):
    def test_ses_from_email_exists(self):
        """Settings 클래스에 SES_FROM_EMAIL 필드가 존재하고 기본값이 맞는지"""
        from src.config import Settings
        # 환경변수 오염 방지를 위해 새 인스턴스 생성
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('SES_FROM_EMAIL', None)
            s = Settings()
            self.assertTrue(hasattr(s, 'SES_FROM_EMAIL'))
            self.assertEqual(s.SES_FROM_EMAIL, 'yyyyjw@naver.com')

    def test_ses_from_email_env_override(self):
        """환경변수로 오버라이드 가능한지"""
        with patch.dict(os.environ, {'SES_FROM_EMAIL': 'test@test.com'}):
            from src.config import Settings
            s = Settings()
            self.assertEqual(s.SES_FROM_EMAIL, 'test@test.com')


# ──────────────────────────────────────────────
# 2. template.yaml 테스트
# ──────────────────────────────────────────────
class TestTemplateYaml(unittest.TestCase):
    def setUp(self):
        template_path = os.path.join(os.path.dirname(__file__), '..', 'template.yaml')
        with open(template_path, 'r') as f:
            self.content = f.read()

    def test_stockplay_api_has_ses_from_email(self):
        """StockPlayAPI Lambda에 SES_FROM_EMAIL이 있는지"""
        # StockPlayAPI 블록 찾기
        lines = self.content.split('\n')
        in_api_block = False
        in_env_vars = False
        found = False

        for line in lines:
            if 'StockPlayAPI:' in line:
                in_api_block = True
            elif in_api_block and 'EmailSenderFunction:' in line:
                break
            elif in_api_block and 'Variables:' in line:
                in_env_vars = True
            elif in_api_block and in_env_vars and 'SES_FROM_EMAIL' in line:
                found = True
                self.assertIn('yyyyjw@naver.com', line)
                break

        self.assertTrue(found, 'SES_FROM_EMAIL not found in StockPlayAPI environment')

    def test_email_sender_has_ses_from_email(self):
        """EmailSenderFunction에도 SES_FROM_EMAIL이 있는지"""
        lines = self.content.split('\n')
        in_email_block = False
        found = False

        for line in lines:
            if 'EmailSenderFunction:' in line:
                in_email_block = True
            elif in_email_block and 'SES_FROM_EMAIL' in line:
                found = True
                self.assertIn('yyyyjw@naver.com', line)
                break

        self.assertTrue(found, 'SES_FROM_EMAIL not found in EmailSenderFunction')

    def test_both_lambdas_same_email(self):
        """두 Lambda의 SES_FROM_EMAIL이 동일한지"""
        import re
        matches = re.findall(r'SES_FROM_EMAIL:\s*"(.+?)"', self.content)
        self.assertGreaterEqual(len(matches), 2, f'Expected 2+ SES_FROM_EMAIL entries, found {len(matches)}')
        self.assertTrue(all(m == matches[0] for m in matches),
                        f'SES_FROM_EMAIL values differ: {matches}')


# ──────────────────────────────────────────────
# 3. email_sender.py 기본값 테스트
# ──────────────────────────────────────────────
class TestEmailSenderDefaults(unittest.TestCase):
    def test_default_from_email_not_noreply(self):
        """email_sender.py 기본값이 noreply@stockplay.com이 아닌지"""
        email_sender_path = os.path.join(os.path.dirname(__file__), '..', 'email_sender.py')
        with open(email_sender_path, 'r') as f:
            content = f.read()
        self.assertNotIn("noreply@stockplay.com", content)
        self.assertIn("yyyyjw@naver.com", content)


# ──────────────────────────────────────────────
# 4. Subscribe 스키마 테스트
# ──────────────────────────────────────────────
class TestSubscribeSchema(unittest.TestCase):
    def test_email_sent_field_exists(self):
        from src.schemas.subscribe import SubscriptionResponse
        fields = SubscriptionResponse.model_fields
        self.assertIn('email_sent', fields)

    def test_email_sent_optional(self):
        """email_sent는 Optional (기존 응답 호환)"""
        from src.schemas.subscribe import SubscriptionResponse
        resp = SubscriptionResponse(
            email='test@test.com',
            notification_enabled=True,
            created_at='2025-01-01',
            updated_at='2025-01-01',
        )
        self.assertIsNone(resp.email_sent)

    def test_email_sent_with_value(self):
        from src.schemas.subscribe import SubscriptionResponse
        resp = SubscriptionResponse(
            email='test@test.com',
            notification_enabled=True,
            created_at='2025-01-01',
            updated_at='2025-01-01',
            email_sent=True,
        )
        self.assertTrue(resp.email_sent)


# ──────────────────────────────────────────────
# 5. 차트 생성 테스트
# ──────────────────────────────────────────────
MOCK_SIGNAL = {
    'symbol': '005930',
    'companyName': 'Samsung Electronics',
    'sector': 'IT',
    'signalType': 'BUY',
    'period': '1d',
    'expectedReturn': 2.5,
    'vsKospi': 1.2,
    'kospiReturn': 1.3,
    'surpriseZ': 2.1,
    'yoyGrowth': 15.3,
    'confidenceScore': 85.0
}

MOCK_SIGNALS_LIST = [
    {'signalType': 'BUY', 'symbol': 'A', 'sector': 'IT', 'expectedReturn': 3.0},
    {'signalType': 'BUY', 'symbol': 'B', 'sector': 'IT', 'expectedReturn': 2.0},
    {'signalType': 'HOLD', 'symbol': 'C', 'sector': 'Finance', 'expectedReturn': 0.5},
    {'signalType': 'SELL', 'symbol': 'D', 'sector': 'Energy', 'expectedReturn': -1.0},
    {'signalType': 'BUY', 'symbol': 'E', 'sector': 'Healthcare', 'expectedReturn': 1.5},
]


class TestNewCharts(unittest.TestCase):
    def test_signal_distribution_chart(self):
        from src.services.chart_generator import generate_signal_distribution_chart
        result = generate_signal_distribution_chart(MOCK_SIGNALS_LIST)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 1000, 'Chart too small, likely empty')
        # PNG 시그니처 확인
        self.assertTrue(result[:4] == b'\x89PNG', 'Not a valid PNG')

    def test_signal_distribution_empty(self):
        """빈 리스트도 처리 가능한지"""
        from src.services.chart_generator import generate_signal_distribution_chart
        result = generate_signal_distribution_chart([])
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:4] == b'\x89PNG')

    def test_sector_performance_chart(self):
        from src.services.chart_generator import generate_sector_performance_chart
        sector_data = [
            {'sector': 'IT', 'avgReturn': 3.5},
            {'sector': 'Finance', 'avgReturn': -1.2},
            {'sector': 'Energy', 'avgReturn': 0.8},
            {'sector': 'Healthcare', 'avgReturn': 2.1},
        ]
        result = generate_sector_performance_chart(sector_data)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 1000)
        self.assertTrue(result[:4] == b'\x89PNG')

    def test_sector_performance_empty(self):
        from src.services.chart_generator import generate_sector_performance_chart
        result = generate_sector_performance_chart([])
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:4] == b'\x89PNG')

    def test_confidence_gauge(self):
        from src.services.chart_generator import generate_confidence_gauge
        result = generate_confidence_gauge(85.0)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 1000)
        self.assertTrue(result[:4] == b'\x89PNG')

    def test_confidence_gauge_boundaries(self):
        """경계값 테스트 (0, 50, 100, 범위 초과)"""
        from src.services.chart_generator import generate_confidence_gauge
        for score in [0, 25, 50, 75, 100, -10, 150]:
            result = generate_confidence_gauge(score)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result[:4] == b'\x89PNG', f'Failed for score={score}')


# ──────────────────────────────────────────────
# 6. 프리미엄 PDF 생성 테스트
# ──────────────────────────────────────────────
class TestPremiumPdf(unittest.TestCase):
    @patch('src.services.pdf_generator.get_logo_image', return_value=None)
    def test_generate_without_ai(self, mock_logo):
        """AI 분석 없이 PDF 생성"""
        from src.services.pdf_generator import generate_full_report_pdf
        result = generate_full_report_pdf(MOCK_SIGNAL, ai_analysis=None)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 5000, 'PDF too small')
        # PDF 시그니처 확인
        self.assertTrue(result[:5] == b'%PDF-', 'Not a valid PDF')

    @patch('src.services.pdf_generator.get_logo_image', return_value=None)
    def test_generate_with_ai(self, mock_logo):
        """AI 분석 포함 PDF 생성"""
        from src.services.pdf_generator import generate_full_report_pdf
        ai_analysis = {
            'overview': 'This is an AI-generated overview of the stock.',
            'investment_opinion': 'We recommend a BUY position based on current indicators.',
            'risk_analysis': 'Market volatility remains a concern.',
            'technical_analysis': 'Technical indicators are bullish.',
        }
        result = generate_full_report_pdf(MOCK_SIGNAL, ai_analysis=ai_analysis)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 5000)
        self.assertTrue(result[:5] == b'%PDF-')

    @patch('src.services.pdf_generator.get_logo_image', return_value=None)
    def test_pdf_multi_page(self, mock_logo):
        """멀티페이지 확인 (PDF 내부에 PageBreak가 있으므로 크기로 간접 확인)"""
        from src.services.pdf_generator import generate_full_report_pdf
        result = generate_full_report_pdf(MOCK_SIGNAL)
        # 멀티페이지 PDF는 단일 페이지보다 상당히 큼
        self.assertGreater(len(result), 10000, 'PDF likely single page — expected multi-page')

    @patch('src.services.pdf_generator.get_logo_image', return_value=None)
    def test_sell_signal_pdf(self, mock_logo):
        """SELL 시그널 데이터로도 정상 생성되는지"""
        from src.services.pdf_generator import generate_full_report_pdf
        sell_data = {**MOCK_SIGNAL, 'signalType': 'SELL', 'expectedReturn': -3.2, 'vsKospi': -4.5}
        result = generate_full_report_pdf(sell_data)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:5] == b'%PDF-')


# ──────────────────────────────────────────────
# 7. 이메일 HTML 테스트
# ──────────────────────────────────────────────
class TestEmailHtml(unittest.TestCase):
    def test_html_has_signal_badges(self):
        """HTML에 시그널 타입 배지가 포함되는지"""
        # email_sender는 최상위 모듈이므로 직접 import
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from email_sender import generate_email_html

        report_data = {
            'topPicks': [
                {'symbol': '005930', 'sector': 'IT', 'signalType': 'BUY',
                 'expectedReturn': 3.0, 'confidenceScore': 85},
                {'symbol': '000660', 'sector': 'IT', 'signalType': 'SELL',
                 'expectedReturn': -1.5, 'confidenceScore': 70},
            ],
            'performance': {'avgReturn': 2.5, 'winRate': 72, 'sharpeRatio': 1.5}
        }

        html = generate_email_html(report_data)
        self.assertIn('BUY', html)
        self.assertIn('SELL', html)
        self.assertIn('#10b981', html)  # BUY 색상
        self.assertIn('#ef4444', html)  # SELL 색상

    def test_html_has_performance_cards(self):
        from email_sender import generate_email_html
        report_data = {
            'topPicks': [],
            'performance': {'avgReturn': 5.3, 'winRate': 80, 'sharpeRatio': 2.1}
        }
        html = generate_email_html(report_data)
        self.assertIn('Avg Return', html)
        self.assertIn('Win Rate', html)
        self.assertIn('Sharpe Ratio', html)

    def test_html_has_distribution_bar(self):
        from email_sender import generate_email_html
        report_data = {
            'topPicks': [
                {'symbol': 'A', 'sector': 'IT', 'signalType': 'BUY', 'expectedReturn': 1, 'confidenceScore': 80},
                {'symbol': 'B', 'sector': 'IT', 'signalType': 'BUY', 'expectedReturn': 2, 'confidenceScore': 85},
                {'symbol': 'C', 'sector': 'FIN', 'signalType': 'HOLD', 'expectedReturn': 0, 'confidenceScore': 60},
            ],
            'performance': {'avgReturn': 1, 'winRate': 66, 'sharpeRatio': 1.0}
        }
        html = generate_email_html(report_data)
        self.assertIn('Signal Distribution', html)
        self.assertIn('BUY 2', html)
        self.assertIn('HOLD 1', html)

    def test_html_has_cta_button(self):
        from email_sender import generate_email_html
        report_data = {'topPicks': [], 'performance': {}}
        html = generate_email_html(report_data)
        self.assertIn('View Full Report', html)
        self.assertIn('cloudfront.net', html)


# ──────────────────────────────────────────────
# 8. 기존 함수 하위 호환성 테스트
# ──────────────────────────────────────────────
class TestBackwardCompatibility(unittest.TestCase):
    @patch('src.services.pdf_generator.get_logo_image', return_value=None)
    def test_dashboard_pdf_still_works(self, mock_logo):
        """기존 dashboard PDF 함수가 여전히 동작하는지"""
        from src.services.pdf_generator import generate_dashboard_pdf
        result = generate_dashboard_pdf(MOCK_SIGNAL)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result[:5] == b'%PDF-')

    def test_existing_chart_functions_still_work(self):
        """기존 차트 함수들이 여전히 동작하는지"""
        from src.services.chart_generator import (
            generate_surprise_chart,
            generate_kospi_comparison_chart,
        )

        surprise = generate_surprise_chart(MOCK_SIGNAL)
        self.assertTrue(surprise[:4] == b'\x89PNG')

        comparison = generate_kospi_comparison_chart(MOCK_SIGNAL)
        self.assertTrue(comparison[:4] == b'\x89PNG')


if __name__ == '__main__':
    unittest.main(verbosity=2)
