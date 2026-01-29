"""
Chinese to English Translation Module for Che168 car titles.
Uses deep-translator with PostgreSQL caching for Heroku.

Updated with comprehensive brand dictionary (240+ brands) from Che168.com
and improved translation logic for accurate model name handling.
"""

import time
import logging
import threading
import os
import re
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

# =============================================================================
# COMPREHENSIVE BRAND TRANSLATIONS (240+ brands from Che168.com)
# Ordered by key length (longest first) for proper matching
# =============================================================================
BRAND_TRANSLATIONS = {
    # === SUB-BRANDS (must come before parent brands for correct matching) ===

    # Geely sub-brands
    "吉利银河": "Geely Galaxy",
    "银河": "Geely Galaxy",  # Sub-brand appears alone in car titles
    "吉利几何": "Geely Geometry",
    "几何汽车": "Geely Geometry",
    "吉利雷达": "Geely Radar",
    "雷达汽车": "Geely Radar",

    # BYD sub-brands
    "方程豹": "BYD Fangchengbao",
    "仰望": "BYD Yangwang",
    "腾势汽车": "Denza",
    "腾势": "Denza",
    "深蓝汽车": "Deepal",
    "深蓝": "Deepal",

    # Great Wall sub-brands
    "哈弗汽车": "Haval",
    "哈弗": "Haval",
    "坦克": "Tank",
    "魏牌": "WEY",
    "欧拉": "ORA",
    "沙龙汽车": "Salon",

    # Changan sub-brands
    "长安启源": "Changan Qiyuan",
    "启源": "Changan Qiyuan",
    "阿维塔": "Avatr",

    # Dongfeng sub-brands
    "东风风行": "Dongfeng Fengxing",
    "东风风神": "Dongfeng Fengshen",
    "东风风光": "Dongfeng Fengguang",
    "东风奕派": "Dongfeng Yipai",
    "奕派": "Dongfeng Yipai",
    "猛士": "Mengshi",
    "岚图汽车": "Voyah",
    "岚图": "Voyah",

    # BAIC sub-brands
    "北京汽车": "BAIC",
    "北汽新能源": "BAIC BJEV",
    "北汽蓝谷": "BAIC Blue Park",
    "极狐汽车": "Arcfox",
    "极狐": "Arcfox",
    "北京越野": "BAIC BJ",
    "北京": "BAIC Beijing",

    # GAC sub-brands
    "广汽传祺": "GAC Trumpchi",
    "广汽埃安": "GAC Aion",
    "埃安": "GAC Aion",
    "广汽新能源": "GAC New Energy",
    "合创汽车": "Hycan",
    "合创": "Hycan",

    # Chery sub-brands
    "奇瑞汽车": "Chery",
    "奇瑞风云": "Chery Fengyun",
    "星途": "Exeed",
    "星纪元": "Sterra",
    "捷途汽车": "Jetour",
    "捷途": "Jetour",
    "iCAR": "iCAR",

    # SAIC sub-brands
    "上汽大众": "SAIC Volkswagen",
    "上汽通用": "SAIC GM",
    "上汽荣威": "Roewe",
    "上汽名爵": "MG",
    "飞凡汽车": "Rising Auto",
    "飞凡": "Rising Auto",
    "智己汽车": "IM Motors",
    "智己": "IM Motors",

    # FAW sub-brands
    "一汽大众": "FAW Volkswagen",
    "一汽丰田": "FAW Toyota",
    "一汽奔腾": "FAW Besturn",
    "奔腾": "FAW Besturn",
    "红旗": "Hongqi",

    # Huawei ecosystem brands
    "问界": "AITO",
    "智界": "Zhijie",
    "享界": "Luxeed",
    "尊界": "Zunjie",
    "鸿蒙智行": "Harmony Intelligent Mobility",

    # === NEW EV BRANDS ===
    "蔚来汽车": "NIO",
    "蔚来": "NIO",
    "小鹏汽车": "Xpeng",
    "小鹏": "Xpeng",
    "理想汽车": "Li Auto",
    "理想": "Li Auto",
    "极氪": "Zeekr",
    "极越汽车": "Jiyue",
    "极越": "Jiyue",
    "零跑汽车": "Leapmotor",
    "零跑": "Leapmotor",
    "哪吒汽车": "Neta",
    "哪吒": "Neta",
    "高合汽车": "HiPhi",
    "高合": "HiPhi",
    "小米汽车": "Xiaomi Auto",
    "小米": "Xiaomi Auto",
    "华为": "Huawei",

    # === OTHER CHINESE BRANDS ===
    "吉利汽车": "Geely",
    "吉利": "Geely",
    "比亚迪": "BYD",
    "长城汽车": "Great Wall",
    "长城": "Great Wall",
    "长安汽车": "Changan",
    "长安": "Changan",
    "奇瑞": "Chery",
    "东风汽车": "Dongfeng",
    "东风": "Dongfeng",
    "传祺": "GAC Trumpchi",
    "五菱汽车": "Wuling",
    "五菱": "Wuling",
    "宝骏": "Baojun",
    "荣威": "Roewe",
    "名爵": "MG",
    "领克": "Lynk & Co",
    "威马汽车": "WM Motor",
    "威马": "WM Motor",
    "爱驰汽车": "Aiways",
    "爱驰": "Aiways",
    "天际汽车": "Enovate",
    "天际": "Enovate",
    "恒驰汽车": "Hengchi",
    "恒驰": "Hengchi",
    "睿蓝汽车": "Ruilan",
    "睿蓝": "Ruilan",
    "曹操汽车": "Caocao Auto",
    "创维汽车": "Skyworth Auto",
    "创维": "Skyworth Auto",
    "东风启辰": "Venucia",
    "启辰": "Venucia",
    "海马汽车": "Haima",
    "海马": "Haima",
    "江淮汽车": "JAC",
    "江淮": "JAC",
    "众泰汽车": "Zotye",
    "众泰": "Zotye",
    "力帆汽车": "Lifan",
    "力帆": "Lifan",
    "陆风汽车": "Landwind",
    "陆风": "Landwind",
    "猎豹汽车": "Leopaard",
    "猎豹": "Leopaard",
    "开瑞汽车": "Karry",
    "开瑞": "Karry",
    "凯翼汽车": "Cowin",
    "凯翼": "Cowin",
    "观致汽车": "Qoros",
    "观致": "Qoros",
    "金杯汽车": "Jinbei",
    "金杯": "Jinbei",
    "华晨汽车": "Brilliance",
    "华晨": "Brilliance",
    "中华汽车": "Brilliance China",
    "中华": "Brilliance China",
    "东南汽车": "Soueast",
    "东南": "Soueast",
    "汉腾汽车": "Hanteng",
    "汉腾": "Hanteng",
    "思皓": "SOL",
    "云度汽车": "Yudo",
    "云度": "Yudo",
    "新特汽车": "Sitech",
    "新特": "Sitech",
    "国机智骏": "GYON",
    "智骏": "GYON",
    "天美汽车": "Skywell",
    "天美": "Skywell",
    "恒润汽车": "Hengren",
    "盛唐汽车": "Shengtang",
    "远航汽车": "Yuanhang Auto",  # Full brand name only
    "极石汽车": "Polarstone",
    "极石": "Polarstone",
    "创业者": "Chuangyezhe",
    "纳智捷": "Luxgen",
    "悦达": "Yueda",
    "知豆": "Zhidou",
    "速达": "Suda",
    "御捷": "Yujie",
    "瑞驰": "Ruichi",
    "雷丁汽车": "Leiding",
    "雷丁": "Leiding",

    # === JAPANESE BRANDS ===
    "丰田汽车": "Toyota",
    "丰田": "Toyota",
    "本田汽车": "Honda",
    "本田": "Honda",
    "日产汽车": "Nissan",
    "日产": "Nissan",
    "马自达": "Mazda",
    "斯巴鲁": "Subaru",
    "三菱汽车": "Mitsubishi",
    "三菱": "Mitsubishi",
    "铃木": "Suzuki",
    "雷克萨斯": "Lexus",
    "英菲尼迪": "Infiniti",
    "讴歌": "Acura",
    "五十铃": "Isuzu",
    "大发": "Daihatsu",

    # === GERMAN BRANDS ===
    "宝马": "BMW",
    "奔驰": "Mercedes-Benz",
    "梅赛德斯": "Mercedes-Benz",
    "奥迪": "Audi",
    "大众汽车": "Volkswagen",
    "大众": "Volkswagen",
    "保时捷": "Porsche",
    "迈巴赫": "Mercedes-Maybach",
    "斯柯达": "Skoda",
    "smart": "Smart",
    "迷你": "MINI",

    # === AMERICAN BRANDS ===
    "福特汽车": "Ford",
    "福特": "Ford",
    "雪佛兰": "Chevrolet",
    "别克": "Buick",
    "凯迪拉克": "Cadillac",
    "林肯": "Lincoln",
    "特斯拉": "Tesla",
    "道奇": "Dodge",
    "克莱斯勒": "Chrysler",
    "Jeep": "Jeep",
    "吉普": "Jeep",
    "悍马": "Hummer",
    "GMC": "GMC",
    "RAM": "RAM",
    "菲斯克": "Fisker",
    "Lucid": "Lucid",
    "Rivian": "Rivian",

    # === KOREAN BRANDS ===
    "现代汽车": "Hyundai",
    "现代": "Hyundai",
    "起亚": "Kia",
    "捷尼赛思": "Genesis",
    "双龙": "SsangYong",

    # === EUROPEAN BRANDS ===
    "沃尔沃": "Volvo",
    "极星": "Polestar",
    "标致": "Peugeot",
    "雪铁龙": "Citroën",
    "DS": "DS",
    "雷诺": "Renault",
    "菲亚特": "Fiat",
    "阿尔法罗密欧": "Alfa Romeo",
    "阿尔法·罗密欧": "Alfa Romeo",
    "玛莎拉蒂": "Maserati",
    "法拉利": "Ferrari",
    "兰博基尼": "Lamborghini",
    "宾利": "Bentley",
    "劳斯莱斯": "Rolls-Royce",
    "阿斯顿马丁": "Aston Martin",
    "阿斯顿·马丁": "Aston Martin",
    "迈凯伦": "McLaren",
    "迈凯轮": "McLaren",
    "路虎": "Land Rover",
    "揽胜": "Range Rover",
    "捷豹": "Jaguar",
    "路特斯": "Lotus",
    "西雅特": "SEAT",
    "布加迪": "Bugatti",
    "帕加尼": "Pagani",
    "柯尼塞格": "Koenigsegg",
    "摩根": "Morgan",
    "光冈": "Mitsuoka",
    "达契亚": "Dacia",
    "欧宝": "Opel",
    "萨博": "Saab",
    "斯堪尼亚": "Scania",
    "依维柯": "Iveco",

    # === COMMERCIAL & TRUCKS ===
    "福田汽车": "Foton",
    "福田": "Foton",
    "江铃汽车": "JMC",
    "江铃": "JMC",
    "上汽大通": "Maxus",
    "大通": "Maxus",
    "依维柯": "Iveco",
    "皮卡": "Pickup",
    "卡车": "Truck",
    "重汽": "Sinotruk",
    "解放": "FAW Jiefang",
    "陕汽": "Shacman",
    "柳汽": "Liuzhou",
}

# =============================================================================
# COMPREHENSIVE TERM TRANSLATIONS
# Model names, trim levels, and automotive terms that are commonly mistranslated
# =============================================================================
TERM_TRANSLATIONS = {
    # === MODEL NAME TERMS (commonly mistranslated) ===
    "星舰": "Starship",  # NOT "Star" - Geely Galaxy model
    "星越": "Xingyue",
    "星瑞": "Xingrui",
    "博越": "Boyue",
    "帝豪": "Emgrand",
    "缤越": "Binyue",
    "缤瑞": "Binrui",
    "远景": "Vision",
    "豪越": "Haoyue",

    # === EDITION/VERSION TERMS ===
    "款": "",  # Year model indicator, often redundant in English
    "版": "Edition",
    "型": "Type",
    "系": "Series",

    # === TRIM LEVELS ===
    "远航": "Voyager",  # NOT "sailing" - common Geely trim
    "领航": "Navigator",
    "旗舰": "Flagship",
    "豪华": "Luxury",
    "尊享": "Premium",
    "尊贵": "Prestige",
    "舒适": "Comfort",
    "运动": "Sport",
    "标准": "Standard",
    "进取": "Progressive",
    "领先": "Leading",
    "套装": "Package",
    "冠军": "Champion",
    "时尚": "Fashion",
    "精英": "Elite",
    "智享": "Smart",
    "臻享": "Ultimate",
    "至尊": "Supreme",
    "行政": "Executive",
    "典藏": "Heritage",
    "限量": "Limited",
    "特别": "Special",
    "纪念": "Anniversary",
    "创始": "Founder",
    "先锋": "Pioneer",
    "探索": "Explorer",
    "城市": "City",
    "都市": "Urban",
    "越野": "Off-road",
    "性能": "Performance",
    "高性能": "High Performance",

    # === POWERTRAIN ===
    "纯电": "EV",
    "纯电动": "BEV",
    "插电混动": "PHEV",
    "插电式混动": "PHEV",
    "插电": "Plug-in",
    "混动": "Hybrid",
    "油电混合": "HEV",
    "增程": "EREV",
    "增程式": "EREV",
    "汽油": "Gasoline",
    "柴油": "Diesel",
    "天然气": "CNG",
    "氢燃料": "Hydrogen",
    "双擎": "Dual Engine",
    "三擎": "Triple Engine",
    "涡轮增压": "Turbo",
    "双涡轮增压": "Twin Turbo",
    "机械增压": "Supercharged",
    "自然吸气": "NA",

    # === DRIVETRAIN ===
    "四驱": "AWD",
    "全驱": "AWD",
    "全轮驱动": "AWD",
    "两驱": "2WD",
    "前驱": "FWD",
    "后驱": "RWD",

    # === TRANSMISSION ===
    "手动": "Manual",
    "自动": "Auto",
    "双离合": "DCT",
    "无级变速": "CVT",
    "手自一体": "Tiptronic",
    "湿式双离合": "Wet DCT",
    "干式双离合": "Dry DCT",
    "8AT": "8AT",
    "9AT": "9AT",
    "10AT": "10AT",

    # === RANGE/BATTERY ===
    "续航": "Range",
    "长续航": "Long Range",
    "超长续航": "Extended Range",
    "标准续航": "Standard Range",
    "电池": "Battery",
    "大电池": "Large Battery",

    # === BODY TYPES ===
    "三厢": "Sedan",
    "两厢": "Hatchback",
    "掀背": "Liftback",
    "旅行": "Wagon",
    "轿跑": "Coupe",
    "敞篷": "Convertible",
    "硬顶": "Hardtop",
    "软顶": "Soft Top",
    "猎装": "Shooting Brake",

    # === SEATING ===
    "座": "Seats",
    "五座": "5-Seater",
    "六座": "6-Seater",
    "七座": "7-Seater",

    # === OTHER FEATURES ===
    "空气悬挂": "Air Suspension",
    "智能": "Intelligent",
    "互联": "Connected",
    "辅助驾驶": "Driving Assist",
    "自动驾驶": "Autonomous",
    "激光雷达": "LiDAR",
}

# =============================================================================
# POST-PROCESSING CORRECTIONS
# Common Google Translate mistakes that we can fix deterministically
# These use regex patterns with word boundaries to avoid partial matches
# =============================================================================

# Patterns that need word boundary matching (regex-based)
POST_PROCESS_PATTERNS = [
    # Model name corrections - must check word boundaries
    (r'\bGalaxy Star\b(?!ship)', 'Galaxy Starship'),  # "Galaxy Star" but not "Galaxy Starship"
    (r'\bStar Ship\b', 'Starship'),
    (r'\bStar 6\b', 'Starship 6'),
    (r'\bStar 7\b', 'Starship 7'),
    (r'\bStar 8\b', 'Starship 8'),

    # Trim level corrections
    (r'\bsailing version\b', 'Voyager Edition'),
    (r'\bSailing version\b', 'Voyager Edition'),
    (r'\bsailing\b', 'Voyager'),
    (r'\bSailing\b', 'Voyager'),

    # Version -> Edition corrections
    (r'\bchampion version\b', 'Champion Edition'),
    (r'\bChampion version\b', 'Champion Edition'),
    (r'\bluxury version\b', 'Luxury Edition'),
    (r'\bLuxury version\b', 'Luxury Edition'),
    (r'\bsports version\b', 'Sport Edition'),
    (r'\bSports version\b', 'Sport Edition'),
    (r'\bflagship version\b', 'Flagship Edition'),
    (r'\bFlagship version\b', 'Flagship Edition'),
    (r'\bcomfort version\b', 'Comfort Edition'),
    (r'\bComfort version\b', 'Comfort Edition'),
    (r'\bpremium version\b', 'Premium Edition'),
    (r'\bPremium version\b', 'Premium Edition'),
    (r'\bstandard version\b', 'Standard Edition'),
    (r'\bStandard version\b', 'Standard Edition'),

    # Common mistranslations (word boundary to avoid "Voyager" -> "Voyagerr")
    (r'\bvoyage\b', 'Voyager'),
    (r'\bVoyage\b', 'Voyager'),
    (r'\bcruising\b', 'Range'),
    (r'\bCruising\b', 'Range'),
    (r'\bendurance\b', 'Range'),
    (r'\bEndurance\b', 'Range'),
    (r'\bbattery life\b', 'Range'),
    (r'\bfour-wheel drive\b', 'AWD'),
    (r'\bFour-wheel drive\b', 'AWD'),
    (r'\ball-wheel drive\b', 'AWD'),
    (r'\bAll-wheel drive\b', 'AWD'),
    (r'\btwo-wheel drive\b', '2WD'),
    (r'\bTwo-wheel drive\b', '2WD'),
    (r'\bpure electric\b', 'EV'),
    (r'\bPure electric\b', 'EV'),
    (r'\ball electric\b', 'EV'),
    (r'\bAll electric\b', 'EV'),
]

# Simple string replacements (no word boundary needed)
POST_PROCESS_SIMPLE = {
    " Edition Edition": " Edition",  # Duplicate Edition
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

# Pre-sorted brand list for longest-match-first processing
_sorted_brands = sorted(BRAND_TRANSLATIONS.keys(), key=len, reverse=True)
_sorted_terms = sorted(TERM_TRANSLATIONS.keys(), key=len, reverse=True)


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
    """
    Replace Chinese brand names with proper English names.
    Uses longest-match-first to handle sub-brands correctly.

    For example: "银河" must be matched before "吉利" to get "Geely Galaxy"
    """
    result = text
    for chinese in _sorted_brands:
        if chinese in result:
            english = BRAND_TRANSLATIONS[chinese]
            # Add space after brand name if followed by Chinese or alphanumeric
            result = result.replace(chinese, english + " ")
    # Clean up multiple spaces
    while "  " in result:
        result = result.replace("  ", " ")
    return result.strip()


def _apply_term_mapping(text: str) -> str:
    """
    Replace common Chinese automotive terms with English equivalents.
    Uses longest-match-first for proper handling.
    """
    result = text
    for chinese in _sorted_terms:
        if chinese in result:
            english = TERM_TRANSLATIONS[chinese]
            if english:  # Only add space if there's actual replacement text
                result = result.replace(chinese, english + " ")
            else:
                result = result.replace(chinese, " ")  # Just remove the Chinese char
    # Clean up multiple spaces
    while "  " in result:
        result = result.replace("  ", " ")
    return result.strip()


def _post_process(text: str) -> str:
    """
    Fix common Google Translate mistakes after translation.
    Applies deterministic corrections for known mistranslations.
    Uses regex with word boundaries to avoid partial matches.
    """
    result = text

    # Apply regex-based patterns with word boundaries
    for pattern, replacement in POST_PROCESS_PATTERNS:
        result = re.sub(pattern, replacement, result)

    # Apply simple string replacements
    for wrong, correct in POST_PROCESS_SIMPLE.items():
        if wrong in result:
            result = result.replace(wrong, correct)

    # Clean up multiple spaces
    while "  " in result:
        result = result.replace("  ", " ")

    return result.strip()


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
    Translate Chinese car title to English with accurate brand names.

    Uses PostgreSQL caching to avoid repeated API calls.
    Applies brand/term mappings before API translation for accuracy.
    Post-processes to fix common Google Translate mistakes.

    Args:
        chinese_text: Original Chinese car title from Che168

    Returns:
        English translation with proper brand names and model terms
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
        # Step 1: Apply brand mapping (longest match first for sub-brands)
        result = _apply_brand_mapping(chinese_text)

        # Step 2: Apply term mapping for model names and trim levels
        result = _apply_term_mapping(result)

        # Step 3: Check if any Chinese characters remain
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in result)

        if has_chinese:
            # Translate remaining Chinese via Google Translate
            result = _translate_with_retry(result)

        # Step 4: Post-process to fix common translation mistakes
        result = _post_process(result)

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
        fallback = _post_process(_apply_term_mapping(_apply_brand_mapping(chinese_text)))
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
        # The specific failing case from the plan
        "银河星舰6 2026款 60km 远航版",

        # Other common cases
        "宝马 3系 2020款 325Li M运动套装",
        "奔驰 E级 2021款 E300L 豪华型",
        "丰田 凯美瑞 2022款 2.5L 双擎豪华版",
        "特斯拉 Model 3 2023款 长续航全轮驱动版",
        "比亚迪 汉 2023款 EV 冠军版 610KM 四驱旗舰型",

        # New EV brands
        "问界 M9 2024款 纯电旗舰版",
        "小米汽车 SU7 2024款 标准版",
        "深蓝汽车 S7 2024款 增程版",
        "星途 凌云 2024款 豪华版",
        "极氪 001 2024款 长续航四驱版",
        "理想汽车 L9 2024款 Pro版",
        "蔚来 ET5 2024款 长续航版",
    ]

    print("Testing Chinese to English translation:\n")
    print("=" * 80)
    for title in test_titles:
        translated = translate_car_title(title)
        print(f"Original:   {title}")
        print(f"Translated: {translated}")
        print("-" * 80)
