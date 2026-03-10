# ⚠️ 개인정보 안내
# 이 스크립트는 게임 로그에서 인증 토큰을 읽어
# 공식 서버(ef-webview.gryphline.com)에만 전송합니다.
# 토큰은 외부 서버로 전송되지 않으며, 로컬에 저장되지 않습니다.

import os, re, csv, time, platform, json, math, threading
import urllib.request
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.error import URLError, HTTPError
from pathlib import Path
from collections import defaultdict
import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk

# ── 테마 설정 ──────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 엔드필드 컬러 팔레트 ──────────────────────────────
BG_DEEP    = "#0d1117"
BG_CARD    = "#161b22"
BG_PANEL   = "#1c2333"
ACCENT     = "#f5a623"   # 황금 오렌지
ACCENT2    = "#58a6ff"   # 스틸 블루
SUCCESS    = "#3fb950"
WARNING    = "#d29922"
DANGER     = "#f85149"
TEXT_PRI   = "#e6edf3"
TEXT_SEC   = "#8b949e"
BORDER     = "#30363d"

STAR6_COLOR  = "#f5a623"
STAR5_COLOR  = "#a371f7"
STAR4_COLOR  = "#58a6ff"

# ── 로직 함수 (기존 코드 기반) ────────────────────────

def calculate_binom_cdf(k, n, p):
    cdf = 0.0
    for i in range(k + 1):
        cdf += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return cdf

def find_best_log_path():
    system = platform.system()
    target_name = "HGWebview.log"
    candidates = []
    if system == "Windows":
        appdata = os.environ.get('USERPROFILE', '')
        win_path = os.path.join(appdata, 'AppData', 'LocalLow', 'Gryphline', 'Endfield', 'sdklogs', target_name)
        if os.path.exists(win_path):
            candidates.append(win_path)
    elif system == "Linux":
        home = str(Path.home())
        search_dirs = [
            os.path.join(home, ".local", "share", "Steam", "steamapps", "compatdata"),
            os.path.join(home, ".steam", "steam", "steamapps", "compatdata"),
            os.path.join(home, ".wine", "drive_c")
        ]
        for s_dir in search_dirs:
            if os.path.exists(s_dir):
                for root, dirs, files in os.walk(s_dir):
                    if target_name in files:
                        candidates.append(os.path.join(root, target_name))
    if not candidates:
        return None
    candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return candidates[0]

def extract_gacha_url_from_log():
    log_path = find_best_log_path()
    if not log_path:
        return None, "❌ 로그 파일을 찾을 수 없습니다."
    url_pattern = re.compile(r"https://[^\s]+u8_token=[^\s]+")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in reversed(f.readlines()):
                match = url_pattern.search(line)
                if match and "/page/giftcode" not in match.group(0):
                    return match.group(0), f"✅ 로그 발견: {log_path}"
    except Exception:
        pass
    return None, "❌ URL을 찾을 수 없습니다. 게임 내 가챠 기록 창을 열어주세요."

def fetch_all_records(url, progress_cb, status_cb, csv_filename="endfield_gacha_history_all.csv"):
    if not url:
        return False, "URL 없음"
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    token = query_params.get('u8_token', query_params.get('token', [None]))[0]
    if not token:
        return False, "토큰을 찾을 수 없습니다."

    gacha_pools = [
        {"name": "기초 헤드헌팅",       "api": "https://ef-webview.gryphline.com/api/record/char",   "pool_type": "E_CharacterGachaPoolType_Standard"},
        {"name": "특별 허가 헤드헌팅",   "api": "https://ef-webview.gryphline.com/api/record/char",   "pool_type": "E_CharacterGachaPoolType_Special"},
        {"name": "여정의 시작 헤드헌팅", "api": "https://ef-webview.gryphline.com/api/record/char",   "pool_type": "E_CharacterGachaPoolType_Beginner"},
        {"name": "표준 무기고",          "api": "https://ef-webview.gryphline.com/api/record/weapon", "pool_type": "E_WeaponGachaPoolType_Standard"},
        {"name": "한정 무기고",          "api": "https://ef-webview.gryphline.com/api/record/weapon", "pool_type": "E_WeaponGachaPoolType_Special"},
    ]

    all_records = []
    total_pools = len(gacha_pools)

    for pool_idx, pool in enumerate(gacha_pools):
        status_cb(f"📡 [{pool['name']}] 수집 중...")
        has_more, seq_id, pool_count = True, "", 0
        while has_more:
            server_id = query_params.get('server_id', ['2'])[0]
            params = {"server_id": server_id, "pool_type": pool["pool_type"], "lang": "ko-kr", "token": token}
            if seq_id:
                params["seq_id"] = seq_id
            full_url = f"{pool['api']}?{urlencode(params)}"
            try:
                req = urllib.request.Request(full_url)
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                code = data.get('code')
                if code != 0:
                    return False, f"서버 오류 (code: {code})"
                records = data.get('data', {}).get('list', [])
                if not records:
                    break
                all_records.extend(records)
                pool_count += len(records)
                progress_cb((pool_idx + pool_count / max(pool_count, 1) * 0.8) / total_pools * 100)
                has_more = data.get('data', {}).get('hasMore', False)
                if has_more:
                    seq_id = records[-1]['seqId']
                    time.sleep(0.1)
            except (HTTPError, URLError) as e:
                return False, f"네트워크 오류: {e}"
        progress_cb((pool_idx + 1) / total_pools * 100)

    if not all_records:
        return False, "수집된 데이터가 없습니다."

    # 중복 제거
    seen, deduped = set(), []
    for r in all_records:
        key = ('weap' if r.get('weaponId') else 'char', r.get('seqId'))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    all_records = deduped

    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
        all_keys = []
        for rec in all_records:
            for k in rec.keys():
                if k not in all_keys:
                    all_keys.append(k)
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        for row in all_records:
            writer.writerow(row)

    return True, f"✅ 총 {len(all_records)}개 저장 완료"

def analyze_data(csv_filename="endfield_gacha_history_all.csv"):
    try:
        with open(csv_filename, 'r', encoding='utf-8-sig') as f:
            rows = sorted(list(csv.DictReader(f)),
                          key=lambda x: (int(x.get('gachaTs', 0)), int(x.get('seqId', 0))))
    except FileNotFoundError:
        return None

    char_pulls, weap_pulls = [], []
    for row in rows:
        rarity  = int(row['rarity'])
        name    = row.get('charName') if row.get('charName') else row.get('weaponName', '이름 없음')
        pool    = row.get('poolName', '')
        is_free = row.get('isFree') == 'True'
        entry   = {'name': name, 'rarity': rarity, 'pool': pool, 'is_free': is_free}
        if row.get('weaponId'):
            weap_pulls.append(entry)
        else:
            char_pulls.append(entry)

    def calc_pity(pulls_list):
        records, pity = [], 0
        for p in pulls_list:
            if not p.get('is_free'):
                pity += 1
            if p['rarity'] == 6:
                records.append({'name': p['name'], 'pity': pity, 'pool': p['pool']})
                pity = 0
        return records, pity

    def process_by_pool(pulls):
        by_pool = defaultdict(list)
        for p in pulls:
            by_pool[p['pool']].append(p)
        all_6stars, pool_results, current_pity = [], {}, 0
        for pool_name, pool_pulls in by_pool.items():
            records, pity = calc_pity(pool_pulls)
            pool_results[pool_name] = {'records': records, 'pity': pity, 'total': len(pool_pulls)}
            all_6stars.extend(records)
            if pool_pulls[-1] == pulls[-1]:
                current_pity = pity
        return by_pool, pool_results, all_6stars, current_pity

    char_by_pool, char_pool_results, all_char_6stars, current_char_pity = process_by_pool(char_pulls)
    weap_by_pool, weap_pool_results, all_weap_6stars, current_weap_pity = process_by_pool(weap_pulls)

    CHAR_RATE, WEAP_RATE = 0.016, 0.050
    total_char = len(char_pulls)
    total_weap = len(weap_pulls)
    total_char_6 = len(all_char_6stars)
    total_weap_6 = len(all_weap_6stars)

    EXCLUDE = {'여정의 시작 헤드헌팅'}
    filtered = [x for x in all_char_6stars if x['pool'] not in EXCLUDE]
    avg_char_pity = sum(x['pity'] for x in filtered) / len(filtered) if filtered else 0
    avg_weap_pity = sum(x['pity'] for x in all_weap_6stars) / total_weap_6 if total_weap_6 > 0 else 0

    char_luck = (1 - calculate_binom_cdf(max(0, total_char_6 - 1), total_char, CHAR_RATE)) * 100 if total_char > 0 else 50
    weap_luck = (1 - calculate_binom_cdf(max(0, total_weap_6 - 1), total_weap, WEAP_RATE)) * 100 if total_weap > 0 else 50

    BANNER_CAP = {'여정의 시작 헤드헌팅': 40}

    return {
        'char': {
            'total': total_char, 'total_6': total_char_6,
            'expected_6': round(total_char * CHAR_RATE, 1),
            'avg_pity': round(avg_char_pity, 1),
            'current_pity': current_char_pity,
            'luck': round(char_luck, 1),
            'pool_results': char_pool_results,
            'banner_cap': BANNER_CAP,
        },
        'weap': {
            'total': total_weap, 'total_6': total_weap_6,
            'expected_6': round(total_weap * WEAP_RATE, 1),
            'avg_pity': round(avg_weap_pity, 1),
            'current_pity': current_weap_pity,
            'luck': round(weap_luck, 1),
            'pool_results': weap_pool_results,
            'banner_cap': {'__default__': 40},
        },
    }

# ── UI 컴포넌트 ────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """수치 하나를 보여주는 카드 위젯"""
    def __init__(self, master, label, value, sub="", accent=ACCENT, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, border_width=1,
                         border_color=BORDER, **kw)
        ctk.CTkLabel(self, text=label, font=("Malgun Gothic", 11),
                     text_color=TEXT_SEC).pack(pady=(12, 2))
        ctk.CTkLabel(self, text=value, font=("Malgun Gothic", 22, "bold"),
                     text_color=accent).pack()
        ctk.CTkLabel(self, text=sub if sub else " ", font=("Malgun Gothic", 10),
                     text_color=TEXT_SEC).pack(pady=(2, 10))

class LuckBar(ctk.CTkFrame):
    """운 점수 게이지 바"""
    def __init__(self, master, score, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10,
                         border_width=1, border_color=BORDER, **kw)
        # 점수가 낮을수록(상위 %) 운이 좋음
        fill = max(0, min(100, 100 - score))
        if score < 20:
            color, msg, emoji = STAR6_COLOR, "압도적인 행운입니다!", "✨"
        elif score < 50:
            color, msg, emoji = SUCCESS, "운이 좋은 편입니다!", "👍"
        elif score <= 70:
            color, msg, emoji = ACCENT2, "평균적인 운입니다.", "⚖️"
        else:
            color, msg, emoji = DANGER, "운이 조금 나빴네요.", "😭"

        ctk.CTkLabel(self, text=f"{emoji} 운(Luck) 점수",
                     font=("Malgun Gothic", 12), text_color=TEXT_SEC).pack(pady=(12, 4), padx=16, anchor="w")

        bar_frame = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=6, height=18)
        bar_frame.pack(fill="x", padx=16, pady=2)
        bar_frame.pack_propagate(False)

        fill_frame = ctk.CTkFrame(bar_frame, fg_color=color, corner_radius=6, height=18)
        fill_frame.place(relx=0, rely=0, relwidth=fill / 100, relheight=1)

        ctk.CTkLabel(self, text=f"상위 {score:.1f}%  |  {msg}",
                     font=("Malgun Gothic", 12, "bold"),
                     text_color=color).pack(pady=(6, 12), padx=16, anchor="w")

class BannerTable(ctk.CTkScrollableFrame):
    """배너별 6성 히스토리 테이블"""
    def __init__(self, master, pool_results, banner_cap, is_weap=False, **kw):
        super().__init__(master, fg_color=BG_DEEP, corner_radius=0, **kw)
        default_cap = 40 if is_weap else 80

        headers = ["배너", "총 횟수", "6성", "평균 천장", "현재 스택", "6성 히스토리"]
        col_widths = [170, 70, 50, 90, 100, 340]

        # 헤더
        hdr_frame = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=6)
        hdr_frame.pack(fill="x", padx=4, pady=(4, 2))
        for i, (h, w) in enumerate(zip(headers, col_widths)):
            ctk.CTkLabel(hdr_frame, text=h, font=("Malgun Gothic", 11, "bold"),
                         text_color=ACCENT, width=w, anchor="center").grid(
                row=0, column=i, padx=4, pady=8)

        # 행
        for pool_name, result in pool_results.items():
            records = result['records']
            pity    = result['pity']
            total   = result['total']
            cap     = banner_cap.get(pool_name, banner_cap.get('__default__', default_cap))
            avg_str = f"{sum(r['pity'] for r in records)/len(records):.1f}회" if records else "-"
            stack_pct = pity / cap
            stack_color = DANGER if stack_pct >= 0.75 else WARNING if stack_pct >= 0.5 else SUCCESS

            row_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=6)
            row_frame.pack(fill="x", padx=4, pady=2)

            # 배너명
            ctk.CTkLabel(row_frame, text=pool_name, font=("Malgun Gothic", 11),
                         text_color=TEXT_PRI, width=col_widths[0], anchor="w",
                         wraplength=165).grid(row=0, column=0, padx=(10,4), pady=8)
            # 총 횟수
            ctk.CTkLabel(row_frame, text=str(total), font=("Malgun Gothic", 11),
                         text_color=TEXT_SEC, width=col_widths[1], anchor="center").grid(
                row=0, column=1, padx=4, pady=8)
            # 6성 수
            ctk.CTkLabel(row_frame, text=str(len(records)), font=("Malgun Gothic", 11, "bold"),
                         text_color=STAR6_COLOR if records else TEXT_SEC,
                         width=col_widths[2], anchor="center").grid(
                row=0, column=2, padx=4, pady=8)
            # 평균 천장
            ctk.CTkLabel(row_frame, text=avg_str, font=("Malgun Gothic", 11),
                         text_color=TEXT_PRI, width=col_widths[3], anchor="center").grid(
                row=0, column=3, padx=4, pady=8)
            # 현재 스택
            stack_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=col_widths[4])
            stack_frame.grid(row=0, column=4, padx=4, pady=8)
            stack_frame.pack_propagate(False)
            ctk.CTkLabel(stack_frame, text=f"{pity} / {cap}",
                         font=("Malgun Gothic", 11, "bold"),
                         text_color=stack_color).pack()
            bar = ctk.CTkProgressBar(stack_frame, width=80, height=6,
                                     fg_color=BG_PANEL, progress_color=stack_color)
            bar.set(stack_pct)
            bar.pack(pady=2)
            # 6성 히스토리 태그들
            hist_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=col_widths[5])
            hist_frame.grid(row=0, column=5, padx=(4,8), pady=8, sticky="w")
            if records:
                wrap = ctk.CTkFrame(hist_frame, fg_color="transparent")
                wrap.pack(fill="x")
                for idx, r in enumerate(records):
                    tag_color = STAR6_COLOR if r['pity'] >= 60 else SUCCESS if r['pity'] <= 20 else ACCENT2
                    tag = ctk.CTkFrame(wrap, fg_color=BG_PANEL, corner_radius=4)
                    tag.grid(row=idx//4, column=idx%4, padx=2, pady=2)
                    ctk.CTkLabel(tag, text=f"[{r['pity']}뽑] {r['name']}",
                                 font=("Malgun Gothic", 10),
                                 text_color=tag_color).pack(padx=6, pady=3)
            else:
                ctk.CTkLabel(hist_frame, text="(아직 6성 없음)",
                             font=("Malgun Gothic", 10),
                             text_color=TEXT_SEC).pack(padx=6)

# ── 메인 앱 ───────────────────────────────────────────

class EndfieldTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎮 Endfield Gacha Tracker")
        self.geometry("1100x780")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DEEP)

        self._build_header()
        self._build_collect_panel()
        self._build_tab_area()

        # CSV가 이미 있으면 바로 분석
        if os.path.exists("endfield_gacha_history_all.csv"):
            self.after(300, self._load_and_render)

    # ── 헤더 ──────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="⬡  ENDFIELD GACHA TRACKER",
                     font=("Malgun Gothic", 18, "bold"),
                     text_color=ACCENT).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(hdr, text="가챠 기록 분석 도구  |  명일방주: 엔드필드",
                     font=("Malgun Gothic", 11),
                     text_color=TEXT_SEC).pack(side="left", padx=0, pady=16)

    # ── 데이터 수집 패널 ──────────────────────────────
    def _build_collect_panel(self):
        panel = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=72)
        panel.pack(fill="x", padx=0, pady=(1, 0))
        panel.pack_propagate(False)

        inner = ctk.CTkFrame(panel, fg_color="transparent")
        inner.pack(side="left", padx=20, pady=12)

        self.btn_collect = ctk.CTkButton(
            inner, text="  📡  데이터 수집 시작", width=180, height=40,
            font=("Malgun Gothic", 13, "bold"),
            fg_color=ACCENT, hover_color="#d4891e", text_color="#000000",
            corner_radius=8, command=self._start_collect)
        self.btn_collect.pack(side="left", padx=(0, 16))

        progress_box = ctk.CTkFrame(inner, fg_color="transparent")
        progress_box.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(progress_box, width=340, height=8,
                                               fg_color=BG_CARD, progress_color=ACCENT)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 4))

        self.status_label = ctk.CTkLabel(progress_box,
                                         text="게임 내 가챠 기록 창을 열고 데이터를 수집하세요.",
                                         font=("Malgun Gothic", 11), text_color=TEXT_SEC)
        self.status_label.pack(anchor="w")

    # ── 탭 영역 ──────────────────────────────────────
    def _build_tab_area(self):
        self.tab_view = ctk.CTkTabview(self, fg_color=BG_DEEP,
                                       segmented_button_fg_color=BG_PANEL,
                                       segmented_button_selected_color=ACCENT,
                                       segmented_button_selected_hover_color="#d4891e",
                                       segmented_button_unselected_color=BG_PANEL,
                                       segmented_button_unselected_hover_color=BG_CARD,
                                       text_color=TEXT_PRI,
                                       text_color_disabled=TEXT_SEC)
        self.tab_view.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self.tab_char = self.tab_view.add("👤  캐릭터 헤드헌팅")
        self.tab_weap = self.tab_view.add("⚔️  무기 헤드헌팅")

        for tab in [self.tab_char, self.tab_weap]:
            tab.configure(fg_color=BG_DEEP)

        # 초기 placeholder
        for tab, label in [(self.tab_char, "캐릭터"), (self.tab_weap, "무기")]:
            ctk.CTkLabel(tab,
                         text=f"데이터를 수집하면 {label} 분석 결과가 여기에 표시됩니다.",
                         font=("Malgun Gothic", 13), text_color=TEXT_SEC).pack(expand=True)

    # ── 수집 시작 ─────────────────────────────────────
    def _start_collect(self):
        self.btn_collect.configure(state="disabled", text="  ⏳  수집 중...")
        self._set_status("🔍 로그 파일 탐색 중...")
        threading.Thread(target=self._collect_thread, daemon=True).start()

    def _collect_thread(self):
        url, msg = extract_gacha_url_from_log()
        self.after(0, lambda: self._set_status(msg))
        if not url:
            self.after(0, lambda: self.btn_collect.configure(state="normal", text="  📡  데이터 수집 시작"))
            return

        ok, result_msg = fetch_all_records(
            url,
            progress_cb=lambda v: self.after(0, lambda vv=v: self.progress_bar.set(vv / 100)),
            status_cb=lambda m: self.after(0, lambda mm=m: self._set_status(mm))
        )
        self.after(0, lambda: self._set_status(result_msg))
        self.after(0, lambda: self.btn_collect.configure(state="normal", text="  📡  데이터 수집 시작"))
        if ok:
            self.after(200, self._load_and_render)

    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    # ── 결과 렌더링 ───────────────────────────────────
    def _load_and_render(self):
        data = analyze_data()
        if not data:
            self._set_status("❌ CSV 파일을 찾을 수 없습니다.")
            return
        self._set_status(f"✅ 분석 완료  |  캐릭터 {data['char']['total']}회  |  무기 {data['weap']['total']}회")
        self.progress_bar.set(1.0)
        self._render_tab(self.tab_char, data['char'], is_weap=False)
        self._render_tab(self.tab_weap, data['weap'], is_weap=True)

    def _render_tab(self, tab, d, is_weap):
        # 기존 위젯 초기화
        for w in tab.winfo_children():
            w.destroy()

        # 탭 내부를 grid로 구성 - row 0,1,2 고정, row 3(테이블)만 확장
        tab.grid_rowconfigure(3, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        kind    = "무기" if is_weap else "캐릭터"
        unit    = "개"   if is_weap else "명"
        avg_ref = "약 20.0회" if is_weap else "약 62.5회"
        cap     = 40 if is_weap else 80

        # ── row 0: 스탯 카드 4개 ──────────────────────
        cards_frame = ctk.CTkFrame(tab, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 4))

        stats = [
            ("총 뽑기 횟수",  f"{d['total']}회",               ""),
            ("6성 획득",      f"{d['total_6']}{unit}",         f"기대치 {d['expected_6']}{unit}"),
            ("평균 6성 천장", f"{d['avg_pity']}회",             f"공식 평균 {avg_ref}"),
            ("현재 스택",     f"{d['current_pity']} / {cap}",  ""),
        ]
        accent_list = [ACCENT2, STAR6_COLOR, TEXT_PRI, WARNING]
        for i, (lbl, val, sub) in enumerate(stats):
            card = StatCard(cards_frame, lbl, val, sub, accent=accent_list[i])
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)

        # ── row 1: 운 점수 게이지 ─────────────────────
        LuckBar(tab, d['luck']).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))

        # ── row 2: 테이블 제목 ────────────────────────
        ctk.CTkLabel(tab, text=f"  📋  {kind} 배너별 6성 히스토리",
                     font=("Malgun Gothic", 13, "bold"),
                     text_color=ACCENT).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 2))

        # ── row 3: 배너 테이블 (expand) ───────────────
        BannerTable(tab, d['pool_results'], d['banner_cap'], is_weap=is_weap).grid(
            row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))

# ── 진입점 ────────────────────────────────────────────
if __name__ == "__main__":
    app = EndfieldTrackerApp()
    app.mainloop()
