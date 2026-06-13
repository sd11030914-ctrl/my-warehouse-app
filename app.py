import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import pytz

st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")
st.title("📦 雲端倉庫管理系統")
st.markdown("---")

SPREADSHEET_ID = "1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ"

# 設定台灣時間
def get_now_time_str():
    tw_tz = pytz.timezone('Asia/Taipei')
    return datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')

def get_sheets_client():
    info = json.loads(st.secrets["google_json"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def load_data():
    try:
        gc = get_sheets_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 1:
            return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])
        
        headers = [str(h).strip() for h in all_values[0]]
        if len(all_values) == 1:
            return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])
            
        df = pd.DataFrame(all_values[1:], columns=headers)
        if "物品名稱" in df.columns and "庫存數量" in df.columns and "儲位" in df.columns:
            df = df[["物品名稱", "庫存數量", "儲位"]]
            df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)
            return df
        else:
            df.columns = ["物品名稱", "庫存數量", "儲位"] + list(df.columns[3:])
            df = df[["物品名稱", "庫存數量", "儲位"]]
            df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)
            return df
    except Exception as e:
        st.error(f"連線異常: {e}")
        return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])

# 💡 新增：讀取第二個分頁（歷史紀錄）
def load_history():
    try:
        gc = get_sheets_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 如果歷史紀錄工作表不存在，自動建立一個
        try:
            worksheet = sh.worksheet("歷史紀錄")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="歷史紀錄", rows="100", cols="5")
            worksheet.update(range_name="A1", values=[["異動時間", "類型", "物品名稱", "異動數量", "儲位"]])
            
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) < 1:
            return pd.DataFrame(columns=["異動時間", "類型", "物品名稱", "異動數量", "儲位"])
            
        headers = [str(h).strip() for h in all_values[0]]
        if len(all_values) == 1:
            return pd.DataFrame(columns=["異動時間", "類型", "物品名稱", "異動數量", "儲位"])
            
        df = pd.DataFrame(all_values[1:], columns=headers)
        # 讓最新時間的紀錄排在最上面，方便看
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except:
        return pd.DataFrame(columns=["異動時間", "類型", "物品名稱", "異動數量", "儲位"])

def update_cloud_data(df):
    try:
        gc = get_sheets_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        worksheet.clear()
        
        clean_df = df.copy()
        clean_df["庫存數量"] = clean_df["庫存數量"].astype(int)
        
        headers = ["物品名稱", "庫存數量", "儲位"]
        rows = clean_df[["物品名稱", "庫存數量", "儲位"]].values.tolist()
        
        worksheet.update(range_name="A1", values=[headers] + rows)
    except Exception as e:
        st.error(f"同步失敗: {e}")

# 💡 新增：將進出貨時間與動作寫入歷史紀錄分頁
def add_history_log(action_type, item_name, qty, location):
    try:
        gc = get_sheets_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("歷史紀錄")
        time_str = get_now_time_str()
        worksheet.append_row([time_str, action_type, item_name, str(qty), location])
    except:
        pass

df_inventory = load_data()

tab1, tab2, tab3 = st.tabs(["📋 當前庫存盤點", "📥 物品快捷進貨", "📦 物品快捷出庫"])

# === 📋 標籤頁 1：當前庫存盤點 (內建即時歷史日誌看版) ===
with tab1:
    st.subheader("📋 倉庫即時庫存表")
    
    search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
    with search_col1:
        search_query = st.text_input("🔍 快捷搜尋物品名稱", placeholder="輸入名稱關鍵字...")
    with search_col2:
        filter_zone = st.selectbox("🗺️ 按區域過濾", ["全部區域", "A 區", "B 區", "C 區", "D 區"])
    with search_col3:
        st.write("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 刷新數據", use_container_width=True):
            st.rerun()
            
    df_filtered = df_inventory.copy()
    if search_query.strip():
        df_filtered = df_filtered[df_filtered["物品名稱"].str.contains(search_query, case=False, na=False)]
    if filter_zone != "全部區域":
        df_filtered = df_filtered[df_filtered["儲位"].str.contains(filter_zone, na=False)]

    if df_filtered.empty:
        st.info("💡 沒有找到符合搜尋條件的貨物。")
    else:
        st.dataframe(df_filtered, width='stretch')
        total_items = df_filtered["庫存數量"].sum()
        unique_items = len(df_filtered)
        
        stat_col1, stat_col2 = st.columns(2)
        with stat_col1: st.metric(label="目前顯示的貨物總數量", value=f"{total_items} 件")
        with stat_col2: st.metric(label="目前顯示的品項種類", value=f"{unique_items} 種")
        
    # 💡 亮點功能：直接在首頁下方秀出「歷史異動時間紀錄」
    st.markdown("---")
    st.subheader("📜 歷史進出貨時間日誌 (最新紀錄排最前)")
    df_hist = load_history()
    if df_hist.empty:
        st.info("目前尚無進出貨時間紀錄。")
    else:
        st.dataframe(df_hist, width='stretch')

# === 📥 標籤頁 2：物品快捷進貨 ===
with tab2:
    st.subheader("📥 貨物入庫登記")
    with st.form("in_form", clear_on_submit=True):
        item_name = st.text_input("物品名稱", placeholder="輸入物品名稱")
        quantity = st.number_input("進貨數量", min_value=1, value=1, step=1)
        st.write("---")
        st.write("📍 指定儲位")
        col1, col2, col3 = st.columns(3)
        with col1: zone = st.selectbox("區域", ["A 區", "B 區", "C 區", "D 區"])
        with col2: shelf = st.text_input("貨架", value="01", max_chars=2)
        with col3: level = st.selectbox("層級", ["1層", "2層", "3層", "4層"])
        submit_btn = st.form_submit_button("確認快速入庫 (將自動記錄時間)", use_container_width=True)
        
        if submit_btn:
            if not item_name.strip():
                st.error("❌ 請輸入物品名稱")
            else:
                location = f"{zone}-{shelf}-{level}"
                mask = (df_inventory["物品名稱"] == item_name) & (df_inventory["儲位"] == location)
                if mask.any():
                    df_inventory.loc[mask, "庫存數量"] += quantity
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": quantity, "儲位": location}])
                    df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                
                # 寫回總庫存
                update_cloud_data(df_inventory)
                # 💡 自動寫入進貨時間紀錄
                add_history_log("📥 入庫", item_name, f"+{quantity}", location)
                st.success(f"🎉 {item_name} 入庫成功！時間已自動記錄。")
                st.rerun()

# === 📦 標籤頁 3：物品快捷出庫 ===
with tab3:
    st.subheader("📦 貨物出庫登記")
    if df_inventory.empty:
        st.warning("倉庫目前無貨可出。")
    else:
        item_options = df_inventory.apply(lambda r: f"{r['物品名稱']} ({r['儲位']})", axis=1).tolist()
        selected_option = st.selectbox("選擇出庫物品：", item_options)
        selected_idx = item_options.index(selected_option)
        current_item = df_inventory.iloc[selected_idx]
        max_qty = int(current_item["庫存數量"])
        remove_qty = st.number_input(f"出庫數量 (庫存剩餘 {max_qty})：", min_value=1, max_value=max_qty, value=1, step=1)
        
        if st.button("確認快速出庫 (將自動記錄時間)", use_container_width=True):
            df_inventory.loc[selected_idx, "庫存數量"] -= remove_qty
            location_saved = current_item['儲位']
            item_name_saved = current_item['物品名稱']
            
            if df_inventory.loc[selected_idx, "庫存數量"] == 0:
                df_inventory = df_inventory.drop(selected_idx).reset_index(drop=True)
                
            # 寫回總庫存
            update_cloud_data(df_inventory)
            # 💡 自動寫入出貨時間紀錄
            add_history_log("📦 出庫", item_name_saved, f"-{remove_qty}", location_saved)
            st.success(f"✅ {item_name_saved} 出庫成功！時間已自動記錄。")
            st.rerun()
