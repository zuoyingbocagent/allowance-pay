import os
import json
import re
import math
import calendar
import streamlit as st
from datetime import datetime, date, timedelta

# ----------------------------------------------------
# 0. Streamlit 頁面基礎設定
# ----------------------------------------------------
st.set_page_config(
    page_title="浯金獺算 (有錢好算)",
    page_icon="🦦",
    layout="centered"
)

st.title("🦦 浯金獺算 (有錢好算)")
st.caption("這是地加、副食費與戰加的計算機，會說明公式算法，也是互相學習的地方~")

with st.expander("💡 薪餉與副食費破月計算公式說明與範例"):
    st.markdown("""
    **1. 薪餉 (地域加給、戰鬥部隊加給) 破月計算：**
    * **計算公式：** `round(月支數額 ÷ 當月總天數) × 應領天數`
    * **範例：** 9 月（共 30 天）外島三級加給 $9,790，支領 13 天：
      * 每日日額：`round(9,790 ÷ 30) = round(326.333...)` → **$326**
      * 應領金額：`326 × 13` = **$4,238**

    ---
    **2. 地區副食費破月計算：**
    * **計算公式：** `無條件捨去至小數第 2 位 → 逐次四捨五入至整數`
    * **範例：** 9 月（共 30 天）志願役外島副食費 $2,920，支領 13 天：
      * 原始算式：`2,920 ÷ 30 × 13 = 1,265.3333...`
      * 取至小數第 2 位（無條件捨去）：`1,265.33`
      * 四捨五入至小數第 1 位：`1,265.3` → 四捨五入至整數：**$1,265**
    """)

# 新增：iOS 與 Android 加入桌面 App 操作說明
with st.expander("📱 如何將此網頁「加入主畫面」像 APP 一樣使用？"):
    tab_ios, tab_android = st.tabs(["🍎 iOS (iPhone / iPad)", "🤖 Android (安卓)"])
    
    with tab_ios:
        st.markdown("""
        1. 使用 Safari 瀏覽器開啟本網頁。
        2. 點擊下方工具列中間的 **分享按鈕** ⎋ (方框朝上箭頭)。
        3. 向下滑動選單，點選 **「加入主畫面」** (＋號圖示)。
        4. 點擊右上角 **「新增」**，即可在 iPhone 桌面看到專屬圖示！
        """)
        
    with tab_android:
        st.markdown("""
        1. 使用 Chrome 瀏覽器開啟本網頁。
        2. 點擊右上角 **選單按鈕** ⸠ (三個垂直圓點)。
        3. 點選 **「加到主畫面」** 或 **「安裝應用程式」**。
        4. 點擊 **「新增/安裝」**，即可在手機桌面快捷開啟！
        """)

# ----------------------------------------------------
# 1. 讀取 rates.json
# ----------------------------------------------------
RATES_FILE = os.path.join(os.path.dirname(__file__), "rates.json")

@st.cache_data
def load_rates():
    if os.path.exists(RATES_FILE):
        with open(RATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

RATES = load_rates()

# ----------------------------------------------------
# 2. 輔助匹配函式 (身分別別名與代碼彈性轉換)
# ----------------------------------------------------
def normalize_identity(identity_input: str) -> str:
    """將聘雇人員的各種別名統一映射為 JSON 內的 '聘雇人員' Key"""
    identity_input = identity_input.strip()
    hire_aliases = ["聘雇", "聘員", "雇員", "約聘", "約雇", "聘雇人員"]
    for alias in hire_aliases:
        if alias in identity_input:
            return "聘雇人員"
    if identity_input in ["志願役", "7301", "志願役官士兵", "志願役幹部", "志願役士官", "志願役軍官"]:
        return "志願役官士兵"
    if identity_input in ["73", "義務役兵", "常備兵役", "軍事訓練役"]:
        return "義務役士兵"
    if identity_input in ["63", "義務役士"]:
        return "義務役士官"
    if identity_input in ["43", "義務役官", "預官"]:
        return "義務役軍官"
    return identity_input

def find_regional_amount(region_input: str, identity_input: str) -> tuple:
    """修復：精準比對 level_name 並完整支援義務役各階級與聘雇人員"""
    identity = normalize_identity(identity_input)
    
    code_match = re.search(r'(O[ABC][1-4]|外島[一二三1-3]級?|離島[一二三1-3]級?|外離島[一二三1-3]級?|高山[一二三四1-4]級?|本島)', region_input, re.IGNORECASE)
    target_key = code_match.group(1).upper() if code_match else region_input.strip()

    reg_data = RATES.get("regional_allowance", {})
    for reg_group, levels in reg_data.items():
        for level_name, id_map in levels.items():
            if isinstance(id_map, dict):
                if target_key in level_name.upper() or level_name.upper() in target_key or region_input in level_name:
                    # 修正1：精準對應身分別（含義務役軍官/士官/士兵及聘雇人員）
                    amount = id_map.get(identity)
                    if amount is None:
                        if "義務役" in identity:
                            amount = id_map.get("義務役士兵", id_map.get("義務役士官", id_map.get("義務役軍官", 0)))
                        else:
                            amount = id_map.get("志願役官士兵", 0)
                    return amount, level_name
    return 0, region_input

def find_food_amount(food_input: str, identity_input: str) -> tuple:
    """修復：按 Key 長度排序優先匹配（解決外離島被誤判為外島問題）"""
    identity = normalize_identity(identity_input)
    if identity == "聘雇人員":
        return 0, "聘雇人員無副食費"
        
    clean_food = food_input.strip()
    subsidy_map = RATES.get("food_subsidy", {})

    # 修正1：修正副食費身份別映射，區分義務役官兵與士官
    id_key = "義務役官士兵" if "義務" in identity else "志願役官士兵"
    sub_map = subsidy_map.get(id_key, subsidy_map.get("志願役官士兵", {}))
    
    # 修正：精準匹配 key，避免 clean_food="本島" 時因為 "本島" in "本島傷患" 誤判為傷患費率
    sorted_keys = sorted(sub_map.keys(), key=len, reverse=True)
    for k in sorted_keys:
        if k == clean_food or k in clean_food:
            return sub_map[k], k
    return 0, food_input

def find_combat_amount(combat_input: str, identity_input: str) -> tuple:
    """修復：正確解析戰鬥加給金額"""
    combat_clean = combat_input.strip().upper()

    if combat_clean in ["無", "0", "NONE"]:
        return 0, "無"

    v_match = re.search(r'V[1-3]', combat_clean)
    target_v = v_match.group(0) if v_match else combat_clean

    # 修正：依據身分別取得志願役或義務役的戰鬥加給金額（解決義務役抓取到志願役金額問題）
    identity = normalize_identity(identity_input)
    combat_data = RATES.get("combat_unit_allowance", {})
    id_key = "義務役官士兵" if "義務" in identity else "志願役官士兵"
    combat_map = combat_data.get(id_key, combat_data.get("志願役官士兵", {}))

    for k, v in combat_map.items():
        if target_v in k.upper() or k.upper() in target_v or combat_clean in k.upper():
            # 修正3：確保取得正確整數金額
            return (v, k) if isinstance(v, int) else (0, combat_input)
    return 0, combat_input

# ----------------------------------------------------
# 3. 破月金額計算核心邏輯
# ----------------------------------------------------
def calc_round_allowance(monthly_amount: int, total_days: int, active_days: int):
    """薪餉與戰鬥加給破月計算：round(月支額 ÷ 當月天數) × 應領天數"""
    if monthly_amount == 0 or active_days == 0:
        return 0, 0, "0"
    daily_rate = round(monthly_amount / total_days)
    final_amount = daily_rate * active_days
    formula_str = f"四捨五入({monthly_amount:,} ÷ {total_days}) × {active_days} = {daily_rate:,} × {active_days}"
    return final_amount, daily_rate, formula_str

def calc_food_subsidy(monthly_amount: int, total_days: int, active_days: int):
    """地區副食費破月計算：無條件捨去至小數第2位後逐次四捨五入至整數"""
    if monthly_amount == 0 or active_days == 0:
        return 0, "0"
    raw_val = monthly_amount / total_days * active_days
    val_2dp = math.floor(raw_val * 100) / 100.0
    val_1dp = round(val_2dp, 1)
    val_int = int(round(val_1dp))
    formula_str = f"({monthly_amount:,} ÷ {total_days} × {active_days}) = {raw_val:.3f}... 無條件捨去取小數第2位→ {val_2dp:.2f} 小數點第2位四捨五入至小數點第1位→ {val_1dp:.1f} 小數點第1位四捨五入至整數→ {val_int:,}"
    return val_int, formula_str

# ----------------------------------------------------
# 4. 日期解析與雙軌天數計算 (語意配對 + 多格式支援)
# ----------------------------------------------------
def parse_chinese_number(cn_str: str) -> int:
    """轉換中文/數字字串為整數"""
    cn_map = {'零': 0, '0': 0, '一': 1, '壹': 1, '1': 1, '二': 2, '貳': 2, '2': 2, 
              '三': 3, '參': 3, '3': 3, '四': 4, '肆': 4, '4': 4, '五': 5, '伍': 5, '5': 5, 
              '六': 6, '陸': 6, '6': 6, '七': 7, '柒': 7, '7': 7, '八': 8, '捌': 8, '8': 8, 
              '九': 9, '玖': 9, '9': 9}
    if cn_str.isdigit(): 
        return int(cn_str)
    val, temp = 0, 0
    for char in cn_str:
        if char in cn_map: 
            temp = cn_map[char]
        elif char in ['十', '拾']:
            if temp == 0: temp = 1
            val += temp * 10
            temp = 0
    val += temp
    return val

def parse_flexible_date(date_str: str) -> date:
    """解析各式日期格式"""
    default_year = datetime.now().year
    date_str = date_str.strip()

    def try_make_date(y, m, d):
        try:
            return date(y, m, d)
        except ValueError:
            if m == 2 and d == 29:
                next_leap = y + (4 - y % 4) if y % 4 != 0 else y
                return date(next_leap, m, d)
            return None

    try:
        if re.fullmatch(r'\d{7}', date_str):
            roc_y = int(date_str[:3])
            return try_make_date(roc_y + 1911, int(date_str[3:5]), int(date_str[5:7]))
        
        if re.fullmatch(r'\d{8}', date_str):
            return try_make_date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))

        if re.fullmatch(r'\d{4}', date_str):
            return try_make_date(default_year, int(date_str[:2]), int(date_str[2:]))

        cn_pattern = r'^(?:([零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+)[年./-])?([零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+)月([零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+)[日號]?$'
        match_cn = re.match(cn_pattern, date_str)
        if match_cn:
            y_str, m_str, d_str = match_cn.groups()
            m, d = parse_chinese_number(m_str), parse_chinese_number(d_str)
            y = default_year
            if y_str:
                parsed_y = parse_chinese_number(y_str)
                y = parsed_y + 1911 if parsed_y < 1000 else parsed_y
            return try_make_date(y, m, d)

        parts = re.split(r'[-/.]', date_str)
        if len(parts) == 2:
            return try_make_date(default_year, int(parts[0]), int(parts[1]))
        elif len(parts) == 3:
            y = int(parts[0]) + 1911 if int(parts[0]) < 1000 else int(parts[0])
            return try_make_date(y, int(parts[1]), int(parts[2]))

    except Exception:
        return None

def extract_events_and_dates(text: str) -> dict:
    """抓取使用者字串中的所有日期與事由，並進行相近關鍵字連結"""
    date_token_pattern = r'(\d{7}|\d{8}|\d{4}|[零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+[年./-][零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+月[零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+[日號]?|[零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+月[零一壹二貳三參四肆五伍六陸七柒八捌九玖十拾\d]+[日號]?|\d{1,4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2})'
    
    parsed_events = {}
    segments = re.split(r'[\n,\s，、；;]+', text)
    
    for segment in segments:
        if not segment.strip():
            continue
            
        matches = list(re.finditer(date_token_pattern, segment))
        if not matches:
            continue
        
        for match in matches:
            d_str = match.group(1)
            parsed_dt = parse_flexible_date(d_str)
            if not parsed_dt:
                continue
            
            has_leave = any(k in segment for k in ["離開", "離金", "離嶼", "離澎", "離馬", "離島"])
            has_train = any(k in segment for k in ["受訓", "參訓", "住院", "住軍醫院"])
            has_arr = any(k in segment for k in ["抵達", "抵金", "抵澎", "抵島", "到達", "抵嶼"])
            has_finish = any(k in segment for k in ["結訓", "完訓", "退訓"])

            if has_leave:
                parsed_events["leave_date"] = parsed_dt
            if has_train:
                parsed_events["train_start_date"] = parsed_dt
            if has_arr:
                parsed_events["arr_date"] = parsed_dt
            if has_finish:
                parsed_events["train_end_date"] = parsed_dt

    if "leave_date" in parsed_events and "train_start_date" not in parsed_events:
        parsed_events["train_start_date"] = parsed_events["leave_date"]   

    return parsed_events

def process_days_calculation(user_msg: str) -> str:
    """處理艱苦地區異動天數與加給雙軌計算 (已修正變數未定義邏輯錯誤)"""
    events = extract_events_and_dates(user_msg)
    
    leave_date = events.get("leave_date")
    train_start_date = events.get("train_start_date")
    arr_date = events.get("arr_date")
    train_end_date = events.get("train_end_date")

    if not leave_date and not train_start_date and not arr_date and not train_end_date:
        return "無法辨識日期與相關事由，請重新輸入（例如：2/28離開艱苦地區受訓、1150228離金3-1受訓、或8/17結訓抵金）。"

    output = ["【艱苦地區異動之加給與副食費天數結果】\n"]

    if leave_date or train_start_date:
        if not leave_date: leave_date = train_start_date
        if not train_start_date: train_start_date = leave_date

        reg_start = leave_date + timedelta(days=1)
        reg_end = reg_start + timedelta(days=29)

        combat_start = train_start_date
        combat_end = combat_start + timedelta(days=29)

        output.append(f"📌 [出發受訓階段]")
        output.append(f"• 離開艱苦地區日期：{leave_date.month}/{leave_date.day}")
        output.append(f"• 受訓開始日期：{train_start_date.month}/{train_start_date.day}")

        orig_food_days = leave_date.day - 1
        days_in_leave_month = calendar.monthrange(leave_date.year, leave_date.month)[1]
        new_food_days = days_in_leave_month - leave_date.day + 1
        
        days_in_m1 = calendar.monthrange(reg_start.year, reg_start.month)[1]
        m1_reg_days = min(days_in_m1 - reg_start.day + 1, 30)
        m2_reg_days = max(0, 30 - m1_reg_days)
        
        output.append(f"\n🔹 地域加給 (離艱苦地區加發30日，第1日為離艱苦地區日+1日)：")
        output.append(f"  - 發放區間：{reg_start.month}/{reg_start.day} ~ {reg_end.month}/{reg_end.day}")
        output.append(f"  - {reg_start.month}月加發：{m1_reg_days} 天")
        if m2_reg_days > 0:
            output.append(f"  - {reg_end.month}月加發：{m2_reg_days} 天 (第30日為 {reg_end.month}/{reg_end.day})") 

        output.append(f"\n🔹 地區性副食費 (離開暨抵達之日改支領抵達地區副食費)：")
        output.append(f"  - 離開暨抵達之日期：{leave_date.month}/{leave_date.day}")
        output.append(f"  - {leave_date.month}月原地區副食費發：{orig_food_days}天")
        output.append(f"  - {leave_date.month}月新地區副食費發：{new_food_days}天")

        c_days_in_m1 = calendar.monthrange(combat_start.year, combat_start.month)[1]
        m1_combat_days = min(c_days_in_m1 - combat_start.day + 1, 30)
        m2_combat_days = max(0, 30 - m1_combat_days)
        
        output.append(f"\n🔹 戰鬥部隊加給 (受訓加發30日，第1日為受訓開始日期)：")
        output.append(f"  - 發放區間：{combat_start.month}/{combat_start.day} ~ {combat_end.month}/{combat_end.day}")
        output.append(f"  - {combat_start.month}月加發：{m1_combat_days} 天")
        if m2_combat_days > 0:
            output.append(f"  - {combat_end.month}月加發：{m2_combat_days} 天 (第30日為 {combat_end.month}/{combat_end.day})")

    if arr_date or train_end_date:
        output.append(f"\n📌 [結訓返回艱苦地區階段]")
        combat_restore_days = 0
        
        if train_end_date:
            c_y, c_m, c_d = train_end_date.year, train_end_date.month, train_end_date.day
            total_c_m_days = calendar.monthrange(c_y, c_m)[1]
            combat_restore_days = total_c_m_days - c_d + 1
            output.append(f"• 結訓(完訓)日期：{train_end_date.month}/{train_end_date.day}")
            output.append(f"• {c_m}月恢復支領戰鬥加給天數：{combat_restore_days} 天 (自 {c_m}/{c_d} 起算)")

        if arr_date:
            a_y, a_m, a_d = arr_date.year, arr_date.month, arr_date.day
            total_a_m_days = calendar.monthrange(a_y, a_m)[1]
            region_restore_days = total_a_m_days - a_d + 1
            orig_food_days_return = a_d - 1
            new_food_days_return = total_a_m_days - a_d + 1
            
            output.append(f"• 抵達艱苦地區日：{a_m}/{a_d}")
            output.append(f"• {a_m}月恢復支領地域加給天數：{region_restore_days} 天 (自 {a_m}/{a_d} 起算)")
            output.append(f"\n🔹 地區性副食費 (離開暨抵達之日改支領抵達地區副食費)：")
            output.append(f"  - 離開暨抵達之日期：{a_m}/{a_d}")
            output.append(f"  - {a_m}月原地區副食費發：{orig_food_days_return}天")
            output.append(f"  - {a_m}月新地區副食費發：{new_food_days_return}天")

        # 同月相加提醒判定 (精準修正變數未定義問題)
        if train_start_date and train_end_date:
            combat_end = train_start_date + timedelta(days=29)
            if combat_end.month == train_end_date.month:
                target_m = combat_end.month
                m2_combat_days_calc = max(0, 30 - (calendar.monthrange(train_start_date.year, train_start_date.month)[1] - train_start_date.day + 1))
                total_same_month_combat = m2_combat_days_calc + combat_restore_days
                output.append(f"\n⚠️ 【同月份相加提醒】：{target_m}月同時包含受訓加發與結訓恢復，{target_m}月應支領戰加總天數為：{total_same_month_combat} 天")

    return "\n".join(output)

# ----------------------------------------------------
# 5. 解析固定格式試算金額 (修正年月 parsing 與聘雇副食費)
# ----------------------------------------------------
def calculate_amount_from_format(user_message: str) -> str:
    month_match = re.search(r"支領年月.*[：:]\s*(\d+)", user_message)
    active_days_match = re.search(r"應支領天數[：:]\s*(\d+)", user_message)
    region_lvl_match = re.search(r"地加等級類別[：:]\s*(.+)", user_message)
    reg_identity_match = re.search(r"地加身分別[：:]\s*(.+)", user_message) or re.search(r"身分別[：:]\s*(.+)", user_message)
    food_identity_match = re.search(r"副食費身分別[：:]\s*(.+)", user_message)
    food_region_match = re.search(r"地區性副食費類別[：:]\s*(.+)", user_message)
    
    combat_match = re.search(r"戰鬥部隊加給類別[：:]\s*(.+)", user_message)
    combat_days_match = re.search(r"應支領戰加天數[：:]\s*(\d+)", user_message)

    issued_reg_match = re.search(r"已發地域加給(?:金額)?[：:]\s*(\d+)", user_message)
    issued_food_match = re.search(r"已發副食費(?:金額)?[：:]\s*(\d+)", user_message)
    issued_combat_match = re.search(r"已發戰加(?:金額)?[：:]\s*(\d+)", user_message)

    if not all([month_match, active_days_match, region_lvl_match, reg_identity_match, food_region_match]):
        return None

    month_str = month_match.group(1).strip()
    
    # 修正：嚴格限制支領年月必須為固定 5 碼民國數字（如 11509）
    if not re.fullmatch(r'\d{5}', month_str):
        return "⚠️ 支領年月格式錯誤！必須為固定 5 碼民國年月數字（例如：11509）。"

    try:
        roc_year = int(month_str[:3])
        month_num = int(month_str[3:])
        total_days = calendar.monthrange(roc_year + 1911, month_num)[1]
    except Exception:
        total_days = 30

    active_days = int(active_days_match.group(1))
    region_lvl_str = region_lvl_match.group(1).strip()
    reg_identity_raw = reg_identity_match.group(1).strip()
    food_identity_raw = food_identity_match.group(1).strip() if food_identity_match else reg_identity_raw
    food_region_str = food_region_match.group(1).strip()

    active_combat_days = int(combat_days_match.group(1)) if combat_days_match else active_days
    combat_lvl_str = combat_match.group(1).strip() if combat_match else "無"

    if not (0 < active_days < total_days) or not (0 <= active_combat_days < total_days):
        return f"⚠️ 破月意指非整月支領。應支領天數必須「大於 0 天」且「小於當月總天數 ({total_days} 天)」，請重新輸入。"

    reg_base, matched_reg_name = find_regional_amount(region_lvl_str, reg_identity_raw)
    food_base, matched_food_name = find_food_amount(food_region_str, food_identity_raw)
    combat_base, matched_combat_name = find_combat_amount(combat_lvl_str, food_identity_raw)

    reg_should, reg_daily, reg_formula = calc_round_allowance(reg_base, total_days, active_days)
    food_should, food_formula = calc_food_subsidy(food_base, total_days, active_days)
    combat_should, combat_daily, combat_formula = calc_round_allowance(combat_base, total_days, active_combat_days)

    diff_section = ""
    if issued_reg_match or issued_food_match or issued_combat_match:
        issued_reg = int(issued_reg_match.group(1)) if issued_reg_match else 0
        issued_food = int(issued_food_match.group(1)) if issued_food_match else 0
        issued_combat = int(issued_combat_match.group(1)) if issued_combat_match else 0
        
        diff_reg = issued_reg - reg_should
        diff_food = issued_food - food_should
        diff_combat = issued_combat - combat_should
        
        diff_section = f"""

------------------------
【差額分析 (已發 - 應發)】
• 地域加給差額：${issued_reg:,} - ${reg_should:,} = ${diff_reg:,} ({'應追扣' if diff_reg > 0 else '應補發' if diff_reg < 0 else '無差額'})
• 地區副食費差額：${issued_food:,} - ${food_should:,} = ${diff_food:,} ({'應追扣' if diff_food > 0 else '應補發' if diff_food < 0 else '無差額'})
• 戰鬥加給差額：${issued_combat:,} - ${combat_should:,} = ${diff_combat:,} ({'應追扣' if diff_combat > 0 else '應補發' if diff_combat < 0 else '無差額'})"""

    total_should = reg_should + food_should + combat_should
    normalized_reg_name = normalize_identity(reg_identity_raw)

    reply_msg = f"""【民國 {month_str} 月破月金額計算結果】
地加身分別：{reg_identity_raw}{f' (匹配至：{normalized_reg_name})' if reg_identity_raw != normalized_reg_name else ''}
副食費/戰加身分別：{food_identity_raw}
地加天數: {active_days} / {total_days} 天 | 戰加天數: {active_combat_days} / {total_days} 天

[1. 地域加給 ({matched_reg_name})]
• 月支數額：${reg_base:,}
• 算式：{reg_formula}
• 應發金額：${reg_should:,}

[2. 地區副食費 ({matched_food_name})]
• 月支數額：${food_base:,}
• 算式：{food_formula}
• 應發金額：${food_should:,}

[3. 戰鬥部隊加給 ({matched_combat_name})]
• 月支數額：${combat_base:,}
• 算式：{combat_formula}
• 應發金額：${combat_should:,}{diff_section}"""

    return reply_msg

# ----------------------------------------------------
# 6. Streamlit 網頁主介面邏輯
# ----------------------------------------------------
tab1, tab2, tab3 = st.tabs(["💰 破月金額試算", "📅 異動天數計算", "📊 費率對照表"])

with tab1:
    st.subheader("📋 輸入試算條件")
    # 取得系統當前年月 (民國年月)
    now = datetime.now()
    default_year_month = f"{now.year - 1911}{now.month:02d}"
    
    col1, col2 = st.columns(2)
    with col1:
        # 修正：將身分別拆分為地域加給與副食費/戰加專用身分別，精準對應 rates.json 費率
        reg_identity = st.selectbox("地域加給身分別", ["志願役官士兵", "義務役軍官", "義務役士官", "義務役士兵", "聘雇人員"])

        month_input = st.text_input(
            "支領年月 (固定民國年月5碼)", 
            value=default_year_month, 
            max_chars=5, 
            placeholder="11509",
            help="請輸入5碼民國年月，例如：11509 代表 115 年 09 月"
        )
        region_lvl = st.selectbox("地加等級類別", [
            "外島第三級(OA3)", "外島第二級(OA2)", "外島第一級(OA1)",
            "離島第三級(OB3)", "離島第二級(OB2)", "離島第一級(OB1)",
            "高山第四級(OC4)", "高山第三級(OC3)", "高山第二級(OC2)", "高山第一級(OC1)",
            "本島-非艱苦地區"
        ])
        
        # 聘雇人員無副食費提醒與介面連動
        food_identity = st.selectbox("副食費/戰加身分別", ["志願役官士兵", "義務役官士兵", "聘雇人員"])
        
        if food_identity == "聘雇人員":
            food_region = st.selectbox("地區性副食費類別", ["無 (聘雇人員不適用)"], disabled=True)
        else:
            food_region = st.selectbox("地區性副食費類別", [
                "外島", "外離島", "本島", "離島", "東沙", "南沙",
                "本島傷患", "離島傷患", "外島傷患", "外離島傷患"
            ])
            
        # 修正：改回 number_input 並提供破月天數提示與九宮格數字鍵盤
        active_days = st.number_input(
            "應支領地域加給/副食費天數", 
            min_value=0, 
            max_value=31, 
            value=13,
            help="💡 破月天數須大於 0 天且小於當月總天數"
        )

    with col2:
        # 修正：聘雇人員連動自動停用戰鬥加給選項
        if food_identity == "聘雇人員":
            combat_lvl = st.selectbox("戰鬥部隊加給類別", ["無 (聘雇人員不適用)"], disabled=True)
        else:
            combat_lvl = st.selectbox("戰鬥部隊加給類別", ["戰鬥部隊第一類型(V1)", "戰鬥部隊第二類型(V2)", "戰鬥部隊第三類型(V3)", "無"])
            
        active_combat_days = st.number_input(
            "應支領戰加天數", 
            min_value=0, 
            max_value=31, 
            value=13,
            help="💡 破月天數須大於 0 天且小於當月總天數"
        )
        
        st.markdown("**【選填】差額分析金額**")
        issued_reg = st.number_input("已發地域加給金額", min_value=0, value=0)
        issued_food = st.number_input("已發副食費金額", min_value=0, value=0)
        issued_combat = st.number_input("已發戰加金額", min_value=0, value=0)
    # 修正：注入原生 JS 強制使頁面上所有數字/文字輸入框觸發行動裝置的九宮格數字鍵盤
    st.components.v1.html("""
        <script>
        const inputs = window.parent.document.querySelectorAll('input');
        inputs.forEach(input => {
            input.setAttribute('inputmode', 'numeric');
            input.setAttribute('pattern', '[0-9]*');
        });
        </script>
    """, height=0)

    if st.button("🚀 開始計算金額", type="primary", use_container_width=True):
        target_food_region = "無" if food_identity == "聘雇人員" else food_region
        target_combat_lvl = "無" if food_identity == "聘雇人員" else combat_lvl
        fmt_text = f"""支領年月(民國年月)：{month_input}
地加身分別：{reg_identity}
副食費身分別：{food_identity}
地加等級類別：{region_lvl}
地區性副食費類別：{target_food_region}
應支領天數：{active_days}
(選填)已發地域加給金額：{issued_reg}
(選填)已發副食費金額：{issued_food}
______________
戰鬥部隊加給類別：{target_combat_lvl}
應支領戰加天數：{active_combat_days}
(選填)已發戰加金額：{issued_combat}"""
        
        res = calculate_amount_from_format(fmt_text)
        if res:
            st.code(res, language="text")
        else:
            st.error("輸入格式有誤或天數不符，請重新檢查輸入條件。")

with tab2:
    st.subheader("🗓️ 輸入變動事件與日期")
    st.info("提示：可直接輸入說明文字，例如：`7/3離開艱苦地區，7/4受訓，8/17結訓抵達艱苦地區；9/5結訓，9/6抵達艱苦地區；9/14因支援抵達艱苦地區`")
    event_text = st.text_area("請輸入異動說明內容：", value="""7/3離開艱苦地區，
                                                               7/4受訓，
                                                               8/17結訓，
                                                               8/18抵達艱苦地區，
                                                               9/14因支援抵達艱苦地區
                                                               請修正填入實際狀況""", height=120)
    
    if st.button("🔍 計算天數", use_container_width=True):
        days_res = process_days_calculation(event_text)
        st.code(days_res, language="text")

with tab3:
    st.subheader("📊 月支數額對照表")
    st.markdown("""
    **一、 地域加給 (志願役官士兵/聘雇)：**
    * 外島一級(OA1)：$20,000
    * 外島二級(OA2)：$12,000
    * 外島三級(OA3)：$9,790 (聘雇: $7,150)
    * 離島三級(OB3)：$9,790 (聘雇: $7,150)
    * 本島-非艱苦地區：$0

    **一-1、 地域加給 (義務役士兵)：**
    * 外島一級(OA1)：$5,460
    * 外島二級(OA2)：$2,270
    * 外島三級(OA3)：$1,030
    * 離島三級(OB3)：$830
    * 本島-非艱苦地區：$0

    **二、 戰鬥部隊加給：**
    * 第一類型(V1)：$12,000
    * 第二類型(V2)：$7,000
    * 第三類型(V3)：$3,000

    **三、 地區副食費：**
    * **志願役官士兵**：外島 $2,920 | 本島 $1,790 | 外離島 $3,160 | 離島 $2,120
                       外島傷$2,510 |本島傷$1,680 |外離島傷$2,690 |離島傷$1,920
    * **義務役官士兵**：外島 $3,429 | 本島 $2,299 | 外離島 $3,669 | 離島 $2,629
                       外島傷$3,019 |本島傷$2,189 |外離島傷$3,199 |離島傷$2,429
    * **聘雇人員**：不支領副食費
    """)