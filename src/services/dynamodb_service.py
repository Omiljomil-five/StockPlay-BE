import boto3
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

class DynamoDBService:
    """DynamoDB 구독자 관리 클래스"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        self.table_name = os.environ.get('DYNAMODB_TABLE', 'stockplay-main')
        self.table = self.dynamodb.Table(self.table_name)
        
        print(f"✅ DynamoDB 테이블 연결: {self.table_name}")
    
    def subscribe(self, email: str) -> Dict[str, Any]:
        """이메일 구독 등록"""
        try:
            timestamp = datetime.utcnow().isoformat() + 'Z'
            
            item = {
                'PK': f'SUBSCRIBER#{email}',
                'SK': 'METADATA',
                'email': email,
                'notification_enabled': 1,
                'created_at': timestamp,
                'updated_at': timestamp
            }
            
            # 조건부 쓰기: 이미 존재하면 실패
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(PK)'
            )
            
            print(f"✅ 구독 등록 성공: {email}")
            return {
                'success': True,
                'message': '구독이 완료되었습니다.',
                'data': item
            }
            
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            print(f"⚠️ 이미 구독 중: {email}")
            return {
                'success': False,
                'message': '이미 구독 중인 이메일입니다.',
                'data': None
            }
        except Exception as e:
            print(f"❌ 구독 등록 실패: {e}")
            return {
                'success': False,
                'message': f'구독 등록 실패: {str(e)}',
                'data': None
            }
    
    def get_subscription(self, email: str) -> Optional[Dict[str, Any]]:
        """구독 상태 조회"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'SUBSCRIBER#{email}',
                    'SK': 'METADATA'
                }
            )
            
            item = response.get('Item')
            if item:
                print(f"✅ 구독 정보 조회 성공: {email}")
                return item
            else:
                print(f"⚠️ 구독 정보 없음: {email}")
                return None
                
        except Exception as e:
            print(f"❌ 구독 조회 실패: {e}")
            return None
    
    def toggle_notification(self, email: str, enabled: bool) -> Dict[str, Any]:
        """알림 설정 토글"""
        try:
            timestamp = datetime.utcnow().isoformat() + 'Z'
            notification_value = 1 if enabled else 0
            
            response = self.table.update_item(
                Key={
                    'PK': f'SUBSCRIBER#{email}',
                    'SK': 'METADATA'
                },
                UpdateExpression='SET notification_enabled = :enabled, updated_at = :updated',
                ExpressionAttributeValues={
                    ':enabled': notification_value,
                    ':updated': timestamp
                },
                ConditionExpression='attribute_exists(PK)',
                ReturnValues='ALL_NEW'
            )
            
            print(f"✅ 알림 설정 변경: {email} -> {enabled}")
            return {
                'success': True,
                'message': f'알림이 {"활성화" if enabled else "비활성화"}되었습니다.',
                'data': response['Attributes']
            }
            
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            print(f"⚠️ 구독 정보 없음: {email}")
            return {
                'success': False,
                'message': '구독 정보를 찾을 수 없습니다.',
                'data': None
            }
        except Exception as e:
            print(f"❌ 알림 설정 변경 실패: {e}")
            return {
                'success': False,
                'message': f'알림 설정 변경 실패: {str(e)}',
                'data': None
            }
    
    def unsubscribe(self, email: str) -> Dict[str, Any]:
        """구독 취소"""
        try:
            self.table.delete_item(
                Key={
                    'PK': f'SUBSCRIBER#{email}',
                    'SK': 'METADATA'
                },
                ConditionExpression='attribute_exists(PK)'
            )
            
            print(f"✅ 구독 취소 성공: {email}")
            return {
                'success': True,
                'message': '구독이 취소되었습니다.',
                'data': None
            }
            
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            print(f"⚠️ 구독 정보 없음: {email}")
            return {
                'success': False,
                'message': '구독 정보를 찾을 수 없습니다.',
                'data': None
            }
        except Exception as e:
            print(f"❌ 구독 취소 실패: {e}")
            return {
                'success': False,
                'message': f'구독 취소 실패: {str(e)}',
                'data': None
            }
    
    def get_active_subscribers(self) -> List[Dict[str, Any]]:
        """활성 구독자 목록 조회 (notification_enabled=1)"""
        try:
            response = self.table.query(
                IndexName='SubscriberIndex',
                KeyConditionExpression='notification_enabled = :enabled',
                ExpressionAttributeValues={
                    ':enabled': 1
                }
            )
            
            items = response.get('Items', [])
            print(f"✅ 활성 구독자 조회: {len(items)}명")
            return items
            
        except Exception as e:
            print(f"❌ 활성 구독자 조회 실패: {e}")
            return []


# 싱글톤
_dynamodb_service = None

def get_dynamodb_service() -> DynamoDBService:
    """DynamoDB 서비스 싱글톤"""
    global _dynamodb_service
    if _dynamodb_service is None:
        _dynamodb_service = DynamoDBService()
    return _dynamodb_service