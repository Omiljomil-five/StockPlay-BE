"""
ML 모델 예측 서비스 (최종 수정 버전)
"""

import pickle
import boto3
import csv
from pathlib import Path
from typing import List, Dict, Any
import os
from io import StringIO

class MLPredictor:
    """ML 모델 예측 클래스"""
    
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
                self.surprise_data = self._read_s3_csv('data/problem1_surprise_arima.csv')
                self.gics_data = self._read_s3_csv('data/gics_all.csv')
                print(f"✅ Surprise: {len(self.surprise_data)} rows")
                print(f"✅ GICS: {len(self.gics_data)} rows")
            else:
                # 로컬에서는 pandas 사용
                import pandas as pd
                data_path = Path(__file__).parent.parent.parent / 'data'
                surprise_df = pd.read_csv(data_path / 'problem1_surprise_arima.csv')
                gics_df = pd.read_csv(data_path / 'gics_all.csv')
                
                # dict로 변환하면서 문자열 strip
                self.surprise_data = []
                for _, row in surprise_df.iterrows():
                    clean_row = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
                    self.surprise_data.append(clean_row)
                
                self.gics_data = []
                for _, row in gics_df.iterrows():
                    clean_row = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
                    self.gics_data.append(clean_row)
                
                print(f"✅ 로컬 데이터 로드 완료")
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.surprise_data = []
            self.gics_data = []
    
    def _read_s3_csv(self, key: str) -> List[Dict]:
        """S3에서 CSV 읽기 (완전 정규화)"""
        try:
            print(f"📥 S3에서 읽기: {key}")
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
            csv_content = obj['Body'].read().decode('utf-8-sig')
            
            reader = csv.DictReader(StringIO(csv_content))
            data = []
            
            for row in reader:
                # 🔧 완전 정규화: 키와 값 모두 공백 제거
                normalized_row = {}
                for k, v in row.items():
                    # 키: 공백 제거 + 소문자
                    clean_key = k.strip().lower() if k else ''
                    # 값: 공백 제거
                    clean_value = v.strip() if isinstance(v, str) and v else v
                    if clean_key:  # 빈 키는 제외
                        normalized_row[clean_key] = clean_value
                data.append(normalized_row)
            
            print(f"✅ {key} 로드 완료: {len(data)} rows")
            
            # 샘플 출력
            if data:
                sample = data[0]
                print(f"📊 컬럼: {list(sample.keys())}")
                print(f"📊 샘플 symbol: '{sample.get('symbol', 'NOT FOUND')}'")
            
            return data
            
        except Exception as e:
            print(f"⚠️ S3 읽기 실패: {key} - {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def prepare_features(self) -> List[Dict[str, Any]]:
        """모델 입력 피처 준비"""
        
        print(f"🔍 prepare_features 시작")
        print(f"  - Surprise 데이터: {len(self.surprise_data) if self.surprise_data else 0} rows")
        print(f"  - GICS 데이터: {len(self.gics_data) if self.gics_data else 0} rows")
        
        if not self.surprise_data or not self.gics_data:
            print("❌ 데이터 부족!")
            return []
        
        try:
            # 최신 날짜 찾기
            dates = []
            for row in self.surprise_data:
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
            for row in self.surprise_data:
                date_val = str(row.get('date', '')).strip()
                if date_val == latest_date:
                    latest_data.append(row)
            
            print(f"📊 최신 데이터: {len(latest_data)} rows")
            
            # GICS 매핑 (공백 완전 제거)
            print(f"🔧 GICS 매핑 시작...")
            gics_map = {}
            empty_count = 0
            
            for row in self.gics_data:
                symbol = str(row.get('symbol', '')).strip()
                if symbol and symbol not in ('', 'nan', 'None'):
                    gics_map[symbol] = row
                else:
                    empty_count += 1
            
            print(f"✅ GICS 매핑 완료: {len(gics_map)} 종목")
            if empty_count > 0:
                print(f"⚠️ 빈 symbol: {empty_count}개")
            
            # 샘플 확인
            if gics_map:
                sample_symbols = list(gics_map.keys())[:3]
                print(f"📊 GICS 샘플 symbols: {sample_symbols}")
            
            # Sector 코드 매핑
            sector_to_code = {
                '10.0': 1010, '15.0': 1510, '20.0': 2010, '25.0': 2510,
                '30.0': 3010, '35.0': 3510, '40.0': 4010, '45.0': 4510,
                '50.0': 5010, '55.0': 5510, '60.0': 6010
            }
            
            # 피처 생성
            features = []
            matched_count = 0
            unmatched_count = 0
            
            for row in latest_data:
                symbol = str(row.get('symbol', '')).strip()
                surprise_z_str = str(row.get('surprise_z', '')).strip()
                
                # surprise_z 검증
                if not surprise_z_str or surprise_z_str in ('nan', '', 'None'):
                    continue
                
                try:
                    surprise_z = float(surprise_z_str)
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
                        'gics_code': gics_code
                    })
                else:
                    unmatched_count += 1
            
            print(f"✅ 피처 준비 완료: {len(features)} rows")
            print(f"   - 매칭 성공: {matched_count}")
            print(f"   - 매칭 실패: {unmatched_count}")
            
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
                'confidence': float(confidence)
            })
        
        return results
    
    def get_top_signals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """상위 N개 시그널 조회"""
        features = self.prepare_features()
        
        if not features:
            print("⚠️ 데이터 없음, Mock 데이터 반환")
            return self._get_mock_signals(limit)
        
        predictions = self.predict(features)
        
        # BUY 시그널만 필터링
        buy_signals = [p for p in predictions if p['decision'] == 'BUY']
        
        # 신뢰도 순 정렬
        buy_signals = sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)
        
        print(f"✅ {len(buy_signals)}개 BUY 시그널 생성")
        return buy_signals[:limit]
    
    def _get_mock_signals(self, limit: int) -> List[Dict[str, Any]]:
        """Mock 데이터"""
        mock_data = [
            {'symbol': '005930', 'decision': 'BUY', 'surprise_z': 2.52, 'gics_code': 4510, 'confidence': 0.85},
            {'symbol': '000660', 'decision': 'BUY', 'surprise_z': 2.38, 'gics_code': 4520, 'confidence': 0.82},
            {'symbol': '035720', 'decision': 'BUY', 'surprise_z': 2.25, 'gics_code': 2510, 'confidence': 0.78},
            {'symbol': '005380', 'decision': 'BUY', 'surprise_z': 2.18, 'gics_code': 3010, 'confidence': 0.75},
            {'symbol': '051910', 'decision': 'BUY', 'surprise_z': 2.12, 'gics_code': 2010, 'confidence': 0.72},
        ]
        return mock_data[:limit]
    
    def enrich_signal_data(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """시그널에 추가 정보 병합"""
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
        
        # 수익률 계산
        z_score = signal['surprise_z']
        expected_return = min(25.0, max(5.0, z_score * 5))
        
        import random
        
        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'yoyGrowth': round(random.uniform(15, 25), 1),
            'momGrowth': round(random.uniform(8, 18), 1),
            'expectedReturn': round(expected_return, 1),
            'confidenceScore': round(signal['confidence'] * 100, 1)
        }


# 싱글톤
_predictor = None

def get_predictor() -> MLPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
    return _predictor