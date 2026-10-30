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

# 原生網頁設定
st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")

st.title("📦 雲端倉庫管理系統")

# 主功能頁籤分頁
tab1, tab2, tab3 = st.tabs(["📋 當前總庫存", "📥 物品進貨", "📦 物品出庫"])

# --- 1. 當前總庫存與歷史日誌 ---
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
        st.metric(label="📊 目前篩選貨物總件數", value=f"{filtered_df['庫存數量'].sum()} 件")

    st.write("---")
    st.subheader("📜 歷史進出貨時間日誌")
    try:
        ws_log = get_worksheet("歷史紀錄")
        log_data = ws_log.get_all_values()
        if len(log_data) > 1:
            df_log = pd.DataFrame(log_data[1:], columns=log_data[0])
            st.dataframe(df_log.iloc[::-1], use_container_width=True, height=220)
        else:
            st.caption("尚無歷史進出貨紀錄。")
    except Exception as e:
        st.caption("載入歷史紀錄失敗。")

# --- 2. 物品進貨 ---
with tab2:
    st.subheader("📥 物品進貨登記")
    with st.form("inbound_form", clear_on_submit=True):
        inbound_item = st.text_input("物品/產品名稱", placeholder="例如：洗髮精")
        inbound_qty = st.number_input("進貨數量", min_value=1, value=1, step=1)
        inbound_location = st.text_input("存放地點 / 儲位", placeholder="例如：A區-01架、主臥抽屜...")
        
        submit_inbound = st.form_submit_button("確認進貨入庫", type="primary")
        
        if submit_inbound:
            if not inbound_item.strip():
                st.error("❌ 請輸入物品名稱！")
            else:
                df = get_current_data()
                item_name = inbound_item.strip()
                location_str = inbound_location.strip() if inbound_location.strip() else "未指定儲位"
                
                mask = (df["物品名稱"] == item_name)
                if mask.any():
                    df.loc[mask, "庫存數量"] += inbound_qty
                    df.loc[mask, "儲位"] = location_str
                    final_qty = int(df.loc[mask, "庫存數量"].values[0])
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": inbound_qty, "儲位": location_str}])
                    df = pd.concat([df, new_row], ignore_index=True)
                    final_qty = inbound_qty
                
                save_all_data(df)
                log_history("📥 物品進貨", item_name, f"+{inbound_qty}", final_qty, location_str)
                
                st.success(f"🎉 進貨成功！【{item_name}】新增 {inbound_qty} 件，存放地點：{location_str}，目前總庫存為 {final_qty} 件！")
                st.rerun()

# --- 3. 物品出庫 ---
with tab3:
    st.subheader("📦 物品出庫登記")
    df = get_current_data()
    if df.empty:
        st.warning("倉庫目前沒有貨物可以出庫。")
    else:
        item_options = df.apply(lambda r: f"{r['物品名稱']} (位置: {r['儲位']}, 現有: {r['庫存數量']}件)", axis=1).tolist()
        selected_option = st.selectbox("請選擇要出庫的物品：", item_options)
        selected_idx = item_options.index(selected_option)
        current_item = df.iloc[selected_idx]
        
        current_stock = int(current_item["庫存數量"])
        remove_qty = st.number_input(f"出貨數量 (目前最多可出 {current_stock} 件)：", min_value=1, max_value=current_stock, value=1, step=1)
        
        remaining_preview = current_stock - remove_qty
        st.info(f"💡 出貨後此物品剩餘庫存將自動更新為：**{remaining_preview}** 件")
        
        if st.button("確認出貨", type="primary"):
            df.loc[selected_idx, "庫存數量"] -= remove_qty
            remaining_qty = int(df.loc[selected_idx, "庫存數量"])
            
            if df.loc[selected_idx, "庫存數量"] == 0:
                df = df.drop(selected_idx).reset_index(drop=True)
            
            save_all_data(df)
            log_history("📦 物品出庫", current_item['物品名稱'], f"-{remove_qty}", remaining_qty, current_item['儲位'])
            
            st.success(f"✅ 出貨成功！順利扣除【{current_item['物品名稱']}】{remove_qty} 件，當前庫存已自動減少為 {remaining_qty} 件。")
            st.rerun()
