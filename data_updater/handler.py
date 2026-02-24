"""
StockPlay 월간 데이터 증분 업데이트 Lambda
==========================================

매월 20일 실행 → 전월 수출/주가 데이터 수집 → ARIMA 예측 → CSV 업데이트 → S3 업로드

analysis.py에서 핵심 로직 추출/경량화.
"""

import os
import io
import csv
import time
import warnings
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict

import boto3
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings('ignore')

# ── Config ───────────────────────────────────────────

S3_BUCKET = os.environ.get('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
CUSTOMS_API_KEY = os.environ.get('CUSTOMS_API_KEY', '')

ARIMA_ORDER = (1, 2, 1)
REFIT_EVERY = 3

SECTOR_STOCKS = {
    "반도체":     {"tickers": ["005930", "000660"], "names": ["삼성전자", "SK하이닉스"]},
    "자동차":     {"tickers": ["005380", "000270"], "names": ["현대자동차", "기아"]},
    "석유화학":   {"tickers": ["051910", "010950"], "names": ["LG화학", "S-Oil"]},
    "철강":       {"tickers": ["005490", "004020"], "names": ["POSCO홀딩스", "현대제철"]},
    "조선":       {"tickers": ["009540", "010140"], "names": ["HD한국조선해양", "삼성중공업"]},
    "디스플레이": {"tickers": ["034220", "006400"], "names": ["LG디스플레이", "삼성SDI"]},
    "바이오":     {"tickers": ["207940", "068270"], "names": ["삼성바이오로직스", "셀트리온"]},
    "기계":       {"tickers": ["034020", "042670"], "names": ["두산에너빌리티", "HD현대인프라코어"]},
}

SECTOR_HS = {
    "반도체":     ["8541", "8542"],
    "자동차":     ["87"],
    "석유화학":   ["29"],
    "철강":       ["72"],
    "조선":       ["89"],
    "바이오":     ["30"],
    "기계":       ["84"],
    "디스플레이": ["8528", "9013"],
}


# ── S3 Helpers ───────────────────────────────────────

s3 = boto3.client('s3', region_name='ap-northeast-2')


def read_s3_csv(key: str) -> pd.DataFrame:
    """S3에서 CSV 읽기"""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return pd.read_csv(io.BytesIO(obj['Body'].read()))
    except Exception as e:
        print(f"S3 read failed: {key} - {e}")
        return pd.DataFrame()


def write_s3_csv(df: pd.DataFrame, key: str):
    """DataFrame을 S3에 CSV로 업로드"""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue().encode('utf-8'))
    print(f"Uploaded: {key} ({len(df)} rows)")


# ── 1. 수출 데이터 수집 (단일 월) ─────────────────────

def fetch_export_month(year: int, month: int) -> pd.DataFrame:
    """관세청 API로 단일 월 수출 데이터 수집"""
    BASE_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
    rows = []

    ym = f"{year}{month:02d}"
    for sector, hs_codes in SECTOR_HS.items():
        for hs_code in hs_codes:
            url = (f"{BASE_URL}?serviceKey={CUSTOMS_API_KEY}"
                   f"&strtYymm={ym}&endYymm={ym}"
                   f"&hsSgn={hs_code}&numOfRows=1&pageNo=1")
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                for item in root.iter("item"):
                    if item.findtext("year") == "총계":
                        exp = int(item.findtext("expDlr") or "0")
                        rows.append({
                            "date": f"{year}-{month:02d}",
                            "sector": sector,
                            "hs_code": hs_code,
                            "export_usd": exp,
                        })
                        break
            except Exception:
                pass
            time.sleep(0.3)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["export_M"] = df["export_usd"] / 1e6

    # HS코드 합산 → 섹터별 수출액
    sector_monthly = (
        df.groupby(["date", "sector"])["export_M"]
        .sum()
        .reset_index()
        .rename(columns={"export_M": "export_value"})
    )
    # date → 월말 timestamp
    sector_monthly["date"] = pd.to_datetime(
        sector_monthly["date"] + "-01"
    ) + pd.offsets.MonthEnd(0)

    return sector_monthly


# ── 2. 주가 데이터 수집 (단일 월) ─────────────────────

def fetch_stock_month(year: int, month: int) -> tuple:
    """pykrx로 단일 월 주가 + KOSPI 수집"""
    from pykrx import stock

    # 해당 월의 시작/끝 날짜
    start = f"{year}{month:02d}01"
    if month == 12:
        end_dt = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_dt = datetime(year, month + 1, 1) - timedelta(days=1)
    end = end_dt.strftime("%Y%m%d")

    # 수익률 계산을 위해 다음 달까지도 필요 (20 영업일 forward)
    ext_end_dt = end_dt + timedelta(days=45)
    ext_end = ext_end_dt.strftime("%Y%m%d")

    all_data = []
    for sector, info in SECTOR_STOCKS.items():
        for ticker, name in zip(info["tickers"], info["names"]):
            try:
                df = stock.get_market_ohlcv_by_date(start, ext_end, ticker)
                time.sleep(1)
                if df.empty:
                    continue
                df = df.reset_index()
                df = df.rename(columns={
                    "날짜": "date", "종가": "close",
                })
                df["ticker"] = ticker
                df["name"] = name
                df["sector"] = sector
                all_data.append(df[["date", "ticker", "name", "sector", "close"]])
            except Exception as e:
                print(f"Stock fetch error {ticker}: {e}")

    stock_df = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    # KOSPI
    try:
        kospi = stock.get_index_ohlcv_by_date(start, ext_end, "1001")
        time.sleep(1)
        kospi = kospi.reset_index()
        kospi = kospi.rename(columns={"날짜": "date", "종가": "kospi_close"})
        kospi_df = kospi[["date", "kospi_close"]]
    except Exception as e:
        print(f"KOSPI fetch error: {e}")
        kospi_df = pd.DataFrame()

    return stock_df, kospi_df


# ── 3. 수익률 계산 (단일 월) ──────────────────────────

def calculate_month_returns(stock_df: pd.DataFrame, kospi_df: pd.DataFrame,
                            target_year: int, target_month: int) -> pd.DataFrame:
    """대상 월 월말 기준 수익률 계산"""
    if stock_df.empty:
        return pd.DataFrame()

    stock_df = stock_df.copy()
    stock_df["date"] = pd.to_datetime(stock_df["date"])
    stock_df = stock_df.sort_values(["ticker", "date"]).reset_index(drop=True)

    kospi_df = kospi_df.copy()
    if not kospi_df.empty:
        kospi_df["date"] = pd.to_datetime(kospi_df["date"])
        kospi_df = kospi_df.sort_values("date").set_index("date")

    # 대상 월 월말 영업일
    month_mask = (stock_df["date"].dt.year == target_year) & (stock_df["date"].dt.month == target_month)
    if not month_mask.any():
        return pd.DataFrame()

    month_end = stock_df.loc[month_mask, "date"].max()

    results = []
    for ticker in stock_df["ticker"].unique():
        tdf = stock_df[stock_df["ticker"] == ticker].set_index("date").sort_index()
        if month_end not in tdf.index:
            continue

        sector = tdf["sector"].iloc[0]
        name = tdf["name"].iloc[0]

        future_prices = tdf.loc[tdf.index >= month_end, "close"]
        if len(future_prices) < 2:
            continue

        base_price = future_prices.iloc[0]
        ret = {}
        for period, label in [(1, "1d"), (5, "5d"), (10, "10d"), (20, "20d")]:
            if len(future_prices) > period:
                ret[f"return_{label}"] = (future_prices.iloc[period] - base_price) / base_price
            else:
                ret[f"return_{label}"] = np.nan

        # KOSPI 20d return
        if not kospi_df.empty:
            future_kospi = kospi_df.loc[kospi_df.index >= month_end, "kospi_close"]
            if len(future_kospi) > 20:
                ret["kospi_return_20d"] = (future_kospi.iloc[20] - future_kospi.iloc[0]) / future_kospi.iloc[0]
            else:
                ret["kospi_return_20d"] = np.nan
        else:
            ret["kospi_return_20d"] = np.nan

        results.append({
            "date": month_end,
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "close_price": base_price,
            **ret,
        })

    return pd.DataFrame(results)


# ── 4. ARIMA 예측 (전체 히스토리 기반) ────────────────

def run_arima_rolling(series, order=(1, 2, 1), refit_every=3):
    """Rolling 1-step-ahead ARIMA 예측"""
    from statsmodels.tsa.arima.model import ARIMA

    n = len(series)
    min_train = max(12, order[1] + order[0] + order[2] + 3)
    forecasts = [np.nan] * min_train

    last_model = None
    for i in range(min_train, n):
        train = series[:i]
        try:
            if last_model is None or (i - min_train) % refit_every == 0:
                model = ARIMA(train, order=order)
                last_model = model.fit()
            fc = last_model.forecast(steps=1).iloc[0]
        except Exception:
            fc = train.iloc[-1]
        forecasts.append(fc)

    return pd.Series(forecasts, index=series.index)


def compute_arima_signals(export_df: pd.DataFrame) -> pd.DataFrame:
    """섹터별 ARIMA 예측 → surprise_z + global_z 계산"""
    all_results = []

    for sector in export_df["sector"].unique():
        sdf = export_df[export_df["sector"] == sector].sort_values("date").copy()
        sdf = sdf.set_index("date")
        series = sdf["export_value"]

        if len(series) < 15:
            continue

        print(f"  ARIMA {sector}: {len(series)} months")
        arima_fc = run_arima_rolling(series, order=ARIMA_ORDER, refit_every=REFIT_EVERY)

        # surprise 계산
        surprise = series - arima_fc
        surprise_pct = (surprise / arima_fc.replace(0, np.nan)) * 100
        roll_mean = surprise_pct.rolling(window=12, min_periods=6).mean()
        roll_std = surprise_pct.rolling(window=12, min_periods=6).std()
        surprise_z = (surprise_pct - roll_mean) / roll_std.replace(0, np.nan)

        result = sdf[["export_value"]].copy()
        result["sector"] = sector
        result["arima_surprise_z"] = surprise_z
        result["arima_surprise_pct"] = surprise_pct
        result = result.reset_index()
        all_results.append(result)

    if not all_results:
        return pd.DataFrame()

    combined = pd.concat(all_results, ignore_index=True)

    # Cross-sectional global Z-score
    pct_col = "arima_surprise_pct"
    g_mean = combined[pct_col].mean()
    g_std = combined[pct_col].std()
    if g_std and g_std > 0:
        combined["arima_global_z"] = (combined[pct_col] - g_mean) / g_std
    else:
        combined["arima_global_z"] = 0.0

    return combined


def merge_signals(forecast_df: pd.DataFrame, returns_df: pd.DataFrame) -> pd.DataFrame:
    """surprise_z와 종목 수익률 매칭"""
    forecast_df = forecast_df.copy()
    returns_df = returns_df.copy()
    forecast_df["date"] = pd.to_datetime(forecast_df["date"])
    returns_df["date"] = pd.to_datetime(returns_df["date"])

    forecast_df["ym"] = forecast_df["date"].dt.to_period("M")
    returns_df["ym"] = returns_df["date"].dt.to_period("M")

    z_cols = [c for c in forecast_df.columns if "surprise_z" in c or "global_z" in c]
    merge_cols = ["ym", "sector", "export_value"] + z_cols

    merged = returns_df.merge(
        forecast_df[merge_cols].drop_duplicates(["ym", "sector"]),
        on=["ym", "sector"],
        how="inner",
    )
    return merged


# ── Lambda Handler ───────────────────────────────────

def lambda_handler(event, context):
    """
    증분 업데이트:
    1. S3에서 현재 CSV 다운로드
    2. 대상 월 결정 (전월)
    3. 이미 처리된 월 스킵 (멱등성)
    4. 수출 + 주가 수집
    5. 전체 히스토리로 ARIMA fit → 시그널 병합
    6. CSV에 append, S3 업로드
    """
    print("=== StockPlay Data Updater Start ===")

    # 대상 월 결정 (전월)
    now = datetime.utcnow() + timedelta(hours=9)  # KST
    if now.month == 1:
        target_year, target_month = now.year - 1, 12
    else:
        target_year, target_month = now.year, now.month - 1

    target_ym = f"{target_year}-{target_month:02d}"
    print(f"Target month: {target_ym}")

    # S3에서 기존 데이터 로드
    print("Loading existing data from S3...")
    merged_df = read_s3_csv('data/merged_signals.csv')
    export_df = read_s3_csv('data/export_by_sector.csv')
    kospi_df = read_s3_csv('data/kospi_real.csv')

    if merged_df.empty or export_df.empty:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to load existing data from S3'})
        }

    # 멱등성 체크: 이미 해당 월 데이터가 있는지
    if 'ym' in merged_df.columns:
        existing_yms = set(merged_df['ym'].dropna().unique())
        if target_ym in existing_yms:
            msg = f"Month {target_ym} already processed. Skipping."
            print(msg)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': msg, 'skipped': True})
            }

    # Step 1: 수출 데이터 수집
    print(f"Fetching export data for {target_ym}...")
    new_export = fetch_export_month(target_year, target_month)
    if new_export.empty:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'No export data for {target_ym}'})
        }
    print(f"  Export rows: {len(new_export)}")

    # Step 2: 주가 데이터 수집
    print(f"Fetching stock prices for {target_ym}...")
    stock_df, new_kospi = fetch_stock_month(target_year, target_month)
    if stock_df.empty:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'No stock data for {target_ym}'})
        }
    print(f"  Stock rows: {len(stock_df)}, KOSPI rows: {len(new_kospi)}")

    # Step 3: 수익률 계산
    print("Calculating returns...")
    returns_df = calculate_month_returns(stock_df, new_kospi, target_year, target_month)
    if returns_df.empty:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'No returns calculated for {target_ym}'})
        }
    print(f"  Returns rows: {len(returns_df)}")

    # Step 4: export_by_sector에 새 데이터 추가
    export_df['date'] = pd.to_datetime(export_df['date'])
    updated_export = pd.concat([export_df, new_export], ignore_index=True)
    updated_export = updated_export.drop_duplicates(subset=['date', 'sector'], keep='last')
    updated_export = updated_export.sort_values(['sector', 'date']).reset_index(drop=True)

    # Step 5: 전체 히스토리로 ARIMA fit
    print("Running ARIMA on full history...")
    forecast_df = compute_arima_signals(updated_export)
    if forecast_df.empty:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'ARIMA computation failed'})
        }

    # Step 6: 시그널 병합
    print("Merging signals...")
    new_merged = merge_signals(forecast_df, returns_df)
    if new_merged.empty:
        print("Warning: merge produced empty result, using returns only")

    # ym 컬럼을 문자열로 통일
    if not new_merged.empty:
        new_merged['ym'] = target_ym
        # 기존 merged_df에 append
        # 기존 데이터의 ym도 문자열로 변환
        merged_df['ym'] = merged_df['ym'].astype(str)
        updated_merged = pd.concat([merged_df, new_merged], ignore_index=True)
        updated_merged = updated_merged.drop_duplicates(
            subset=['date', 'ticker', 'ym'], keep='last'
        )
    else:
        updated_merged = merged_df

    # Step 7: KOSPI 업데이트
    if not new_kospi.empty:
        kospi_df['date'] = pd.to_datetime(kospi_df['date'])
        new_kospi['date'] = pd.to_datetime(new_kospi['date'])
        updated_kospi = pd.concat([kospi_df, new_kospi], ignore_index=True)
        updated_kospi = updated_kospi.drop_duplicates(subset=['date'], keep='last')
        updated_kospi = updated_kospi.sort_values('date').reset_index(drop=True)
    else:
        updated_kospi = kospi_df

    # Step 8: S3 업로드
    print("Uploading updated data to S3...")
    write_s3_csv(updated_merged, 'data/merged_signals.csv')
    write_s3_csv(updated_export, 'data/export_by_sector.csv')
    write_s3_csv(updated_kospi, 'data/kospi_real.csv')

    result = {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Successfully updated data for {target_ym}',
            'new_signals': len(new_merged) if not new_merged.empty else 0,
            'total_signals': len(updated_merged),
            'target_month': target_ym,
        })
    }
    print(f"=== Done: {result} ===")
    return result
