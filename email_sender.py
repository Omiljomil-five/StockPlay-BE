import json
import boto3
import os
from datetime import datetime
from typing import List, Dict, Any

# AWS 클라이언트
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
ses = boto3.client('ses', region_name='ap-northeast-2')
s3 = boto3.client('s3', region_name='ap-northeast-2')

# 환경변수
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'stockplay-main')
SES_FROM_EMAIL = os.environ.get('SES_FROM_EMAIL', 'yyyyjw@naver.com')
S3_REPORT_BUCKET = os.environ.get('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')
API_URL = os.environ.get('API_URL', 'https://4alrpz1t36.execute-api.ap-northeast-2.amazonaws.com/Prod/api')

table = dynamodb.Table(DYNAMODB_TABLE)


def get_active_subscribers() -> List[Dict[str, Any]]:
    """활성 구독자 목록 조회"""
    try:
        response = table.query(
            IndexName='SubscriberIndex',
            KeyConditionExpression='notification_enabled = :enabled',
            ExpressionAttributeValues={':enabled': 1}
        )
        
        subscribers = response.get('Items', [])
        print(f"✅ 활성 구독자: {len(subscribers)}명")
        return subscribers
        
    except Exception as e:
        print(f"❌ 구독자 조회 실패: {e}")
        return []


def generate_report_data() -> Dict[str, Any]:
    """리포트 데이터 생성 (ML 모델 호출)"""
    try:
        import requests
        
        # API 호출하여 최신 시그널 가져오기
        response = requests.get(f"{API_URL}/signals?limit=10")
        data = response.json()
        
        if data['success']:
            print(f"✅ 리포트 데이터 생성 완료")
            return data['data']
        else:
            print(f"⚠️ 리포트 데이터 생성 실패: {data.get('error')}")
            return None
            
    except Exception as e:
        print(f"❌ 리포트 데이터 생성 실패: {e}")
        return None


def send_email(to_email: str, report_data: Dict[str, Any]) -> bool:
    """이메일 발송"""
    try:
        # 이메일 본문 생성
        subject = f"📊 StockPlay 일일 트레이딩 리포트 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # HTML 본문
        html_body = generate_email_html(report_data)
        
        # 텍스트 본문
        text_body = generate_email_text(report_data)
        
        # SES로 이메일 발송
        response = ses.send_email(
            Source=SES_FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"✅ 이메일 발송 성공: {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ 이메일 발송 실패 ({to_email}): {e}")
        return False


def generate_email_html(report_data: Dict[str, Any]) -> str:
    """HTML 이메일 본문 생성 (프리미엄 스타일)"""

    top_picks = report_data.get('topPicks', [])[:5]
    performance = report_data.get('performance', {})

    # 시그널 분포 계산
    all_signals = report_data.get('topPicks', [])
    buy_count = sum(1 for s in all_signals if s.get('signalType') == 'BUY')
    hold_count = sum(1 for s in all_signals if s.get('signalType') == 'HOLD')
    sell_count = sum(1 for s in all_signals if s.get('signalType') == 'SELL')
    total_signals = max(buy_count + hold_count + sell_count, 1)
    buy_pct = buy_count / total_signals * 100
    hold_pct = hold_count / total_signals * 100
    sell_pct = sell_count / total_signals * 100

    # 색상 코딩된 종목 테이블
    picks_html = ""
    for pick in top_picks:
        signal_type = pick.get('signalType', 'BUY')
        ret = pick.get('expectedReturn', 0)
        ret_color = '#10b981' if ret >= 0 else '#ef4444'
        signal_colors = {'BUY': '#10b981', 'HOLD': '#f59e0b', 'SELL': '#ef4444'}
        signal_bg = {'BUY': '#ecfdf5', 'HOLD': '#fffbeb', 'SELL': '#fef2f2'}
        badge_color = signal_colors.get(signal_type, '#6b7280')
        badge_bg = signal_bg.get(signal_type, '#f3f4f6')
        picks_html += f"""
        <tr>
            <td style="padding: 12px 10px; border-bottom: 1px solid #f0f0f0; font-weight: bold;">{pick.get('symbol', '')}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #f0f0f0; color: #666;">{pick.get('sector', '')}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #f0f0f0;">
                <span style="background: {badge_bg}; color: {badge_color}; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{signal_type}</span>
            </td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #f0f0f0; color: {ret_color}; font-weight: bold;">{ret:+.1f}%</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #f0f0f0;">{pick.get('confidenceScore', 0):.0f}%</td>
        </tr>
        """

    avg_return = performance.get('avgReturn', 0)
    win_rate = performance.get('winRate', 0)
    sharpe = performance.get('sharpeRatio', 0)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 640px; margin: 0 auto; padding: 0; background-color: #f5f5f5;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #4c6fff 0%, #667eea 50%, #764ba2 100%); padding: 40px 30px; text-align: center;">
            <h1 style="margin: 0; color: white; font-size: 28px;">StockPlay</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.85); font-size: 14px;">Daily Trading Report - {datetime.now().strftime('%Y.%m.%d')}</p>
        </div>

        <div style="background: white; padding: 30px;">
            <!-- Performance Cards -->
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                <tr>
                    <td style="width: 33%; text-align: center; padding: 20px 10px; background: #f8f9ff; border-radius: 8px 0 0 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: {'#10b981' if avg_return >= 0 else '#ef4444'};">{avg_return:+.1f}%</div>
                        <div style="font-size: 12px; color: #888; margin-top: 4px;">Avg Return</div>
                    </td>
                    <td style="width: 33%; text-align: center; padding: 20px 10px; background: #f8f9ff; border-left: 1px solid #e8e8e8; border-right: 1px solid #e8e8e8;">
                        <div style="font-size: 24px; font-weight: bold; color: #4c6fff;">{win_rate:.0f}%</div>
                        <div style="font-size: 12px; color: #888; margin-top: 4px;">Win Rate</div>
                    </td>
                    <td style="width: 33%; text-align: center; padding: 20px 10px; background: #f8f9ff; border-radius: 0 8px 8px 0;">
                        <div style="font-size: 24px; font-weight: bold; color: #4c6fff;">{sharpe:.2f}</div>
                        <div style="font-size: 12px; color: #888; margin-top: 4px;">Sharpe Ratio</div>
                    </td>
                </tr>
            </table>

            <!-- Signal Distribution Bar -->
            <div style="margin-bottom: 30px;">
                <h3 style="color: #333; font-size: 14px; margin-bottom: 10px;">Signal Distribution</h3>
                <div style="display: flex; height: 28px; border-radius: 14px; overflow: hidden; background: #f0f0f0;">
                    <div style="width: {buy_pct:.0f}%; background: #10b981; display: flex; align-items: center; justify-content: center;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{'BUY ' + str(buy_count) if buy_pct > 15 else ''}</span>
                    </div>
                    <div style="width: {hold_pct:.0f}%; background: #f59e0b; display: flex; align-items: center; justify-content: center;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{'HOLD ' + str(hold_count) if hold_pct > 15 else ''}</span>
                    </div>
                    <div style="width: {sell_pct:.0f}%; background: #ef4444; display: flex; align-items: center; justify-content: center;">
                        <span style="color: white; font-size: 11px; font-weight: bold;">{'SELL ' + str(sell_count) if sell_pct > 15 else ''}</span>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: #888;">
                    <span>BUY {buy_count} ({buy_pct:.0f}%)</span>
                    <span>HOLD {hold_count} ({hold_pct:.0f}%)</span>
                    <span>SELL {sell_count} ({sell_pct:.0f}%)</span>
                </div>
            </div>

            <!-- Top 5 Picks Table -->
            <h2 style="color: #333; font-size: 16px; margin-bottom: 15px;">Top 5 Picks</h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                <thead>
                    <tr style="background-color: #4c6fff;">
                        <th style="padding: 12px 10px; text-align: left; color: white; font-size: 12px;">Symbol</th>
                        <th style="padding: 12px 10px; text-align: left; color: white; font-size: 12px;">Sector</th>
                        <th style="padding: 12px 10px; text-align: left; color: white; font-size: 12px;">Signal</th>
                        <th style="padding: 12px 10px; text-align: left; color: white; font-size: 12px;">Return</th>
                        <th style="padding: 12px 10px; text-align: left; color: white; font-size: 12px;">Conf.</th>
                    </tr>
                </thead>
                <tbody>
                    {picks_html}
                </tbody>
            </table>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://dj4zhs98x0113.cloudfront.net/reports" style="display: inline-block; background: linear-gradient(135deg, #4c6fff, #667eea); color: white; padding: 14px 40px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px;">
                    View Full Report
                </a>
            </div>
        </div>

        <!-- Disclaimer -->
        <div style="padding: 20px 30px; background-color: #fff8e1; border-top: 3px solid #ffc107;">
            <p style="margin: 0; color: #856404; font-size: 12px;">
                ⚠️ This report is for reference only. Investment decisions and outcomes are the sole responsibility of the investor.
            </p>
        </div>

        <!-- Footer -->
        <div style="padding: 20px; text-align: center; color: #999; font-size: 11px;">
            <p style="margin: 0;">© 2025 StockPlay. All rights reserved.</p>
            <p style="margin: 5px 0 0 0;">
                <a href="https://dj4zhs98x0113.cloudfront.net/subscribe" style="color: #4c6fff; text-decoration: none;">Manage Subscription</a>
            </p>
        </div>
    </body>
    </html>
    """

    return html


def generate_email_text(report_data: Dict[str, Any]) -> str:
    """텍스트 이메일 본문 생성"""
    
    top_picks = report_data.get('topPicks', [])[:5]
    performance = report_data.get('performance', {})
    
    text = f"""
StockPlay 일일 트레이딩 리포트
{datetime.now().strftime('%Y-%m-%d')}

오늘의 Top 5 추천 종목:

"""
    
    for i, pick in enumerate(top_picks, 1):
        text += f"{i}. {pick['symbol']} ({pick['sector']})\n"
        text += f"   예상수익률: {pick['expectedReturn']}% | 신뢰도: {pick['confidenceScore']}%\n\n"
    
    text += f"""
성과 지표:
- 평균 수익률: {performance.get('avgReturn', 0)}%
- 승률: {performance.get('winRate', 0)}%
- Sharpe Ratio: {performance.get('sharpeRatio', 0)}

⚠️ 본 리포트는 투자 참고용이며, 투자 판단의 책임은 투자자 본인에게 있습니다.

© 2025 StockPlay. All rights reserved.
    """
    
    return text


def lambda_handler(event, context):
    """Lambda 핸들러"""
    
    print("=" * 80)
    print("📧 이메일 자동 발송 시작")
    print(f"⏰ 실행 시간: {datetime.now().isoformat()}")
    print("=" * 80)
    
    try:
        # 1. 활성 구독자 조회
        subscribers = get_active_subscribers()
        
        if not subscribers:
            print("⚠️ 활성 구독자가 없습니다.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': '활성 구독자가 없습니다.'})
            }
        
        # 2. 리포트 데이터 생성
        report_data = generate_report_data()
        
        if not report_data:
            print("❌ 리포트 데이터 생성 실패")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': '리포트 데이터 생성 실패'})
            }
        
        # 3. 각 구독자에게 이메일 발송
        success_count = 0
        fail_count = 0
        
        for subscriber in subscribers:
            email = subscriber.get('email')
            if email:
                if send_email(email, report_data):
                    success_count += 1
                else:
                    fail_count += 1
        
        # 4. 결과 반환
        result = {
            'total': len(subscribers),
            'success': success_count,
            'fail': fail_count,
            'timestamp': datetime.now().isoformat()
        }
        
        print("=" * 80)
        print(f"✅ 이메일 발송 완료")
        print(f"   - 총 {result['total']}명")
        print(f"   - 성공: {result['success']}명")
        print(f"   - 실패: {result['fail']}명")
        print("=" * 80)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        print(f"❌ Lambda 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }