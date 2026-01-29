"""
Chinese to English Translation Module for Che168 car titles.
Uses deep-translator with PostgreSQL caching for Heroku.
"""

import time
import logging
import threading
import os
import psycopg2

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TooManyRequests, RequestError, TranslationNotFound

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
RATE_LIMIT_DELAY = 0.2  # 5 req/sec

# Rate limiter
_last_request_time = 0
_rate_lock = threading.Lock()

# Hardcoded brand translations for accuracy
BRAND_TRANSLATIONS = {
    "宝马": "BMW",
    "奔驰": "Mercedes-Benz",
    "奥迪": "Audi",
    "大众": "Volkswagen",
    "丰田": "Toyota",
    "本田": "Honda",
    "日产": "Nissan",
    "马自达": "Mazda",
    "雷克萨斯": "Lexus",
    "保时捷": "Porsche",
    "沃尔沃": "Volvo",
    "现代": "Hyundai",
    "起亚": "Kia",
    "特斯拉": "Tesla",
    "比亚迪": "BYD",
    "吉利": "Geely",
    "长城": "Great Wall",
    "红旗": "Hongqi",
    "蔚来": "NIO",
    "理想": "Li Auto",
    "小鹏": "Xpeng",
    "领克": "Lynk & Co",
    "哈弗": "Haval",
    "坦克": "Tank",
    "极氪": "Zeekr",
    "福特": "Ford",
    "雪佛兰": "Chevrolet",
    "别克": "Buick",
    "凯迪拉克": "Cadillac",
    "林肯": "Lincoln",
    "捷豹": "Jaguar",
    "路虎": "Land Rover",
    "阿斯顿马丁": "Aston Martin",
    "宾利": "Bentley",
    "劳斯莱斯": "Rolls-Royce",
    "法拉利": "Ferrari",
    "兰博基尼": "Lamborghini",
    "玛莎拉蒂": "Maserati",
    "阿尔法罗密欧": "Alfa Romeo",
    "菲亚特": "Fiat",
    "标致": "Peugeot",
    "雪铁龙": "Citroën",
    "雷诺": "Renault",
    "斯巴鲁": "Subaru",
    "三菱": "Mitsubishi",
    "铃木": "Suzuki",
    "英菲尼迪": "Infiniti",
    "讴歌": "Acura",
    "斯柯达": "Skoda",
    "西雅特": "SEAT",
    "迷你": "MINI",
    "smart": "Smart",
    "长安": "Changan",
    "奇瑞": "Chery",
    "荣威": "Roewe",
    "名爵": "MG",
    "传祺": "GAC Trumpchi",
    "五菱": "Wuling",
    "宝骏": "Baojun",
    "欧拉": "ORA",
    "魏牌": "WEY",
    "零跑": "Leapmotor",
    "哪吒": "Neta",
    "高合": "HiPhi",
    "极狐": "Arcfox",
    "岚图": "Voyah",
    "智己": "IM Motors",
    "飞凡": "Rising Auto",
    "腾势": "Denza",
    "仰望": "Yangwang",
    "方程豹": "Fang Cheng Bao",
}

# Common automotive terms
TERM_TRANSLATIONS = {
    "款": "Model",
    "系": "Series",
    "型": "Type",
    "版": "Edition",
    "运动": "Sport",
    "豪华": "Luxury",
    "尊享": "Premium",
    "旗舰": "Flagship",
    "标准": "Standard",
    "舒适": "Comfort",
    "时尚": "Fashion",
    "进取": "Progressive",
    "领先": "Leading",
    "套装": "Package",
    "四驱": "AWD",
    "两驱": "2WD",
    "混动": "Hybrid",
    "纯电": "Electric",
    "插电": "Plug-in",
    "增程": "EREV",
    "涡轮增压": "Turbo",
    "自然吸气": "NA",
    "手动": "Manual",
    "自动": "Auto",
    "双离合": "DCT",
    "无级变速": "CVT",
}


class PostgresTranslationCache:
    """Persistent cache using existing PostgreSQL database."""

    def __init__(self):
        self._table_ensured = False

    def _ensure_table(self):
        """Create translation_cache table if it doesn't exist."""
        if self._table_ensured:
            return

        if not DATABASE_URL:
            logging.warning("DATABASE_URL not set, cache disabled")
            return

        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translation_cache (
                    chinese_text TEXT PRIMARY KEY,
                    english_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
            self._table_ensured = True
            logging.info("Translation cache table ensured")
        except Exception as e:
            logging.error(f"Failed to ensure translation cache table: {e}")

    def get(self, chinese_text: str) -> str | None:
        """Get cached translation from PostgreSQL."""
        self._ensure_table()

        if not DATABASE_URL:
            return None

        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT english_text FROM translation_cache WHERE chinese_text = %s",
                (chinese_text,)
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                logging.debug(f"Cache hit for: {chinese_text[:30]}...")
                return result[0]
            return None
        except Exception as e:
            logging.error(f"Cache get error: {e}")
            return None

    def set(self, chinese_text: str, english_text: str):
        """Store translation in PostgreSQL cache."""
        self._ensure_table()

        if not DATABASE_URL:
            return

        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO translation_cache (chinese_text, english_text)
                VALUES (%s, %s)
                ON CONFLICT (chinese_text) DO UPDATE SET english_text = EXCLUDED.english_text
            """, (chinese_text, english_text))
            conn.commit()
            cursor.close()
            conn.close()
            logging.debug(f"Cached translation for: {chinese_text[:30]}...")
        except Exception as e:
            logging.error(f"Cache set error: {e}")


# Global cache instance
_cache = PostgresTranslationCache()


def _rate_limit():
    """Enforce 5 requests/second rate limit."""
    global _last_request_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.time()


def _apply_brand_mapping(text: str) -> str:
    """Replace Chinese brand names with proper English names."""
    result = text
    for chinese, english in BRAND_TRANSLATIONS.items():
        if chinese in result:
            result = result.replace(chinese, english)
    return result


def _apply_term_mapping(text: str) -> str:
    """Replace common Chinese automotive terms with English equivalents."""
    result = text
    for chinese, english in TERM_TRANSLATIONS.items():
        if chinese in result:
            result = result.replace(chinese, english)
    return result


def _translate_with_retry(text: str) -> str:
    """Translate text with exponential backoff retry."""
    for attempt in range(MAX_RETRIES):
        try:
            _rate_limit()
            translator = GoogleTranslator(source='zh-CN', target='en')
            result = translator.translate(text)
            return result if result else text
        except TooManyRequests:
            delay = RETRY_DELAY_BASE * (2 ** attempt)
            logging.warning(f"Translation rate limited, retry in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(delay)
        except (RequestError, TranslationNotFound) as e:
            logging.warning(f"Translation error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES - 1:
                return text
            time.sleep(RETRY_DELAY_BASE)
        except Exception as e:
            logging.error(f"Unexpected translation error: {e}")
            return text
    return text


def translate_car_title(chinese_text: str) -> str:
    """
    Translate Chinese car title to English.

    Uses PostgreSQL caching to avoid repeated API calls.
    Falls back to brand/term mapping if translation fails.

    Args:
        chinese_text: Original Chinese car title from Che168

    Returns:
        English translation, or original text with brand mapping if translation fails
    """
    if not chinese_text:
        return chinese_text

    # Strip whitespace
    chinese_text = chinese_text.strip()

    # Check cache first
    cached = _cache.get(chinese_text)
    if cached:
        return cached

    try:
        # Apply brand mapping first (ensures proper brand names)
        text_with_brands = _apply_brand_mapping(chinese_text)

        # Check if any Chinese characters remain after brand mapping
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text_with_brands)

        if not has_chinese:
            # No Chinese characters left, just return with brand mapping
            _cache.set(chinese_text, text_with_brands)
            return text_with_brands

        # Translate the remaining text
        result = _translate_with_retry(text_with_brands)

        # Clean up the result
        result = result.strip()

        # Cache result if translation was successful
        if result and result != chinese_text:
            _cache.set(chinese_text, result)
            logging.info(f"Translated: '{chinese_text}' -> '{result}'")

        return result

    except Exception as e:
        logging.error(f"Translation failed for '{chinese_text}': {e}")
        # Fallback: return with brand and term mappings applied
        fallback = _apply_term_mapping(_apply_brand_mapping(chinese_text))
        return fallback


def translate_batch(chinese_texts: list[str]) -> list[str]:
    """
    Translate multiple Chinese car titles to English.

    Args:
        chinese_texts: List of Chinese car titles

    Returns:
        List of English translations in the same order
    """
    return [translate_car_title(text) for text in chinese_texts]


# For testing
if __name__ == "__main__":
    # Test translations
    test_titles = [
        "宝马 3系 2020款 325Li M运动套装",
        "奔驰 E级 2021款 E300L 豪华型",
        "丰田 凯美瑞 2022款 2.5L 双擎豪华版",
        "特斯拉 Model 3 2023款 长续航全轮驱动版",
        "比亚迪 汉 2023款 EV 冠军版 610KM 四驱旗舰型",
    ]

    print("Testing Chinese to English translation:\n")
    for title in test_titles:
        translated = translate_car_title(title)
        print(f"Original:   {title}")
        print(f"Translated: {translated}")
        print("-" * 60)
