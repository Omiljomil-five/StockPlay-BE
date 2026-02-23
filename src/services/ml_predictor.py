import pickle
import boto3
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from io import StringIO


class MLPredictor:
    """
    ML 모델 예측 클래스.
    ARIMA 예측 결과가 있으면 signal_generator를 통해 v5 5-Factor 판단,
    없으면 기존 정적 CSV 기반 폴백.
    """

    def __init__(self):
        self.model_path = Path(__file__).parent.parent.parent / 'models' / 'model_ver5_final_hybrid.pkl'

        self.use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        self.s3_bucket = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')

        print(f"데이터 소스: {'S3' if self.use_s3 else '로컬'}")

        if self.use_s3:
            self.s3 = boto3.client('s3', region_name='ap-northeast-2')

        # 모델 설정 로드
        with open(self.model_path, 'rb') as f:
            self.model_config = pickle.load(f)

        self.z_threshold = self.model_config.get('z_threshold', 2.0)

        # 데이터 로드
        try:
            if self.use_s3:
                self.vendor_data = self._read_s3_csv('data/problem2_vendor_analysis.csv')
                self.gics_data = self._read_s3_csv('data/gics_all.csv')
                self.kospi_data = self._read_s3_csv('data/kospi.csv')
            else:
                import pandas as pd
                data_path = Path(__file__).parent.parent.parent / 'data'

                self.vendor_data = self._df_to_dicts(pd.read_csv(data_path / 'problem2_vendor_analysis.csv'))
                self.gics_data = self._df_to_dicts(pd.read_csv(data_path / 'gics_all.csv'))
                self.kospi_data = self._df_to_dicts(pd.read_csv(data_path / 'kospi.csv'))

            print(f"데이터 로드 완료: vendor={len(self.vendor_data)}, gics={len(self.gics_data)}, kospi={len(self.kospi_data)}")
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.vendor_data = []
            self.gics_data = []
            self.kospi_data = []

        # ARIMA + SignalGenerator 초기화 시도
        self._signal_gen = None
        self._arima_predictions = None
        self._init_arima_pipeline()

    def _init_arima_pipeline(self):
        """ARIMA 파이프라인 초기화 (실패해도 폴백 가능)"""
        try:
            from .signal_generator import get_signal_generator
            self._signal_gen = get_signal_generator()

            from .arima_service import get_arima_service
            arima = get_arima_service()
            self._arima_predictions = arima.load_latest_predictions()

            if self._arima_predictions is not None:
                print(f"ARIMA 예측 로드 완료: {len(self._arima_predictions)} 행")
            else:
                print("ARIMA 예측 없음 - 정적 CSV 폴백 사용")
        except Exception as e:
            print(f"ARIMA 파이프라인 초기화 실패 (폴백 사용): {e}")
            self._signal_gen = None
            self._arima_predictions = None

    @staticmethod
    def _df_to_dicts(df) -> List[Dict]:
        result = []
        for _, row in df.iterrows():
            clean = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
            result.append(clean)
        return result

    def _read_s3_csv(self, key: str) -> List[Dict]:
        """S3에서 CSV 읽기"""
        try:
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
            csv_content = obj['Body'].read().decode('utf-8-sig')

            reader = csv.DictReader(StringIO(csv_content))
            data = []
            for row in reader:
                normalized = {}
                for k, v in row.items():
                    clean_key = k.strip().lower() if k else ''
                    clean_value = v.strip() if isinstance(v, str) and v else v
                    if clean_key:
                        normalized[clean_key] = clean_value
                data.append(normalized)
            return data
        except Exception as e:
            print(f"S3 읽기 실패: {key} - {e}")
            return []

    def _calculate_kospi_return(self) -> float:
        """KOSPI 수익률 계산"""
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

    def get_top_signals(self, limit: int = 20, period: str = '1d') -> List[Dict[str, Any]]:
        """
        상위 N개 시그널 조회.
        ARIMA + SignalGenerator가 가능하면 사용, 아니면 기존 방식 폴백.
        """
        # ARIMA 파이프라인 사용 가능하면 우선
        if self._signal_gen is not None:
            try:
                signals = self._signal_gen.generate_signals(
                    predictions_df=self._arima_predictions,
                    vendor_data=self.vendor_data,
                    period=period,
                    limit=limit
                )
                if signals:
                    buy = sum(1 for s in signals if s['decision'] == 'BUY')
                    hold = sum(1 for s in signals if s['decision'] == 'HOLD')
                    sell = sum(1 for s in signals if s['decision'] == 'SELL')
                    src = "ARIMA" if self._arima_predictions is not None else "v5-rules"
                    print(f"{len(signals)}개 시그널 ({src}, {period}) - BUY:{buy} HOLD:{hold} SELL:{sell}")
                    return signals
            except Exception as e:
                print(f"SignalGenerator 실패, 폴백: {e}")

        # 폴백: 기존 정적 CSV 로직
        return self._legacy_get_top_signals(limit, period)

    def _legacy_get_top_signals(self, limit: int, period: str) -> List[Dict[str, Any]]:
        """기존 정적 CSV 기반 시그널 (하위 호환)"""
        features = self._prepare_features(period)
        if not features:
            return self._get_mock_signals(limit)

        predictions = self._predict(features)

        import random
        import hashlib
        seed_str = f"{getattr(self, 'latest_date', '2024-10-31')}-{period}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        random.shuffle(predictions)

        return predictions[:limit]

    def _prepare_features(self, period: str = '1d') -> List[Dict[str, Any]]:
        """피처 준비 (기존 로직)"""
        if not self.vendor_data or not self.gics_data:
            return []

        period_col_map = {
            '1d': 'return_post_1d', '2d': 'return_post_2d',
            '5d': 'return_post_5d', '10d': 'return_post_10d', '20d': 'return_post_20d'
        }
        return_col = period_col_map.get(period, 'return_post_1d')

        dates = [str(r.get('date', '')).strip() for r in self.vendor_data
                 if str(r.get('date', '')).strip() not in ('', 'nan', 'None')]
        if not dates:
            return []

        latest_date = max(dates)
        self.latest_date = latest_date
        latest_data = [r for r in self.vendor_data if str(r.get('date', '')).strip() == latest_date]

        gics_map = {}
        for row in self.gics_data:
            sym = str(row.get('symbol', '')).strip()
            if sym and sym not in ('', 'nan', 'None'):
                gics_map[sym] = row

        sector_to_code = {
            '10.0': 1010, '15.0': 1510, '20.0': 2010, '25.0': 2510,
            '30.0': 3010, '35.0': 3510, '40.0': 4010, '45.0': 4510,
            '50.0': 5010, '55.0': 5510, '60.0': 6010
        }

        features = []
        for row in latest_data:
            symbol = str(row.get('symbol', '')).strip()
            z_str = str(row.get('surprise_z', '')).strip()
            ret_str = str(row.get(return_col, '')).strip()

            if not z_str or z_str in ('nan', '', 'None'):
                continue
            try:
                surprise_z = float(z_str)
                expected_return = float(ret_str) * 100 if ret_str not in ('nan', '', 'None') else 0.0
            except (ValueError, TypeError):
                continue

            if symbol in gics_map:
                sector = str(gics_map[symbol].get('sector', '')).strip()
                gics_code = sector_to_code.get(sector, 4510)
                features.append({
                    'symbol': symbol, 'surprise_z': surprise_z,
                    'gics_code': gics_code, 'expected_return': expected_return, 'period': period
                })

        return features

    def _predict(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """규칙 기반 예측 (KOSPI 대비) - 기존 로직"""
        if not features:
            return []

        kospi_return = self._calculate_kospi_return()
        results = []

        for row in features:
            z = row['surprise_z']
            ret = row['expected_return']

            if ret > 0:
                decision, conf = 'BUY', min(0.95, 0.5 + (z / 10))
            elif ret < 0 and ret > kospi_return:
                decision, conf = 'HOLD', 0.6
            else:
                decision, conf = 'SELL', min(0.95, 0.5 + (abs(z) / 10))

            results.append({
                'symbol': row['symbol'], 'decision': decision,
                'surprise_z': float(z), 'gics_code': int(row['gics_code']),
                'confidence': float(conf), 'expected_return': ret,
                'vs_kospi': ret - kospi_return, 'kospi_return': kospi_return,
                'period': row['period']
            })

        return results

    def _get_mock_signals(self, limit: int) -> List[Dict[str, Any]]:
        """Mock 데이터"""
        mock = [
            {'symbol': '005930', 'decision': 'BUY', 'surprise_z': 2.52, 'gics_code': 4510, 'confidence': 0.85, 'expected_return': 12.5, 'vs_kospi': 10.5, 'kospi_return': 2.0, 'period': '1d'},
            {'symbol': '000660', 'decision': 'BUY', 'surprise_z': 2.38, 'gics_code': 4520, 'confidence': 0.82, 'expected_return': 11.3, 'vs_kospi': 9.3, 'kospi_return': 2.0, 'period': '1d'},
            {'symbol': '035720', 'decision': 'HOLD', 'surprise_z': -0.5, 'gics_code': 2510, 'confidence': 0.6, 'expected_return': -1.2, 'vs_kospi': -3.2, 'kospi_return': 2.0, 'period': '1d'},
            {'symbol': '005380', 'decision': 'BUY', 'surprise_z': 2.18, 'gics_code': 3010, 'confidence': 0.75, 'expected_return': 9.5, 'vs_kospi': 7.5, 'kospi_return': 2.0, 'period': '1d'},
            {'symbol': '051910', 'decision': 'BUY', 'surprise_z': 2.12, 'gics_code': 2010, 'confidence': 0.72, 'expected_return': 8.7, 'vs_kospi': 6.7, 'kospi_return': 2.0, 'period': '1d'},
        ]
        return mock[:limit]

    def enrich_signal_data(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """시그널에 표시용 정보 추가"""
        # SignalGenerator가 있으면 위임
        if self._signal_gen is not None:
            latest_date = getattr(self, 'latest_date', '2024-10-31')
            return self._signal_gen.enrich_signal(signal, latest_date=latest_date)

        # 폴백: 기존 로직
        return self._legacy_enrich(signal)

    def _legacy_enrich(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """기존 enrichment 로직"""
        symbol = signal['symbol']

        gics_row = None
        for row in self.gics_data:
            if str(row.get('symbol', '')).strip() == symbol:
                gics_row = row
                break

        sector_name_map = {
            '10.0': '에너지', '15.0': '소재', '20.0': '산업재', '25.0': '임의소비재',
            '30.0': '필수소비재', '35.0': '헬스케어', '40.0': '금융', '45.0': 'IT',
            '50.0': '통신서비스', '55.0': '유틸리티', '60.0': '부동산'
        }

        if gics_row:
            sector_str = str(gics_row.get('sector', '')).strip()
            sector = sector_name_map.get(sector_str, 'Unknown')
            company_name = f"{sector} 종목 {symbol}"
        else:
            sector = 'Unknown'
            company_name = f"종목 {symbol}"

        import random
        import hashlib
        period = signal.get('period', '1d')
        seed_str = f"{getattr(self, 'latest_date', '2024-10-31')}-{period}-{symbol}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)

        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'surpriseZ': round(signal.get('surprise_z', 0.0), 2),
            'yoyGrowth': round(random.uniform(15, 25), 1),
            'expectedReturn': round(signal.get('expected_return', 0.0), 1),
            'vsKospi': round(signal.get('vs_kospi', 0.0), 1),
            'kospiReturn': round(signal.get('kospi_return', 0.0), 1),
            'confidenceScore': round(signal.get('confidence', 0.5) * 100, 1),
            'period': period
        }


# 싱글톤
_predictor = None

def get_predictor() -> MLPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
    return _predictor
