import boto3
import csv
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from io import StringIO


class MLPredictor:
    """실데이터 기반 시그널 예측 (CSV 직접 사용)"""

    def __init__(self):
        self.use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        self.s3_bucket = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')

        print(f"데이터 소스: {'S3' if self.use_s3 else '로컬'}")

        if self.use_s3:
            self.s3 = boto3.client('s3', region_name='ap-northeast-2')

        try:
            if self.use_s3:
                print("S3에서 데이터 로드 시작...")
                self.signals_data = self._read_s3_csv('data/merged_signals.csv')
                self.export_data = self._read_s3_csv('data/export_by_sector.csv')
                self.sector_mapping_data = self._read_s3_csv('data/sector_mapping.csv')
                self.kospi_data = self._read_s3_csv('data/kospi_real.csv')
            else:
                import pandas as pd
                data_path = Path(__file__).parent.parent.parent / 'data'

                self.signals_data = self._df_to_dicts(pd.read_csv(data_path / 'merged_signals.csv'))
                self.export_data = self._df_to_dicts(pd.read_csv(data_path / 'export_by_sector.csv'))
                self.sector_mapping_data = self._df_to_dicts(pd.read_csv(data_path / 'sector_mapping.csv'))
                self.kospi_data = self._df_to_dicts(pd.read_csv(data_path / 'kospi_real.csv'))

            print(f"Signals: {len(self.signals_data)} rows")
            print(f"Export: {len(self.export_data)} rows")
            print(f"Sector Mapping: {len(self.sector_mapping_data)} rows")
            print(f"KOSPI: {len(self.kospi_data)} rows")

            # 종목코드 -> 이름/섹터 매핑 구축
            self.ticker_to_name = {}
            self.ticker_to_sector = {}
            for row in self.sector_mapping_data:
                ticker = str(row.get('ticker', '')).strip().split('.')[0]  # pandas int/float 대응
                name = str(row.get('name', '')).strip()
                sector = str(row.get('sector', '')).strip()
                if ticker:
                    ticker = ticker.zfill(6)  # leading zero 보장
                    self.ticker_to_name[ticker] = name
                    self.ticker_to_sector[ticker] = sector

            print(f"종목 매핑: {len(self.ticker_to_name)} 종목")

            # 섹터별 수출 YoY/MoM 통계 구축
            self.sector_export_stats = self._build_sector_export_stats()

        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.signals_data = []
            self.export_data = []
            self.sector_mapping_data = []
            self.kospi_data = []
            self.ticker_to_name = {}
            self.ticker_to_sector = {}
            self.sector_export_stats = {}

    def _df_to_dicts(self, df) -> List[Dict]:
        """DataFrame을 dict 리스트로 변환"""
        result = []
        for _, row in df.iterrows():
            clean_row = {k: str(v).strip() if isinstance(v, str) else v for k, v in row.items()}
            result.append(clean_row)
        return result

    def _read_s3_csv(self, key: str) -> List[Dict]:
        """S3에서 CSV 읽기"""
        try:
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

            print(f"{key}: {len(data)} rows")
            return data

        except Exception as e:
            print(f"S3 읽기 실패: {key} - {e}")
            return []

    def _build_sector_export_stats(self) -> Dict[str, Dict[str, float]]:
        """export_by_sector.csv에서 실제 YoY/MoM 계산"""
        sector_date_map = {}
        for row in self.export_data:
            date = str(row.get('date', '')).strip()
            sector = str(row.get('sector', '')).strip()
            try:
                value = float(row.get('export_value', 0))
            except (ValueError, TypeError):
                continue

            if sector not in sector_date_map:
                sector_date_map[sector] = {}
            sector_date_map[sector][date] = value

        stats = {}
        for sector, dates in sector_date_map.items():
            nov_2024 = dates.get('2024-11-30', 0)
            oct_2024 = dates.get('2024-10-31', 0)
            nov_2023 = dates.get('2023-11-30', 0)

            yoy = ((nov_2024 / nov_2023) - 1) * 100 if nov_2023 > 0 else 0.0
            mom = ((nov_2024 / oct_2024) - 1) * 100 if oct_2024 > 0 else 0.0

            stats[sector] = {
                'yoy': round(yoy, 1),
                'mom': round(mom, 1),
            }

        print(f"섹터 수출 통계: {stats}")
        return stats

    def _calculate_kospi_return(self, period: str = '1d') -> float:
        """KOSPI 기간별 수익률 계산"""
        if not self.kospi_data or len(self.kospi_data) < 21:
            return 0.0

        period_days = {'1d': 1, '5d': 5, '10d': 10, '20d': 20}
        days = period_days.get(period, 1)

        try:
            latest = float(self.kospi_data[-1].get('kospi_close', 0))
            previous_idx = max(0, len(self.kospi_data) - 1 - days)
            previous = float(self.kospi_data[previous_idx].get('kospi_close', 0))

            if previous > 0:
                return ((latest - previous) / previous) * 100
            return 0.0
        except Exception:
            return 0.0

    def prepare_features(self, period: str = '1d') -> List[Dict[str, Any]]:
        """merged_signals.csv 최신 날짜 필터, arima_global_z 사용"""
        if not self.signals_data:
            return []

        period_column_map = {
            '1d': 'return_1d', '5d': 'return_5d',
            '10d': 'return_10d', '20d': 'return_20d'
        }
        return_column = period_column_map.get(period, 'return_1d')

        # 최신 날짜 찾기
        dates = set()
        for row in self.signals_data:
            date_val = str(row.get('date', '')).strip()
            if date_val and date_val not in ('', 'nan', 'None'):
                dates.add(date_val)

        if not dates:
            return []

        latest_date = max(dates)
        self.latest_date = latest_date
        print(f"최신 날짜: {latest_date}")

        # 최신 데이터 필터링
        features = []
        for row in self.signals_data:
            if str(row.get('date', '')).strip() != latest_date:
                continue

            ticker_raw = str(row.get('ticker', '')).strip()
            global_z_str = str(row.get('arima_global_z', '')).strip()
            return_str = str(row.get(return_column, '')).strip()

            if not global_z_str or global_z_str in ('nan', '', 'None'):
                continue

            try:
                global_z = float(global_z_str)
                expected_return = float(return_str) * 100 if return_str not in ('nan', '', 'None') else 0.0
            except (ValueError, TypeError):
                continue

            # ticker 정규화: 270 -> 000270
            ticker = ticker_raw.zfill(6)

            features.append({
                'symbol': ticker,
                'arima_global_z': global_z,
                'expected_return': expected_return,
                'period': period,
            })

        print(f"피처 준비 완료: {len(features)} rows")
        return features

    def predict(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """시그널 분류 (arima_global_z 기반)"""
        if not features:
            return []

        kospi_return = self._calculate_kospi_return(features[0].get('period', '1d'))

        results = []
        for row in features:
            global_z = row['arima_global_z']
            expected_return = row['expected_return']

            # 시그널 분류
            if global_z > 1.25:
                decision = 'BUY'
            elif global_z > 0:
                decision = 'HOLD'
            else:
                decision = 'SELL'

            confidence = min(0.95, 0.5 + abs(global_z) / 6.0)
            vs_kospi = expected_return - kospi_return

            results.append({
                'symbol': row['symbol'],
                'decision': decision,
                'arima_global_z': global_z,
                'confidence': float(confidence),
                'expected_return': expected_return,
                'vs_kospi': vs_kospi,
                'kospi_return': kospi_return,
                'period': row['period'],
            })

        return results

    def get_top_signals(self, limit: int = 20, period: str = '1d') -> List[Dict[str, Any]]:
        """상위 시그널 조회 (|arima_global_z| 내림차순)"""
        features = self.prepare_features(period=period)

        if not features:
            return self._get_mock_signals(limit)

        predictions = self.predict(features)

        # |arima_global_z| 내림차순 정렬 (확신도 순)
        predictions.sort(key=lambda x: abs(x['arima_global_z']), reverse=True)

        result = predictions[:limit]

        buy_count = sum(1 for s in result if s['decision'] == 'BUY')
        hold_count = sum(1 for s in result if s['decision'] == 'HOLD')
        sell_count = sum(1 for s in result if s['decision'] == 'SELL')
        print(f"{len(result)}개 시그널 ({period}) - BUY: {buy_count}, HOLD: {hold_count}, SELL: {sell_count}")

        return result

    def _get_mock_signals(self, limit: int) -> List[Dict[str, Any]]:
        """Mock 데이터"""
        mock_data = [
            {'symbol': '005930', 'decision': 'BUY', 'arima_global_z': 2.52, 'confidence': 0.85, 'expected_return': 3.5, 'vs_kospi': 5.5, 'kospi_return': -2.0, 'period': '1d'},
            {'symbol': '000660', 'decision': 'BUY', 'arima_global_z': 2.38, 'confidence': 0.82, 'expected_return': 4.5, 'vs_kospi': 6.5, 'kospi_return': -2.0, 'period': '1d'},
            {'symbol': '005380', 'decision': 'HOLD', 'arima_global_z': 0.5, 'confidence': 0.58, 'expected_return': -1.2, 'vs_kospi': 0.8, 'kospi_return': -2.0, 'period': '1d'},
        ]
        return mock_data[:limit]

    # ── 월별 리포트 요약 ──────────────────────────────

    _monthly_summaries_cache: Optional[List[Dict[str, Any]]] = None

    def get_monthly_summaries(self) -> List[Dict[str, Any]]:
        """merged_signals.csv를 ym별로 그룹화, 월별 성과 지표 계산"""
        if self._monthly_summaries_cache is not None:
            return self._monthly_summaries_cache

        if not self.signals_data:
            return []

        # ym별 그룹화
        ym_groups: Dict[str, List[Dict]] = {}
        for row in self.signals_data:
            ym = str(row.get('ym', '')).strip()
            if not ym or ym in ('nan', 'None', ''):
                continue
            if ym not in ym_groups:
                ym_groups[ym] = []
            ym_groups[ym].append(row)

        summaries = []
        for ym, rows in sorted(ym_groups.items()):
            # arima_global_z 유효한 행만 필터
            valid_rows = []
            for r in rows:
                gz = str(r.get('arima_global_z', '')).strip()
                if gz and gz not in ('nan', '', 'None'):
                    try:
                        float(gz)
                        valid_rows.append(r)
                    except (ValueError, TypeError):
                        pass

            if not valid_rows:
                continue

            # return_10d 수집
            returns = []
            for r in valid_rows:
                ret_str = str(r.get('return_10d', '')).strip()
                if ret_str and ret_str not in ('nan', '', 'None'):
                    try:
                        returns.append(float(ret_str))
                    except (ValueError, TypeError):
                        pass

            if not returns:
                continue

            # avgReturn (×100 → 퍼센트)
            avg_return = sum(returns) / len(returns) * 100

            # winRate: BUY 시그널(z > 1.25) 중 return_10d > 0 비율
            buy_count = 0
            buy_win = 0
            for r in valid_rows:
                gz = float(str(r.get('arima_global_z', '0')).strip())
                ret_str = str(r.get('return_10d', '')).strip()
                if gz > 1.25 and ret_str and ret_str not in ('nan', '', 'None'):
                    buy_count += 1
                    if float(ret_str) > 0:
                        buy_win += 1
            win_rate = (buy_win / buy_count * 100) if buy_count > 0 else 50.0

            # sharpeRatio
            if len(returns) > 1:
                mean_r = sum(returns) / len(returns)
                var_r = sum((x - mean_r) ** 2 for x in returns) / (len(returns) - 1)
                std_r = math.sqrt(var_r) if var_r > 0 else 0.001
                sharpe = mean_r / std_r
            else:
                sharpe = 0.0

            # maxDrawdown (최악 return_10d, ×100 퍼센트)
            max_dd = min(returns) * 100

            # topPicks: |arima_global_z| 내림차순 Top 5
            sorted_rows = sorted(
                valid_rows,
                key=lambda r: abs(float(str(r.get('arima_global_z', '0')).strip())),
                reverse=True
            )
            top_picks = []
            for r in sorted_rows[:5]:
                ticker_raw = str(r.get('ticker', '')).strip()
                ticker = ticker_raw.split('.')[0].zfill(6)
                company_name = self.ticker_to_name.get(ticker, str(r.get('name', f'종목 {ticker}')))
                sector = self.ticker_to_sector.get(ticker, str(r.get('sector', 'Unknown')))
                gz = float(str(r.get('arima_global_z', '0')).strip())

                # 시그널 타입
                if gz > 1.25:
                    sig_type = 'BUY'
                elif gz > 0:
                    sig_type = 'HOLD'
                else:
                    sig_type = 'SELL'

                ret_10d_str = str(r.get('return_10d', '')).strip()
                exp_ret = float(ret_10d_str) * 100 if ret_10d_str not in ('nan', '', 'None') else 0.0

                top_picks.append({
                    'id': f'signal-{ticker}-{ym}',
                    'symbol': ticker,
                    'companyName': company_name,
                    'sector': sector,
                    'signalType': sig_type,
                    'yoyGrowth': 0.0,
                    'expectedReturn': round(exp_ret, 1),
                    'confidenceScore': round(min(95.0, 50.0 + abs(gz) / 6.0 * 100), 1),
                    'period': '10d',
                })

            summaries.append({
                'ym': ym,
                'avgReturn': round(avg_return, 2),
                'winRate': round(win_rate, 1),
                'sharpeRatio': round(sharpe, 2),
                'maxDrawdown': round(max_dd, 2),
                'topPicks': top_picks,
                'totalSignals': len(valid_rows),
            })

        # 신규순 정렬
        summaries.sort(key=lambda x: x['ym'], reverse=True)
        self._monthly_summaries_cache = summaries
        print(f"월별 리포트 생성: {len(summaries)}개월")
        return summaries

    def enrich_signal_data(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """시그널에 실제 회사명, 섹터, 수출 데이터 병합"""
        symbol = signal['symbol']

        # 종목 매핑 조회
        company_name = self.ticker_to_name.get(symbol, f'종목 {symbol}')
        sector = self.ticker_to_sector.get(symbol, 'Unknown')

        # 섹터별 실제 수출 YoY/MoM
        export_stats = self.sector_export_stats.get(sector, {'yoy': 0.0, 'mom': 0.0})

        return {
            'id': f"signal-{symbol}",
            'symbol': symbol,
            'companyName': company_name,
            'sector': sector,
            'signalType': signal['decision'],
            'surpriseZ': round(signal.get('arima_global_z', 0.0), 2),
            'yoyGrowth': export_stats['yoy'],
            'momGrowth': export_stats['mom'],
            'expectedReturn': round(signal.get('expected_return', 0.0), 1),
            'vsKospi': round(signal.get('vs_kospi', 0.0), 1),
            'kospiReturn': round(signal.get('kospi_return', 0.0), 1),
            'confidenceScore': round(signal['confidence'] * 100, 1),
            'period': signal.get('period', '1d'),
        }


# 싱글톤
_predictor = None

def get_predictor() -> MLPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
    return _predictor
