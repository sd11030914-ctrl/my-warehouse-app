import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")
st.title("📦 雲端倉庫管理系統 (終極直覺版)")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ/edit?usp=sharing"

@st.cache_resource(ttl=0)
def get_sheets_client():
    info = json.loads(st.secrets["google_json"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def load_data():
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])
        df = pd.DataFrame(data)
        df.columns = df.columns.str.strip()
        df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])

def update_cloud_data(df):
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.get_worksheet(0)
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.toast("雲端資料同步成功！", icon="☁️")
    except Exception as e:
        st.error(f"同步失敗: {e}")

df_inventory = load_data()

st.sidebar.header("功能選單")
action = st.sidebar.radio("請選擇操作項目：", ["📋 當前庫存盤點", "📥 物品進貨 (入庫)", "📦 物品出庫"])

if action == "📋 當前庫存盤點":
    st.subheader("📋 當前倉庫庫存盤點表")
    if st.button("🔄 刷新最新資料"):
        st.cache_resource.clear()
        st.rerun()
    if df_inventory.empty:
        st.info("目前倉庫內沒有任何貨物。")
    else:
        st.dataframe(df_inventory, use_container_width=True)
        total_items = df_inventory["庫存數量"].sum()
        st.metric(label="倉庫貨物總數量", value=f"{total_items} 件")

elif action == "📥 物品進貨 (入庫)":
    st.subheader("📥 新生物資 / 追加庫存")
    with st.form("in_form", clear_on_submit=True):
        item_name = st.text_input("物品名稱", placeholder="例如：螺絲 A")
        quantity = st.number_input("進貨數量", min_value=1, value=1, step=1)
        st.write("--- 🗺️ 指定擺放儲位 ---")
        col1, col2, col3 = st.columns(3)
        with col1: zone = st.selectbox("區域", ["A 區", "B 區", "C 區", "D 區"])
        with col2: shelf = st.text_input("貨架編號", value="01", max_chars=2)
        with col3: level = st.selectbox("層級", ["1層", "2層", "3層", "4層"])
        submit_btn = st.form_submit_button("確認進貨入庫")
        
        if submit_btn:
            if not item_name.strip():
                st.error("❌ 請輸入物品名稱！")
            else:
                location = f"{zone}-{shelf}-{level}"
                mask = (df_inventory["物品名稱"] == item_name) & (df_inventory["儲位"] == location)
                if mask.any():
                    df_inventory.loc[mask, "庫存數量"] += quantity
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": quantity, "儲位": location}])
                    df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                update_cloud_data(df_inventory)
                st.success(f"🎉 成功入庫！")

elif action == "📦 物品出庫":
    st.subheader("📦 物品出庫登記")
    if df_inventory.empty:
        st.warning("倉庫目前沒有貨物可以出庫。")
    else:
        item_options = df_inventory.apply(lambda r: f"{r['物品名稱']} (位置: {r['儲位']})", axis=1).tolist()
        selected_option = st.selectbox("請選擇要出庫的物品與儲位：", item_options)
        selected_idx = item_options.index(selected_option)
        current_item = df_inventory.iloc[selected_idx]
        max_qty = int(current_item["庫存數量"])
        remove_qty = st.number_input(f"請輸入出庫數量 (剩餘 {max_qty} 件)：", min_value=1, max_value=max_qty, value=1, step=1)
        
        if st.button("確認扣除庫存並出庫"):
            df_inventory.loc[selected_idx, "庫存數量"] -= remove_qty
            if df_inventory.loc[selected_idx, "庫存數量"] == 0:
                df_inventory = df_inventory.drop(selected_idx).reset_index(drop=True)
            update_cloud_data(df_inventory)
            st.success(f"✅ 出庫成功！")
