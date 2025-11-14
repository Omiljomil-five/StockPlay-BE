"""Pillow를 사용한 경량 차트 생성"""
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import io
from typing import List, Dict, Any, Tuple
import os
import csv
from io import StringIO


def load_kospi_data(days: int = 60) -> Tuple[List[datetime], List[float]]:
    """KOSPI 데이터 로드"""
    try:
        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'

        if use_s3:
            import boto3
            s3_bucket = os.getenv('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
            s3 = boto3.client('s3')

            obj = s3.get_object(Bucket=s3_bucket, Key='data/kospi.csv')
            csv_content = obj['Body'].read().decode('utf-8-sig')

            reader = csv.DictReader(StringIO(csv_content))
            data = []
            for row in reader:
                data.append({
                    'date': row.get('date', '').strip(),
                    'close': float(row.get('close', 0)),
                })
        else:
            from pathlib import Path
            data_path = Path(__file__).parent.parent.parent / 'data' / 'kospi.csv'

            with open(data_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = []
                for row in reader:
                    data.append({
                        'date': row.get('date', '').strip(),
                        'close': float(row.get('close', 0)),
                    })

        # 유효한 데이터만 필터링
        valid_data = []
        for d in data:
            try:
                if d['date'] and d['close'] > 0:
                    valid_data.append(d)
            except (KeyError, TypeError, ValueError):
                continue

        if not valid_data:
            raise Exception("유효한 KOSPI 데이터가 없습니다")

        # 최근 N일 데이터
        valid_data = sorted(valid_data, key=lambda x: x['date'])[-days:]

        dates = []
        closes = []

        for d in valid_data:
            try:
                dates.append(datetime.strptime(d['date'], '%Y-%m-%d'))
                closes.append(float(d['close']))
            except Exception:
                continue

        print(f"✅ KOSPI 데이터 로드 완료: {len(dates)}일")
        return dates, closes

    except Exception as e:
        print(f"⚠️ KOSPI 데이터 로드 실패: {e}, Mock 데이터 사용")
        # Fallback: Mock 데이터
        dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
        closes = [2500 + i * 2 for i in range(days)]
        return dates, closes


def generate_kospi_chart_pillow(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """
    Pillow로 KOSPI 차트 생성

    Args:
        signal_data: 시그널 데이터
        days: 표시 일수

    Returns:
        PNG 이미지 바이트
    """
    print(f"📊 Pillow KOSPI 차트 생성 시작 (days={days})")

    try:
        # KOSPI 데이터 로드
        dates, closes = load_kospi_data(days)

        if not dates or not closes:
            raise Exception("데이터가 비어있습니다")

        # 이미지 크기
        width, height = 1200, 600
        padding = 80
        chart_width = width - 2 * padding
        chart_height = height - 2 * padding

        # 배경색
        bg_color = (26, 31, 58)  # #1a1f3a
        line_color = (76, 111, 255)  # #4c6fff
        grid_color = (42, 47, 74)  # #2a2f4a
        text_color = (229, 231, 235)  # #e5e7eb

        # 이미지 생성
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # 폰트 (시스템 기본 폰트 사용)
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()

        # 제목
        title = "KOSPI Technical Analysis"
        draw.text((width // 2, 30), title, fill=text_color, font=title_font, anchor="mm")

        # 데이터 정규화
        min_price = min(closes)
        max_price = max(closes)
        price_range = max_price - min_price

        if price_range == 0:
            price_range = 1

        def normalize_y(price):
            return padding + chart_height - int((price - min_price) / price_range * chart_height)

        def normalize_x(index):
            return padding + int(index / (len(closes) - 1) * chart_width)

        # 그리드 그리기
        for i in range(5):
            y = padding + int(i * chart_height / 4)
            draw.line([(padding, y), (width - padding, y)], fill=grid_color, width=1)

            # 가격 레이블
            price = max_price - (i * price_range / 4)
            draw.text((padding - 10, y), f"{price:.0f}", fill=text_color, font=label_font, anchor="rm")

        # KOSPI 선 그리기
        points = []
        for i, (date, close) in enumerate(zip(dates, closes)):
            x = normalize_x(i)
            y = normalize_y(close)
            points.append((x, y))

        # 선 그리기
        if len(points) > 1:
            draw.line(points, fill=line_color, width=3)

        # 현재 포인트 강조
        if points:
            last_x, last_y = points[-1]
            draw.ellipse([last_x - 8, last_y - 8, last_x + 8, last_y + 8],
                        fill=(245, 158, 11), outline=(255, 255, 255))

            # 현재 가격 표시
            current_price = closes[-1]
            draw.text((last_x, last_y - 20), f"{current_price:.0f}",
                     fill=(245, 158, 11), font=label_font, anchor="mm")

        # 날짜 레이블
        date_indices = [0, len(dates) // 2, len(dates) - 1]
        for idx in date_indices:
            if idx < len(dates):
                x = normalize_x(idx)
                date_str = dates[idx].strftime('%m/%d')
                draw.text((x, height - padding + 20), date_str,
                         fill=text_color, font=label_font, anchor="mm")

        # 범례
        legend_y = padding + 20
        draw.rectangle([padding, legend_y, padding + 200, legend_y + 30],
                      fill=(17, 24, 39), outline=grid_color)
        draw.line([(padding + 10, legend_y + 15), (padding + 40, legend_y + 15)],
                 fill=line_color, width=3)
        draw.text((padding + 50, legend_y + 15), "KOSPI Index",
                 fill=text_color, font=label_font, anchor="lm")

        # 이미지를 바이트로 변환
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        print(f"✅ Pillow 차트 생성 완료: {len(buf.getvalue())} bytes")
        return buf.getvalue()

    except Exception as e:
        print(f"❌ Pillow 차트 생성 실패: {e}")
        import traceback
        traceback.print_exc()

        # 에러 발생 시 간단한 에러 이미지 반환
        img = Image.new('RGB', (800, 400), (26, 31, 58))
        draw = ImageDraw.Draw(img)
        draw.text((400, 200), "Chart generation error", fill=(239, 68, 68),
                 anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()
