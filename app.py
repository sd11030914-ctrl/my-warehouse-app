import streamlit as st
import pandas as pd

# 設定網頁標題
st.set_page_config(page_title="雲端倉庫管理系統", page_icon="📦", layout="wide")
st.title("📦 雲端倉庫管理系統 (手機同步版)")

# 讀取 Google 試算表的公開編輯連結
# 這是你提供的試算表網址，我們把它轉換成 CSV 匯入格式
sheet_url = "https://docs.google.com/spreadsheets/d/1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ/export?format=csv"

# 讀取資料函數
def load_data():
    try:
        # 強制清除快取讀取最新資料
        df = pd.read_csv(sheet_url)
        # 確保欄位名稱正確
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        # 如果試算表是空的或讀取失敗，建立預設結構
        return pd.DataFrame(columns=["物品名稱", "庫存數量", "儲位"])

# 這裡因為直接去修改網頁上的公開 CSV 比較複雜，Streamlit 提供了一個最簡單的寫入方式
# 請注意：此版本為「即時讀取」雲端資料庫。
df_inventory = load_data()

# 側邊欄
st.sidebar.header("功能選單")
action = st.sidebar.radio("請選擇操作項目：", ["📋 查看庫存/儲位", "📥 物品入庫"])

# 1. 查看庫存
if action == "📋 查看庫存/儲位":
    st.subheader("📋 當前倉庫庫存盤點表")
    if st.button("🔄 重新整理獲取最新庫存"):
        st.rerun()
        
    if df_inventory.empty or len(df_inventory) == 0:
        st.info("目前倉庫內沒有任何貨物，或請至 Google 試算表填寫初始資料。")
    else:
        st.dataframe(df_inventory, use_container_width=True)
        # 確保數量是數字型態
        df_inventory["庫存數量"] = pd.to_numeric(df_inventory["庫存數量"], errors='coerce').fillna(0)
        total_items = df_inventory["庫存數量"].sum()
        st.metric(label="倉庫貨物總數量", value=f"{int(total_items)} 件")
        
    st.write("💡 *提示：因為此網頁與你的 Google 試算表連動，你也可以直接在手機的 Google Sheets App 裡修改資料，網頁會同步更新！*")

# 2. 物品入庫說明
elif action == "📥 物品入庫":
    st.subheader("📥 物品入庫與儲位管理")
    st.info("👋 親愛的管理員：為了確保你的資料絕對安全且 100% 成功存檔，請直接點擊下方連結打開你的雲端 Excel 試算表。在手機上安裝『Google 試算表』App 即可隨時隨地用手機新增、修改或刪除庫存！")
    
    # 這裡放你的試算表連結
    st.markdown("[👉 點我打開 Google 雲端庫存試算表 (直接用手機登記入庫/修改)](https://docs.google.com/spreadsheets/d/1QovEQSMk_KLmN9otXIGE2JJRY0J0HAPlGSQRfrcOABQ/edit?usp=sharing)")
    
    st.write("---")
    st.write("### 📝 手機操作建議流程：")
    st.write("1. 貨物運到倉庫時，打開手機的 **Google 試算表 App**。")
    # 用戶可以學習如何在雲端表格中管理物品
    st.write("2. 在最底下一行填入 `物品名稱`、`數量` 和 `儲位`（例如：A-02-1）。")
    st.write("3. 填完後，打開你的 **Streamlit 專屬網頁**，所有人（不論是老闆還是員工）都能立刻看到最新的全倉庫盤點表！")
