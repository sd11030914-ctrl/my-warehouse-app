import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 設定網頁標題
st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")
st.title("📦 雲端倉庫管理系統 (直覺操作版)")

# 建立與 Google Sheets 的安全連接
conn = st.connection("gsheets", type=GSheetsConnection)

# 讀取雲端最新資料
def get_current_data():
    # ttl=0 代表不使用快取，每次都抓最新資料
    df = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], ttl=0)
    df.columns = df.columns.str.strip()
    # 確保數量是數字型態
    df["庫存數量"] = pd.to_numeric(df["庫存數量"], errors='coerce').fillna(0).astype(int)
    return df

# 寫入雲端資料
def update_cloud_data(df):
    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
    st.toast("雲端資料同步成功！", icon="☁️")

# 獲取目前最新庫存
df_inventory = get_current_data()

# 側邊欄功能選單
st.sidebar.header("功能選單")
action = st.sidebar.radio("請選擇操作項目：", ["📋 當前庫存盤點", "📥 物品進貨 (入庫)", "📦 物品出庫"])

# --- 1. 查看庫存 ---
if action == "📋 當前庫存盤點":
    st.subheader("📋 當前倉庫庫存盤點表")
    if st.button("🔄 刷新最新資料"):
        st.clear_cache()
        st.rerun()
        
    if df_inventory.empty:
        st.info("目前倉庫內沒有任何貨物。")
    else:
        st.dataframe(df_inventory, use_container_width=True)
        total_items = df_inventory["庫存數量"].sum()
        st.metric(label="倉庫貨物總數量", value=f"{total_items} 件")

# --- 2. 物品進貨 ---
elif action == "📥 物品進貨 (入庫)":
    st.subheader("📥 新生物資 / 追加庫存")
    
    with st.form("in_form", clear_on_submit=True):
        item_name = st.text_input("物品名稱", placeholder="例如：螺絲 A")
        quantity = st.number_input("進貨數量", min_value=1, value=1, step=1)
        
        st.write("--- 🗺️ 指定擺放儲位 ---")
        col1, col2, col3 = st.columns(3)
        with col1:
            zone = st.selectbox("區域", ["A 區", "B 區", "C 區", "D 區"])
        with col2:
            shelf = st.text_input("貨架編號", value="01", max_chars=2)
        with col3:
            level = st.selectbox("層級", ["1層", "2層", "3層", "4層"])
            
        submit_btn = st.form_submit_button("確認進貨入庫")
        
        if submit_btn:
            if not item_name.strip():
                st.error("❌ 請輸入物品名稱！")
            else:
                location = f"{zone}-{shelf}-{level}"
                # 檢查是否已有相同物品在相同儲位
                mask = (df_inventory["物品名稱"] == item_name) & (df_inventory["儲位"] == location)
                
                if mask.any():
                    df_inventory.loc[mask, "庫存數量"] += quantity
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": quantity, "儲位": location}])
                    df_inventory = pd.concat([df_inventory, new_row], ignore_index=True)
                
                # 寫回雲端 Google Sheets
                update_cloud_data(df_inventory)
                st.success(f"🎉 成功入庫！【{item_name}】{quantity} 件，已放置於 {location}")

# --- 3. 物品出庫 ---
elif action == "📦 物品出庫":
    st.subheader("📦 物品出庫登記")
    
    if df_inventory.empty:
        st.warning("倉庫目前沒有貨物可以出庫。")
    else:
        # 建立選項清單：物品名稱 (位置)
        item_options = df_inventory.apply(lambda r: f"{r['物品名稱']} (位置: {r['儲位']})", axis=1).tolist()
        selected_option = st.selectbox("請選擇要出庫的物品與儲位：", item_options)
        
        selected_idx = item_options.index(selected_option)
        current_item = df_inventory.iloc[selected_idx]
        max_qty = int(current_item["庫存數量"])
        
        remove_qty = st.number_input(f"請輸入出庫數量 (目前該儲位剩餘 {max_qty} 件)：", min_value=1, max_value=max_qty, value=1, step=1)
        
        if st.button("確認扣除庫存並出庫"):
            df_inventory.loc[selected_idx, "庫存數量"] -= remove_qty
            
            # 如果數量扣到 0，就從表格中移除這筆記錄
            if df_inventory.loc[selected_idx, "庫存數量"] == 0:
                df_inventory = df_inventory.drop(selected_idx).reset_index(drop=True)
                st.info(f"💡 提示：{current_item['物品名稱']} 在該儲位的庫存已清空。")
                
            # 寫回雲端 Google Sheets
            update_cloud_data(df_inventory)
            st.success(f"✅ 出庫成功！順利扣除【{current_item['物品名稱']}】共 {remove_qty} 件。")
