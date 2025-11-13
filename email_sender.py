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
SES_FROM_EMAIL = os.environ.get('SES_FROM_EMAIL', 'noreply@stockplay.com')
S3_REPORT_BUCKET = os.environ.get('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')
API_URL = os.environ.get('API_URL', 'https://rwcdhytnni.execute-api.ap-northeast-2.amazonaws.com/Prod/api')

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
    """HTML 이메일 본문 생성"""
    
    top_picks = report_data.get('topPicks', [])[:5]
    performance = report_data.get('performance', {})
    
    picks_html = ""
    for pick in top_picks:
        picks_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{pick['symbol']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{pick['sector']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee; color: #10b981;">{pick['expectedReturn']}%</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{pick['confidenceScore']}%</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1 style="margin: 0;">📊 StockPlay</h1>
            <p style="margin: 10px 0 0 0;">일일 트레이딩 리포트</p>
        </div>
        
        <div style="margin-top: 30px;">
            <h2 style="color: #333;">🎯 오늘의 Top 5 추천 종목</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 10px; text-align: left;">종목</th>
                        <th style="padding: 10px; text-align: left;">섹터</th>
                        <th style="padding: 10px; text-align: left;">예상수익률</th>
                        <th style="padding: 10px; text-align: left;">신뢰도</th>
                    </tr>
                </thead>
                <tbody>
                    {picks_html}
                </tbody>
            </table>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
            <h3 style="margin-top: 0; color: #333;">📈 성과 지표</h3>
            <p><strong>평균 수익률:</strong> {performance.get('avgReturn', 0)}%</p>
            <p><strong>승률:</strong> {performance.get('winRate', 0)}%</p>
            <p><strong>Sharpe Ratio:</strong> {performance.get('sharpeRatio', 0)}</p>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background-color: #fff3cd; border-radius: 10px; border-left: 4px solid #ffc107;">
            <p style="margin: 0; color: #856404;">
                ⚠️ 본 리포트는 투자 참고용이며, 투자 판단의 책임은 투자자 본인에게 있습니다.
            </p>
        </div>
        
        <div style="margin-top: 30px; text-align: center; color: #999; font-size: 12px;">
            <p>© 2025 StockPlay. All rights reserved.</p>
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