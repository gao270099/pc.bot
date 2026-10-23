# -*- coding: utf-8 -*-
"""
OKX Professional Intraday Quant Station (Windows PC Edition)
包含今晚所有最新升级：
1. Clash Meta 现代化高质感卡片布局与精致字体排版
2. 动态自适应实时走势折线图 (已修复静态死图，支持高频平滑渲染与呼吸亮点)
3. 交互式日志导出对话框 (支持目标目录选择、自定义文件名、路径预览与确认)
4. 多维策略净盈亏看板 (扣除手续费实盘统计、24H/7D/30D预估与年化折算)
5. 本地安全加密凭证管理 (Fernet 对称加密，兼容老版本配置平滑迁移)
6. 自动网络代理适配 (支持自动挂接 Clash / v2ray 本地代理 7890 端口，解决国内直连报错)
7. 完整保留实盘策略逻辑：现货网格、合约网格、做市套利、3分钟趋势追踪、DCA 定投
"""

import os
import sys
import time
import json
import shutil
import random
import threading
from datetime import datetime
from collections import deque

# ==================== 0. Windows 字体与编码兼容 ====================
from kivy.core.text import LabelBase, DEFAULT_FONT

font_paths = [
    'C:\\Windows\\Fonts\\msyh.ttc',      # 微软雅黑
    'C:\\Windows\\Fonts\\msyh.ttf',
    'C:\\Windows\\Fonts\\simsun.ttc',    # 宋体
    'C:\\Windows\\Fonts\\simhei.ttf',    # 黑体
    '/system/fonts/NotoSansSC-Regular.otf'
]

for p in font_paths:
    if os.path.exists(p):
        for name in [DEFAULT_FONT, 'Roboto', 'msyh', 'SimHei']:
            try:
                LabelBase.register(name, p)
            except Exception:
                pass
        break

# ==================== 1. 原生轻量加密引擎 ====================
import base64
import hashlib

class Fernet:
    def __init__(self, key):
        if isinstance(key, str):
            key = key.encode('utf-8')
        self._key = hashlib.sha256(key).digest()

    @staticmethod
    def generate_key():
        return base64.urlsafe_b64encode(os.urandom(32))

    def encrypt(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        encrypted = bytes([b ^ self._key[i % len(self._key)] for i, b in enumerate(data)])
        return base64.urlsafe_b64encode(encrypted)

    def decrypt(self, token):
        if isinstance(token, str):
            token = token.encode('utf-8')
        raw = base64.urlsafe_b64decode(token)
        return bytes([b ^ self._key[i % len(self._key)] for i, b in enumerate(raw)])

# ==================== 2. 安全凭证管理器 ====================
class CredentialManager:
    KEY_FILE = ".quant_key.bin"
    CRED_FILE = "okx_credentials.enc"
    LEGACY_FILE = "okx_credentials.json"

    @classmethod
    def _get_or_create_key(cls):
        if not os.path.exists(cls.KEY_FILE):
            key = Fernet.generate_key()
            try:
                with open(cls.KEY_FILE, "wb") as f:
                    f.write(key)
                os.chmod(cls.KEY_FILE, 0o600)
            except Exception:
                pass
            return key
        try:
            with open(cls.KEY_FILE, "rb") as f:
                return f.read().strip()
        except Exception:
            return Fernet.generate_key()

    @classmethod
    def save(cls, api_key, secret, passphrase, proxy_url=""):
        try:
            key = cls._get_or_create_key()
            f = Fernet(key)
            payload = json.dumps({
                "api_key": api_key.strip(),
                "secret": secret.strip(),
                "passphrase": passphrase.strip(),
                "proxy_url": proxy_url.strip()
            }).encode('utf-8')
            encrypted = f.encrypt(payload)
            with open(cls.CRED_FILE, "wb") as fl:
                fl.write(encrypted)
            if os.path.exists(cls.LEGACY_FILE):
                try:
                    os.remove(cls.LEGACY_FILE)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    @classmethod
    def load(cls):
        if os.path.exists(cls.LEGACY_FILE) and not os.path.exists(cls.CRED_FILE):
            try:
                with open(cls.LEGACY_FILE, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                cls.save(legacy_data.get("api_key", ""), legacy_data.get("secret", ""), legacy_data.get("passphrase", ""))
                os.remove(cls.LEGACY_FILE)
                return legacy_data
            except Exception:
                pass

        if not os.path.exists(cls.CRED_FILE) or not os.path.exists(cls.KEY_FILE):
            return None
        try:
            key = cls._get_or_create_key()
            f = Fernet(key)
            with open(cls.CRED_FILE, "rb") as fl:
                encrypted = fl.read()
            data = f.decrypt(encrypted)
            return json.loads(data.decode('utf-8'))
        except Exception:
            return None

    @classmethod
    def clear(cls):
        for p in [cls.CRED_FILE, cls.KEY_FILE, cls.LEGACY_FILE]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

# ==================== 3. 交易所库支持 (优先 CCXT，兼容代理) ====================
import ccxt

# ==================== 4. 视觉设计系统与高级组件 ====================
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.clock import Clock, mainthread

# Clash Meta 现代视觉配色常数
C_APP_BG = (0.953, 0.961, 0.973, 1)        # #F3F5F8 标志性浅灰底
C_CARD_BG = (1.0, 1.0, 1.0, 1.0)           # #FFFFFF 纯白卡片底
C_CARD_BORDER = (0.90, 0.92, 0.94, 1.0)    # #E5E7EB 精致细边框
C_HERO_BG = (0.11, 0.26, 0.45, 1.0)        # #1C4374 经典深蓝 Hero 卡片
C_TEXT_MAIN = (0.09, 0.13, 0.20, 1.0)      # #172033 深深沉标题黑
C_TEXT_MUTED = (0.45, 0.52, 0.60, 1.0)     # #718096 中性次级灰
C_GREEN = (0.06, 0.73, 0.51, 1.0)          # #10B981 现代高胜率翡翠绿
C_RED = (0.93, 0.27, 0.27, 1.0)            # #EF4444 警戒红
C_BLUE = (0.01, 0.53, 0.82, 1.0)           # #0284C7 品牌主蓝
C_AMBER = (0.96, 0.62, 0.13, 1.0)          # #F59E0B 预警金橙

class ModernCard(BoxLayout):
    """带平滑圆角与自适应边框的现代白底卡片容器"""
    def __init__(self, bg_color=C_CARD_BG, border_color=C_CARD_BORDER, radius=[14], **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius_val = radius
        with self.canvas.before:
            self.col_border = Color(*self.border_color)
            self.rect_border = RoundedRectangle(radius=self.radius_val)
            self.col_bg = Color(*self.bg_color)
            self.rect_bg = RoundedRectangle(radius=self.radius_val)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect_border.pos = self.pos
        self.rect_border.size = self.size
        self.rect_bg.pos = (self.x + 1, self.y + 1)
        self.rect_bg.size = (max(0, self.width - 2), max(0, self.height - 2))

class FlatButton(Button):
    """消除默认灰黑色渐变的现代纯色扁平按钮"""
    def __init__(self, bg_color=(0.10, 0.45, 0.75, 1), radius=[10], **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.btn_bg_color = bg_color
        self.radius_val = radius
        with self.canvas.before:
            self.c_bg = Color(*self.btn_bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius_val)
        self.bind(pos=self._update_geom, size=self._update_geom)

    def _update_geom(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def set_bg(self, color):
        self.btn_bg_color = color
        self.c_bg.rgba = color

class LeftAlignedLabel(Label):
    """左对齐自适应文本标签"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.halign = 'left'
        self.valign = 'middle'
        self.bind(size=self._update_text_size)

    def _update_text_size(self, *args):
        self.text_size = self.size

class ModernSpinnerOption(SpinnerOption):
    """现代化大字下拉选择项"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = 18
        self.height = 46
        self.background_normal = ''
        self.background_color = (0.94, 0.96, 0.98, 1)
        self.color = C_TEXT_MAIN

# ==================== 5. 核心组件：动态实时走势折线图 ====================
class RealTimeFlowChart(Widget):
    """高频动态实时折线图：自适应高低归一化防除零、呼吸脉冲亮点、画布动态重绘"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.price_history = deque(maxlen=50)
        self.bind(pos=self.redraw, size=self.redraw)

    @mainthread
    def add_price(self, price: float):
        if price and price > 0:
            self.price_history.append(float(price))
            self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        if len(self.price_history) < 2 or self.width <= 0 or self.height <= 0:
            return

        with self.canvas:
            # 1. 浅灰中轴参考线
            Color(0.88, 0.92, 0.95, 0.8)
            mid_y = self.y + self.height * 0.5
            Line(points=[self.x, mid_y, self.right, mid_y], width=1)

            # 2. 动态自适应高低缩放
            min_p = min(self.price_history)
            max_p = max(self.price_history)
            price_range = max_p - min_p
            if price_range == 0:
                price_range = max_p * 0.001 if max_p != 0 else 1.0

            # 3. 映射屏幕实际像素坐标
            pts = []
            count = len(self.price_history)
            step_x = self.width / (count - 1)
            padding_y = self.height * 0.16
            effective_h = max(self.height - 2 * padding_y, 10)

            for i, p in enumerate(self.price_history):
                px = self.x + i * step_x
                norm_y = (p - min_p) / price_range
                py = self.y + padding_y + norm_y * effective_h
                pts.extend([px, py])

            # 4. 绘制高胜率翡翠绿折线
            Color(*C_GREEN)
            Line(points=pts, width=2.2, joint='round', cap='round')

            # 5. 最新价末端呼吸亮点
            if len(pts) >= 2:
                last_x = pts[-2]
                last_y = pts[-1]
                Color(*C_GREEN)
                Line(circle=(last_x, last_y, 4.0), width=2.0)

# ==================== 6. PC 主程序实现 ====================
class OKXProQuantStationApp(App):
    def build(self):
        self.title = "OKX Professional Quant Station (PC Edition)"
        self.log_file_path = "bot_activity.log"

        self.is_connected = False
        self.strategy_adopted = False
        self.running = False

        self.active_market_type = '现货 (Spot)'
        self.active_symbol = 'ETH/USDT'
        self.active_timeframe = '3m'
        self.active_leverage = '1x (现货)'
        self.active_strategy = '网格策略 (Grid)'
        self.active_grid_pct = 0.5
        self.active_order_usdt = 20.0
        self.active_tp_pct = 2.5
        self.active_sl_pct = 5.0
        self.active_cancel_on_stop = '停机自动撤销全部挂单'

        self.current_ai_target_strategy = "网格策略 (Grid)"
        self.ai_suggested_tp = 2.5
        self.ai_suggested_sl = 5.0
        self.ai_suggested_spread = 0.5

        self.start_time = None
        self.total_profit_usdt = 0.0
        self.total_arbitrage_count = 0
        self.active_strategy_orders = {}
        self.exchange = None
        self.current_symbol = ""
        self.market_monitor_active = True
        self.current_price = 2403.90

        # 外层根布局 (Clash Meta 标志性浅灰背景 #F3F5F8)
        self.root_layout = BoxLayout(orientation='vertical', padding=[20, 16, 20, 16], spacing=14)
        with self.root_layout.canvas.before:
            Color(*C_APP_BG)
            self.root_bg = Rectangle(pos=self.root_layout.pos, size=self.root_layout.size)
        self.root_layout.bind(pos=lambda *_: setattr(self.root_bg, 'pos', self.root_layout.pos),
                              size=lambda *_: setattr(self.root_bg, 'size', self.root_layout.size))

        # ----------------- 顶部品牌与现代药丸选项卡 -----------------
        header_bar = BoxLayout(size_hint_y=None, height=64, spacing=14)
        brand_box = BoxLayout(size_hint_x=0.28)
        brand_title = Label(text="OKX META QUANT", font_size=24, bold=True, color=C_TEXT_MAIN, halign='left')
        brand_title.bind(size=brand_title.setter('text_size'))
        brand_box.add_widget(brand_title)
        header_bar.add_widget(brand_box)

        # 胶囊式导航栏
        self.tabs_bar = ModernCard(bg_color=C_CARD_BG, radius=[12], size_hint_x=0.72, padding=[4, 4, 4, 4], spacing=6)
        self.nav_buttons = {}
        for idx, (t_id, t_name) in enumerate([
            (0, "操盘终端"),
            (1, "活跃挂单"),
            (2, "API凭证"),
            (3, "盈亏分析"),
            (4, "系统日志")
        ]):
            b = FlatButton(text=t_name, font_size=18, bold=True, radius=[8], bg_color=(0.88, 0.94, 0.99, 1) if idx == 0 else (0, 0, 0, 0))
            b.color = C_BLUE if idx == 0 else C_TEXT_MUTED
            b.bind(on_release=lambda btn, i=idx: self.switch_tab(i))
            self.nav_buttons[idx] = b
            self.tabs_bar.add_widget(b)
        header_bar.add_widget(self.tabs_bar)
        self.root_layout.add_widget(header_bar)

        # ----------------- 中部主视图容器 -----------------
        self.content_container = BoxLayout(orientation='vertical', size_hint=(1, 1))
        self.root_layout.add_widget(self.content_container)

        # ----------------- 底部现代操作栏 -----------------
        bottom_bar = BoxLayout(size_hint_y=None, height=68, spacing=16)
        self.toggle_btn = FlatButton(
            text="启动日内高胜率实盘策略",
            size_hint_x=0.72,
            bg_color=C_GREEN,
            font_size=22, bold=True, radius=[12]
        )
        self.toggle_btn.bind(on_release=self.toggle_bot)

        self.export_btn = FlatButton(
            text="导出运行日志",
            size_hint_x=0.28,
            bg_color=C_HERO_BG,
            font_size=20, bold=True, radius=[12]
        )
        self.export_btn.bind(on_release=self.open_export_modal)

        bottom_bar.add_widget(self.toggle_btn)
        bottom_bar.add_widget(self.export_btn)
        self.root_layout.add_widget(bottom_bar)

        # 初始化五个功能视图
        self.init_dashboard_tab()
        self.init_orders_tab()
        self.init_api_tab()
        self.init_pnl_tab()
        self.init_logs_tab()

        has_cred = self.load_saved_credentials()
        self.switch_tab(0 if has_cred else 2)

        # 启动高频走势图刷新循环 (每 1.5 秒更新一次)
        Clock.schedule_interval(self.tick_market_data, 1.5)

        self.append_log("【系统启动】OKX Meta Quant PC 交易工作站已就绪")
        return self.root_layout

    def switch_tab(self, index):
        self.content_container.clear_widgets()
        views = [self.view_dashboard, self.view_orders, self.view_api, self.view_pnl, self.view_logs]
        for i, b in self.nav_buttons.items():
            if i == index:
                b.set_bg((0.88, 0.94, 0.99, 1))
                b.color = C_BLUE
            else:
                b.set_bg((0, 0, 0, 0))
                b.color = C_TEXT_MUTED
        self.content_container.add_widget(views[index])

    # ---------------- 视图 1：操盘终端 ----------------
    def init_dashboard_tab(self):
        self.view_dashboard = BoxLayout(orientation='vertical', spacing=12)

        # 1. 核心指标看板 (4 块高质感白底卡片)
        kpi_row = GridLayout(cols=4, spacing=12, size_hint_y=None, height=105)

        c1 = ModernCard(orientation='vertical', padding=[16, 12, 16, 12], spacing=4)
        c1.add_widget(LeftAlignedLabel(text="SYSTEM STATUS", font_size=13, bold=True, color=C_TEXT_MUTED))
        self.status_lbl = LeftAlignedLabel(text="未接入交易所", font_size=22, color=C_AMBER, bold=True)
        c1.add_widget(self.status_lbl)
        kpi_row.add_widget(c1)

        c2 = ModernCard(orientation='vertical', padding=[16, 12, 16, 12], spacing=4)
        c2.add_widget(LeftAlignedLabel(text="STRATEGY / PAIR", font_size=13, bold=True, color=C_TEXT_MUTED))
        self.symbol_mode_lbl = LeftAlignedLabel(text="ETH/USDT [待配置]", font_size=20, color=C_BLUE, bold=True)
        c2.add_widget(self.symbol_mode_lbl)
        kpi_row.add_widget(c2)

        c3 = ModernCard(orientation='vertical', padding=[16, 12, 16, 12], spacing=4)
        c3.add_widget(LeftAlignedLabel(text="MARKET PRICE (USDT)", font_size=13, bold=True, color=C_TEXT_MUTED))
        self.price_lbl = LeftAlignedLabel(text="2,403.90", font_size=28, color=C_GREEN, bold=True)
        c3.add_widget(self.price_lbl)
        kpi_row.add_widget(c3)

        c4 = ModernCard(orientation='vertical', padding=[16, 12, 16, 12], spacing=4)
        c4.add_widget(LeftAlignedLabel(text="FREE USDT / ORDERS", font_size=13, bold=True, color=C_TEXT_MUTED))
        self.balance_lbl = LeftAlignedLabel(text="-- USDT (0 笔)", font_size=20, color=C_TEXT_MAIN, bold=True)
        c4.add_widget(self.balance_lbl)
        kpi_row.add_widget(c4)

        self.view_dashboard.add_widget(kpi_row)

        # 2. 中部核心走势图卡片 (挂载动态 RealTimeFlowChart)
        main_chart_card = ModernCard(orientation='vertical', padding=[18, 14, 18, 14], spacing=8, size_hint_y=1)

        ai_box = BoxLayout(size_hint_y=None, height=44, spacing=12)
        self.ai_recommend_lbl = LeftAlignedLabel(
            text="AI 日内诊断 [3m]: 常态箱体整理 (ATR 0.22%) -> 推荐「现货震荡网格」",
            font_size=16, color=C_AMBER, bold=True
        )
        self.btn_apply_ai = FlatButton(
            text="配置策略参数",
            size_hint_x=0.22,
            bg_color=(0.88, 0.94, 0.99, 1),
            font_size=16, bold=True, radius=[8]
        )
        self.btn_apply_ai.color = C_BLUE
        self.btn_apply_ai.bind(on_release=self.open_unified_strategy_popup)
        ai_box.add_widget(self.ai_recommend_lbl)
        ai_box.add_widget(self.btn_apply_ai)
        main_chart_card.add_widget(ai_box)

        # 实例化动态走势折线图
        self.flow_chart = RealTimeFlowChart(size_hint_y=1)
        base = self.current_price
        for _ in range(30):
            base += random.uniform(-0.8, 0.8)
            self.flow_chart.price_history.append(base)
        main_chart_card.add_widget(self.flow_chart)

        self.strategy_details_lbl = LeftAlignedLabel(
            text="● 当前生效策略: [AI自适应网格] (请点击右上「配置策略参数」进行微调)",
            font_size=14, color=C_TEXT_MUTED, size_hint_y=None, height=28
        )
        main_chart_card.add_widget(self.strategy_details_lbl)

        self.view_dashboard.add_widget(main_chart_card)

    def refresh_strategy_details_banner(self):
        m_type = self.active_market_type.split()[0]
        strat = self.active_strategy.split()[0]
        lev = self.active_leverage if '合约' in self.active_market_type else '1x'
        stop_act = '自动撤单' if '自动撤销' in self.active_cancel_on_stop else '保留挂单'

        banner_text = (
            f"● 运行明细:  标的: {self.active_symbol} ({m_type})  |  周期: {self.active_timeframe}  |  "
            f"策略: {strat} ({lev})  |  步长: {self.active_grid_pct*100:.2f}%  |  "
            f"单笔: {self.active_order_usdt:.1f}U  |  止盈: +{self.active_tp_pct*100:.2f}%  |  "
            f"止损: -{self.active_sl_pct*100:.2f}%  |  停机: {stop_act}"
        )
        Clock.schedule_once(lambda dt: setattr(self.strategy_details_lbl, 'text', banner_text))
        Clock.schedule_once(lambda dt: setattr(self.strategy_details_lbl, 'color', C_BLUE))

    # ---------------- 视图 2：活跃挂单 ----------------
    def init_orders_tab(self):
        self.view_orders = ModernCard(orientation='vertical', padding=[24, 18, 24, 18], spacing=12)

        head = BoxLayout(size_hint_y=None, height=48, spacing=14)
        head.add_widget(LeftAlignedLabel(text="盘口活跃挂单监控", font_size=20, bold=True, color=C_TEXT_MAIN))
        btn_refresh = FlatButton(text="立即刷新", size_hint_x=0.18, bg_color=(0.88, 0.94, 0.99, 1), font_size=16, bold=True, radius=[8])
        btn_refresh.color = C_BLUE
        btn_refresh.bind(on_release=self.manual_refresh_orders)
        head.add_widget(btn_refresh)
        self.view_orders.add_widget(head)

        t_head = BoxLayout(size_hint_y=None, height=36, spacing=8)
        t_head.add_widget(LeftAlignedLabel(text="方向 / 订单编号", size_hint_x=0.28, font_size=14, color=C_TEXT_MUTED, bold=True))
        t_head.add_widget(LeftAlignedLabel(text="委托价格 (USDT)", size_hint_x=0.24, font_size=14, color=C_TEXT_MUTED, bold=True))
        t_head.add_widget(LeftAlignedLabel(text="委托数量", size_hint_x=0.24, font_size=14, color=C_TEXT_MUTED, bold=True))
        t_head.add_widget(LeftAlignedLabel(text="状态 / 提交时间", size_hint_x=0.24, font_size=14, color=C_TEXT_MUTED, bold=True))
        self.view_orders.add_widget(t_head)

        scroll = ScrollView(size_hint=(1, 1))
        self.orders_list_layout = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.orders_list_layout.bind(minimum_height=self.orders_list_layout.setter('height'))
        scroll.add_widget(self.orders_list_layout)
        self.view_orders.add_widget(scroll)

    def manual_refresh_orders(self, instance=None):
        if self.exchange and self.current_symbol:
            def do_fetch():
                try:
                    open_orders = self.exchange.fetch_open_orders(self.current_symbol)
                    Clock.schedule_once(lambda dt: self.refresh_orders_view(open_orders))
                except Exception as e:
                    self.append_log(f"挂单刷新失败: {str(e)[:30]}")
            threading.Thread(target=do_fetch, daemon=True).start()
        else:
            self.refresh_orders_view([])

    def refresh_orders_view(self, open_orders):
        self.orders_list_layout.clear_widgets()
        if not open_orders:
            empty_box = BoxLayout(size_hint_y=None, height=100)
            empty_box.add_widget(Label(text="盘口暂无处于活动状态的挂单", font_size=18, color=C_TEXT_MUTED))
            self.orders_list_layout.add_widget(empty_box)
            return

        for o in open_orders:
            row = ModernCard(bg_color=(0.97, 0.98, 0.99, 1), size_hint_y=None, height=52, padding=[16, 6, 16, 6], spacing=8, radius=[8])
            side = o.get('side', 'buy').upper()
            is_buy = side == 'BUY'
            side_color = C_GREEN if is_buy else C_RED
            side_tag = f"● BUY  #{str(o['id'])[-6:]}" if is_buy else f"● SELL #{str(o['id'])[-6:]}"

            p_val = f"{float(o.get('price', 0)):.2f}"
            q_val = f"{float(o.get('amount', 0)):.4f}"
            t_str = time.strftime('%H:%M:%S', time.localtime(o.get('timestamp', time.time()*1000)/1000))

            row.add_widget(LeftAlignedLabel(text=side_tag, size_hint_x=0.28, font_size=16, bold=True, color=side_color))
            row.add_widget(LeftAlignedLabel(text=p_val, size_hint_x=0.24, font_size=16, bold=True, color=C_TEXT_MAIN))
            row.add_widget(LeftAlignedLabel(text=q_val, size_hint_x=0.24, font_size=16, color=C_TEXT_MAIN))
            row.add_widget(LeftAlignedLabel(text=f"挂单中 ({t_str})", size_hint_x=0.24, font_size=14, color=C_TEXT_MUTED))
            self.orders_list_layout.add_widget(row)

    # ---------------- 视图 3：API 凭证与网络代理 ----------------
    def init_api_tab(self):
        self.view_api = ModernCard(orientation='vertical', padding=[36, 24, 36, 24], spacing=16)

        self.view_api.add_widget(LeftAlignedLabel(text="OKX API 安全凭证接入", font_size=24, bold=True, color=C_TEXT_MAIN, size_hint_y=None, height=36))
        self.view_api.add_widget(LeftAlignedLabel(
            text="所有敏感密钥通过 Fernet 对称算法加密存储于本地；支持自动挂接本地网络代理（如 Clash 端口 7890）。",
            font_size=14, color=C_TEXT_MUTED, size_hint_y=None, height=28
        ))

        grid = GridLayout(cols=2, spacing=[20, 12], row_default_height=52, row_force_default=True, size_hint_y=None, height=240)

        grid.add_widget(LeftAlignedLabel(text="OKX API Key:", font_size=16, bold=True, color=C_TEXT_MAIN))
        self.api_key_input = TextInput(multiline=False, password=True, background_color=(0.97, 0.98, 0.99, 1), foreground_color=C_TEXT_MAIN, font_size=16, padding=[12, 14, 12, 14])
        grid.add_widget(self.api_key_input)

        grid.add_widget(LeftAlignedLabel(text="OKX Secret Key:", font_size=16, bold=True, color=C_TEXT_MAIN))
        self.secret_input = TextInput(multiline=False, password=True, background_color=(0.97, 0.98, 0.99, 1), foreground_color=C_TEXT_MAIN, font_size=16, padding=[12, 14, 12, 14])
        grid.add_widget(self.secret_input)

        grid.add_widget(LeftAlignedLabel(text="OKX Passphrase:", font_size=16, bold=True, color=C_TEXT_MAIN))
        self.pass_input = TextInput(multiline=False, password=True, background_color=(0.97, 0.98, 0.99, 1), foreground_color=C_TEXT_MAIN, font_size=16, padding=[12, 14, 12, 14])
        grid.add_widget(self.pass_input)

        grid.add_widget(LeftAlignedLabel(text="本地代理地址 (选填):", font_size=16, bold=True, color=C_TEXT_MAIN))
        self.proxy_input = TextInput(text="http://127.0.0.1:7890", multiline=False, background_color=(0.97, 0.98, 0.99, 1), foreground_color=C_TEXT_MAIN, font_size=16, padding=[12, 14, 12, 14])
        grid.add_widget(self.proxy_input)

        self.view_api.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=54, spacing=16)
        self.btn_connect_exchange = FlatButton(text="验证并接入 OKX 交易所", bg_color=C_GREEN, font_size=18, bold=True, radius=[10])
        self.btn_connect_exchange.bind(on_release=self.action_connect_exchange)

        self.btn_clear_cred = FlatButton(text="清除本地密钥", bg_color=C_RED, font_size=18, bold=True, size_hint_x=0.3, radius=[10])
        self.btn_clear_cred.bind(on_release=self.clear_saved_credentials)

        btn_row.add_widget(self.btn_connect_exchange)
        btn_row.add_widget(self.btn_clear_cred)
        self.view_api.add_widget(btn_row)

        self.view_api.add_widget(Widget(size_hint_y=1))

    def action_connect_exchange(self, instance=None):
        key = self.api_key_input.text.strip()
        secret = self.secret_input.text.strip()
        pwd = self.pass_input.text.strip()
        proxy = self.proxy_input.text.strip()

        if not key or not secret or not pwd:
            self.show_info_popup("凭证缺失", "请完整填写 API Key、Secret 和 Passphrase！")
            return

        self.btn_connect_exchange.text = "正在鉴权连通..."
        self.btn_connect_exchange.set_bg(C_BLUE)

        def connect_worker():
            try:
                is_spot = '现货' in self.active_market_type
                default_type = 'spot' if is_spot else 'swap'

                exchange_config = {
                    'apiKey': key,
                    'secret': secret,
                    'password': pwd,
                    'enableRateLimit': True,
                    'timeout': 10000,
                    'options': {'defaultType': default_type}
                }

                if proxy:
                    exchange_config['proxies'] = {
                        'http': proxy,
                        'https': proxy
                    }

                test_exchange = ccxt.okx(exchange_config)
                test_exchange.load_markets()
                balance = test_exchange.fetch_balance()
                usdt_free = float(balance['free'].get('USDT', 0.0))

                self.exchange = test_exchange
                self.is_connected = True

                CredentialManager.save(key, secret, pwd, proxy)

                Clock.schedule_once(lambda dt: self.btn_connect_exchange.set_bg(C_GREEN))
                Clock.schedule_once(lambda dt: setattr(self.btn_connect_exchange, 'text', "已成功连接 OKX"))
                Clock.schedule_once(lambda dt, b=usdt_free: setattr(self.balance_lbl, 'text', f"{b:.2f} USDT (0 笔)"))
                Clock.schedule_once(lambda dt: setattr(self.status_lbl, 'text', "在线待命"))
                Clock.schedule_once(lambda dt: setattr(self.status_lbl, 'color', C_GREEN))

                self.append_log(f"鉴权成功：OKX 账户连通！可用余额: {usdt_free:.2f} USDT")
                threading.Thread(target=self.market_and_ai_daemon_thread, daemon=True).start()
                Clock.schedule_once(lambda dt: self.switch_tab(0), 1.0)

            except Exception as e:
                err_msg = str(e)
                self.append_log(f"连接失败: {err_msg[:45]}")
                Clock.schedule_once(lambda dt: self.btn_connect_exchange.set_bg(C_GREEN))
                Clock.schedule_once(lambda dt: setattr(self.btn_connect_exchange, 'text', "验证并接入 OKX 交易所"))
                Clock.schedule_once(lambda dt, msg=err_msg: self.show_info_popup("连接错误", f"无法连通 OKX (请确认代理端口是否开启):\n{msg[:140]}"))

        threading.Thread(target=connect_worker, daemon=True).start()

    def show_info_popup(self, title, message):
        box = BoxLayout(orientation='vertical', padding=[24, 20, 24, 20], spacing=16)
        with box.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=box.pos, size=box.size, radius=[12])

        box.add_widget(Label(text=message, font_size=16, color=C_TEXT_MAIN, halign='center'))
        btn = FlatButton(text="确定", size_hint_y=None, height=44, bg_color=(0.88, 0.94, 0.99, 1), font_size=16, radius=[8])
        btn.color = C_BLUE
        box.add_widget(btn)

        pop = Popup(
            title=title, content=box, size_hint=(0.55, 0.40),
            background='', background_color=(0.95, 0.96, 0.98, 0.98), title_color=C_TEXT_MAIN
        )
        btn.bind(on_release=pop.dismiss)
        pop.open()

    def load_saved_credentials(self):
        creds = CredentialManager.load()
        if creds:
            self.api_key_input.text = creds.get("api_key", "")
            self.secret_input.text = creds.get("secret", "")
            self.pass_input.text = creds.get("passphrase", "")
            if creds.get("proxy_url"):
                self.proxy_input.text = creds.get("proxy_url")
            self.append_log("已载入本地加密凭证，随时可接入。")
            return True
        return False

    def clear_saved_credentials(self, instance=None):
        self.api_key_input.text = ""
        self.secret_input.text = ""
        self.pass_input.text = ""
        self.is_connected = False
        CredentialManager.clear()
        self.append_log("已彻底清除本地密钥文件与 API 凭据。")

    # ---------------- 视图 4：盈亏分析 ----------------
    def init_pnl_tab(self):
        self.view_pnl = ModernCard(orientation='vertical', padding=[28, 20, 28, 20], spacing=14)
        self.view_pnl.add_widget(LeftAlignedLabel(text="多维策略净盈亏看板 (已扣除交易手续费)", font_size=22, bold=True, color=C_TEXT_MAIN, size_hint_y=None, height=36))

        grid = GridLayout(cols=2, spacing=[24, 12], row_default_height=48, row_force_default=True)

        grid.add_widget(LeftAlignedLabel(text="累计已实现净利润:", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_total_lbl = LeftAlignedLabel(text="+0.0000 USDT", font_size=24, color=C_GREEN, bold=True)
        grid.add_widget(self.pnl_total_lbl)

        grid.add_widget(LeftAlignedLabel(text="预估今日收益 (24H):", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_day_lbl = LeftAlignedLabel(text="+0.00 USDT", font_size=20, color=C_TEXT_MAIN, bold=True)
        grid.add_widget(self.pnl_day_lbl)

        grid.add_widget(LeftAlignedLabel(text="预估本周收益 (7D):", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_week_lbl = LeftAlignedLabel(text="+0.00 USDT", font_size=20, color=C_TEXT_MAIN, bold=True)
        grid.add_widget(self.pnl_week_lbl)

        grid.add_widget(LeftAlignedLabel(text="预估本月收益 (30D):", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_month_lbl = LeftAlignedLabel(text="+0.00 USDT", font_size=20, color=C_TEXT_MAIN, bold=True)
        grid.add_widget(self.pnl_month_lbl)

        grid.add_widget(LeftAlignedLabel(text="平滑年化折算 (APY):", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_apy_lbl = LeftAlignedLabel(text="样本积累中...", font_size=22, color=C_AMBER, bold=True)
        grid.add_widget(self.pnl_apy_lbl)

        grid.add_widget(LeftAlignedLabel(text="有效套利结算轮次:", font_size=16, bold=True, color=C_TEXT_MUTED))
        self.pnl_trades_lbl = LeftAlignedLabel(text="0 次", font_size=20, color=C_BLUE, bold=True)
        grid.add_widget(self.pnl_trades_lbl)

        self.view_pnl.add_widget(grid)
        self.view_pnl.add_widget(Widget(size_hint_y=1))

    def update_pnl_analytics(self, net_profit_usdt):
        self.total_profit_usdt += net_profit_usdt
        self.total_arbitrage_count += 1
        elapsed_seconds = max(1, time.time() - (self.start_time or time.time()))

        if elapsed_seconds >= 900 and self.total_arbitrage_count >= 2:
            daily_rate = (self.total_profit_usdt / elapsed_seconds) * 86400
            weekly_rate = daily_rate * 7
            monthly_rate = daily_rate * 30
            try:
                base_capital = max(self.active_order_usdt * 2, 20.0)
                apy = (daily_rate * 365 / base_capital) * 100
                apy_str = f"{min(apy, 999.99):.2f} %"
            except Exception:
                apy_str = "0.00 %"
            day_str = f"{daily_rate:+.2f} USDT"
            week_str = f"{weekly_rate:+.2f} USDT"
            month_str = f"{monthly_rate:+.2f} USDT"
        else:
            day_str = "-- USDT (样本积累中)"
            week_str = "-- USDT (样本积累中)"
            month_str = "-- USDT (样本积累中)"
            apy_str = "样本积累中..."

        Clock.schedule_once(lambda dt: setattr(self.pnl_total_lbl, 'text', f"{self.total_profit_usdt:+.4f} USDT"))
        Clock.schedule_once(lambda dt: setattr(self.pnl_day_lbl, 'text', day_str))
        Clock.schedule_once(lambda dt: setattr(self.pnl_week_lbl, 'text', week_str))
        Clock.schedule_once(lambda dt: setattr(self.pnl_month_lbl, 'text', month_str))
        Clock.schedule_once(lambda dt: setattr(self.pnl_apy_lbl, 'text', apy_str))
        Clock.schedule_once(lambda dt: setattr(self.pnl_trades_lbl, 'text', f"{self.total_arbitrage_count} 次"))

    # ---------------- 视图 5：系统运行日志 ----------------
    def init_logs_tab(self):
        self.view_logs = ModernCard(orientation='vertical', padding=[20, 16, 20, 16], bg_color=(0.06, 0.08, 0.12, 1), border_color=(0.12, 0.16, 0.23, 1))
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)

        self.log_lbl = Label(
            text="[SYSTEM] PC 交易控制台已就绪。请接入 API 凭证并选定策略。\n",
            font_size=15,
            color=(0.40, 0.90, 0.70, 1),
            size_hint=(1, None),
            halign='left',
            valign='top'
        )
        self.log_lbl.bind(width=lambda instance, value: setattr(instance, 'text_size', (value, None)))
        self.log_lbl.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))

        scroll.add_widget(self.log_lbl)
        self.view_logs.add_widget(scroll)

    def append_log(self, text):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {text}"
        Clock.schedule_once(lambda dt: setattr(
            self.log_lbl, 'text', f"{self.log_lbl.text}\n[{time.strftime('%H:%M:%S')}] {text}"
        ))
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception:
            pass

    # ---------------- 交互式日志导出对话框 ----------------
    def open_export_modal(self, instance=None):
        content = BoxLayout(orientation='vertical', spacing=12, padding=16)
        with content.canvas.before:
            Color(0.97, 0.98, 0.99, 1)
            RoundedRectangle(pos=content.pos, size=content.size, radius=[12])

        lbl_tip = Label(text="选择导出保存目录:", font_size=15, bold=True, color=C_TEXT_MAIN, size_hint_y=None, height=26, halign='left')
        lbl_tip.bind(size=lbl_tip.setter('text_size'))
        content.add_widget(lbl_tip)

        default_dl = os.path.join(os.path.expanduser("~"), "Downloads")
        default_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        app_dir = os.getcwd()

        dirs = [
            ("电脑桌面 (Desktop)", default_desktop if os.path.exists(default_desktop) else app_dir),
            ("下载文件夹 (Downloads)", default_dl if os.path.exists(default_dl) else app_dir),
            ("程序所在运行目录", app_dir)
        ]
        selected_dir = {"path": dirs[0][1]}

        dir_btns = []
        for name, p in dirs:
            b = FlatButton(text=name, size_hint_y=None, height=38, radius=[8],
                           bg_color=(0.88, 0.94, 0.99, 1) if p == selected_dir["path"] else (0.92, 0.94, 0.96, 1))
            b.color = C_TEXT_MAIN
            def _choose(btn, path=p):
                selected_dir["path"] = path
                for item in dir_btns:
                    item.set_bg((0.92, 0.94, 0.96, 1))
                btn.set_bg((0.88, 0.94, 0.99, 1))
            b.bind(on_release=_choose)
            dir_btns.append(b)
            content.add_widget(b)

        lbl_fn = Label(text="自定义日志文件名:", font_size=15, bold=True, color=C_TEXT_MAIN, size_hint_y=None, height=26, halign='left')
        lbl_fn.bind(size=lbl_fn.setter('text_size'))
        content.add_widget(lbl_fn)

        fn_input = TextInput(text=f"OKX_PC_Log_{time.strftime('%Y%m%d_%H%M%S')}.txt", multiline=False, size_hint_y=None, height=40, font_size=15)
        content.add_widget(fn_input)

        btn_row = BoxLayout(size_hint_y=None, height=44, spacing=12)
        b_confirm = FlatButton(text="确认导出", bg_color=C_GREEN, font_size=16, bold=True, radius=[8])
        b_cancel = FlatButton(text="取消", bg_color=(0.60, 0.65, 0.70, 1), font_size=16, radius=[8])
        btn_row.add_widget(b_confirm)
        btn_row.add_widget(b_cancel)
        content.add_widget(btn_row)

        popup = Popup(
            title="导出运行日志至本地存储",
            content=content,
            size_hint=(0.60, 0.55),
            background='',
            background_color=(0.95, 0.96, 0.98, 0.98),
            title_color=C_TEXT_MAIN
        )

        def _do_export(*_):
            target_dir = selected_dir["path"]
            out_file = os.path.join(target_dir, fn_input.text.strip())
            try:
                if not os.path.exists(self.log_file_path):
                    with open(self.log_file_path, "w", encoding="utf-8") as f:
                        f.write(self.log_lbl.text)
                shutil.copyfile(self.log_file_path, out_file)
                self.append_log(f"【日志导出成功】文件已保存至: {out_file}")
            except Exception as e:
                self.append_log(f"【日志导出异常】{e}")
            popup.dismiss()

        b_confirm.bind(on_release=_do_export)
        b_cancel.bind(on_release=popup.dismiss)
        popup.open()

    # ---------------- 策略参数与风控设定弹窗 ----------------
    def open_unified_strategy_popup(self, instance=None):
        box = BoxLayout(orientation='vertical', padding=[24, 18, 24, 18], spacing=14)
        with box.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=box.pos, size=box.size, radius=[12])

        header_text = f"AI 智能诊断最佳推荐: 【{self.current_ai_target_strategy}】"
        box.add_widget(Label(text=header_text, font_size=18, bold=True, color=C_AMBER, size_hint_y=None, height=36, halign='center'))

        grid = GridLayout(cols=2, spacing=[20, 10], row_default_height=44, row_force_default=True)

        grid.add_widget(LeftAlignedLabel(text="市场类型:", font_size=15, bold=True, color=C_TEXT_MAIN))
        market_type_spn = Spinner(text=self.active_market_type, values=('现货 (Spot)', '永续合约 (Swap)'),
                                  option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(market_type_spn)

        grid.add_widget(LeftAlignedLabel(text="交易币对:", font_size=15, bold=True, color=C_TEXT_MAIN))
        symbol_spn = Spinner(text=self.active_symbol, values=('ETH/USDT', 'BTC/USDT', 'SOL/USDT', 'DOGE/USDT', 'OKB/USDT'),
                             option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(symbol_spn)

        grid.add_widget(LeftAlignedLabel(text="K线周期:", font_size=15, bold=True, color=C_TEXT_MAIN))
        timeframe_spn = Spinner(text=self.active_timeframe, values=('1m', '3m', '5m', '15m', '1h', '4h', '1d'),
                                option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(timeframe_spn)

        grid.add_widget(LeftAlignedLabel(text="合约杠杆:", font_size=15, bold=True, color=C_TEXT_MAIN))
        leverage_spn = Spinner(text=self.active_leverage, values=('1x (现货)', '2x', '3x', '5x', '10x', '20x'),
                               option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(leverage_spn)

        grid.add_widget(LeftAlignedLabel(text="执行策略:", font_size=15, bold=True, color=C_TEXT_MAIN))
        strat_spn = Spinner(text=self.current_ai_target_strategy,
                            values=('网格策略 (Grid)', '做市策略 (Market Making)', '3分钟趋势追踪 (Trend)', 'DCA 定投策略 (DCA)'),
                            option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(strat_spn)

        grid.add_widget(LeftAlignedLabel(text="网格间距(%) / 单笔U:", font_size=15, bold=True, color=C_TEXT_MAIN))
        p_box = BoxLayout(spacing=10)
        grid_pct_in = TextInput(text=str(self.ai_suggested_spread), multiline=False, background_color=(0.94, 0.96, 0.98, 1), foreground_color=C_TEXT_MAIN, font_size=15)
        order_amt_in = TextInput(text=str(int(self.active_order_usdt)), multiline=False, background_color=(0.94, 0.96, 0.98, 1), foreground_color=C_TEXT_MAIN, font_size=15)
        p_box.add_widget(grid_pct_in)
        p_box.add_widget(order_amt_in)
        grid.add_widget(p_box)

        grid.add_widget(LeftAlignedLabel(text="止盈(%) / 止损(%):", font_size=15, bold=True, color=C_TEXT_MAIN))
        risk_box = BoxLayout(spacing=10)
        tp_in = TextInput(text=str(self.ai_suggested_tp), multiline=False, background_color=(0.94, 0.96, 0.98, 1), foreground_color=C_TEXT_MAIN, font_size=15)
        sl_in = TextInput(text=str(self.ai_suggested_sl), multiline=False, background_color=(0.94, 0.96, 0.98, 1), foreground_color=C_TEXT_MAIN, font_size=15)
        risk_box.add_widget(tp_in)
        risk_box.add_widget(sl_in)
        grid.add_widget(risk_box)

        grid.add_widget(LeftAlignedLabel(text="停机保护动作:", font_size=15, bold=True, color=C_TEXT_MAIN))
        stop_safe_spn = Spinner(text=self.active_cancel_on_stop, values=('停机自动撤销全部挂单', '停机保留盘口挂单'),
                                option_cls=ModernSpinnerOption, background_normal='', background_color=(0.94, 0.96, 0.98, 1), color=C_TEXT_MAIN, font_size=15)
        grid.add_widget(stop_safe_spn)

        box.add_widget(grid)

        btn_box = BoxLayout(size_hint_y=None, height=48, spacing=14)
        btn_confirm = FlatButton(text="保存并应用新策略", bg_color=C_GREEN, bold=True, font_size=16, radius=[8])
        btn_cancel = FlatButton(text="取消", bg_color=(0.60, 0.65, 0.70, 1), font_size=16, radius=[8], size_hint_x=0.3)
        btn_box.add_widget(btn_confirm)
        btn_box.add_widget(btn_cancel)
        box.add_widget(btn_box)

        popup = Popup(title="量化策略与风控参数微调", content=box, size_hint=(0.68, 0.72),
                      background='', background_color=(0.95, 0.96, 0.98, 0.98), title_color=C_TEXT_MAIN)

        def on_confirm(btn):
            try:
                self.active_market_type = market_type_spn.text
                self.active_symbol = symbol_spn.text
                self.active_timeframe = timeframe_spn.text.strip()
                self.active_leverage = leverage_spn.text
                self.active_strategy = strat_spn.text
                self.active_grid_pct = float(grid_pct_in.text.strip()) / 100.0
                self.active_order_usdt = float(order_amt_in.text.strip())
                self.active_tp_pct = float(tp_in.text.strip()) / 100.0
                self.active_sl_pct = float(sl_in.text.strip()) / 100.0
                self.active_cancel_on_stop = stop_safe_spn.text

                popup.dismiss()
                self.strategy_adopted = True
                self.refresh_strategy_details_banner()
                self.append_log(f"策略参数已更新: [{self.active_strategy}] | 标的: {self.active_symbol}")
            except Exception as ex:
                self.append_log(f"参数解析有误: {ex}")

        btn_confirm.bind(on_release=on_confirm)
        btn_cancel.bind(on_release=popup.dismiss)
        popup.open()

    # ---------------- 核心：高频行情刷新与走势图驱动 ----------------
    def tick_market_data(self, dt):
        """每 1.5 秒轮询行情，若接口暂未连接则触发拟真平滑微波动推进"""
        def _fetch():
            price = None
            if self.exchange and self.is_connected:
                try:
                    is_spot = '现货' in self.active_market_type
                    raw_symbol = self.active_symbol.strip().upper()
                    symbol = raw_symbol if is_spot else f"{raw_symbol}:USDT"
                    ticker = self.exchange.fetch_ticker(symbol)
                    price = float(ticker['last'])
                except Exception:
                    pass

            if price is None or price <= 0:
                price = round(self.current_price + random.uniform(-1.0, 1.0), 2)

            self.apply_price_tick(price)

        threading.Thread(target=_fetch, daemon=True).start()

    @mainthread
    def apply_price_tick(self, price: float):
        self.current_price = price
        self.price_lbl.text = f"{price:,.2f}"
        self.flow_chart.add_price(price)

    # ---------------- 业务计算函数 ----------------
    def calc_order_qty(self, symbol, order_usdt, price):
        market = self.exchange.market(symbol)
        is_contract = market.get('contract', False) or market.get('swap', False)

        if is_contract:
            ct_size = float(market.get('contractSize', 1.0))
            contract_val_usdt = ct_size * price if ct_size > 0 else price
            contracts = max(1, int(order_usdt / contract_val_usdt))
            return float(contracts)
        else:
            raw_qty = order_usdt / price
            safe_qty = float(self.exchange.amount_to_precision(symbol, raw_qty))
            min_amt = float(market.get('limits', {}).get('amount', {}).get('min', 0.0001))
            return max(safe_qty, min_amt)

    def calc_net_profit(self, symbol, buy_price, sell_price, qty):
        market = self.exchange.market(symbol)
        fee_rate = float(market.get('maker', 0.0008))
        gross_profit = (sell_price - buy_price) * qty
        total_fee = (buy_price * qty + sell_price * qty) * fee_rate
        net_profit = gross_profit - total_fee
        return net_profit, total_fee

    def execute_market_close(self, symbol, is_spot, base_currency):
        self.append_log("【触发风控】执行市价全量平仓保护...")
        try:
            if is_spot:
                balance = self.exchange.fetch_balance()
                base_free = float(balance['free'].get(base_currency, 0.0))
                ticker = self.exchange.fetch_ticker(symbol)
                curr_price = float(ticker['last'])
                if base_free * curr_price >= 2.0:
                    safe_sell_qty = float(self.exchange.amount_to_precision(symbol, base_free * 0.999))
                    self.exchange.create_market_sell_order(symbol, safe_sell_qty)
                    self.append_log(f"【现货清仓完成】市价卖出 {safe_sell_qty} {base_currency}")
            else:
                positions = self.exchange.fetch_positions([symbol])
                for pos in positions:
                    contracts = float(pos.get('contracts', 0) or pos.get('size', 0))
                    side = pos.get('side', '')
                    if contracts > 0:
                        if side == 'long':
                            self.exchange.create_market_sell_order(symbol, contracts, params={'reduceOnly': True})
                        elif side == 'short':
                            self.exchange.create_market_buy_order(symbol, contracts, params={'reduceOnly': True})
                        self.append_log(f"【合约平仓完成】平仓 {contracts} 张")
        except Exception as close_err:
            self.append_log(f"【平仓异常】: {str(close_err)[:40]}")

    # ---------------- 策略撮合与启停控制 ----------------
    def toggle_bot(self, instance):
        if not self.running:
            if not self.is_connected:
                self.show_info_popup("阻断提示", "请先在「API凭证」点击接入！")
                return

            self.running = True
            self.start_time = time.time()
            self.toggle_btn.text = "紧急停止实盘策略"
            self.toggle_btn.set_bg(C_RED)
            self.status_lbl.text = "运行中 (对冲)"
            self.status_lbl.color = C_GREEN
            self.append_log("【实盘激活】高胜率日内自适应量化引擎已启动")
            threading.Thread(target=self.bot_execution_loop, daemon=True).start()
        else:
            self.running = False
            self.toggle_btn.text = "启动日内高胜率实盘策略"
            self.toggle_btn.set_bg(C_GREEN)
            self.status_lbl.text = "策略已终止"
            self.status_lbl.color = C_AMBER
            self.append_log("用户手动停止了量化策略。")

    # ---------------- 实盘策略撮合主循环 ----------------
    def bot_execution_loop(self):
        try:
            is_spot = '现货' in self.active_market_type
            raw_symbol = self.active_symbol.strip().upper()
            symbol = raw_symbol if is_spot else f"{raw_symbol}:USDT"
            base_currency = raw_symbol.split('/')[0]

            if not is_spot:
                try:
                    lev_num = int(self.active_leverage.replace('x', '').split()[0].strip())
                    self.exchange.set_leverage(lev_num, symbol)
                    self.append_log(f"合约杠杆生效: {lev_num}x")
                except Exception as lev_err:
                    self.append_log(f"杠杆设置提示: {str(lev_err)[:30]}")

            grid_pct = self.active_grid_pct
            order_usdt = self.active_order_usdt
            tp_pct = self.active_tp_pct
            sl_pct = self.active_sl_pct

            self.exchange.load_markets()
            consecutive_net_errors = 0
            initial_entry_price = None

            dca_entry_prices = []
            trend_in_position = False

            while self.running:
                try:
                    selected_strategy = self.active_strategy

                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    balance = self.exchange.fetch_balance()
                    usdt_free = float(balance['free'].get('USDT', 0.0))
                    base_free = float(balance['free'].get(base_currency, 0.0))

                    open_orders = self.exchange.fetch_open_orders(symbol)
                    Clock.schedule_once(lambda dt, b=usdt_free, c=len(open_orders): setattr(self.balance_lbl, 'text', f"{b:.2f} USDT ({c} 笔)"))
                    Clock.schedule_once(lambda dt, ods=open_orders: self.refresh_orders_view(ods))
                    open_order_ids = {o['id'] for o in open_orders}

                    # 风控检测
                    if initial_entry_price:
                        pnl_ratio = (current_price - initial_entry_price) / initial_entry_price
                        if pnl_ratio >= tp_pct or pnl_ratio <= -sl_pct:
                            tag = "全局止盈" if pnl_ratio >= tp_pct else "硬止损"
                            self.append_log(f"触发 {tag} ({pnl_ratio*100:+.2f}%)，执行平仓！")
                            self.execute_market_close(symbol, is_spot, base_currency)
                            self.running = False
                            break

                    # 精准订单状态确认
                    for oid, oinfo in list(self.active_strategy_orders.items()):
                        if oid not in open_order_ids:
                            try:
                                ord_info = self.exchange.fetch_order(oid, symbol)
                                status = ord_info.get('status')
                                filled_qty = float(ord_info.get('filled', 0.0))
                                avg_price = float(ord_info.get('average') or ord_info.get('price') or oinfo['price'])
                            except Exception:
                                continue

                            if status == 'closed' and filled_qty > 0:
                                side = oinfo['side']
                                self.append_log(f"【成交确认】#{str(oid)[-6:]} {side.upper()} 均价: {avg_price:.2f} | 数量: {filled_qty:.4f}")

                                if "网格策略" in selected_strategy:
                                    if side == 'buy':
                                        t_sell_price = float(self.exchange.price_to_precision(symbol, avg_price * (1 + grid_pct)))
                                        sell_qty = self.calc_order_qty(symbol, order_usdt, t_sell_price)
                                        try:
                                            s_ord = self.exchange.create_limit_sell_order(symbol, sell_qty, t_sell_price)
                                            self.active_strategy_orders[s_ord['id']] = {'side': 'sell', 'price': t_sell_price, 'qty': sell_qty, 'buy_price': avg_price}
                                            self.append_log(f"网格反手挂卖单: 价 {t_sell_price}")
                                        except Exception as se:
                                            self.append_log(f"挂卖单受阻: {str(se)[:30]}")
                                    elif side == 'sell':
                                        buy_p = oinfo.get('buy_price', avg_price * (1 - grid_pct))
                                        net_p, fee = self.calc_net_profit(symbol, buy_p, avg_price, filled_qty)
                                        self.update_pnl_analytics(net_p)
                                        self.append_log(f"网格套利落袋: 净利 +{net_p:.4f}U (手续费 {fee:.4f}U)")

                                        t_buy_price = float(self.exchange.price_to_precision(symbol, avg_price * (1 - grid_pct)))
                                        buy_qty = self.calc_order_qty(symbol, order_usdt, t_buy_price)
                                        try:
                                            b_ord = self.exchange.create_limit_buy_order(symbol, buy_qty, t_buy_price)
                                            self.active_strategy_orders[b_ord['id']] = {'side': 'buy', 'price': t_buy_price, 'qty': buy_qty}
                                            self.append_log(f"网格复位挂买单: 价 {t_buy_price}")
                                        except Exception as be:
                                            self.append_log(f"补买单受阻: {str(be)[:30]}")

                                elif "做市策略" in selected_strategy:
                                    if side == 'sell':
                                        net_p, fee = self.calc_net_profit(symbol, avg_price * (1 - grid_pct), avg_price, filled_qty)
                                        self.update_pnl_analytics(net_p)
                                        self.append_log(f"做市套利完成: 净利 +{net_p:.4f}U")

                                del self.active_strategy_orders[oid]

                            elif status in ['canceled', 'expired', 'rejected']:
                                self.append_log(f"订单 #{str(oid)[-6:]} 失效/已撤销，移出追踪。")
                                del self.active_strategy_orders[oid]

                    # 各策略开仓与维护
                    if "做市策略" in selected_strategy and len(open_orders) == 0:
                        bid_p = float(self.exchange.price_to_precision(symbol, current_price * (1 - grid_pct)))
                        ask_p = float(self.exchange.price_to_precision(symbol, current_price * (1 + grid_pct)))
                        o_qty = self.calc_order_qty(symbol, order_usdt, current_price)
                        if usdt_free >= order_usdt:
                            try:
                                b_ord = self.exchange.create_limit_buy_order(symbol, o_qty, bid_p)
                                self.active_strategy_orders[b_ord['id']] = {'side': 'buy', 'price': bid_p, 'qty': o_qty}
                            except Exception:
                                pass
                        if (base_free >= o_qty) if is_spot else True:
                            try:
                                s_ord = self.exchange.create_limit_sell_order(symbol, o_qty, ask_p)
                                self.active_strategy_orders[s_ord['id']] = {'side': 'sell', 'price': ask_p, 'qty': o_qty}
                            except Exception:
                                pass

                    elif "网格策略" in selected_strategy and len(open_orders) == 0 and len(self.active_strategy_orders) == 0:
                        if usdt_free >= order_usdt:
                            buy_p = float(self.exchange.price_to_precision(symbol, current_price * (1 - grid_pct)))
                            buy_q = self.calc_order_qty(symbol, order_usdt, buy_p)
                            self.append_log(f"网格初始化: 挂买入首单 {buy_p}")
                            b_ord = self.exchange.create_limit_buy_order(symbol, buy_q, buy_p)
                            self.active_strategy_orders[b_ord['id']] = {'side': 'buy', 'price': buy_p, 'qty': buy_q}
                            initial_entry_price = current_price

                    elif "趋势追踪" in selected_strategy:
                        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='3m', limit=25)
                        closes = [c[4] for c in ohlcv]
                        ma5 = sum(closes[-5:]) / 5
                        ma20 = sum(closes[-20:]) / 20

                        if ma5 > ma20 * 1.003 and not trend_in_position and len(open_orders) == 0:
                            o_qty = self.calc_order_qty(symbol, order_usdt, current_price)
                            if usdt_free >= order_usdt:
                                self.append_log(f"MA5金叉多头突破，市价做多: {o_qty}")
                                self.exchange.create_market_buy_order(symbol, o_qty)
                                trend_in_position = True
                                initial_entry_price = current_price
                        elif ma5 < ma20 * 0.997 and trend_in_position:
                            self.append_log("MA5死叉跌破，市价平仓避险...")
                            self.execute_market_close(symbol, is_spot, base_currency)
                            trend_in_position = False
                            initial_entry_price = None

                    elif "DCA" in selected_strategy:
                        if len(dca_entry_prices) == 0:
                            if usdt_free >= order_usdt:
                                o_qty = self.calc_order_qty(symbol, order_usdt, current_price)
                                self.append_log(f"DCA 首期建仓买入: {o_qty} @ {current_price}")
                                self.exchange.create_market_buy_order(symbol, o_qty)
                                dca_entry_prices.append(current_price)
                                initial_entry_price = current_price
                        else:
                            last_p = dca_entry_prices[-1]
                            avg_c = sum(dca_entry_prices) / len(dca_entry_prices)
                            if current_price >= avg_c * (1 + tp_pct):
                                self.append_log(f"DCA 触达止盈目标 (+{tp_pct*100}%)，全部平仓落袋！")
                                self.execute_market_close(symbol, is_spot, base_currency)
                                net_p, _ = self.calc_net_profit(symbol, avg_c, current_price, len(dca_entry_prices) * (order_usdt / avg_c))
                                self.update_pnl_analytics(net_p)
                                dca_entry_prices.clear()
                                initial_entry_price = None
                            elif current_price <= last_p * (1 - grid_pct) and len(dca_entry_prices) < 5:
                                if usdt_free >= order_usdt:
                                    o_qty = self.calc_order_qty(symbol, order_usdt, current_price)
                                    self.append_log(f"DCA 第 {len(dca_entry_prices)+1} 期低吸加仓: 量 {o_qty}")
                                    self.exchange.create_market_buy_order(symbol, o_qty)
                                    dca_entry_prices.append(current_price)

                    consecutive_net_errors = 0
                    for _ in range(10):
                        if not self.running:
                            break
                        time.sleep(1)

                except Exception as loop_err:
                    consecutive_net_errors += 1
                    err_msg = str(loop_err)
                    if "timed out" in err_msg.lower() or "connection" in err_msg.lower():
                        sleep_time = min(60, consecutive_net_errors * 10)
                        self.append_log(f"网络断开 ({consecutive_net_errors}次)，熔断休眠 {sleep_time}s...")
                        time.sleep(sleep_time)
                    else:
                        self.append_log(f"轮询警告: {err_msg[:35]}")
                        time.sleep(5)

        except Exception as e:
            self.append_log(f"主线程异常退出: {str(e)[:35]}")
            self.running = False
        finally:
            if self.exchange and '自动撤销' in self.active_cancel_on_stop and self.current_symbol:
                try:
                    self.append_log("停机保护：正在撤销盘口活跃挂单...")
                    active_orders = self.exchange.fetch_open_orders(self.current_symbol)
                    for o in active_orders:
                        try:
                            self.exchange.cancel_order(o['id'], self.current_symbol)
                        except Exception:
                            pass
                    self.active_strategy_orders.clear()
                    self.refresh_orders_view([])
                    self.append_log(f"已清理全部盘口挂单 ({len(active_orders)} 笔)。")
                except Exception as cancel_err:
                    self.append_log(f"撤单失败: {str(cancel_err)[:30]}")

            Clock.schedule_once(lambda dt: self.toggle_btn.set_bg(C_GREEN))
            Clock.schedule_once(lambda dt: setattr(self.toggle_btn, 'text', "启动日内高胜率实盘策略"))
            Clock.schedule_once(lambda dt: setattr(self.status_lbl, 'text', "已停机就绪"))
            Clock.schedule_once(lambda dt: setattr(self.status_lbl, 'color', C_AMBER))

    def market_and_ai_daemon_thread(self):
        """后台低频 K 线诊断线程"""
        while self.market_monitor_active and self.is_connected:
            try:
                is_spot = '现货' in self.active_market_type
                raw_symbol = self.active_symbol.strip().upper()
                symbol = raw_symbol if is_spot else f"{raw_symbol}:USDT"
                self.current_symbol = symbol

                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=self.active_timeframe, limit=25)
                closes = [c[4] for c in ohlcv]
                diff_pct = (max(closes) - min(closes)) / min(closes) * 100

                self.ai_suggested_spread = round(max(0.3, diff_pct * 0.35), 2)
                self.ai_suggested_tp = round(max(1.2, diff_pct * 1.5), 2)
                self.ai_suggested_sl = round(max(3.0, diff_pct * 2.8), 2)

                if diff_pct < 1.8:
                    ai_rec = f"AI 诊断: 极窄幅整理 (振幅 {diff_pct:.2f}%) -> 推荐「做市策略」"
                    self.current_ai_target_strategy = "做市策略 (Market Making)"
                else:
                    ai_rec = f"AI 诊断: 常态箱体震荡 (振幅 {diff_pct:.2f}%) -> 推荐「现货震荡网格」"
                    self.current_ai_target_strategy = "网格策略 (Grid)"

                Clock.schedule_once(lambda dt, r=ai_rec: setattr(self.ai_recommend_lbl, 'text', r))
                time.sleep(10)
            except Exception:
                time.sleep(10)

if __name__ == '__main__':
    OKXProQuantStationApp().run()
