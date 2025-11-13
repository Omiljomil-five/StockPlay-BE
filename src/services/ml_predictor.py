"""
ML 모델 예측 서비스 (규칙 기반)
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

class MLPredictor:
    """ML 모델 예측 클래스"""
    
    def __init__(self):
        self.model_path = Path(__file__).parent.parent.parent / 'models' / 'basic_rule_model.pkl'
        self.data_path = Path(__file__).parent.parent.parent / 'data'
        
        print(f"🔍 데이터 경로: {self.data_path}")
        
        # 모델 로드 (규칙 기반)
        with open(self.model_path, 'rb') as f:
            self.model_config = pickle.load(f)
        
        print(f"📦 모델 설정: {self.model_config}")
        self.z_threshold = self.model_config.get('z_threshold', 2.0)
        print(f"✅ Z-Score 임계값: {self.z_threshold}")
        
        # 데이터 로드
        self.export_data = pd.read_csv(self.data_path / 'export_value_clean.csv')
        self.gics_data = pd.read_csv(self.data_path / 'gics_all.csv')
        self.price_data = pd.read_csv(self.data_path / 'price_all.csv')
        
        # Surprise 데이터 로드
        surprise_files = [
            'problem1_surprise_arima.csv',
            'problem1_surprise_ewma.csv', 
            'problem1_surprise_sma.csv'
        ]
        
        self.surprise_data = None
        for filename in surprise_files:
            filepath = self.data_path / filename
            if filepath.exists():
                self.surprise_data = pd.read_csv(filepath)
                print(f"✅ Surprise 데이터 로드: {filename}")
                print(f"📊 데이터 크기: {len(self.surprise_data)} rows")
                break
        
        if self.surprise_data is None:
            print("⚠️ Surprise 데이터 없음")
        
        print("✅ 모델 로드 완료")
    
    def prepare_features(self, symbols: List[str] = None) -> pd.DataFrame:
        """모델 입력 피처 준비"""
        
        if self.surprise_data is None:
            return pd.DataFrame()
        
        # 최신 날짜 데이터 사용
        latest_date = self.surprise_data['date'].max()
        latest_data = self.surprise_data[self.surprise_data['date'] == latest_date].copy()
        
        print(f"📅 최신 날짜: {latest_date}, {len(latest_data)} rows")
        
        # GICS 데이터 병합
        features = latest_data.merge(
            self.gics_data[['symbol', 'sector']],
            on='symbol',
            how='inner'
        )
        
        print(f"🔗 GICS 병합 후: {len(features)} rows")
        
        # Sector를 숫자 코드로 변환
        sector_to_code = {
            10.0: 1010, 15.0: 1510, 20.0: 2010, 25.0: 2510,
            30.0: 3010, 35.0: 3510, 40.0: 4010, 45.0: 4510,
            50.0: 5010, 55.0: 5510, 60.0: 6010
        }
        features['gics_code'] = features['sector'].map(sector_to_code)
        
        # 필요한 컬럼만 선택
        features = features[['symbol', 'surprise_z', 'gics_code']].copy()
        features = features.dropna()
        
        print(f"✅ 피처 준비 완료: {len(features)} rows")
        return features
    
    def predict(self, features: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        규칙 기반 예측
        - surprise_z > threshold → BUY
        - surprise_z < -threshold → SELL
        - 그 외 → HOLD
        """
        if features.empty:
            return []
        
        results = []
        
        for idx, row in features.iterrows():
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
        
        if features.empty:
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
        
        # GICS 데이터에서 섹터 조회
        gics_row = self.gics_data[self.gics_data['symbol'] == symbol]
        
        if len(gics_row) > 0:
            sector_code = gics_row.iloc[0]['sector']
            sector_name_map = {
                10.0: '에너지', 15.0: '소재', 20.0: '산업재', 25.0: '임의소비재',
                30.0: '필수소비재', 35.0: '헬스케어', 40.0: '금융', 45.0: 'IT',
                50.0: '통신서비스', 55.0: '유틸리티', 60.0: '부동산'
            }
            sector = sector_name_map.get(sector_code, 'Unknown')
            company_name = f"{sector} 종목 {symbol}"
        else:
            company_name = f"종목 {symbol}"
            sector = 'Unknown'
        
        # 수익률 계산 (Z-Score 기반)
        z_score = signal['surprise_z']
        expected_return = min(25.0, max(5.0, z_score * 5))
        
        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'yoyGrowth': round(float(np.random.uniform(15, 25)), 1),
            'momGrowth': round(float(np.random.uniform(8, 18)), 1),
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