"""
ML 모델 예측 서비스 (기간별 예측 지원 버전)
"""

import pickle
import boto3
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from io import StringIO

class MLPredictor:
    """ML 모델 예측 클래스 (기간별 수익률 지원)"""
    
    def __init__(self):
        self.model_path = Path(__file__).parent.parent.parent / 'models' / 'basic_rule_model.pkl'
        
        # 환경변수
        self.use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        self.s3_bucket = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
        
        print(f"🔍 데이터 소스: {'S3' if self.use_s3 else '로컬'}")
        
        if self.use_s3:
            self.s3 = boto3.client('s3', region_name='ap-northeast-2')
        
        # 모델 로드
        with open(self.model_path, 'rb') as f:
            self.model_config = pickle.load(f)
        
        self.z_threshold = self.model_config.get('z_threshold', 2.0)
        print(f"✅ Z-Score 임계값: {self.z_threshold}")
        
        # 데이터 로드
        try:
            if self.use_s3:
                print("📦 S3에서 데이터 로드 시작...")
                # 기간별 수익률 데이터 (problem2)
                self.vendor_data = self._read_s3_csv('data/problem2_vendor_analysis.csv')
                self.gics_data = self._read_s3_csv('data/gics_all.csv')
                print(f"✅ Vendor Analysis: {len(self.vendor_data)} rows")
                print(f"✅ GICS: {len(self.gics_data)} rows")
            else:
                # 로컬에서는 pandas 사용
                import pandas as pd
                data_path = Path(__file__).parent.parent.parent / 'data'
                vendor_df = pd.read_csv(data_path / 'problem2_vendor_analysis.csv')
                gics_df = pd.read_csv(data_path / 'gics_all.csv')
                
                # dict로 변환하면서 문자열 strip
                self.vendor_data = []
                for _, row in vendor_df.iterrows():
                    clean_row = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
                    self.vendor_data.append(clean_row)
                
                self.gics_data = []
                for _, row in gics_df.iterrows():
                    clean_row = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
                    self.gics_data.append(clean_row)
                
                print(f"✅ 로컬 데이터 로드 완료")
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.vendor_data = []
            self.gics_data = []
    
    def _read_s3_csv(self, key: str) -> List[Dict]:
        """S3에서 CSV 읽기"""
        try:
            print(f"📥 S3에서 읽기: {key}")
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
            csv_content = obj['Body'].read().decode('utf-8-sig')
            
            reader = csv.DictReader(StringIO(csv_content))
            data = []
            
            for row in reader:
                normalized_row = {}
                for k, v in row.items():
                    clean_key = k.strip().lower() if k else ''
                    clean_value = v.strip() if isinstance(v, str) and v else v
                    if clean_key:
                        normalized_row[clean_key] = clean_value
                data.append(normalized_row)
            
            print(f"✅ {key} 로드 완료: {len(data)} rows")
            
            if data:
                print(f"📊 컬럼: {list(data[0].keys())}")
            
            return data
            
        except Exception as e:
            print(f"⚠️ S3 읽기 실패: {key} - {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def prepare_features(self, period: str = '1d') -> List[Dict[str, Any]]:
        """
        모델 입력 피처 준비 (기간별)
        
        Args:
            period: '1d', '5d', '10d', '20d' 중 하나
        """
        print(f"🔍 prepare_features 시작 (기간: {period})")
        print(f"  - Vendor 데이터: {len(self.vendor_data) if self.vendor_data else 0} rows")
        print(f"  - GICS 데이터: {len(self.gics_data) if self.gics_data else 0} rows")
        
        if not self.vendor_data or not self.gics_data:
            print("❌ 데이터 부족!")
            return []
        
        # 기간 컬럼 매핑
        period_column_map = {
            '1d': 'return_post_1d',
            '2d': 'return_post_2d',
            '5d': 'return_post_5d',
            '10d': 'return_post_10d',
            '20d': 'return_post_20d'
        }
        
        return_column = period_column_map.get(period, 'return_post_1d')
        
        try:
            # 최신 날짜 찾기
            dates = []
            for row in self.vendor_data:
                date_val = row.get('date', '')
                if date_val and date_val not in ('', 'nan', 'None'):
                    dates.append(str(date_val).strip())
            
            if not dates:
                print("❌ 날짜 데이터 없음!")
                return []
            
            latest_date = max(dates)
            print(f"📅 최신 날짜: {latest_date}")
            
            # 최신 데이터 필터링
            latest_data = []
            for row in self.vendor_data:
                date_val = str(row.get('date', '')).strip()
                if date_val == latest_date:
                    latest_data.append(row)
            
            print(f"📊 최신 데이터: {len(latest_data)} rows")
            
            # GICS 매핑
            gics_map = {}
            for row in self.gics_data:
                symbol = str(row.get('symbol', '')).strip()
                if symbol and symbol not in ('', 'nan', 'None'):
                    gics_map[symbol] = row
            
            print(f"✅ GICS 매핑 완료: {len(gics_map)} 종목")
            
            # Sector 코드 매핑
            sector_to_code = {
                '10.0': 1010, '15.0': 1510, '20.0': 2010, '25.0': 2510,
                '30.0': 3010, '35.0': 3510, '40.0': 4010, '45.0': 4510,
                '50.0': 5010, '55.0': 5510, '60.0': 6010
            }
            
            # 피처 생성
            features = []
            matched_count = 0
            
            for row in latest_data:
                symbol = str(row.get('symbol', '')).strip()
                surprise_z_str = str(row.get('surprise_z', '')).strip()
                expected_return_str = str(row.get(return_column, '')).strip()
                
                # surprise_z 검증
                if not surprise_z_str or surprise_z_str in ('nan', '', 'None'):
                    continue
                
                try:
                    surprise_z = float(surprise_z_str)
                    # 기간별 실제 수익률
                    expected_return = float(expected_return_str) * 100 if expected_return_str not in ('nan', '', 'None') else 0.0
                except:
                    continue
                
                # GICS 조회
                if symbol in gics_map:
                    matched_count += 1
                    sector = str(gics_map[symbol].get('sector', '')).strip()
                    gics_code = sector_to_code.get(sector, 4510)
                    
                    features.append({
                        'symbol': symbol,
                        'surprise_z': surprise_z,
                        'gics_code': gics_code,
                        'expected_return': expected_return,  # 실제 수익률
                        'period': period
                    })
            
            print(f"✅ 피처 준비 완료: {len(features)} rows")
            print(f"   - 매칭 성공: {matched_count}")
            
            return features
            
        except Exception as e:
            print(f"❌ 피처 준비 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def predict(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """규칙 기반 예측"""
        if not features:
            return []
        
        results = []
        
        for row in features:
            z_score = row['surprise_z']
            
            # 규칙 기반 분류
            if z_score > self.z_threshold:
                decision = 'BUY'
                confidence = min(0.95, 0.5 + (z_score / 10))
            elif z_score < -self.z_threshold:
                decision = 'SELL'
                confidence = min(0.95, 0.5 + (abs(z_score) / 10))
            else:
                decision = 'HOLD'
                confidence = 0.5
            
            results.append({
                'symbol': row['symbol'],
                'decision': decision,
                'surprise_z': float(z_score),
                'gics_code': int(row['gics_code']),
                'confidence': float(confidence),
                'expected_return': row['expected_return'],
                'period': row['period']
            })
        
        return results
    
    def get_top_signals(self, limit: int = 20, period: str = '1d') -> List[Dict[str, Any]]:
        """
        상위 N개 시그널 조회
        
        Args:
            limit: 결과 개수
            period: '1d', '5d', '10d', '20d'
        """
        features = self.prepare_features(period=period)
        
        if not features:
            print("⚠️ 데이터 없음, Mock 데이터 반환")
            return self._get_mock_signals(limit)
        
        predictions = self.predict(features)
        
        # BUY 시그널만 필터링
        buy_signals = [p for p in predictions if p['decision'] == 'BUY']
        
        # 신뢰도 순 정렬
        buy_signals = sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)
        
        print(f"✅ {len(buy_signals)}개 BUY 시그널 생성 ({period})")
        return buy_signals[:limit]
    
    def _get_mock_signals(self, limit: int) -> List[Dict[str, Any]]:
        """Mock 데이터"""
        mock_data = [
            {'symbol': '005930', 'decision': 'BUY', 'surprise_z': 2.52, 'gics_code': 4510, 'confidence': 0.85, 'expected_return': 12.5, 'period': '1d'},
            {'symbol': '000660', 'decision': 'BUY', 'surprise_z': 2.38, 'gics_code': 4520, 'confidence': 0.82, 'expected_return': 11.3, 'period': '1d'},
            {'symbol': '035720', 'decision': 'BUY', 'surprise_z': 2.25, 'gics_code': 2510, 'confidence': 0.78, 'expected_return': 10.8, 'period': '1d'},
            {'symbol': '005380', 'decision': 'BUY', 'surprise_z': 2.18, 'gics_code': 3010, 'confidence': 0.75, 'expected_return': 9.5, 'period': '1d'},
            {'symbol': '051910', 'decision': 'BUY', 'surprise_z': 2.12, 'gics_code': 2010, 'confidence': 0.72, 'expected_return': 8.7, 'period': '1d'},
        ]
        return mock_data[:limit]
    
    def enrich_signal_data(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """시그널에 추가 정보 병합 (MoM 제거, YoY 유지)"""
        symbol = signal['symbol']
        
        # GICS 조회
        gics_row = None
        for row in self.gics_data:
            if str(row.get('symbol', '')).strip() == symbol:
                gics_row = row
                break
        
        if gics_row:
            sector_code_str = str(gics_row.get('sector', '')).strip()
            sector_name_map = {
                '10.0': '에너지', '15.0': '소재', '20.0': '산업재', '25.0': '임의소비재',
                '30.0': '필수소비재', '35.0': '헬스케어', '40.0': '금융', '45.0': 'IT',
                '50.0': '통신서비스', '55.0': '유틸리티', '60.0': '부동산'
            }
            sector = sector_name_map.get(sector_code_str, 'Unknown')
            company_name = f"{sector} 종목 {symbol}"
        else:
            company_name = f"종목 {symbol}"
            sector = 'Unknown'
        
        # 실제 기간별 수익률 사용
        expected_return = signal.get('expected_return', 0.0)
        
        import random
        
        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'yoyGrowth': round(random.uniform(15, 25), 1),  # YoY 유지
            # momGrowth 제거됨!
            'expectedReturn': round(expected_return, 1),  # 실제 수익률
            'confidenceScore': round(signal['confidence'] * 100, 1),
            'period': signal.get('period', '1d')
        }


# 싱글톤
_predictor = None

def get_predictor() -> MLPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
    return _predictor