"""SES 이메일 전송 서비스"""
import boto3
from typing import Optional
import traceback


class EmailService:
    """AWS SES를 사용한 이메일 전송 클래스"""

    def __init__(self):
        from ..config import settings
        self.ses = boto3.client('ses', region_name=settings.AWS_REGION)
        self.from_email = settings.SES_FROM_EMAIL
        print(f"✅ SES 이메일 서비스 초기화: {self.from_email}")

    def send_welcome_email(self, to_email: str) -> bool:
        """
        신규 구독자에게 환영 이메일 전송

        Args:
            to_email: 수신자 이메일

        Returns:
            전송 성공 여부
        """
        try:
            subject = "🎉 StockPlay 구독을 환영합니다!"

            # HTML 이메일 본문
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #4c6fff 0%, #667eea 100%);
                        color: white;
                        padding: 30px 20px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                    }}
                    .content {{
                        background: #f8f9fa;
                        padding: 30px 20px;
                        border-radius: 0 0 10px 10px;
                    }}
                    .info-box {{
                        background: white;
                        padding: 20px;
                        margin: 20px 0;
                        border-left: 4px solid #4c6fff;
                        border-radius: 5px;
                    }}
                    .info-box h3 {{
                        margin-top: 0;
                        color: #4c6fff;
                    }}
                    .schedule {{
                        background: #e8f4fd;
                        padding: 15px;
                        margin: 15px 0;
                        border-radius: 5px;
                    }}
                    .footer {{
                        text-align: center;
                        padding: 20px;
                        color: #666;
                        font-size: 14px;
                    }}
                    .unsubscribe {{
                        color: #999;
                        font-size: 12px;
                        margin-top: 20px;
                    }}
                    .unsubscribe a {{
                        color: #4c6fff;
                        text-decoration: none;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📊 StockPlay에 오신 것을 환영합니다!</h1>
                </div>

                <div class="content">
                    <p>안녕하세요, <strong>{to_email}</strong>님!</p>

                    <p>StockPlay AI 투자 리포트 구독을 완료해주셔서 감사합니다.
                    이제 매일 최신 투자 시그널과 AI 분석 리포트를 받아보실 수 있습니다.</p>

                    <div class="info-box">
                        <h3>📬 리포트 발송 일정</h3>
                        <div class="schedule">
                            <p><strong>⏰ 발송 시간:</strong> 매일 오전 9시 (한국 시간 KST)</p>
                            <p><strong>📅 발송 주기:</strong> 평일 매일 (주말 및 공휴일 제외)</p>
                            <p><strong>📊 내용:</strong>
                                <ul>
                                    <li>AI 기반 Top 20 투자 시그널</li>
                                    <li>섹터별 분석 및 성과 지표</li>
                                    <li>KOSPI 시장 동향 및 기술적 분석</li>
                                    <li>개별 종목 상세 PDF 리포트</li>
                                </ul>
                            </p>
                        </div>
                    </div>

                    <div class="info-box">
                        <h3>💡 주요 특징</h3>
                        <ul>
                            <li><strong>AI 분석:</strong> Claude AI가 시장 상황을 분석하여 투자 의견 제공</li>
                            <li><strong>실시간 데이터:</strong> 최신 시장 데이터를 기반으로 매일 업데이트</li>
                            <li><strong>기술적 지표:</strong> Surprise Z-Score, YoY 성장률 등 다양한 지표 제공</li>
                            <li><strong>PDF 리포트:</strong> 전문적인 투자 리포트를 PDF로 제공</li>
                        </ul>
                    </div>

                    <div class="info-box">
                        <h3>⚠️ 유의사항</h3>
                        <p>본 리포트는 AI 분석 기반 참고 자료이며, 투자 판단 및 결과에 대한 책임은 투자자 본인에게 있습니다.
                        StockPlay는 데이터 분석을 제공할 뿐, 투자 손실에 대한 책임을 지지 않습니다.</p>
                    </div>

                    <p style="text-align: center; margin-top: 30px;">
                        <strong>🚀 첫 번째 리포트는 내일 오전 9시에 발송됩니다!</strong>
                    </p>
                </div>

                <div class="footer">
                    <p>감사합니다,<br><strong>StockPlay Team</strong></p>

                    <div class="unsubscribe">
                        <p>구독을 취소하고 싶으신가요?<br>
                        웹사이트의 구독 관리 페이지에서 언제든지 구독을 취소하실 수 있습니다.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # 텍스트 버전 (HTML을 지원하지 않는 이메일 클라이언트용)
            text_body = f"""
StockPlay에 오신 것을 환영합니다!

안녕하세요, {to_email}님!

StockPlay AI 투자 리포트 구독을 완료해주셔서 감사합니다.

[리포트 발송 일정]
⏰ 발송 시간: 매일 오전 9시 (한국 시간 KST)
📅 발송 주기: 평일 매일 (주말 및 공휴일 제외)

[내용]
- AI 기반 Top 20 투자 시그널
- 섹터별 분석 및 성과 지표
- KOSPI 시장 동향 및 기술적 분석
- 개별 종목 상세 PDF 리포트

첫 번째 리포트는 내일 오전 9시에 발송됩니다!

감사합니다,
StockPlay Team

⚠️ 본 리포트는 AI 분석 기반 참고 자료이며, 투자 판단 및 결과에 대한 책임은 투자자 본인에게 있습니다.
            """

            response = self.ses.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                    }
                }
            )

            print(f"✅ 환영 이메일 전송 성공: {to_email} (MessageId: {response['MessageId']})")
            return True

        except Exception as e:
            print(f"❌ 환영 이메일 전송 실패: {to_email} - {type(e).__name__}: {e}")
            print(f"   발신자: {self.from_email}")
            traceback.print_exc()
            return False


# 싱글톤
_email_service = None

def get_email_service() -> EmailService:
    """이메일 서비스 싱글톤"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
