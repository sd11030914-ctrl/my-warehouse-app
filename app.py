import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# 1. 修改網頁分頁標題
st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")

# 2. 修改主標題，拿掉括號，讓介面更正式
st.title("📦 雲端倉庫管理系統")

# 你的試算表唯一 ID
SPREADSHEET_ID = "1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ"

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
        st.toast("雲端資料已同步", icon="✅")
    except Exception as e:
        st.error(f"同步失敗: {e}")

df_inventory = load_data()

# 側邊欄設定
st.sidebar.header("核心功能")
action = st.sidebar.radio("請選擇操作項目：", ["📋 當前庫存盤點", "📥 物品進貨", "📦 物品出庫"])

if action == "📋 當前庫存盤點":
    st.subheader("📋 倉庫即時庫存表")
    if st.button("🔄 刷新資料"):
        st.rerun()
    if df_inventory.empty:
        st.info("目前倉庫內沒有任何貨物。")
    else:
        st.dataframe(df_inventory, width='stretch')
        total_items = df_inventory["庫存數量"].sum()
        st.metric(label="倉庫貨物總數量", value=f"{total_items} 件")

elif action == "📥 物品進貨":
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
        submit_btn = st.form_submit_button("確認入庫")
        
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
                update_cloud_data(df_inventory)
                st.success(f"成功入庫")
                st.rerun()

elif action == "📦 物品出庫":
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
        
        if st.button("確認出庫"):
            df_inventory.loc[selected_idx, "庫存數量"] -= remove_qty
            if df_inventory.loc[selected_idx, "庫存數量"] == 0:
                df_inventory = df_inventory.drop(selected_idx).reset_index(drop=True)
            update_cloud_data(df_inventory)
            st.success(f"已完成出庫")
            st.rerun()
