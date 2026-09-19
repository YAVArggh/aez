"""
═══════════════════════════════════════════════════════════════════════
💎 Price Bot v8.0 — JAVED SHAH EDITION 🦁☀️
═══════════════════════════════════════════════════════════════════════
✅ «جاوید شاه» slogan with Lion & Sun flag in every message
✅ Auto-broadcast all prices to channels & groups
✅ Command menu — instant / suggestions
✅ Ultra admin panel
═══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup,
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
)

try:
    from aiogram.enums import ButtonStyle
    STYLE_SUPPORTED = True
except ImportError:
    ButtonStyle = None
    STYLE_SUPPORTED = False


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8885016188:AAHCwWCG7B7_CbJ5Tk4bDY70vn3hws-H6ek")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "8094551428"))
    DB_PATH: str = os.getenv("DB_PATH", "price_bot_v8.db")
    LOG_FILE: str = "logs/price_bot_v8.log"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PRICE_CACHE_TTL: int = 60

    # Auto-broadcast default interval (minutes)
    DEFAULT_BC_INTERVAL: int = 30

    @classmethod
    def validate(cls):
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", cls.BOT_TOKEN):
            raise RuntimeError("❌ BOT_TOKEN invalid")
        if cls.ADMIN_ID <= 0:
            raise RuntimeError("❌ ADMIN_ID invalid")


def setup_logger():
    os.makedirs(os.path.dirname(Config.LOG_FILE) or ".", exist_ok=True)
    logger = logging.getLogger("price_bot_v8")
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    if not logger.handlers:
        fh = RotatingFileHandler(Config.LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger

log = setup_logger()


# ═══════════════════════════════════════════════════════════════════════
# 🇮🇷 JAVED SHAH HEADER 🦁☀️
# ═══════════════════════════════════════════════════════════════════════

# Lion & Sun flag representation
LION_SUN = "🦁☀️"
JAVED_SHAH = f"{LION_SUN} <b>جاوید شاه</b> {LION_SUN}"
JAVED_SHAH_SIMPLE = f"🦁☀️ جاوید شاه 🦁☀️"
IRAN_FLAG_LINE = "🟩⬜🟥"


def royal_header() -> str:
    """هدر سلطنتی برای ابتدای هر پیام"""
    return (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"        {JAVED_SHAH}\n"
        f"      {IRAN_FLAG_LINE} {LION_SUN} {IRAN_FLAG_LINE}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )


def royal_footer() -> str:
    """فوتر سلطنتی"""
    return (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{JAVED_SHAH_SIMPLE}\n"
        f"🕐 {fa_now()}"
    )


def with_royal(text: str) -> str:
    """قرار دادن متن بین هدر و فوتر سلطنتی"""
    return f"{royal_header()}\n\n{text}\n\n{royal_footer()}"


# ═══════════════════════════════════════════════════════════════════════
# TIME
# ═══════════════════════════════════════════════════════════════════════

IRAN_TZ = ZoneInfo("Asia/Tehran")
WEEKDAYS_FA = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
MONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def now_iran(): return datetime.now(IRAN_TZ)


def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def fa_now():
    n = now_iran()
    jy, jm, jd = g2j(n.year, n.month, n.day)
    wd = (n.weekday() + 2) % 7
    return f"🕐 {n.hour:02d}:{n.minute:02d}  |  📅 {WEEKDAYS_FA[wd]} {jd} {MONTHS_FA[jm-1]} {jy}"


def fa_full():
    n = now_iran()
    jy, jm, jd = g2j(n.year, n.month, n.day)
    wd = (n.weekday() + 2) % 7
    return f"🕐 {n.hour:02d}:{n.minute:02d}:{n.second:02d}  |  📅 {WEEKDAYS_FA[wd]} {jd} {MONTHS_FA[jm-1]} {jy}"


# ═══════════════════════════════════════════════════════════════════════
# NUMBER FORMATTERS
# ═══════════════════════════════════════════════════════════════════════

def fmt_int(v) -> str:
    try:
        return f"{int(float(str(v).replace(',', '').strip())):,}"
    except Exception:
        return "0"


def fmt_usd(v) -> str:
    try:
        f = float(str(v).replace(",", "").strip())
        if f >= 1000: return f"{f:,.2f}"
        if f >= 1:    return f"{f:.4f}"
        if f >= 0.001: return f"{f:.6f}"
        return f"{f:.8f}"
    except Exception:
        return "0"


# ═══════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════

class TTLCache:
    def __init__(self, ttl=60):
        self._d = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def get(self, k):
        async with self._lock:
            it = self._d.get(k)
            if not it: return None
            v, exp = it
            if exp < time.monotonic():
                self._d.pop(k, None)
                return None
            return v

    async def set(self, k, v, ttl=None):
        async with self._lock:
            self._d[k] = (v, time.monotonic() + (ttl or self._ttl))


cache = TTLCache(Config.PRICE_CACHE_TTL)


# ═══════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    is_banned INTEGER DEFAULT 0,
    ban_reason TEXT,
    warn_count INTEGER DEFAULT 0,
    mute_until TIMESTAMP,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    chat_type TEXT DEFAULT 'group',
    auto_broadcast INTEGER DEFAULT 0,
    broadcast_interval INTEGER DEFAULT 30,
    last_broadcast TIMESTAMP,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER,
    symbol TEXT NOT NULL,
    target_price REAL NOT NULL,
    direction TEXT NOT NULL,
    triggered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""


class Database:
    _i = None
    _c = None

    def __new__(cls):
        if cls._i is None: cls._i = super().__new__(cls)
        return cls._i

    async def connect(self):
        if self._c is not None: return
        self._c = await aiosqlite.connect(Config.DB_PATH)
        self._c.row_factory = aiosqlite.Row
        await self._c.execute("PRAGMA journal_mode=WAL")
        await self._c.executescript(SCHEMA)
        await self._c.commit()
        log.info("✅ DB ready")

    async def close(self):
        if self._c: await self._c.close()

    @property
    def conn(self): return self._c

    async def ex(self, q, p=()):
        cur = await self.conn.execute(q, p)
        await self.conn.commit()
        return cur

    async def one(self, q, p=()):
        cur = await self.conn.execute(q, p)
        r = await cur.fetchone()
        await cur.close()
        return r

    async def all(self, q, p=()):
        cur = await self.conn.execute(q, p)
        r = await cur.fetchall()
        await cur.close()
        return list(r)

    async def val(self, q, p=(), default=None):
        r = await self.one(q, p)
        return list(r)[0] if r else default


db = Database()


# ═══════════════════════════════════════════════════════════════════════
# PRICE SERVICE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FiatItem:
    key: str
    name_fa: str
    flag: str
    toman: float
    usd: float


@dataclass
class CryptoItem:
    key: str
    cg_id: str
    name_fa: str
    icon: str
    usd: float
    toman: float
    change: float = 0.0


class PriceService:
    TGJU = "https://call1.tgju.org/ajax.json"

    FIAT = [
        ("usd", "price_dollar_rl", "دلار آمریکا",       "🇺🇸"),
        ("eur", "price_eur",       "یورو",              "🇪🇺"),
        ("gbp", "price_gbp",       "پوند انگلیس",       "🇬🇧"),
        ("aed", "price_aed",       "درهم امارات",       "🇦🇪"),
        ("try", "price_try",       "لیر ترکیه",         "🇹🇷"),
        ("cny", "price_cny",       "یوان چین",          "🇨🇳"),
        ("rub", "price_rub",       "روبل روسیه",        "🇷🇺"),
        ("chf", "price_chf",       "فرانک سوئیس",       "🇨🇭"),
        ("afn", "price_afn",       "افغانی",            "🇦🇫"),
        ("kwd", "price_kwd",       "دینار کویت",        "🇰🇼"),
        ("iqd", "price_iqd",       "دینار عراق",        "🇮🇶"),
        ("sar", "price_sar",       "ریال عربستان",      "🇸🇦"),
        ("jpy", "price_jpy",       "ین ژاپن",           "🇯🇵"),
        ("cad", "price_cad",       "دلار کانادا",       "🇨🇦"),
        ("aud", "price_aud",       "دلار استرالیا",     "🇦🇺"),
        ("sek", "price_sek",       "کرون سوئد",         "🇸🇪"),
    ]

    GOLD = [
        ("gold18", "geram18", "طلای ۱۸ عیار",  "🥇"),
        ("gold24", "geram24", "طلای ۲۴ عیار",  "🥇"),
        ("mesghal","mesghal", "مثقال طلا",     "⚖️"),
        ("ounce",  "ons",     "انس جهانی",     "🌍"),
    ]

    COIN = [
        ("sekke_emami", "sekeb",  "سکه امامی",     "🪙"),
        ("sekke_bahar", "sekeb",  "سکه بهار",      "🪙"),
        ("sekke_nim",   "nim",    "نیم سکه",       "🪙"),
        ("sekke_rob",   "rob",    "ربع سکه",       "🪙"),
        ("sekke_1g",    "gerami", "سکه گرمی",      "🪙"),
    ]

    CRYPTO = [
        ("BTC",  "bitcoin",          "بیت‌کوین",      "₿"),
        ("ETH",  "ethereum",         "اتریوم",        "Ξ"),
        ("USDT", "tether",           "تتر",           "💵"),
        ("SOL",  "solana",           "سولانا",        "◎"),
        ("XRP",  "ripple",           "ریپل",          "✕"),
        ("BNB",  "binancecoin",      "بایننس‌کوین",   "🟡"),
        ("TRX",  "tron",             "ترون",          "🔺"),
        ("DOGE", "dogecoin",         "دوج‌کوین",      "🐕"),
        ("ADA",  "cardano",          "کاردانو",       "🔵"),
        ("BCH",  "bitcoin-cash",     "بیت‌کوین کش",   "Ƀ"),
        ("LTC",  "litecoin",         "لایت‌کوین",     "Ł"),
        ("SHIB", "shiba-inu",        "شیبا",          "🐕"),
        ("PEPE", "pepe",             "پپه",           "🐸"),
        ("BONK", "bonk",             "بونک",          "🔥"),
        ("CAKE", "pancakeswap-token","پنیک سواپ",    "🥞"),
        ("FLOKI","floki",            "فلوکی",         "🐕"),
        ("NOT",  "notcoin",          "نات کوین",      "💎"),
        ("TON",  "the-open-network", "تون‌کوین",     "💎"),
    ]

    def __init__(self):
        self._s = None
        self._lock = asyncio.Lock()

    async def _sess(self):
        if self._s is None or self._s.closed:
            self._s = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0 PriceBot/8.0"})
        return self._s

    async def close(self):
        if self._s and not self._s.closed: await self._s.close()

    async def _tgju(self) -> dict:
        key = "tgju:current"
        c = await cache.get(key)
        if c is not None: return c
        sess = await self._sess()
        try:
            async with sess.get(self.TGJU) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    current = data.get("current", {})
                    await cache.set(key, current, ttl=Config.PRICE_CACHE_TTL)
                    log.info("✅ TGJU: %d keys", len(current))
                    return current
        except Exception as e:
            log.warning("TGJU: %s", e)
        return {}

    async def _usd_toman(self) -> float:
        cur = await self._tgju()
        if "price_dollar_rl" not in cur: return 0
        v = cur["price_dollar_rl"]
        try:
            rial = float(str(v.get("p") if isinstance(v, dict) else v).replace(",", ""))
            return rial / 10
        except Exception: return 0

    async def get_fiat(self):
        cur = await self._tgju()
        usd_toman = await self._usd_toman()
        items = []
        for key, tk, name, flag in self.FIAT:
            if tk in cur:
                v = cur[tk]
                try:
                    rial = float(str(v.get("p") if isinstance(v, dict) else v).replace(",", ""))
                    if rial <= 0: continue
                    toman = rial / 10
                    usd = toman / usd_toman if usd_toman else 0
                    items.append(FiatItem(key=key, name_fa=name, flag=flag,
                                          toman=toman, usd=usd))
                except Exception: pass
        return items, usd_toman

    async def get_gold(self):
        cur = await self._tgju()
        usd_toman = await self._usd_toman()
        items = []
        for key, tk, name, flag in self.GOLD:
            if tk in cur:
                v = cur[tk]
                try:
                    val = float(str(v.get("p") if isinstance(v, dict) else v).replace(",", ""))
                    if val <= 0: continue
                    if key == "ounce":
                        usd_val = val
                        toman_val = val * usd_toman
                    else:
                        toman_val = val / 10
                        usd_val = toman_val / usd_toman if usd_toman else 0
                    items.append({"key": key, "name": name, "flag": flag,
                                  "toman": toman_val, "usd": usd_val,
                                  "is_usd": (key == "ounce")})
                except Exception: pass
        return items

    async def get_coins(self):
        cur = await self._tgju()
        usd_toman = await self._usd_toman()
        items = []
        for key, tk, name, flag in self.COIN:
            if tk in cur:
                v = cur[tk]
                try:
                    val = float(str(v.get("p") if isinstance(v, dict) else v).replace(",", ""))
                    if val <= 0: continue
                    toman_val = val / 10
                    usd_val = toman_val / usd_toman if usd_toman else 0
                    items.append({"key": key, "name": name, "flag": flag,
                                  "toman": toman_val, "usd": usd_val})
                except Exception: pass
        return items

    async def get_crypto(self):
        key = "cg:prices"
        c = await cache.get(key)
        usd_toman = await self._usd_toman()
        if c is not None:
            return self._build_crypto(c, usd_toman)

        sess = await self._sess()
        ids = ",".join(c[1] for c in self.CRYPTO)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        raw = {}
        try:
            async with sess.get(url) as r:
                if r.status == 200:
                    raw = await r.json()
                    await cache.set(key, raw, ttl=Config.PRICE_CACHE_TTL)
                    log.info("✅ CoinGecko: %d coins", len(raw))
        except Exception as e:
            log.warning("CoinGecko: %s", e)
        return self._build_crypto(raw, usd_toman)

    def _build_crypto(self, raw, usd_toman):
        items = []
        for sym, cg, name_fa, icon in self.CRYPTO:
            if cg in raw:
                d = raw[cg]
                usd = float(d.get("usd", 0))
                ch = float(d.get("usd_24h_change", 0) or 0)
                if usd <= 0: continue
                items.append(CryptoItem(
                    key=sym, cg_id=cg, name_fa=name_fa, icon=icon,
                    usd=usd, toman=usd * usd_toman, change=ch))
        return items

    async def check_alerts(self, bot):
        try:
            alerts = await db.all("SELECT * FROM alerts WHERE triggered=0 LIMIT 100")
            if not alerts: return
            fiat, _ = await self.get_fiat()
            crypto = await self.get_crypto()
            lookup = {i.key: i.toman for i in fiat}
            lookup.update({c.key: c.toman for c in crypto})
            for a in alerts:
                sym = a["symbol"]
                if sym not in lookup: continue
                cur_v = lookup[sym]
                tgt = a["target_price"]
                d = a["direction"]
                hit = (d == "above" and cur_v >= tgt) or (d == "below" and cur_v <= tgt)
                if hit:
                    cid = a["chat_id"] or a["user_id"]
                    try:
                        await bot.send_message(cid, with_royal(
                            f"🔔 <b>هشدار قیمت!</b>\n\n"
                            f"🎯 {sym.upper()}\n"
                            f"💰 قیمت فعلی: <code>{fmt_int(cur_v)}</code> تومان\n"
                            f"📊 هدف: <code>{fmt_int(tgt)}</code> تومان"))
                        await db.ex("UPDATE alerts SET triggered=1 WHERE id=?", (a["id"],))
                    except Exception: pass
        except Exception as e:
            log.exception("alerts: %s", e)


price_svc = PriceService()


# ═══════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════

def _ib(text, style=None, **kw):
    if STYLE_SUPPORTED and style is not None:
        return InlineKeyboardButton(text=text, style=style, **kw)
    return InlineKeyboardButton(text=text, **kw)


def _kb(text, style=None, **kw):
    if STYLE_SUPPORTED and style is not None:
        try:
            return KeyboardButton(text=text, style=style, **kw)
        except Exception:
            return KeyboardButton(text=text, **kw)
    return KeyboardButton(text=text, **kw)


PRIMARY = ButtonStyle.PRIMARY if STYLE_SUPPORTED else None
SUCCESS = ButtonStyle.SUCCESS if STYLE_SUPPORTED else None
DANGER  = ButtonStyle.DANGER  if STYLE_SUPPORTED else None


def main_kb(is_admin=False):
    kb = [
        [_kb("💱 ارزها", PRIMARY), _kb("🥇 طلا", PRIMARY)],
        [_kb("🪙 سکه", PRIMARY), _kb("₿ ارز دیجیتال", PRIMARY)],
        [_kb("🔔 هشدار قیمت", SUCCESS), _kb("🕐 ساعت", PRIMARY)],
        [_kb("📜 قوانین", PRIMARY), _kb("❓ راهنما", PRIMARY)],
    ]
    if is_admin:
        kb.append([_kb("👑 پنل ادمین", SUCCESS)])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True,
                                is_persistent=True,
                                input_field_placeholder="یک گزینه را انتخاب کن...")


def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [_kb("📊 داشبورد", PRIMARY), _kb("👥 کاربران", PRIMARY)],
        [_kb("📂 گروه‌ها", PRIMARY), _kb("🔔 هشدارها", PRIMARY)],
        [_kb("📢 پیام همگانی", SUCCESS), _kb("📡 ارسال قیمت", SUCCESS)],
        [_kb("📝 لاگ‌ها", PRIMARY), _kb("🚫 بن‌ها", DANGER)],
        [_kb("⚠️ اخطارها", DANGER), _kb("🔒 کانال اجباری", PRIMARY)],
        [_kb("🔧 حالت تعمیر", PRIMARY), _kb("💾 بکاپ", SUCCESS)],
        [_kb("◀️ بازگشت", DANGER)],
    ], resize_keyboard=True, is_persistent=True)


def page_kb(prev_cb, next_cb, back_cb="p:menu"):
    row = []
    if prev_cb: row.append(_ib("◀️ صفحه قبل", PRIMARY, callback_data=prev_cb))
    if next_cb: row.append(_ib("صفحه بعد ▶️", PRIMARY, callback_data=next_cb))
    rows = []
    if row: rows.append(row)
    rows.append([_ib("🏠 بازگشت", DANGER, callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb(cb="global:cancel"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("❌ لغو", DANGER, callback_data=cb)]])


def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("✅ می‌پذیرم", SUCCESS, callback_data="rules:ok")],
        [_ib("❌ انصراف", DANGER, callback_data="rules:no")]])


def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("💱 ارزها", PRIMARY, callback_data="p:fiat:0"),
         _ib("🥇 طلا", SUCCESS, callback_data="p:gold")],
        [_ib("🪙 سکه", SUCCESS, callback_data="p:coin")],
        [_ib("₿ ارز دیجیتال", PRIMARY, callback_data="p:crypto:0")]])


def alert_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("💵 دلار", PRIMARY, callback_data="al:sym:usd"),
         _ib("🥇 طلا", SUCCESS, callback_data="al:sym:gold18")],
        [_ib("₿ بیت‌کوین", PRIMARY, callback_data="al:sym:BTC"),
         _ib("💎 تتر", SUCCESS, callback_data="al:sym:USDT")],
        [_ib("📋 لیست هشدارها", PRIMARY, callback_data="al:list")]])


def alert_dir_kb(sym):
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("⬆️ بالاتر از", SUCCESS, callback_data=f"al:dir:{sym}:above")],
        [_ib("⬇️ پایین‌تر از", DANGER, callback_data=f"al:dir:{sym}:below")],
        [_ib("◀️ بازگشت", DANGER, callback_data="al:menu")]])


def group_kb(cid, enabled, interval):
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib(f"{'🟢' if enabled else '⚪'} ارسال خودکار",
             SUCCESS if enabled else PRIMARY, callback_data=f"g:toggle:{cid}")],
        [_ib("⏱ تنظیم فاصله", PRIMARY, callback_data=f"g:interval:{cid}")],
        [_ib("📊 ارسال فوری الان", SUCCESS, callback_data=f"g:send:{cid}")]])


def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("📊 آمار", PRIMARY, callback_data="ap:stats"),
         _ib("📈 پیشرفته", PRIMARY, callback_data="ap:adv")],
        [_ib("👥 کاربران", PRIMARY, callback_data="ap:users:0"),
         _ib("📂 گروه‌ها", PRIMARY, callback_data="ap:groups:0")],
        [_ib("📡 ارسال قیمت به همه", SUCCESS, callback_data="ap:broadcast_prices")],
        [_ib("🚫 بن‌ها", DANGER, callback_data="ap:bans"),
         _ib("⚠️ اخطارها", DANGER, callback_data="ap:warns")],
        [_ib("🔔 هشدارها", PRIMARY, callback_data="ap:alerts")],
        [_ib("🔒 کانال", PRIMARY, callback_data="ap:ch"),
         _ib("🔧 تعمیر", PRIMARY, callback_data="ap:maint")],
        [_ib("📝 لاگ‌ها", PRIMARY, callback_data="ap:logs"),
         _ib("💾 بکاپ", SUCCESS, callback_data="ap:backup")]])


def admin_user_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("🚫 بن", DANGER, callback_data=f"au:ban:{uid}"),
         _ib("✅ آنبن", SUCCESS, callback_data=f"au:unban:{uid}")],
        [_ib("⚠️ اخطار", DANGER, callback_data=f"au:warn:{uid}"),
         _ib("🔇 سکوت ۱س", DANGER, callback_data=f"au:mute:{uid}")],
        [_ib("🔊 رفع سکوت", SUCCESS, callback_data=f"au:unmute:{uid}")],
        [_ib("📨 پیام", PRIMARY, callback_data=f"au:msg:{uid}")]])


# ═══════════════════════════════════════════════════════════════════════
# STATES
# ═══════════════════════════════════════════════════════════════════════

class AlertState(StatesGroup):
    price = State()

class GroupState(StatesGroup):
    interval = State()

class AdminState(StatesGroup):
    broadcast = State()
    send_to_user = State()
    set_channel = State()


# ═══════════════════════════════════════════════════════════════════════
# RULES
# ═══════════════════════════════════════════════════════════════════════

RULES_TEXT = """📜 <b>قوانین استفاده از ربات قیمت</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>1️⃣ استفاده صحیح</b>
• ربات برای اطلاع از قیمت‌های لحظه‌ای طراحی شده است.
• استفاده تبلیغاتی بدون اجازه ادمین ممنوع است.

<b>2️⃣ دقت اطلاعات</b>
• منبع: TGJU + CoinGecko (لحظه‌ای)
• ربات هیچ مسئولیتی در قبال تصمیمات مالی ندارد.
• قبل از هر معامله، قیمت را از منابع دیگر چک کنید.

<b>3️⃣ ارسال خودکار در گروه/کانال</b>
• فقط با اجازه ادمین گروه فعال می‌شود.
• حداقل فاصله ارسال: ۵ دقیقه.

<b>4️⃣ هشدار قیمت</b>
• هشدارها فقط اطلاع‌رسانی هستند.

<b>5️⃣ حریم خصوصی</b>
• اطلاعات کاربران نزد ربات محفوظ است.

<b>6️⃣ محدودیت‌ها</b>
• سوءاستفاده باعث بن دائمی می‌شود.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ با زدن «✅ می‌پذیرم» تأیید می‌کنید تمام قوانین را خوانده و پذیرفته‌اید.
"""


# ═══════════════════════════════════════════════════════════════════════
# REPOS
# ═══════════════════════════════════════════════════════════════════════

class UserRepo:
    async def create(self, uid, fn, un):
        await db.ex("INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?,?,?)",
                    (uid, fn, un))
    async def update(self, uid, fn, un):
        await db.ex("UPDATE users SET full_name=?, username=?, last_seen=CURRENT_TIMESTAMP WHERE user_id=?",
                    (fn, un, uid))
    async def get(self, uid): return await db.one("SELECT * FROM users WHERE user_id=?", (uid,))
    async def exists(self, uid): return bool(await db.one("SELECT 1 FROM users WHERE user_id=?", (uid,)))
    async def ban(self, uid, reason):
        await db.ex("UPDATE users SET is_banned=1, ban_reason=? WHERE user_id=?", (reason, uid))
    async def unban(self, uid):
        await db.ex("UPDATE users SET is_banned=0, ban_reason=NULL WHERE user_id=?", (uid,))
    async def warn(self, uid):
        await db.ex("UPDATE users SET warn_count=warn_count+1 WHERE user_id=?", (uid,))
        return int(await db.val("SELECT warn_count FROM users WHERE user_id=?", (uid,), 0))
    async def clear_warns(self, uid):
        await db.ex("UPDATE users SET warn_count=0 WHERE user_id=?", (uid,))
    async def mute(self, uid, m):
        from datetime import timedelta
        await db.ex("UPDATE users SET mute_until=? WHERE user_id=?",
                    ((now_iran()+timedelta(minutes=m)).isoformat(), uid))
    async def unmute(self, uid):
        await db.ex("UPDATE users SET mute_until=NULL WHERE user_id=?", (uid,))
    async def count(self): return int(await db.val("SELECT COUNT(*) FROM users", (), 0))
    async def count_banned(self): return int(await db.val("SELECT COUNT(*) FROM users WHERE is_banned=1", (), 0))
    async def count_today(self):
        return int(await db.val("SELECT COUNT(*) FROM users WHERE date(first_seen)=date('now')", (), 0))
    async def all(self, limit=10, offset=0):
        return await db.all("SELECT * FROM users ORDER BY first_seen DESC LIMIT ? OFFSET ?", (limit, offset))
    async def all_ids(self):
        rows = await db.all("SELECT user_id FROM users WHERE is_banned=0")
        return [int(r["user_id"]) for r in rows]


class GroupRepo:
    async def add(self, cid, t, ct, by):
        await db.ex(
            """INSERT INTO groups (chat_id, title, chat_type, added_by) VALUES (?,?,?,?)
               ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title""", (cid, t, ct, by))
    async def remove(self, cid): await db.ex("DELETE FROM groups WHERE chat_id=?", (cid,))
    async def get(self, cid): return await db.one("SELECT * FROM groups WHERE chat_id=?", (cid,))
    async def all(self): return await db.all("SELECT * FROM groups ORDER BY added_at DESC")
    async def active(self): return await db.all("SELECT * FROM groups WHERE auto_broadcast=1")
    async def all_for_broadcast(self): return await db.all("SELECT * FROM groups")
    async def count(self): return int(await db.val("SELECT COUNT(*) FROM groups", (), 0))
    async def count_active(self):
        return int(await db.val("SELECT COUNT(*) FROM groups WHERE auto_broadcast=1", (), 0))
    async def toggle(self, cid):
        await db.ex("UPDATE groups SET auto_broadcast=1-auto_broadcast WHERE chat_id=?", (cid,))
        r = await db.one("SELECT auto_broadcast FROM groups WHERE chat_id=?", (cid,))
        return bool(r["auto_broadcast"]) if r else False
    async def set_interval(self, cid, m):
        await db.ex("UPDATE groups SET broadcast_interval=? WHERE chat_id=?", (m, cid))
    async def last_bc(self, cid):
        await db.ex("UPDATE groups SET last_broadcast=CURRENT_TIMESTAMP WHERE chat_id=?", (cid,))


class AlertRepo:
    async def create(self, uid, cid, sym, tgt, d):
        await db.ex(
            "INSERT INTO alerts (user_id,chat_id,symbol,target_price,direction) VALUES (?,?,?,?,?)",
            (uid, cid, sym, tgt, d))
    async def list_user(self, uid):
        return await db.all("SELECT * FROM alerts WHERE user_id=? AND triggered=0 ORDER BY id DESC", (uid,))
    async def count(self): return int(await db.val("SELECT COUNT(*) FROM alerts WHERE triggered=0", (), 0))
    async def all_active(self):
        return await db.all("SELECT * FROM alerts WHERE triggered=0 ORDER BY id DESC LIMIT 30")


class LogRepo:
    async def log(self, aid, action, details=""):
        await db.ex("INSERT INTO admin_logs (admin_id,action,details) VALUES (?,?,?)",
                    (aid, action, details))
    async def recent(self, n=15):
        return await db.all("SELECT * FROM admin_logs ORDER BY id DESC LIMIT ?", (n,))


class SettingRepo:
    async def get(self, key):
        return await db.val("SELECT value FROM settings WHERE key=?", (key,))
    async def set(self, key, val):
        await db.ex(
            """INSERT INTO settings (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (key, val))
    async def delete(self, key): await db.ex("DELETE FROM settings WHERE key=?", (key,))
    async def get_channel(self): return await self.get("force_channel")
    async def set_channel(self, ch): await self.set("force_channel", ch)
    async def clear_channel(self): await self.delete("force_channel")
    async def is_maintenance(self): return (await self.get("maintenance")) == "1"
    async def set_maintenance(self, on): await self.set("maintenance", "1" if on else "0")


user_repo = UserRepo()
group_repo = GroupRepo()
alert_repo = AlertRepo()
log_repo = LogRepo()
setting_repo = SettingRepo()


# ═══════════════════════════════════════════════════════════════════════
# RENDERERS — با شعار جاوید شاه
# ═══════════════════════════════════════════════════════════════════════

FIAT_PER_PAGE = 6
CRYPTO_PER_PAGE = 6


def render_fiat_page(items, page):
    start = page * FIAT_PER_PAGE
    end = min(start + FIAT_PER_PAGE, len(items))
    chunk = items[start:end]

    lines = ["🏳️ <b>نرخ ارزهای حقیقی:</b>\n"]
    for it in chunk:
        lines.append(
            f"{it.flag} <b>{it.name_fa}</b>\n"
            f"🇺🇸 <code>{fmt_usd(it.usd)}</code> دلار\n"
            f"🇮🇷 <code>{fmt_int(it.toman)}</code> تومان\n")

    text = with_royal("\n".join(lines))
    prev_cb = f"p:fiat:{page-1}" if page > 0 else None
    next_cb = f"p:fiat:{page+1}" if end < len(items) else None
    return text, page_kb(prev_cb, next_cb)


def render_crypto_page(items, page):
    start = page * CRYPTO_PER_PAGE
    end = min(start + CRYPTO_PER_PAGE, len(items))
    chunk = items[start:end]

    lines = ["🪙 <b>قیمت لحظه‌ای ارزهای دیجیتال:</b>\n"]
    for it in chunk:
        ch = it.change
        arrow = "🟢" if ch > 0 else ("🔴" if ch < 0 else "⚪")
        lines.append(
            f"{it.icon} <b>{it.name_fa}</b>:\n"
            f"🇺🇸 <code>{fmt_usd(it.usd)}</code> دلار {arrow}\n"
            f"🇮🇷 <code>{fmt_int(it.toman)}</code> تومان\n")

    text = with_royal("\n".join(lines))
    prev_cb = f"p:crypto:{page-1}" if page > 0 else None
    next_cb = f"p:crypto:{page+1}" if end < len(items) else None
    return text, page_kb(prev_cb, next_cb)


def render_gold(items):
    lines = ["🥇 <b>طلا</b>\n"]
    for it in items:
        if it.get("is_usd"):
            lines.append(f"{it['flag']} <b>{it['name']}</b>\n"
                         f"🇺🇸 <code>${fmt_usd(it['usd'])}</code>\n")
        else:
            lines.append(f"{it['flag']} <b>{it['name']}</b>\n"
                         f"🇺🇸 <code>{fmt_usd(it['usd'])}</code> دلار\n"
                         f"🇮🇷 <code>{fmt_int(it['toman'])}</code> تومان\n")
    return with_royal("\n".join(lines))


def render_coins(items):
    lines = ["🪙 <b>سکه‌ها</b>\n"]
    for it in items:
        lines.append(f"{it['flag']} <b>{it['name']}</b>\n"
                     f"🇺🇸 <code>{fmt_usd(it['usd'])}</code> دلار\n"
                     f"🇮🇷 <code>{fmt_int(it['toman'])}</code> تومان\n")
    return with_royal("\n".join(lines))


def render_overview(fiat, gold, coins, crypto=None):
    """نمای کلی برای ارسال خودکار به گروه/کانال"""
    lines = ["💎 <b>قیمت لحظه‌ای بازار ایران</b>\n"]

    lines.append("💵 <b>ارزها</b>")
    for it in fiat[:5]:
        lines.append(f"{it.flag} {it.name_fa}: <code>{fmt_int(it.toman)}</code> تومان")

    if gold:
        lines.append("\n🥇 <b>طلا</b>")
        for it in gold[:2]:
            lines.append(f"{it['flag']} {it['name']}: <code>{fmt_int(it['toman'])}</code> تومان")

    if coins:
        lines.append("\n🪙 <b>سکه</b>")
        for it in coins[:3]:
            lines.append(f"{it['flag']} {it['name']}: <code>{fmt_int(it['toman'])}</code> تومان")

    if crypto:
        lines.append("\n₿ <b>ارز دیجیتال</b>")
        for it in crypto[:3]:
            lines.append(f"{it.icon} {it.name_fa}: <code>{fmt_int(it.toman)}</code> تومان")

    return with_royal("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════
# ROUTERS
# ═══════════════════════════════════════════════════════════════════════

common_router = Router()
price_router = Router()
crypto_router = Router()
alert_router = Router()
group_router = Router()
admin_router = Router()


# ─── /start ───

@common_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    uid = message.from_user.id
    if not await user_repo.exists(uid):
        await user_repo.create(uid, message.from_user.full_name, message.from_user.username)
    else:
        await user_repo.update(uid, message.from_user.full_name, message.from_user.username)
    is_admin = (uid == Config.ADMIN_ID)

    if message.chat.type in ("group", "supergroup", "channel"):
        await group_repo.add(message.chat.id, message.chat.title or "گروه",
                             message.chat.type, uid)
        await message.answer(
            with_royal(
                "💎 <b>ربات قیمت لحظه‌ای</b>\n\n"
                "✅ گروه شما ثبت شد.\n\n"
                "<b>📌 کامندهای موجود:</b>\n"
                "/price — منوی قیمت\n/dollar /euro /pound — ارزها\n"
                "/gold /coin — طلا و سکه\n/crypto — ارز دیجیتال\n"
                "/settings — تنظیمات گروه"),
            reply_markup=main_kb(is_admin))
        return

    await message.answer(
        with_royal(
            "💎 <b>خوش آمدی!</b>\n\n"
            "قیمت لحظه‌ای دلار، طلا، سکه و ارز دیجیتال\n\n"
            "📌 کامندها را با / ببین"),
        reply_markup=main_kb(is_admin))


@common_router.message(Command("help"))
@common_router.message(F.text == "❓ راهنما")
async def cmd_help(message: Message):
    is_admin = (message.from_user.id == Config.ADMIN_ID)
    text = (
        "❓ <b>راهنمای ربات</b>\n\n"
        "<b>💰 قیمت‌ها:</b>\n/price /dollar /euro /pound /gold /coin /crypto\n\n"
        "<b>🔔 هشدار:</b>\n/alert\n\n"
        "<b>⚙️ گروه:</b>\n/settings\n\n"
        "<b>📌 عمومی:</b>\n/time /rules /myid")
    if is_admin:
        text += "\n\n<b>👑 ادمین:</b>\n/admin"
    await message.answer(with_royal(text), reply_markup=main_kb(is_admin))


@common_router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(with_royal(
        f"🆔 <code>{message.from_user.id}</code>\n"
        f"💬 <code>{message.chat.id}</code>"))


@common_router.message(Command("time"))
@common_router.message(F.text == "🕐 ساعت")
async def cmd_time(message: Message):
    await message.answer(with_royal(f"🇮🇷 <b>ساعت ایران</b>\n\n{fa_full()}"))


@common_router.message(Command("rules"))
@common_router.message(F.text == "📜 قوانین")
async def cmd_rules(message: Message):
    await message.answer(with_royal(RULES_TEXT), reply_markup=rules_kb())


@common_router.callback_query(F.data == "rules:ok")
async def cb_rules_ok(cb: CallbackQuery):
    try:
        await cb.message.edit_text(with_royal("✅ <b>پذیرفته شد.</b>"))
    except TelegramBadRequest: pass
    await cb.answer("✅")


@common_router.callback_query(F.data == "rules:no")
async def cb_rules_no(cb: CallbackQuery):
    try:
        await cb.message.edit_text(with_royal("😔 باید بپذیرید."))
    except TelegramBadRequest: pass
    await cb.answer("😔")


@common_router.callback_query(F.data == "global:cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_text(with_royal("❌ لغو شد."))
    except TelegramBadRequest: pass
    await cb.answer()


# ─── PRICE ───

@price_router.message(Command("price"))
async def cmd_price(message: Message):
    fiat, _ = await price_svc.get_fiat()
    gold = await price_svc.get_gold()
    coins = await price_svc.get_coins()
    crypto = await price_svc.get_crypto()
    if not fiat and not gold and not coins:
        await message.answer(with_royal("❌ خطا. بعداً تلاش کن."))
        return
    await message.answer(render_overview(fiat, gold, coins, crypto), reply_markup=menu_kb())


@price_router.message(Command("dollar"))
async def cmd_dollar(message: Message):
    fiat, _ = await price_svc.get_fiat()
    usd = next((i for i in fiat if i.key == "usd"), None)
    if not usd:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    await message.answer(with_royal(
        f"🇺🇸 <b>دلار آمریکا</b>\n\n"
        f"🇺🇸 <code>1.0000</code> دلار\n"
        f"🇮🇷 <code>{fmt_int(usd.toman)}</code> تومان"))


@price_router.message(Command("euro"))
async def cmd_euro(message: Message):
    fiat, _ = await price_svc.get_fiat()
    it = next((i for i in fiat if i.key == "eur"), None)
    if not it:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    await message.answer(with_royal(
        f"🇪🇺 <b>یورو</b>\n\n"
        f"🇺🇸 <code>{fmt_usd(it.usd)}</code> دلار\n"
        f"🇮🇷 <code>{fmt_int(it.toman)}</code> تومان"))


@price_router.message(Command("pound"))
async def cmd_pound(message: Message):
    fiat, _ = await price_svc.get_fiat()
    it = next((i for i in fiat if i.key == "gbp"), None)
    if not it:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    await message.answer(with_royal(
        f"🇬🇧 <b>پوند انگلیس</b>\n\n"
        f"🇺🇸 <code>{fmt_usd(it.usd)}</code> دلار\n"
        f"🇮🇷 <code>{fmt_int(it.toman)}</code> تومان"))


@price_router.message(Command("gold"))
@price_router.message(F.text == "🥇 طلا")
async def cmd_gold(message: Message):
    items = await price_svc.get_gold()
    if not items:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    await message.answer(render_gold(items),
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                              [_ib("🏠 بازگشت", DANGER, callback_data="p:menu")]]))


@price_router.message(Command("coin"))
@price_router.message(F.text == "🪙 سکه")
async def cmd_coin(message: Message):
    items = await price_svc.get_coins()
    if not items:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    await message.answer(render_coins(items),
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                              [_ib("🏠 بازگشت", DANGER, callback_data="p:menu")]]))


@price_router.message(F.text == "💱 ارزها")
async def btn_fiat(message: Message):
    items, _ = await price_svc.get_fiat()
    if not items:
        await message.answer(with_royal("❌ در دسترس نیست."))
        return
    text, kb = render_fiat_page(items, 0)
    await message.answer(text, reply_markup=kb)


@price_router.callback_query(F.data == "p:menu")
async def cb_p_menu(cb: CallbackQuery):
    fiat, _ = await price_svc.get_fiat()
    gold = await price_svc.get_gold()
    coins = await price_svc.get_coins()
    crypto = await price_svc.get_crypto()
    try:
        await cb.message.edit_text(render_overview(fiat, gold, coins, crypto), reply_markup=menu_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@price_router.callback_query(F.data.startswith("p:fiat:"))
async def cb_fiat_page(cb: CallbackQuery):
    try:
        page = int(cb.data.split(":")[2])
    except Exception: page = 0
    items, _ = await price_svc.get_fiat()
    if not items:
        await cb.answer("❌", show_alert=True)
        return
    text, kb = render_fiat_page(items, page)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest: pass
    await cb.answer()


@price_router.callback_query(F.data == "p:gold")
async def cb_p_gold(cb: CallbackQuery):
    items = await price_svc.get_gold()
    if not items:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(render_gold(items),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [_ib("🏠 بازگشت", DANGER, callback_data="p:menu")]]))
    except TelegramBadRequest: pass
    await cb.answer()


@price_router.callback_query(F.data == "p:coin")
async def cb_p_coin(cb: CallbackQuery):
    items = await price_svc.get_coins()
    if not items:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(render_coins(items),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [_ib("🏠 بازگشت", DANGER, callback_data="p:menu")]]))
    except TelegramBadRequest: pass
    await cb.answer()


# ─── CRYPTO ───

@crypto_router.message(Command("crypto"))
@crypto_router.message(F.text == "₿ ارز دیجیتال")
async def cmd_crypto(message: Message):
    items = await price_svc.get_crypto()
    if not items:
        await message.answer(with_royal("❌ خطا در دریافت."))
        return
    text, kb = render_crypto_page(items, 0)
    await message.answer(text, reply_markup=kb)


@crypto_router.callback_query(F.data.startswith("p:crypto:"))
async def cb_crypto_page(cb: CallbackQuery):
    try:
        page = int(cb.data.split(":")[2])
    except Exception: page = 0
    items = await price_svc.get_crypto()
    if not items:
        await cb.answer("❌", show_alert=True)
        return
    text, kb = render_crypto_page(items, page)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest: pass
    await cb.answer()


# ─── ALERTS ───

@alert_router.message(Command("alert"))
@alert_router.message(F.text == "🔔 هشدار قیمت")
async def cmd_alert(message: Message):
    await message.answer(with_royal("🔔 <b>هشدار قیمت</b>\n\nنماد را انتخاب کنید:"),
                         reply_markup=alert_menu_kb())


@alert_router.callback_query(F.data == "al:menu")
async def cb_al_menu(cb: CallbackQuery):
    try:
        await cb.message.edit_text(with_royal("🔔 <b>هشدار قیمت</b>"),
                                    reply_markup=alert_menu_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@alert_router.callback_query(F.data.startswith("al:sym:"))
async def cb_al_sym(cb: CallbackQuery):
    sym = cb.data.split(":")[2]
    try:
        await cb.message.edit_text(
            with_royal(f"🔔 <b>{sym.upper()}</b>\n\nجهت هشدار:"),
            reply_markup=alert_dir_kb(sym))
    except TelegramBadRequest: pass
    await cb.answer()


@alert_router.callback_query(F.data.startswith("al:dir:"))
async def cb_al_dir(cb: CallbackQuery, state: FSMContext):
    _, _, sym, direction = cb.data.split(":")
    await state.update_data(sym=sym, direction=direction, chat=cb.message.chat.id)
    await state.set_state(AlertState.price)
    try:
        await cb.message.edit_text(
            with_royal(f"🔔 <b>{sym.upper()}</b>\n"
                       f"جهت: {'بالاتر از' if direction=='above' else 'پایین‌تر از'}\n\n"
                       f"💰 قیمت هدف (تومان):\n<code>250000</code>"),
            reply_markup=cancel_kb("al:cancel"))
    except TelegramBadRequest: pass
    await cb.answer()


@alert_router.callback_query(F.data == "al:cancel")
async def cb_al_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_text(with_royal("❌ لغو شد."))
    except TelegramBadRequest: pass
    await cb.answer()


@alert_router.message(AlertState.price)
async def al_recv(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        target = float((message.text or "").replace(",", "").strip())
        if target <= 0: raise ValueError
    except (ValueError, AttributeError):
        await message.answer("⚠️ عدد نامعتبر.")
        return
    await alert_repo.create(message.from_user.id, data.get("chat"),
                            data.get("sym"), target, data.get("direction"))
    await state.clear()
    await message.answer(with_royal(
        f"✅ <b>هشدار ثبت شد</b>\n\n"
        f"🎯 {data.get('sym','').upper()}\n"
        f"جهت: {'بالاتر از' if data.get('direction')=='above' else 'پایین‌تر از'}\n"
        f"💰 <code>{fmt_int(target)}</code> تومان"))


@alert_router.callback_query(F.data == "al:list")
async def cb_al_list(cb: CallbackQuery):
    alerts = await alert_repo.list_user(cb.from_user.id)
    if not alerts:
        try:
            await cb.message.edit_text(with_royal("📋 هشداری نداری."),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [_ib("🏠 بازگشت", DANGER, callback_data="al:menu")]]))
        except TelegramBadRequest: pass
        await cb.answer()
        return
    lines = ["🔔 <b>هشدارهای فعال شما</b>\n"]
    for a in alerts[:15]:
        lines.append(f"• <b>{a['symbol'].upper()}</b>: "
                     f"{'⬆️' if a['direction']=='above' else '⬇️'} "
                     f"<code>{fmt_int(a['target_price'])}</code> تومان")
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [_ib("🏠 بازگشت", DANGER, callback_data="al:menu")]]))
    except TelegramBadRequest: pass
    await cb.answer()


# ─── GROUP ───

@group_router.message(Command("settings"))
async def cmd_settings(message: Message):
    if message.chat.type not in ("group", "supergroup", "channel"):
        await message.answer(with_royal("⚠️ فقط در گروه/کانال."))
        return
    g = await group_repo.get(message.chat.id)
    if not g:
        await group_repo.add(message.chat.id, message.chat.title or "گروه",
                             message.chat.type, message.from_user.id)
        g = await group_repo.get(message.chat.id)
    enabled = bool(g["auto_broadcast"])
    interval = g["broadcast_interval"]
    await message.answer(
        with_royal(
            f"⚙️ <b>تنظیمات گروه</b>\n\n"
            f"📌 {message.chat.title or 'گروه'}\n"
            f"📢 ارسال خودکار: <b>{'🟢 روشن' if enabled else '⚪ خاموش'}</b>\n"
            f"⏱ فاصله: <b>{interval} دقیقه</b>"),
        reply_markup=group_kb(message.chat.id, enabled, interval))


@group_router.callback_query(F.data.startswith("g:toggle:"))
async def cb_g_toggle(cb: CallbackQuery):
    cid = int(cb.data.split(":")[2])
    try:
        m = await cb.bot.get_chat_member(cid, cb.from_user.id)
        if m.status not in ("administrator", "creator"):
            await cb.answer("❌ فقط ادمین‌های گروه!", show_alert=True)
            return
    except Exception: pass
    enabled = await group_repo.toggle(cid)
    g = await group_repo.get(cid)
    interval = g["broadcast_interval"] if g else 30
    try:
        await cb.message.edit_reply_markup(reply_markup=group_kb(cid, enabled, interval))
    except TelegramBadRequest: pass
    await cb.answer(f"{'🟢 روشن' if enabled else '⚪ خاموش'}")


@group_router.callback_query(F.data.startswith("g:interval:"))
async def cb_g_interval(cb: CallbackQuery, state: FSMContext):
    cid = int(cb.data.split(":")[2])
    try:
        m = await cb.bot.get_chat_member(cid, cb.from_user.id)
        if m.status not in ("administrator", "creator"):
            await cb.answer("❌ فقط ادمین‌های گروه!", show_alert=True)
            return
    except Exception: pass
    await state.update_data(g_chat=cid)
    await state.set_state(GroupState.interval)
    try:
        await cb.message.edit_text(
            with_royal("⏱ فاصله ارسال (دقیقه):\nمثال: <code>30</code>"),
            reply_markup=cancel_kb("global:cancel"))
    except TelegramBadRequest: pass
    await cb.answer()


@group_router.callback_query(F.data.startswith("g:send:"))
async def cb_g_send(cb: CallbackQuery):
    cid = int(cb.data.split(":")[2])
    try:
        m = await cb.bot.get_chat_member(cid, cb.from_user.id)
        if m.status not in ("administrator", "creator"):
            await cb.answer("❌ فقط ادمین‌های گروه!", show_alert=True)
            return
    except Exception: pass
    await cb.answer("⏳")
    fiat, _ = await price_svc.get_fiat()
    gold = await price_svc.get_gold()
    coins = await price_svc.get_coins()
    crypto = await price_svc.get_crypto()
    text = render_overview(fiat, gold, coins, crypto)
    try:
        await cb.bot.send_message(cid, text, reply_markup=menu_kb())
        await cb.message.answer(with_royal("✅ ارسال شد."))
    except Exception as e:
        await cb.message.answer(f"❌ {e}")


@group_router.message(GroupState.interval)
async def g_recv(message: Message, state: FSMContext):
    data = await state.get_data()
    cid = data.get("g_chat")
    await state.clear()
    try:
        m = int((message.text or "").strip())
        if m < 5 or m > 1440: raise ValueError
    except (ValueError, AttributeError):
        await message.answer("⚠️ عدد بین ۵ تا ۱۴۴۰.")
        return
    await group_repo.set_interval(cid, m)
    g = await group_repo.get(cid)
    enabled = bool(g["auto_broadcast"]) if g else False
    await message.answer(with_royal(f"✅ فاصله: <b>{m} دقیقه</b>"),
                         reply_markup=group_kb(cid, enabled, m))


# ═══════════════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════════════

def is_adm(uid): return uid == Config.ADMIN_ID


@admin_router.message(Command("admin"))
@admin_router.message(F.text == "👑 پنل ادمین")
async def adm_panel(message: Message):
    if not is_adm(message.from_user.id): return
    await message.answer(
        with_royal("👑 <b>پنل مدیریت فوق پیشرفته</b>\n\nیک گزینه انتخاب کن:"),
        reply_markup=admin_kb())
    await message.answer("📋 دکمه‌های سریع:", reply_markup=admin_panel_kb())


@admin_router.message(F.text == "◀️ بازگشت")
async def adm_back(message: Message):
    if not is_adm(message.from_user.id): return
    await message.answer(with_royal("🏠 منوی اصلی"), reply_markup=main_kb(True))


@admin_router.message(F.text == "📊 داشبورد")
async def adm_dash(message: Message):
    if not is_adm(message.from_user.id): return
    u = await user_repo.count()
    ut = await user_repo.count_today()
    ub = await user_repo.count_banned()
    g = await group_repo.count()
    ga = await group_repo.count_active()
    a = await alert_repo.count()
    maint = await setting_repo.is_maintenance()
    ch = await setting_repo.get_channel()
    await message.answer(with_royal(
        f"📊 <b>داشبورد</b>\n\n"
        f"👥 کاربران: <b>{u}</b> (+{ut} امروز)\n"
        f"🚫 بن: <b>{ub}</b>\n"
        f"📂 گروه‌ها: <b>{g}</b> (فعال: {ga})\n"
        f"🔔 هشدار: <b>{a}</b>\n"
        f"🔒 کانال: <code>{ch or '—'}</code>\n"
        f"🔧 تعمیر: <b>{'✅' if maint else '❌'}</b>\n\n"
        f"🕐 {fa_full()}"),
        reply_markup=admin_kb())


@admin_router.message(F.text == "👥 کاربران")
async def adm_users(message: Message):
    if not is_adm(message.from_user.id): return
    users = await user_repo.all(20)
    if not users:
        await message.answer(with_royal("خالی."), reply_markup=admin_kb())
        return
    lines = ["👥 <b>۲۰ کاربر آخر</b>\n"]
    for u in users:
        st = "🚫" if u["is_banned"] else "✅"
        w = f" ⚠️{u['warn_count']}" if u["warn_count"] else ""
        lines.append(f"{st} <code>{u['user_id']}</code> — {u['full_name'] or '—'}{w}")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "📂 گروه‌ها")
async def adm_groups(message: Message):
    if not is_adm(message.from_user.id): return
    groups = await group_repo.all()
    if not groups:
        await message.answer(with_royal("گروهی نیست."), reply_markup=admin_kb())
        return
    lines = ["📂 <b>گروه‌های ثبت‌شده</b>\n"]
    for g in groups[:20]:
        st = "🟢" if g["auto_broadcast"] else "⚪"
        lines.append(f"{st} <code>{g['chat_id']}</code> — {g['title'] or '—'}")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "🔔 هشدارها")
async def adm_alerts(message: Message):
    if not is_adm(message.from_user.id): return
    alerts = await alert_repo.all_active()
    lines = ["🔔 <b>هشدارهای فعال</b>\n"]
    if not alerts: lines.append("خالی.")
    else:
        for a in alerts:
            lines.append(f"• <code>{a['user_id']}</code> — {a['symbol'].upper()} "
                         f"{'⬆️' if a['direction']=='above' else '⬇️'} "
                         f"<code>{fmt_int(a['target_price'])}</code>")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "📢 پیام همگانی")
async def adm_bc(message: Message, state: FSMContext):
    if not is_adm(message.from_user.id): return
    await state.set_state(AdminState.broadcast)
    await message.answer(with_royal("📢 پیام همگانی\n\nپیام را بفرست:"),
                         reply_markup=cancel_kb())


@admin_router.message(AdminState.broadcast)
async def adm_bc_send(message: Message, bot: Bot, state: FSMContext):
    if not is_adm(message.from_user.id): return
    await state.clear()
    ids = await user_repo.all_ids()
    if not ids:
        await message.answer("❌ کاربری نیست.", reply_markup=admin_kb())
        return
    msg = await message.answer(with_royal(f"⏳ ارسال به {len(ids)}..."))
    ok, fail = 0, 0
    for uid in ids:
        try:
            await bot.copy_message(uid, message.chat.id, message.message_id)
            ok += 1
        except Exception: fail += 1
        await asyncio.sleep(0.05)
    await log_repo.log(Config.ADMIN_ID, "broadcast", f"{ok}/{fail}")
    try:
        await msg.edit_text(with_royal(f"✅ پایان\nموفق: <b>{ok}</b>\nناموفق: <b>{fail}</b>"))
    except TelegramBadRequest: pass
    await message.answer("🏠", reply_markup=admin_kb())


@admin_router.message(F.text == "📡 ارسال قیمت")
async def adm_send_prices(message: Message, bot: Bot):
    """ارسال فوری قیمت به همه گروه‌ها/کانال‌های ثبت‌شده"""
    if not is_adm(message.from_user.id): return
    groups = await group_repo.all_for_broadcast()
    if not groups:
        await message.answer(with_royal("❌ هیچ گروه/کانالی ثبت نشده."),
                             reply_markup=admin_kb())
        return
    fiat, _ = await price_svc.get_fiat()
    gold = await price_svc.get_gold()
    coins = await price_svc.get_coins()
    crypto = await price_svc.get_crypto()
    text = render_overview(fiat, gold, coins, crypto)
    msg = await message.answer(with_royal(f"⏳ ارسال به {len(groups)} چت..."))
    ok, fail = 0, 0
    for g in groups:
        try:
            await bot.send_message(g["chat_id"], text, reply_markup=menu_kb())
            await group_repo.last_bc(g["chat_id"])
            ok += 1
        except TelegramForbiddenError:
            await group_repo.remove(g["chat_id"])
            fail += 1
        except Exception: fail += 1
        await asyncio.sleep(1.0)
    await log_repo.log(Config.ADMIN_ID, "send_prices", f"{ok}/{fail}")
    try:
        await msg.edit_text(with_royal(
            f"✅ <b>ارسال قیمت</b>\n\n"
            f"📤 موفق: <b>{ok}</b>\n📭 ناموفق: <b>{fail}</b>"))
    except TelegramBadRequest: pass
    await message.answer("🏠", reply_markup=admin_kb())


@admin_router.message(F.text == "📝 لاگ‌ها")
async def adm_logs(message: Message):
    if not is_adm(message.from_user.id): return
    logs = await log_repo.recent(15)
    lines = ["📝 <b>۱۵ لاگ آخر</b>\n"]
    if not logs: lines.append("خالی.")
    else:
        for r in logs:
            lines.append(f"• [{r['created_at'][11:16]}] {r['action']} — {r['details'] or '—'}")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "🚫 بن‌ها")
async def adm_bans(message: Message):
    if not is_adm(message.from_user.id): return
    rows = await db.all("SELECT user_id, full_name, ban_reason FROM users WHERE is_banned=1 LIMIT 20")
    lines = ["🚫 <b>بن‌شده‌ها</b>\n"]
    if not rows: lines.append("خالی.")
    else:
        for r in rows:
            lines.append(f"• <code>{r['user_id']}</code> — {r['full_name'] or '—'}\n  {r['ban_reason'] or '—'}")
    lines.append("\n💡 /ban ID دلیل | /unban ID")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "⚠️ اخطارها")
async def adm_warns(message: Message):
    if not is_adm(message.from_user.id): return
    rows = await db.all("SELECT user_id, full_name, warn_count FROM users WHERE warn_count>0 ORDER BY warn_count DESC LIMIT 20")
    lines = ["⚠️ <b>اخطاردار</b>\n"]
    if not rows: lines.append("خالی.")
    else:
        for r in rows:
            lines.append(f"• <code>{r['user_id']}</code> — {r['full_name'] or '—'} ⚠️{r['warn_count']}")
    await message.answer(with_royal("\n".join(lines)), reply_markup=admin_kb())


@admin_router.message(F.text == "🔒 کانال اجباری")
async def adm_ch(message: Message):
    if not is_adm(message.from_user.id): return
    ch = await setting_repo.get_channel()
    text = f"🔒 <b>کانال اجباری</b>\n\nکانال: <code>{ch or 'تنظیم نشده'}</code>"
    await message.answer(with_royal(text),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_ib("🔧 تنظیم کانال", PRIMARY, callback_data="ap:ch_set")],
            [_ib("🗑 حذف کانال", DANGER, callback_data="ap:ch_remove")] if ch else []]))


@admin_router.message(F.text == "🔧 حالت تعمیر")
async def adm_maint(message: Message):
    if not is_adm(message.from_user.id): return
    on = await setting_repo.is_maintenance()
    await message.answer(with_royal(f"🔧 حالت تعمیر: <b>{'✅ روشن' if on else '❌ خاموش'}</b>"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_ib("🟢 خاموش", SUCCESS, callback_data="ap:maint_off"),
             _ib("🔴 روشن", DANGER, callback_data="ap:maint_on")]]))


@admin_router.message(F.text == "💾 بکاپ")
async def adm_backup(message: Message, bot: Bot):
    if not is_adm(message.from_user.id): return
    try:
        with open(Config.DB_PATH, "rb") as f:
            data = f.read()
        stamp = now_iran().strftime("%Y%m%d_%H%M%S")
        await bot.send_document(Config.ADMIN_ID,
                                BufferedInputFile(data, filename=f"backup_{stamp}.db"),
                                caption=with_royal("💾 بکاپ دیتابیس"))
        await log_repo.log(Config.ADMIN_ID, "backup", "")
    except Exception as e:
        await message.answer(f"❌ {e}")


# ─── admin callbacks ───

@admin_router.callback_query(F.data == "ap:stats")
async def cb_ap_stats(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    u = await user_repo.count()
    ub = await user_repo.count_banned()
    g = await group_repo.count()
    ga = await group_repo.count_active()
    a = await alert_repo.count()
    try:
        await cb.message.edit_text(with_royal(
            f"📊 <b>آمار</b>\n\n"
            f"👥 کاربران: {u}\n"
            f"🚫 بن: {ub}\n"
            f"📂 گروه: {g} (فعال: {ga})\n"
            f"🔔 هشدار: {a}"),
            reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:adv")
async def cb_ap_adv(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    u = await user_repo.count()
    ut = await user_repo.count_today()
    ub = await user_repo.count_banned()
    g = await group_repo.count()
    ga = await group_repo.count_active()
    a = await alert_repo.count()
    logs = await log_repo.recent(1)
    last = logs[0]["created_at"][:16] if logs else "—"
    try:
        await cb.message.edit_text(with_royal(
            f"📈 <b>آمار پیشرفته</b>\n\n"
            f"👥 کاربران کل: <b>{u}</b>\n"
            f"🆕 امروز: <b>{ut}</b>\n"
            f"🚫 بن: <b>{ub}</b>\n"
            f"📂 گروه: <b>{g}</b>\n"
            f"🟢 فعال: <b>{ga}</b>\n"
            f"🔔 هشدار: <b>{a}</b>\n"
            f"📝 آخرین: <code>{last}</code>\n\n"
            f"🕐 {fa_full()}"),
            reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:broadcast_prices")
async def cb_ap_broadcast_prices(cb: CallbackQuery, bot: Bot):
    """ارسال قیمت به همه از طریق پنل اینلاین"""
    if not is_adm(cb.from_user.id): return
    await cb.answer("⏳")
    groups = await group_repo.all_for_broadcast()
    if not groups:
        try:
            await cb.message.edit_text(with_royal("❌ گروهی ثبت نشده."),
                                        reply_markup=admin_panel_kb())
        except TelegramBadRequest: pass
        return
    fiat, _ = await price_svc.get_fiat()
    gold = await price_svc.get_gold()
    coins = await price_svc.get_coins()
    crypto = await price_svc.get_crypto()
    text = render_overview(fiat, gold, coins, crypto)
    ok, fail = 0, 0
    for g in groups:
        try:
            await bot.send_message(g["chat_id"], text, reply_markup=menu_kb())
            await group_repo.last_bc(g["chat_id"])
            ok += 1
        except TelegramForbiddenError:
            await group_repo.remove(g["chat_id"])
            fail += 1
        except Exception: fail += 1
        await asyncio.sleep(1.0)
    await log_repo.log(Config.ADMIN_ID, "bc_prices", f"{ok}/{fail}")
    try:
        await cb.message.edit_text(with_royal(
            f"✅ <b>ارسال قیمت</b>\n\n📤 {ok}\n📭 {fail}"),
            reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass


@admin_router.callback_query(F.data == "ap:ch_set")
async def cb_ch_set(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await state.set_state(AdminState.set_channel)
    try:
        await cb.message.edit_text(with_royal(
            "🔧 <b>کانال اجباری</b>\n\n<code>@channel</code> یا <code>-100...</code>"),
            reply_markup=cancel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:ch_remove")
async def cb_ch_remove(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    await setting_repo.clear_channel()
    try:
        await cb.message.edit_text(with_royal("🗑 حذف شد."))
    except TelegramBadRequest: pass
    await cb.answer("✅")


@admin_router.callback_query(F.data.startswith("ap:maint_"))
async def cb_ap_maint(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    on = cb.data.endswith("on")
    await setting_repo.set_maintenance(on)
    try:
        await cb.message.edit_text(
            with_royal(f"🔧 تعمیر: <b>{'✅' if on else '❌'}</b>"),
            reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer("✅")


@admin_router.message(AdminState.set_channel)
async def adm_recv_ch(message: Message, state: FSMContext, bot: Bot):
    if not is_adm(message.from_user.id): return
    raw = (message.text or "").strip()
    await state.clear()
    if not raw: return
    if re.match(r"^-?\d+$", raw): parsed = raw
    elif raw.startswith("@"): parsed = raw
    else:
        m = re.match(r"^https?://t\.me/([A-Za-z0-9_]+)/?$", raw)
        parsed = f"@{m.group(1)}" if m else (f"@{raw}" if re.match(r"^[A-Za-z0-9_]{4,}$", raw) else None)
    if not parsed:
        await message.answer("❌ نامعتبر.")
        return
    try:
        await bot.get_chat(parsed)
        await bot.get_chat_member(parsed, bot.id)
    except Exception as e:
        await message.answer(f"❌ {e}")
        return
    await setting_repo.set_channel(parsed)
    await log_repo.log(Config.ADMIN_ID, "set_channel", parsed)
    await message.answer(with_royal(f"✅ کانال: <code>{parsed}</code>"),
                         reply_markup=admin_kb())


# ─── admin commands ───

@admin_router.message(Command("ban"))
async def adm_ban(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    args = (command.args or "").split(maxsplit=1)
    if not args or not args[0].isdigit(): return
    t = int(args[0])
    reason = args[1] if len(args) > 1 else "بدون دلیل"
    await user_repo.ban(t, reason)
    await log_repo.log(Config.ADMIN_ID, "ban", f"{t}: {reason}")
    await message.answer(f"🚫 {t} بن شد.")


@admin_router.message(Command("unban"))
async def adm_unban(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    a = (command.args or "").strip()
    if not a.isdigit(): return
    await user_repo.unban(int(a))
    await message.answer("✅")


@admin_router.message(Command("warn"))
async def adm_warn(message: Message, command: CommandObject, bot: Bot):
    if not is_adm(message.from_user.id): return
    a = (command.args or "").strip()
    if not a.isdigit(): return
    n = await user_repo.warn(int(a))
    try: await bot.send_message(int(a), f"⚠️ اخطار ({n})")
    except Exception: pass
    await message.answer(f"⚠️ #{n}")


@admin_router.message(Command("unwarn"))
async def adm_unwarn(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    a = (command.args or "").strip()
    if not a.isdigit(): return
    await user_repo.clear_warns(int(a))
    await message.answer("✅")


@admin_router.message(Command("mute"))
async def adm_mute(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    args = (command.args or "").split()
    if not args or not args[0].isdigit(): return
    t = int(args[0])
    m = int(args[1]) if len(args) > 1 and args[1].isdigit() else 60
    await user_repo.mute(t, m)
    await message.answer(f"🔇 {m}د")


@admin_router.message(Command("unmute"))
async def adm_unmute(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    a = (command.args or "").strip()
    if not a.isdigit(): return
    await user_repo.unmute(int(a))
    await message.answer("✅")


@admin_router.message(Command("userinfo"))
async def adm_uinfo(message: Message, command: CommandObject):
    if not is_adm(message.from_user.id): return
    a = (command.args or "").strip()
    if not a.isdigit(): return
    u = await user_repo.get(int(a))
    if not u:
        await message.answer("❌ یافت نشد.")
        return
    text = (f"👤 <b>کاربر</b>\n\n🆔 <code>{u['user_id']}</code>\n"
            f"👤 {u['full_name'] or '—'}\n🔗 @{u['username'] or '—'}\n"
            f"🚫 {'✅ ' + (u['ban_reason'] or '') if u['is_banned'] else '❌'}\n"
            f"⚠️ اخطار: <b>{u['warn_count']}</b>\n"
            f"📅 {u['first_seen'][:10]}\n🕐 {u['last_seen'][:16]}")
    await message.answer(with_royal(text), reply_markup=admin_user_kb(u["user_id"]))


@admin_router.message(Command("stats"))
async def adm_stats_cmd(message: Message):
    if not is_adm(message.from_user.id): return
    u = await user_repo.count()
    ub = await user_repo.count_banned()
    g = await group_repo.count()
    ga = await group_repo.count_active()
    a = await alert_repo.count()
    await message.answer(with_royal(
        f"📊 <b>آمار سریع</b>\n\n👥 {u}\n🚫 {ub}\n📂 {g} (فعال: {ga})\n🔔 {a}"))


@admin_router.message(Command("backup"))
async def adm_cmd_backup(message: Message, bot: Bot):
    if not is_adm(message.from_user.id): return
    try:
        with open(Config.DB_PATH, "rb") as f:
            data = f.read()
        stamp = now_iran().strftime("%Y%m%d_%H%M%S")
        await bot.send_document(Config.ADMIN_ID,
                                BufferedInputFile(data, filename=f"backup_{stamp}.db"),
                                caption=with_royal("💾 بکاپ"))
    except Exception as e:
        await message.answer(f"❌ {e}")


@admin_router.callback_query(F.data.startswith("au:"))
async def cb_au(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_adm(cb.from_user.id): return
    parts = cb.data.split(":")
    act = parts[1]
    uid = int(parts[2])
    if act == "ban":
        await user_repo.ban(uid, "ادمین")
        await cb.answer("🚫", show_alert=True)
    elif act == "unban":
        await user_repo.unban(uid)
        await cb.answer("✅", show_alert=True)
    elif act == "warn":
        n = await user_repo.warn(uid)
        try: await bot.send_message(uid, f"⚠️ اخطار ({n})")
        except Exception: pass
        await cb.answer(f"⚠️ #{n}", show_alert=True)
    elif act == "mute":
        await user_repo.mute(uid, 60)
        await cb.answer("🔇", show_alert=True)
    elif act == "unmute":
        await user_repo.unmute(uid)
        await cb.answer("🔊", show_alert=True)
    elif act == "msg":
        await state.set_state(AdminState.send_to_user)
        await state.update_data(target=uid)
        await cb.message.answer(with_royal(f"📨 به <code>{uid}</code>:"),
                                reply_markup=cancel_kb())
        await cb.answer()


@admin_router.message(AdminState.send_to_user)
async def adm_send_to_user(message: Message, state: FSMContext, bot: Bot):
    if not is_adm(message.from_user.id): return
    d = await state.get_data()
    target = d.get("target")
    await state.clear()
    if not target: return
    try:
        await bot.copy_message(target, message.chat.id, message.message_id)
        await message.answer(with_royal("✅ ارسال شد."), reply_markup=admin_kb())
    except Exception as e:
        await message.answer(f"❌ {e}")


@admin_router.callback_query(F.data.startswith("ap:users:"))
async def cb_ap_users(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    try: page = int(cb.data.split(":")[2])
    except Exception: page = 0
    per_page = 10
    total = await user_repo.count()
    users = await user_repo.all(per_page, page * per_page)
    if not users:
        await cb.answer("خالی", show_alert=True); return
    start = page * per_page + 1
    end = min(start + len(users) - 1, total)
    lines = [f"👥 <b>({start}-{end} از {total})</b>\n"]
    for u in users:
        st = "🚫" if u["is_banned"] else "✅"
        lines.append(f"{st} <code>{u['user_id']}</code> — {u['full_name'] or '—'}")
    nav = []
    if page > 0: nav.append(_ib("◀️", PRIMARY, callback_data=f"ap:users:{page-1}"))
    if end < total: nav.append(_ib("▶️", PRIMARY, callback_data=f"ap:users:{page+1}"))
    rows = []
    if nav: rows.append(nav)
    rows.append([_ib("🏠 بازگشت", DANGER, callback_data="ap:menu")])
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)),
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data.startswith("ap:groups:"))
async def cb_ap_groups(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    try: page = int(cb.data.split(":")[2])
    except Exception: page = 0
    per_page = 10
    groups = await group_repo.all()
    if not groups:
        await cb.answer("خالی", show_alert=True); return
    start = page * per_page
    end = min(start + per_page, len(groups))
    chunk = groups[start:end]
    lines = [f"📂 <b>({start+1}-{end} از {len(groups)})</b>\n"]
    for g in chunk:
        st = "🟢" if g["auto_broadcast"] else "⚪"
        lines.append(f"{st} <code>{g['chat_id']}</code> — {g['title'] or '—'}")
    nav = []
    if page > 0: nav.append(_ib("◀️", PRIMARY, callback_data=f"ap:groups:{page-1}"))
    if end < len(groups): nav.append(_ib("▶️", PRIMARY, callback_data=f"ap:groups:{page+1}"))
    rows = []
    if nav: rows.append(nav)
    rows.append([_ib("🏠 بازگشت", DANGER, callback_data="ap:menu")])
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)),
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:menu")
async def cb_ap_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    try:
        await cb.message.edit_text(with_royal("👑 <b>پنل ادمین</b>"),
                                    reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:bans")
async def cb_ap_bans(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    rows = await db.all("SELECT user_id, full_name, ban_reason FROM users WHERE is_banned=1 LIMIT 20")
    lines = ["🚫 <b>بن‌شده‌ها</b>\n"]
    if not rows: lines.append("خالی.")
    else:
        for r in rows:
            lines.append(f"• <code>{r['user_id']}</code> — {r['full_name'] or '—'}")
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)), reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:warns")
async def cb_ap_warns(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    rows = await db.all("SELECT user_id, full_name, warn_count FROM users WHERE warn_count>0 ORDER BY warn_count DESC LIMIT 20")
    lines = ["⚠️ <b>اخطاردار</b>\n"]
    if not rows: lines.append("خالی.")
    else:
        for r in rows:
            lines.append(f"• <code>{r['user_id']}</code> — {r['full_name'] or '—'} ⚠️{r['warn_count']}")
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)), reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:alerts")
async def cb_ap_alerts(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    alerts = await alert_repo.all_active()
    lines = ["🔔 <b>هشدارها</b>\n"]
    if not alerts: lines.append("خالی.")
    else:
        for a in alerts[:20]:
            lines.append(f"• <code>{a['user_id']}</code> — {a['symbol'].upper()} "
                         f"<code>{fmt_int(a['target_price'])}</code>")
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)), reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:ch")
async def cb_ap_ch(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    ch = await setting_repo.get_channel()
    text = f"🔒 <b>کانال اجباری</b>\n\n<code>{ch or 'تنظیم نشده'}</code>"
    rows = [[_ib("🔧 تنظیم", PRIMARY, callback_data="ap:ch_set")]]
    if ch: rows.append([_ib("🗑 حذف", DANGER, callback_data="ap:ch_remove")])
    rows.append([_ib("🏠 بازگشت", DANGER, callback_data="ap:menu")])
    try:
        await cb.message.edit_text(with_royal(text),
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:maint")
async def cb_ap_maint_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    on = await setting_repo.is_maintenance()
    try:
        await cb.message.edit_text(with_royal(f"🔧 تعمیر: <b>{'✅' if on else '❌'}</b>"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [_ib("🟢 خاموش", SUCCESS, callback_data="ap:maint_off"),
                 _ib("🔴 روشن", DANGER, callback_data="ap:maint_on")],
                [_ib("🏠 بازگشت", DANGER, callback_data="ap:menu")]]))
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:logs")
async def cb_ap_logs(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    logs = await log_repo.recent(15)
    lines = ["📝 <b>لاگ‌ها</b>\n"]
    if not logs: lines.append("خالی.")
    else:
        for r in logs:
            lines.append(f"• [{r['created_at'][11:16]}] {r['action']} — {r['details'] or '—'}")
    try:
        await cb.message.edit_text(with_royal("\n".join(lines)), reply_markup=admin_panel_kb())
    except TelegramBadRequest: pass
    await cb.answer()


@admin_router.callback_query(F.data == "ap:backup")
async def cb_ap_backup(cb: CallbackQuery, bot: Bot):
    if not is_adm(cb.from_user.id): return
    try:
        with open(Config.DB_PATH, "rb") as f:
            data = f.read()
        stamp = now_iran().strftime("%Y%m%d_%H%M%S")
        await bot.send_document(Config.ADMIN_ID,
                                BufferedInputFile(data, filename=f"backup_{stamp}.db"),
                                caption=with_royal("💾 بکاپ"))
        await cb.answer("✅")
    except Exception as e:
        await cb.answer(f"❌ {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════════════
# FORCE CHANNEL MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════

async def _is_member(bot, ch, uid):
    try:
        m = await bot.get_chat_member(ch, uid)
        return m.status not in ("left", "kicked")
    except Exception:
        return True


# ═══════════════════════════════════════════════════════════════════════
# AUTO BROADCAST — ارسال همه قیمت‌ها به کانال و گروه
# ═══════════════════════════════════════════════════════════════════════

async def broadcast_job(bot):
    """ارسال خودکار به همه گروه‌ها و کانال‌های ثبت‌شده"""
    try:
        groups = await group_repo.active()
        if not groups: return
        fiat, _ = await price_svc.get_fiat()
        gold = await price_svc.get_gold()
        coins = await price_svc.get_coins()
        crypto = await price_svc.get_crypto()
        text = render_overview(fiat, gold, coins, crypto)
        for g in groups:
            cid = g["chat_id"]
            interval = g["broadcast_interval"] or Config.DEFAULT_BC_INTERVAL
            last = g["last_broadcast"]
            if last:
                try:
                    ld = datetime.fromisoformat(last)
                    if ld.tzinfo is None: ld = ld.replace(tzinfo=IRAN_TZ)
                    if (now_iran() - ld).total_seconds() / 60 < interval:
                        continue
                except Exception: pass
            try:
                await bot.send_message(cid, text, reply_markup=menu_kb())
                await group_repo.last_bc(cid)
                log.info("📡 Sent prices to %s", cid)
            except TelegramForbiddenError:
                await group_repo.remove(cid)
            except Exception as e:
                log.warning("bc %s: %s", cid, e)
            await asyncio.sleep(1.5)
    except Exception as e:
        log.exception("bc: %s", e)


scheduler = AsyncIOScheduler(timezone=IRAN_TZ)


async def job_bc(bot): await broadcast_job(bot)
async def job_alerts(bot): await price_svc.check_alerts(bot)
async def job_refresh(bot):
    try:
        await price_svc.get_fiat()
        await price_svc.get_crypto()
    except Exception as e:
        log.exception("refresh: %s", e)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None


async def set_commands(bot: Bot):
    private_cmds = [
        BotCommand(command="price", description="💰 منوی قیمت"),
        BotCommand(command="dollar", description="💵 قیمت دلار"),
        BotCommand(command="euro", description="💶 قیمت یورو"),
        BotCommand(command="pound", description="💷 قیمت پوند"),
        BotCommand(command="gold", description="🥇 قیمت طلا"),
        BotCommand(command="coin", description="🪙 قیمت سکه"),
        BotCommand(command="crypto", description="₿ ارز دیجیتال"),
        BotCommand(command="alert", description="🔔 هشدار قیمت"),
        BotCommand(command="time", description="🕐 ساعت ایران"),
        BotCommand(command="rules", description="📜 قوانین"),
        BotCommand(command="myid", description="🆔 آیدی من"),
        BotCommand(command="help", description="❓ راهنما"),
    ]
    group_cmds = [
        BotCommand(command="price", description="💰 منوی قیمت"),
        BotCommand(command="dollar", description="💵 قیمت دلار"),
        BotCommand(command="euro", description="💶 قیمت یورو"),
        BotCommand(command="pound", description="💷 قیمت پوند"),
        BotCommand(command="gold", description="🥇 قیمت طلا"),
        BotCommand(command="coin", description="🪙 قیمت سکه"),
        BotCommand(command="crypto", description="₿ ارز دیجیتال"),
        BotCommand(command="alert", description="🔔 هشدار قیمت"),
        BotCommand(command="settings", description="⚙️ تنظیمات گروه"),
        BotCommand(command="time", description="🕐 ساعت"),
        BotCommand(command="help", description="❓ راهنما"),
    ]
    admin_cmds = [
        BotCommand(command="admin", description="👑 پنل ادمین"),
        BotCommand(command="price", description="💰 قیمت"),
        BotCommand(command="stats", description="📊 آمار"),
        BotCommand(command="userinfo", description="👤 اطلاعات کاربر"),
        BotCommand(command="ban", description="🚫 بن"),
        BotCommand(command="unban", description="✅ آنبن"),
        BotCommand(command="warn", description="⚠️ اخطار"),
        BotCommand(command="mute", description="🔇 سکوت"),
        BotCommand(command="backup", description="💾 بکاپ"),
    ]
    try:
        await bot.set_my_commands(commands=private_cmds, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=group_cmds, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(commands=admin_cmds, scope=BotCommandScopeChat(chat_id=Config.ADMIN_ID))
        log.info("✅ Commands registered")
    except Exception as e:
        log.warning("set_commands: %s", e)


async def on_startup(bot: Bot, **kwargs):
    log.info("🚀 Bot v8.0 — Javed Shah Edition")
    me = await bot.get_me()
    log.info("🤖 @%s | 👑 %s", me.username, Config.ADMIN_ID)
    await set_commands(bot)
    fiat, usd_t = await price_svc.get_fiat()
    crypto = await price_svc.get_crypto()
    log.info("💰 Fiat: %d | Crypto: %d | USD: %s تومان",
             len(fiat), len(crypto), fmt_int(usd_t))
    try:
        await bot.send_message(Config.ADMIN_ID,
            with_royal(
                f"✅ <b>ربات قیمت v8.0 راه‌اندازی شد</b>\n\n"
                f"@{me.username}\n"
                f"💱 ارزها: {len(fiat)}\n"
                f"₿ کریپتو: {len(crypto)}\n"
                f"💵 دلار: {fmt_int(usd_t)} تومان\n"
                f"📡 ارسال خودکار: فعال"))
    except Exception: pass


async def on_shutdown(bot: Bot = None, **kwargs):
    try:
        if scheduler.running: scheduler.shutdown(wait=False)
    except Exception: pass
    await price_svc.close()
    await db.close()
    if bot:
        try: await bot.session.close()
        except Exception: pass


async def run_bot():
    global bot, dp
    bot = Bot(token=Config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(group_router)
    dp.include_router(alert_router)
    dp.include_router(crypto_router)
    dp.include_router(price_router)
    dp.include_router(common_router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def scheduler_start():
    while bot is None:
        await asyncio.sleep(0.5)
    scheduler.add_job(job_bc, "interval", minutes=1, args=[bot], id="bc")
    scheduler.add_job(job_alerts, "interval", minutes=2, args=[bot], id="al")
    scheduler.add_job(job_refresh, "interval", minutes=15, args=[bot], id="rf")
    scheduler.start()
    log.info("⏰ Scheduler active")


async def main():
    Config.validate()
    await db.connect()
    await asyncio.gather(run_bot(), scheduler_start())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("👋 Bye")
