import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import pytz

# 設定台灣時區
TW_TZ = pytz.timezone('Asia/Taipei')

# 1. Google 試算表驗證與連接
SPREADSHEET_ID = "1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ"[cite: 1]

@st.cache_resource
def get_gspread_client():
    secrets_dict = json.loads(st.secrets["google_json"])[cite: 1]
    return gspread.service_account_from_dict(secrets_dict)

def get_worksheet(sheet_name="工作表1"):
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except:
        if sheet_name == "歷史紀錄":
            ws = sh.add_worksheet(title="歷史紀錄", rows="100", cols="5")
            ws.append_row(["時間", "類型", "物品名稱", "數量", "位置/儲位"])
            return ws
        return sh.sheet1

def get_current_data():
    ws = get_worksheet("工作表1")
    data = ws.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])[cite: 1]
    df = pd.DataFrame(data[1:], columns=["物品名稱", "庫存數量", "儲位"])[cite: 1]
    df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)[cite: 1]
    return df

def save_all_data(df):
    ws = get_worksheet("工作表1")
    ws.clear()
    ws.append_row(["物品名稱", "庫存數量", "儲位"])[cite: 1]
    if not df.empty:
        ws.append_rows(df.astype(str).values.tolist())

def log_history(action_type, item_name, quantity, location):
    ws_log = get_worksheet("歷史紀錄")
    now_str = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")[cite: 1]
    ws_log.append_row([now_str, action_type, item_name, str(quantity), location])

# 初始化 session state 計數器
if 'batch_item' not in st.session_state:
    st.session_state.batch_item = ""
if 'batch_location' not in st.session_state:
    st.session_state.batch_location = ""
if 'batch_count' not in st.session_state:
    st.session_state.batch_count = 0

# 網頁UI設定
st.set_page_config(page_title="雲端倉庫與生產計數系統", page_icon="📦", layout="wide")[cite: 1]
st.title("📦 雲端倉庫與生產計數系統")[cite: 1]

# 使用橫向頁籤
tab1, tab2, tab3 = st.tabs(["📋 當前總庫存", "🧪 即時生產計數 (計瓶器)", "📦 物品出庫"])[cite: 1]

# --- 頁籤 1: 當前總庫存與歷史紀錄 ---
with tab1:
    st.subheader("📋 當前倉庫總庫存盤點表")[cite: 1]
    if st.button("🔄 刷新最新資料"):[cite: 1]
        st.cache_data.clear()
        st.rerun()

    df_inventory = get_current_data()
    if df_inventory.empty:
        st.info("目前倉庫內沒有任何貨物。")[cite: 1]
    else:
        col_search, col_filter = st.columns([2, 1])[cite: 1]
        with col_search:
            search_term = st.text_input("🔍 快捷搜尋物品名稱：", placeholder="例如：洗髮精...")[cite: 1]
        with col_filter:
            zone_filter = st.selectbox("🗺️ 按區域過濾：", ["全部區域", "A 區", "B 區", "C 區", "D 區", "主臥", "客廳", "儲藏室"])[cite: 1]

        filtered_df = df_inventory.copy()
        if search_term.strip():
            filtered_df = filtered_df[filtered_df["物品名稱"].str.contains(search_term, case=False, na=False)][cite: 1]
        if zone_filter != "全部區域":
            filtered_df = filtered_df[filtered_df["儲位"].str.contains(zone_filter, na=False)][cite: 1]

        st.dataframe(filtered_df, use_container_width=True)[cite: 1]
        st.metric(label="目前篩選貨物總瓶/件數", value=f"{filtered_df['庫存數量'].sum()} 件")[cite: 1]

    st.write("---")[cite: 1]
    st.subheader("📜 歷史進出貨與生產時間日誌")[cite: 1]
    try:
        ws_log = get_worksheet("歷史紀錄")
        log_data = ws_log.get_all_values()
        if len(log_data) > 1:
            df_log = pd.DataFrame(log_data[1:], columns=log_data[0])[cite: 1]
            st.dataframe(df_log.iloc[::-1], use_container_width=True, height=250)[cite: 1]
        else:
            st.caption("尚無歷史異動紀錄。")[cite: 1]
    except:
        st.caption("載入歷史紀錄失敗。")[cite: 1]

# --- 頁籤 2: 即時生產計數 (核心新功能) ---
with tab2:
    st.subheader("🧪 產品製作與計瓶器")[cite: 1]
    st.info("💡 說明：在製作同一款產品時，每次做好幾瓶就按一次「疊加數量」。等這批完全做完後，按下「完成本批次」就會一次性寫入雲端庫存！")[cite: 1]
    
    # 顯示目前正在記錄的產品狀態
    if st.session_state.batch_count > 0 or st.session_state.batch_item:
        st.success(f"📌 **當前生產中產品**：【{st.session_state.batch_item}】｜ 位置：{st.session_state.batch_location} ｜ 累計完成瓶數：**{st.session_state.batch_count}** 瓶")[cite: 1]
    else:
        st.warning("⚠️ 目前尚未開始任何產品的計數。")[cite: 1]

    st.write("---")[cite: 1]
    
    # 輸入表單
    item_input = st.text_input("物品/產品名稱", value=st.session_state.batch_item, placeholder="例如：洗髮精 A")[cite: 1]
    
    col_a, col_b = st.columns(2)[cite: 1]
    with col_a:
        zone_input = st.selectbox("擺放區域", ["A 區", "B 區", "C 區", "D 區", "主臥", "客廳", "儲藏室"])[cite: 1]
    with col_b:
        shelf_input = st.text_input("詳細位置/貨架", value="01")[cite: 1]

    location_str = f"{zone_input}-{shelf_input}"[cite: 1]
    add_qty = st.number_input("本次新增製作數量 (瓶)", min_value=1, value=1, step=1)[cite: 1]

    btn_col1, btn_col2 = st.columns(2)[cite: 1]
    
    # 疊加按鈕
    with btn_col1:
        if st.button("➕ 疊加數量到當前產品", use_container_width=True):[cite: 1]
            if not item_input.strip():
                st.error("❌ 請輸入產品名稱！")[cite: 1]
            else:
                # 鎖定產品名稱與地點
                st.session_state.batch_item = item_input.strip()[cite: 1]
                st.session_state.batch_location = location_str[cite: 1]
                st.session_state.batch_count += add_qty[cite: 1]
                st.toast(f"已累加 {add_qty} 瓶！目前共 {st.session_state.batch_count} 瓶", icon="🧪")[cite: 1]
                st.rerun()[cite: 1]

    # 完成按鈕
    with btn_col2:
        if st.button("✅ 完成本批次並寫入庫存", type="primary", use_container_width=True):[cite: 1]
            if st.session_state.batch_count == 0:
                st.error("❌ 當前累計瓶數為 0，無法結算！請先按下「疊加數量」。")[cite: 1]
            else:
                df = get_current_data()
                item_name = st.session_state.batch_item[cite: 1]
                loc = st.session_state.batch_location[cite: 1]
                total_qty = st.session_state.batch_count[cite: 1]
                
                # 檢查試算表是否已有相同品項與儲位
                mask = (df["物品名稱"] == item_name) & (df["儲位"] == loc)[cite: 1]
                if mask.any():
                    df.loc[mask, "庫存數量"] += total_qty[cite: 1]
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": total_qty, "儲位": loc}])[cite: 1]
                    df = pd.concat([df, new_row], ignore_index=True)[cite: 1]
                
                # 儲存至雲端
                save_all_data(df)[cite: 1]
                log_history("🧪 生產完工", item_name, total_qty, loc)[cite: 1]
                
                st.success(f"🎉 成功完成結算！【{item_name}】共 {total_qty} 瓶，已順利存入 {loc}！")[cite: 1]
                
                # 清空暫存，準備下一個產品
                st.session_state.batch_item = ""[cite: 1]
                st.session_state.batch_location = ""[cite: 1]
                st.session_state.batch_count = 0[cite: 1]
                st.rerun()[cite: 1]

# --- 頁籤 3: 物品出庫 ---
with tab3:
    st.subheader("📦 物品出庫登記")[cite: 1]
    df = get_current_data()
    if df.empty:
        st.warning("倉庫目前沒有貨物可以出庫。")[cite: 1]
    else:
        item_options = df.apply(lambda r: f"{r['物品名稱']} (位置: {r['儲位']}, 現有: {r['庫存數量']}件)", axis=1).tolist()[cite: 1]
        selected_option = st.selectbox("請選擇要出庫的物品：", item_options)[cite: 1]
        selected_idx = item_options.index(selected_option)[cite: 1]
        current_item = df.iloc[selected_idx][cite: 1]
        
        max_qty = int(current_item["庫存數量"])[cite: 1]
        remove_qty = st.number_input(f"出庫數量 (目前最多可出 {max_qty} 件)：", min_value=1, max_value=max_qty, value=1, step=1)[cite: 1]
        
        if st.button("確認出庫", type="primary"):[cite: 1]
            df.loc[selected_idx, "庫存數量"] -= remove_qty[cite: 1]
            if df.loc[selected_idx, "庫存數量"] == 0:
                df = df.drop(selected_idx).reset_index(drop=True)[cite: 1]
            
            save_all_data(df)[cite: 1]
            log_history("📦 物品出庫", current_item['物品名稱'], -remove_qty, current_item['儲位'])[cite: 1]
            
            st.success(f"✅ 出庫成功！順利扣除【{current_item['物品名稱']}】共 {remove_qty} 件。")[cite: 1]
            st.rerun()[cite: 1]
