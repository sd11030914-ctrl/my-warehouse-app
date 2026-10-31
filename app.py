import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import pytz
import streamlit.components.v1 as components
import time

# 設定台灣時區
TW_TZ = pytz.timezone('Asia/Taipei')

# Google 試算表設定 (倉庫資料庫)
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

# 初始化 Session State (計瓶器所需)
if 'batch_item' not in st.session_state:
    st.session_state.batch_item = ""
if 'batch_count' not in st.session_state:
    st.session_state.batch_count = 0
if 'last_completed_item' not in st.session_state:
    st.session_state.last_completed_item = ""
if 'last_completed_count' not in st.session_state:
    st.session_state.last_completed_count = 0

# 原生網頁設定
st.set_page_config(page_title="雲端倉庫與生產管理系統", page_icon="📦", layout="wide")

# --- 核心：獨立裝置字體放大功能 + 疊加數量按鈕藍色化 ---
custom_js = """
<script>
    const savedSize = window.localStorage.getItem('device_font_size');
    if (savedSize) {
        window.parent.document.documentElement.style.fontSize = savedSize + 'px';
    }

    const observer = new MutationObserver(() => {
        const btns = window.parent.document.querySelectorAll('button');
        btns.forEach(btn => {
            if (btn.innerText && btn.innerText.includes('疊加數量')) {
                btn.style.backgroundColor = '#007BFF';
                btn.style.color = 'white';
                btn.style.borderColor = '#007BFF';
            }
        });
    });
    observer.observe(window.parent.document.body, {childList: true, subtree: true});
</script>
"""
components.html(custom_js, height=0, width=0)

st.title("⚡ 雲端倉庫與生產管理系統")

# 主功能頁籤分頁
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 當前總庫存", "📥 物品進貨", "📦 物品出庫", "🧪 即時生產計數", "⚙️ 其他"])

# --- 1. 當前總庫存與歷史紀錄 ---
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
            zone_filter = st.text_input("🗺️ 按存放地點/關鍵字過濾：", placeholder="例如：A區...")

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
            
            col_date, col_keyword = st.columns([1, 2])
            with col_date:
                selected_date = st.date_input("📅 選擇日誌日期", value=datetime.now(TW_TZ))
            with col_keyword:
                log_search = st.text_input("🔍 關鍵字過濾 (物品名稱)", placeholder="例如：洗髮精...")

            target_date_str = selected_date.strftime("%Y-%m-%d")
            
            df_filtered_base = df_log[df_log["時間"].str.startswith(target_date_str, na=False)]
            if log_search.strip():
                df_filtered_base = df_filtered_base[df_filtered_base["物品名稱"].str.contains(log_search.strip(), case=False, na=False)]

            log_tab_in, log_tab_prod, log_tab_out, log_tab_all = st.tabs([
                "📥 進貨紀錄", "🧪 生產紀錄", "📦 出貨紀錄", "🌐 全部異動"
            ])

            def render_log_table(data_frame, category_label):
                if data_frame.empty:
                    st.caption(f"🗓️ {target_date_str} 無【{category_label}】紀錄。")
                else:
                    st.caption(f"顯示日期：**{target_date_str}**（{category_label} 共 {len(data_frame)} 筆）")
                    st.dataframe(data_frame.iloc[::-1], use_container_width=True, height=220)

            with log_tab_in:
                df_in = df_filtered_base[df_filtered_base["類型"] == "📥 物品進貨"]
                render_log_table(df_in, "物品進貨")

            with log_tab_prod:
                df_prod = df_filtered_base[df_filtered_base["類型"] == "🧪 生產完工"]
                render_log_table(df_prod, "生產完工")

            with log_tab_out:
                df_out = df_filtered_base[df_filtered_base["類型"] == "📦 物品出庫"]
                render_log_table(df_out, "物品出貨")

            with log_tab_all:
                render_log_table(df_filtered_base, "全部異動")

        else:
            st.caption("尚無歷史異動紀錄。")
    except Exception as e:
        st.caption("載入歷史紀錄失敗。")

# --- 2. 物品進貨 ---
with tab2:
    st.subheader("📥 物品進貨登記")
    with st.form("inbound_form", clear_on_submit=True):
        inbound_item = st.text_input("物品/產品名稱", placeholder="例如：洗髮精 A")
        inbound_qty = st.number_input("進貨數量", min_value=1, value=1, step=1)
        inbound_location = st.text_input("存放地點 / 儲位", placeholder="例如：A區-01架...")
        
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
                
                # 新增的提示訊息
                st.balloons()
                st.success("✅ **已經確定進貨！**")
                st.info(f"詳細資訊：【{item_name}】新增 {inbound_qty} 件，目前總庫存為 {final_qty} 件。")
                time.sleep(2) # 讓提示訊息停留兩秒
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
            
            st.success(f"✅ 出貨成功！順利扣除【{current_item['物品名稱']}】{remove_qty} 件，當前庫存為 {remaining_qty} 件。")
            st.rerun()

# --- 4. 即時生產計數 ---
with tab4:
    st.subheader("🧪 產品製作與計瓶器")
    
    if st.session_state.last_completed_item:
        st.info(f"⏮️ **上次完成紀錄**：【{st.session_state.last_completed_item}】共製作了 **{st.session_state.last_completed_count}** 瓶")
    
    if st.session_state.batch_count > 0 or st.session_state.batch_item:
        st.success(f"📌 **當前生產中產品**：【{st.session_state.batch_item}】｜ 當前累計：**{st.session_state.batch_count}** 瓶")
    else:
        st.caption("⚠️ 目前尚未開始任何產品的計數。")

    st.write("---")
    
    item_input = st.text_input("產品名稱", value=st.session_state.batch_item, placeholder="例如：洗髮精 A")
    add_qty = st.number_input("本次製作數量 (瓶)", min_value=1, value=1, step=1)

    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("➕ 疊加數量"):
            if not item_input.strip():
                st.error("❌ 請輸入產品名稱！")
            else:
                st.session_state.batch_item = item_input.strip()
                st.session_state.batch_count += add_qty
                st.toast(f"已累加 {add_qty} 瓶！目前共 {st.session_state.batch_count} 瓶", icon="🧪")
                st.rerun()

    with btn_col2:
        if st.button("✅ 完成此產品", type="primary"):
            if st.session_state.batch_count == 0:
                st.error("❌ 當前累計瓶數為 0，無法結算！請先點擊「疊加數量」。")
            else:
                df = get_current_data()
                item_name = st.session_state.batch_item
                added_qty = st.session_state.batch_count
                default_loc = "未指定儲位"
                
                mask = (df["物品名稱"] == item_name)
                if mask.any():
                    df.loc[mask, "庫存數量"] += added_qty
                    final_qty = int(df.loc[mask, "庫存數量"].values[0])
                else:
                    new_row = pd.DataFrame([{"物品名稱": item_name, "庫存數量": added_qty, "儲位": default_loc}])
                    df = pd.concat([df, new_row], ignore_index=True)
                    final_qty = added_qty
                
                save_all_data(df)
                log_history("🧪 生產完工", item_name, f"+{added_qty}", final_qty, default_loc)
                
                st.session_state.last_completed_item = item_name
                st.session_state.last_completed_count = added_qty
                
                st.success(f"🎉 成功完成！【{item_name}】本次新增 {added_qty} 瓶，目前總庫存為 {final_qty} 瓶！")
                
                st.session_state.batch_item = ""
                st.session_state.batch_count = 0
                st.rerun()

# --- 5. 其他 (獨立字體設定) ---
with tab5:
    st.subheader("⚙️ 獨立裝置設定 (僅限本機)")
    st.info("💡 這裡的字體大小調整只會記憶在「您現在使用的這台手機或電腦」上，其他人的畫面與系統資料完全不受影響。")
    
    selected_font_size = st.slider("調整畫面字體與版面倍率：", min_value=12, max_value=32, value=16, step=1)
    
    if st.button("💾 套用並記憶字體大小", type="primary"):
        save_font_js = f"""
        <script>
            window.parent.document.documentElement.style.fontSize = '{selected_font_size}px';
            window.localStorage.setItem('device_font_size', '{selected_font_size}');
        </script>
        """
        components.html(save_font_js, height=0, width=0)
        st.success(f"✅ 成功！這台裝置的基準字體已設定為 {selected_font_size}px。")
