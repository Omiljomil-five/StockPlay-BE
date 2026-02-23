import os
import csv
import numpy as np
import pandas as pd
import boto3
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# mg-data 분석 결과 기반 최적 하이퍼파라미터
ARIMA_ORDER = (1, 2, 1)
REFIT_EVERY = 3
Z_THRESHOLD = 2.0


class ARIMASurpriseService:
    """
    ARIMA 기반 수출 서프라이즈 예측 서비스.
    mg-data problem1_surprise.ipynb에서 추출한 SARIMAX(1,2,1) 로직.
    """

    def __init__(self):
        self.use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        self.s3_bucket = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
        self.order = ARIMA_ORDER
        self.refit_every = REFIT_EVERY

        if self.use_s3:
            self.s3 = boto3.client('s3', region_name='ap-northeast-2')

    def _read_csv_from_s3(self, key: str) -> pd.DataFrame:
        obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
        content = obj['Body'].read().decode('utf-8-sig')
        return pd.read_csv(StringIO(content))

    def _write_csv_to_s3(self, df: pd.DataFrame, key: str):
        buf = StringIO()
        df.to_csv(buf, index=False)
        self.s3.put_object(
            Bucket=self.s3_bucket,
            Key=key,
            Body=buf.getvalue().encode('utf-8'),
            ContentType='text/csv'
        )
        print(f"  S3 저장 완료: {key}")

    def _read_csv_local(self, filename: str) -> pd.DataFrame:
        data_path = Path(__file__).parent.parent.parent / 'data' / filename
        return pd.read_csv(data_path)

    def load_export_data(self) -> pd.DataFrame:
        """수출 데이터 로드 (S3 또는 로컬)"""
        if self.use_s3:
            return self._read_csv_from_s3('data/problem2_vendor_analysis.csv')
        return self._read_csv_local('problem2_vendor_analysis.csv')

    def forecast_symbol(self, y: pd.Series) -> pd.Series:
        """
        단일 종목 시계열에 대해 ARIMA rolling one-step ahead 예측.
        과거 데이터만 사용하여 각 시점의 1스텝 예측을 수행.

        Args:
            y: 시계열 (시간순 정렬, export_value)

        Returns:
            forecast Series (같은 인덱스)
        """
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        y = y.astype(float)
        idx = y.index
        fc = pd.Series(index=idx, dtype=float)

        start = 1
        last_fit_i = None
        results = None

        for i in range(start, len(y)):
            # 주기적으로 모델 재학습
            if results is None or (i - (last_fit_i or 0) >= self.refit_every):
                train = y.iloc[:i]
                if train.notna().sum() < max(self.order[1] + 1, 5):
                    fc.iloc[i] = np.nan
                    continue
                try:
                    model = SARIMAX(
                        train,
                        order=self.order,
                        enforce_stationarity=False,
                        enforce_invertibility=False
                    )
                    results = model.fit(disp=False)
                    last_fit_i = i
                except Exception:
                    fc.iloc[i] = np.nan
                    continue

            # 1-step ahead forecast
            try:
                pred = results.get_forecast(steps=1)
                fc.iloc[i] = float(pred.predicted_mean.iloc[0])
            except Exception:
                fc.iloc[i] = np.nan

        return fc

    def calculate_surprise(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        실제값과 예측값으로 surprise 지표 계산.

        Returns:
            surprise, surprise_pct, surprise_z 컬럼이 추가된 DataFrame
        """
        out = df.copy()
        out["surprise"] = out["export_value"] - out["forecast"]
        out["surprise_pct"] = np.where(
            out["forecast"].abs() > 1e-12,
            (out["surprise"] / out["forecast"]) * 100.0,
            np.nan
        )
        # 심볼별 z-score 표준화
        out["surprise_z"] = (
            out.groupby("symbol")["surprise"]
               .transform(lambda x: (x - x.mean()) / (x.std(ddof=0) if x.std(ddof=0) else np.nan))
        )
        return out

    def run_batch(self) -> pd.DataFrame:
        """
        전 종목 ARIMA 일괄 예측 실행.

        Returns:
            예측 결과 DataFrame (date, symbol, export_value, forecast, surprise, surprise_pct, surprise_z)
        """
        print("ARIMA 배치 예측 시작...")
        df = self.load_export_data()

        # export_value 컬럼 확인 (problem2에는 없을 수 있음 - surprise_z로 대체)
        value_col = None
        for col in ['export_value', 'export_val', 'value']:
            if col in df.columns:
                value_col = col
                break

        if value_col is None:
            print("  export_value 컬럼 없음 - vendor_analysis 데이터로 서프라이즈 직접 계산")
            return self._run_batch_from_vendor(df)

        if value_col != 'export_value':
            df = df.rename(columns={value_col: 'export_value'})

        out_list = []
        symbols = df['symbol'].unique()
        total = len(symbols)

        for idx, sym in enumerate(symbols):
            if (idx + 1) % 50 == 0:
                print(f"  진행: {idx + 1}/{total} 종목...")

            g = df[df['symbol'] == sym].sort_values('date').reset_index(drop=True)
            y = g['export_value']
            fc = self.forecast_symbol(y)
            g = g.copy()
            g['forecast'] = fc.values
            out_list.append(g)

        result = pd.concat(out_list, ignore_index=True)
        result = self.calculate_surprise(result)

        # 결과 컬럼 정리
        result = result[['date', 'symbol', 'export_value', 'forecast', 'surprise', 'surprise_pct', 'surprise_z']]
        result.sort_values(['symbol', 'date'], inplace=True)

        # 저장
        self._save_predictions(result)

        print(f"ARIMA 배치 완료: {len(symbols)} 종목, {len(result)} 행")
        return result

    def _run_batch_from_vendor(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        vendor_analysis CSV에 이미 surprise_z가 있는 경우 사용.
        export_value가 없으면 기존 surprise_z를 활용하되,
        가능한 경우 ARIMA로 재계산.
        """
        if 'surprise_z' in df.columns:
            print("  기존 surprise_z 활용 (vendor_analysis)")
            cols = [c for c in ['date', 'symbol', 'surprise_z'] if c in df.columns]
            result = df[cols].copy()
            self._save_predictions(result)
            return result

        raise ValueError("ARIMA 실행에 필요한 데이터 컬럼을 찾을 수 없습니다")

    def _save_predictions(self, df: pd.DataFrame):
        """예측 결과를 S3 또는 로컬에 저장"""
        if self.use_s3:
            self._write_csv_to_s3(df, 'data/arima_predictions_latest.csv')
        else:
            out_path = Path(__file__).parent.parent.parent / 'data' / 'arima_predictions_latest.csv'
            df.to_csv(out_path, index=False)
            print(f"  로컬 저장: {out_path}")

    def load_latest_predictions(self) -> Optional[pd.DataFrame]:
        """최신 ARIMA 예측 결과 로드"""
        try:
            if self.use_s3:
                return self._read_csv_from_s3('data/arima_predictions_latest.csv')
            else:
                path = Path(__file__).parent.parent.parent / 'data' / 'arima_predictions_latest.csv'
                if path.exists():
                    return pd.read_csv(path)
                return None
        except Exception as e:
            print(f"ARIMA 예측 결과 로드 실패: {e}")
            return None


# 싱글톤
_arima_service = None


def get_arima_service() -> ARIMASurpriseService:
    global _arima_service
    if _arima_service is None:
        _arima_service = ARIMASurpriseService()
    return _arima_service
