import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import pytz

# 設定台灣時區
TW_TZ = pytz.timezone('Asia/Taipei')

# 1. Google 試算表驗證與連接
SPREADSHEET_ID = "1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ"

@st.cache_resource
def get_gspread_client():
    secrets_dict = json.loads(st.secrets["google_json"])
    return gspread.service_account_from_dict(secrets_dict)

def get_worksheet(sheet_name="工作表1"):
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except:
        if sheet_name == "歷史紀錄":
            ws = sh.add_worksheet(title="歷史紀錄", rows="100", cols="6")
            ws.append_row(["時間", "類型", "物品名稱", "變動數量", "結算總數", "位置/儲位"])
            return ws
        return sh.sheet1

def get_current_data():
    ws = get_worksheet("工作表1")
    data = ws.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])
    df = pd.DataFrame(data[1:], columns=["物品名稱", "庫存數量", "儲位"])
    df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)
    return df

def save_all_data(df):
    ws = get_worksheet("工作表1")
    ws.clear()
    ws.append_row(["物品名稱", "庫存數量", "儲位"])
    if not df.empty:
        ws.append_rows(df.astype(str).values.tolist())

def log_history(action_type, item_name, change_qty, total_qty, location):
    ws_log = get_worksheet("歷史紀錄")
    now_str = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    ws_log.append_row([now_str, action_type, item_name, str(change_qty), str(total_qty), location])

# 初始化 session state
if 'batch_item' not in st.session_state:
    st.session_state.batch_item = ""
if 'batch_count' not in st.session_state:
    st.session_state.batch_count = 0
if 'last_completed_item' not in st.session_state:
    st.session_state.last_completed_item = ""
if 'last_completed_count' not in st.session_state:
    st.session_state.last_completed_count = 0

# 網頁UI設定：活潑現代風格
st.set_page_config(page_title="雲端倉庫與生產管理系統", page_icon="📦", layout="wide")

st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    h1 {
        color: #1E3A8A;
        font-family: 'Trebuchet MS', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #ffffff;
        border-radius: 8px 8px 0px 0px;
        color: #4B5563;
        font-weight: bold;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        color: #ffffff !important;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #3B82F6;
    }
    div[data-testid="stDataFrame"] {
        background-color: transparent !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ 雲端倉庫與生產管理系統")

# 主頁籤選單：即時生產計數 (計瓶器) 排在最後一個
tab1, tab2, tab3, tab4 = st.tabs(["📋 當前總庫存", "📥 物品進貨", "📦 物品出庫", "🧪 即時生產計數 (計瓶器)"])

# --- 頁籤 1: 當前總庫存與分門別類的歷史日誌 ---
with tab1:
    st.subheader("📋 當前倉庫總庫存盤點表")
    if st.button("🔄 刷新最新資料"):
        st.cache_data.clear()
        st.rerun()

    df_inventory = get_current_data()
    if df_inventory.empty:
        st.info("💡 目前倉庫內沒有任何貨物。")
    else:
        col_search, col_filter = st.columns([2, 1])
        with col_search:
            search_term = st.text_input("🔍 快捷搜尋物品名稱：", placeholder="例如：洗髮精...")
        with col_filter:
            zone_filter = st.text_input("🗺️ 按存放地點/關鍵字過濾：", placeholder="例如：A區 或 客廳...")

        filtered_df = df_inventory.copy()
        if search_term.strip():
            filtered_df = filtered_df[filtered_df["物品名稱"].str.contains(search_term, case=False, na=False)]
        if zone_filter.strip():
            filtered_df = filtered_df[filtered_df["儲位"].str.contains(zone_filter.strip(), case=False, na=False)]

        st.dataframe(filtered_df, use_container_width=True)
        st.metric(label="📊 目前篩選貨物總瓶/件數", value=f"{filtered_df['庫存數量'].sum()} 件")

    st.write("---")
    st.subheader("📜 歷史進出貨與生產時間日誌")
    try:
        ws_log = get_worksheet("歷史紀錄")
        log_data = ws_log.get_all_values()
        if len(log_data) > 1:
            df_log = pd.DataFrame(log_data[1:], columns=log_data[0])
            
            # 日期過濾與關鍵字過濾輸入列
            col_date, col_keyword = st.columns([1, 2])
            with col_date:
                selected_date = st.date_input("📅 選擇日誌日期", value=datetime.now(TW_TZ))
            with col_keyword:
                log_search = st.text_input("🔍 關鍵字過濾 (物品名稱)", placeholder="例如：洗髮精...")

            target_date_str = selected_date.strftime("%Y-%m-%d")
            
            # 先進行日期過濾
            df_filtered_base = df_log[df_log["時間"].str.startswith(target_date_str, na=False)]
            if log_search.strip():
                df_filtered_base = df_filtered_base[df_filtered_base["物品名稱"].str.contains(log_search.strip(), case=False, na=False)]

            # 分類展示頁籤（進貨與生產分開顯示）
            log_tab_in, log_tab_prod, log_tab_out, log_tab_all = st.tabs([
                "📥 進貨紀錄", "🧪 生產紀錄", "📦 出貨紀錄", "🌐 全部異動"
            ])

            def render_log_table(data_frame, category_label):
                if data_frame.empty:
                    st.caption(f"🗓️ {target_date_str} 無【{category_label}】紀錄。")
                else:
                    st.caption(f"顯示日期：**{target_date_str}**（{category_label} 共 {len(data_frame)} 筆）")
                    st.dataframe(data_frame.iloc[::-1], use_container_width=True, height=220)

            # 1. 僅顯示進貨紀錄
            with log_tab_in:
                df_in = df_filtered_base[df_filtered_base["類型"] == "📥 物品進貨"]
                render_log_table(df_in, "物品進貨")

            # 2. 僅顯示生產紀錄
            with log_tab_prod:
                df_prod = df_filtered_base[df_filtered_base["類型"] == "🧪 生產完工"]
                render_log_table(df_prod, "生產完工")

            # 3. 僅顯示出貨紀錄
            with log_tab_out:
                df_out = df_filtered_base[df_filtered_base["類型"] == "📦 物品出庫"]
                render_log_table(df_out, "物品出貨")

            # 4. 全部異動紀錄
            with log_tab_all:
                render_log_table(df_filtered_base, "全部異動")

        else
