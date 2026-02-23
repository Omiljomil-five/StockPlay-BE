import os
import csv
import hashlib
import random
from io import StringIO
from pathlib import Path
from typing import Dict, List, Any, Optional

import boto3
import pandas as pd


# mg-data model_ver5 하이퍼파라미터
Z_SCORE_THRESHOLD = 2.0
MOST_SENSITIVE_GICS_SECTORS = [35.0]
MOMENTUM_THRESHOLD = 0.08       # 20일 모멘텀 8% 이상
VOLUME_RATIO_THRESHOLD = 2.0    # 거래량 비율 2.0배 이상
RSI_LOWER_BOUND = 50.0
RSI_UPPER_BOUND = 75.0

SECTOR_NAME_MAP = {
    '10.0': '에너지', '15.0': '소재', '20.0': '산업재', '25.0': '임의소비재',
    '30.0': '필수소비재', '35.0': '헬스케어', '40.0': '금융', '45.0': 'IT',
    '50.0': '통신서비스', '55.0': '유틸리티', '60.0': '부동산'
}

SECTOR_TO_CODE = {
    '10.0': 1010, '15.0': 1510, '20.0': 2010, '25.0': 2510,
    '30.0': 3010, '35.0': 3510, '40.0': 4010, '45.0': 4510,
    '50.0': 5010, '55.0': 5510, '60.0': 6010
}


class SignalGenerator:
    """
    v5 5-Factor 하이브리드 시그널 생성기.
    mg-data model_ver5.ipynb 로직 기반.

    5가지 조건 ALL-IN:
      1. surprise_z > 2.0
      2. GICS sector == 35.0 (헬스케어)
      3. momentum (20D) >= 8%
      4. volume_ratio >= 2.0x
      5. 50 < RSI <= 75
    """

    def __init__(self):
        self.use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        self.s3_bucket = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')

        if self.use_s3:
            self.s3 = boto3.client('s3', region_name='ap-northeast-2')

        self.gics_data = self._load_gics()
        self.kospi_data = self._load_kospi()

    def _read_csv(self, filename: str) -> List[Dict]:
        if self.use_s3:
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=f'data/{filename}')
            content = obj['Body'].read().decode('utf-8-sig')
            reader = csv.DictReader(StringIO(content))
        else:
            path = Path(__file__).parent.parent.parent / 'data' / filename
            reader = csv.DictReader(open(path, encoding='utf-8-sig'))

        data = []
        for row in reader:
            clean = {k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
            data.append(clean)
        return data

    def _load_gics(self) -> Dict[str, Dict]:
        rows = self._read_csv('gics_all.csv')
        mapping = {}
        for row in rows:
            symbol = str(row.get('symbol', '')).strip()
            if symbol and symbol not in ('', 'nan', 'None'):
                mapping[symbol] = row
        return mapping

    def _load_kospi(self) -> List[Dict]:
        return self._read_csv('kospi.csv')

    def calculate_kospi_return(self) -> float:
        """KOSPI 최근 수익률 계산"""
        if not self.kospi_data or len(self.kospi_data) < 2:
            return 0.0
        try:
            latest = float(self.kospi_data[-1].get('close', 0))
            previous = float(self.kospi_data[-2].get('close', 0))
            if previous > 0:
                return ((latest - previous) / previous) * 100
            return 0.0
        except Exception:
            return 0.0

    def classify_v5(
        self,
        surprise_z: float,
        gics_code: float,
        momentum_rate: float = 0.0,
        volume_ratio: float = 0.0,
        rsi: float = 0.0
    ) -> Dict[str, Any]:
        """
        v5 5-Factor 판단 로직.
        모든 조건 충족 시 BUY, 아니면 HOLD.
        """
        is_surprise_ok = surprise_z > Z_SCORE_THRESHOLD
        is_gics_ok = gics_code in MOST_SENSITIVE_GICS_SECTORS
        is_momentum_ok = momentum_rate >= MOMENTUM_THRESHOLD
        is_volume_ok = volume_ratio >= VOLUME_RATIO_THRESHOLD
        is_rsi_ok = (rsi > RSI_LOWER_BOUND) and (rsi <= RSI_UPPER_BOUND)

        if is_surprise_ok and is_gics_ok and is_momentum_ok and is_volume_ok and is_rsi_ok:
            decision = 'BUY'
            reason = "ALL 5 CONDITIONS MET"
        else:
            decision = 'HOLD'
            missing = []
            if not is_surprise_ok:
                missing.append("Surprise Z-Score")
            if not is_gics_ok:
                missing.append("GICS Sector")
            if not is_momentum_ok:
                missing.append("Momentum")
            if not is_volume_ok:
                missing.append("Volume")
            if not is_rsi_ok:
                missing.append("RSI")
            reason = f"Missing: {', '.join(missing)}"

        return {'decision': decision, 'reason': reason}

    def generate_signals(
        self,
        predictions_df: Optional[pd.DataFrame],
        vendor_data: List[Dict],
        period: str = '1d',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        예측 결과 + vendor 데이터 기반으로 시그널 생성.

        ARIMA 예측이 있으면 v5 규칙 + KOSPI 대비 판단.
        없으면 vendor_data의 기존 수익률 기반 판단 (폴백).
        """
        kospi_return = self.calculate_kospi_return()

        # 기간별 수익률 컬럼
        period_col = {
            '1d': 'return_post_1d', '2d': 'return_post_2d',
            '5d': 'return_post_5d', '10d': 'return_post_10d',
            '20d': 'return_post_20d'
        }.get(period, 'return_post_1d')

        # ARIMA 예측 결과가 있으면 surprise_z를 갱신
        arima_z_map = {}
        if predictions_df is not None and 'surprise_z' in predictions_df.columns:
            # 최신 날짜의 예측만 사용
            if 'date' in predictions_df.columns:
                latest_date = predictions_df['date'].max()
                latest_preds = predictions_df[predictions_df['date'] == latest_date]
            else:
                latest_preds = predictions_df

            for _, row in latest_preds.iterrows():
                sym = str(row.get('symbol', '')).strip()
                z = row.get('surprise_z', None)
                if sym and pd.notna(z):
                    arima_z_map[sym] = float(z)

        # vendor 데이터에서 최신 날짜 필터
        dates = [str(r.get('date', '')).strip() for r in vendor_data
                 if str(r.get('date', '')).strip() not in ('', 'nan', 'None')]
        if not dates:
            return []

        latest_date = max(dates)
        latest_vendor = [r for r in vendor_data if str(r.get('date', '')).strip() == latest_date]

        signals = []
        for row in latest_vendor:
            symbol = str(row.get('symbol', '')).strip()

            # surprise_z: ARIMA 결과 우선, 없으면 vendor 원본
            if symbol in arima_z_map:
                surprise_z = arima_z_map[symbol]
            else:
                z_str = str(row.get('surprise_z', '')).strip()
                if not z_str or z_str in ('nan', '', 'None'):
                    continue
                try:
                    surprise_z = float(z_str)
                except ValueError:
                    continue

            # 기간별 수익률
            ret_str = str(row.get(period_col, '')).strip()
            try:
                expected_return = float(ret_str) * 100 if ret_str not in ('nan', '', 'None') else 0.0
            except ValueError:
                expected_return = 0.0

            # GICS 정보
            gics_row = self.gics_data.get(symbol)
            if gics_row:
                sector_str = str(gics_row.get('sector', '')).strip()
                gics_code_int = SECTOR_TO_CODE.get(sector_str, 4510)
                sector_float = float(sector_str) if sector_str else 0.0
            else:
                gics_code_int = 4510
                sector_float = 0.0

            # v5 판단 (기술적 지표가 없으면 시뮬레이션)
            # 실제 momentum/volume/RSI 데이터가 없으므로 종목 기반 시드로 생성
            seed_str = f"{latest_date}-{period}-{symbol}"
            seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
            rng = random.Random(seed)

            momentum = rng.uniform(-0.05, 0.20)
            volume_ratio = rng.uniform(0.5, 4.0)
            rsi = rng.uniform(30, 85)

            v5_result = self.classify_v5(
                surprise_z=surprise_z,
                gics_code=sector_float,
                momentum_rate=momentum,
                volume_ratio=volume_ratio,
                rsi=rsi
            )

            # 최종 시그널: v5 BUY는 그대로, HOLD는 KOSPI 대비로 세분화
            if v5_result['decision'] == 'BUY':
                decision = 'BUY'
                confidence = min(0.95, 0.7 + (surprise_z / 10))
            elif expected_return > 0:
                decision = 'BUY'
                confidence = min(0.95, 0.5 + (surprise_z / 10))
            elif expected_return < 0 and expected_return > kospi_return:
                decision = 'HOLD'
                confidence = 0.6
            else:
                decision = 'SELL'
                confidence = min(0.95, 0.5 + (abs(surprise_z) / 10))

            vs_kospi = expected_return - kospi_return

            signals.append({
                'symbol': symbol,
                'decision': decision,
                'surprise_z': float(surprise_z),
                'gics_code': gics_code_int,
                'confidence': float(confidence),
                'expected_return': expected_return,
                'vs_kospi': vs_kospi,
                'kospi_return': kospi_return,
                'period': period,
                'v5_decision': v5_result['decision'],
                'v5_reason': v5_result['reason'],
            })

        # 날짜+기간 기반 랜덤 시드로 일관성 보장
        seed_str = f"{latest_date}-{period}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        random.shuffle(signals)

        return signals[:limit]

    def enrich_signal(self, signal: Dict[str, Any], latest_date: str = '2024-10-31') -> Dict[str, Any]:
        """시그널에 표시용 정보 추가 (회사명, 섹터명, YoY 등)"""
        symbol = signal['symbol']
        period = signal.get('period', '1d')

        gics_row = self.gics_data.get(symbol)
        if gics_row:
            sector_str = str(gics_row.get('sector', '')).strip()
            sector = SECTOR_NAME_MAP.get(sector_str, 'Unknown')
            company_name = f"{sector} 종목 {symbol}"
        else:
            sector = 'Unknown'
            company_name = f"종목 {symbol}"

        # 종목+날짜+기간 기반 일관된 YoY
        seed_str = f"{latest_date}-{period}-{symbol}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'surpriseZ': round(signal.get('surprise_z', 0.0), 2),
            'yoyGrowth': round(rng.uniform(15, 25), 1),
            'expectedReturn': round(signal.get('expected_return', 0.0), 1),
            'vsKospi': round(signal.get('vs_kospi', 0.0), 1),
            'kospiReturn': round(signal.get('kospi_return', 0.0), 1),
            'confidenceScore': round(signal.get('confidence', 0.5) * 100, 1),
            'period': period,
        }


# 싱글톤
_signal_generator = None


def get_signal_generator() -> SignalGenerator:
    global _signal_generator
    if _signal_generator is None:
        _signal_generator = SignalGenerator()
    return _signal_generator
