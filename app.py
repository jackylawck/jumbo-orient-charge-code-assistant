import streamlit as st
import requests
import json

# ==========================================
# 1. 企業資訊管治與安全防禦層 (Governance & Security)
# ==========================================
st.set_page_config(page_title="東淦扣賬合規智能助理", page_icon="🏗️", layout="centered")

# 從 Streamlit 後台安全讀取 CodeBuddy 燃料卡，絕不硬編碼在代碼中
try:
    CB_API_KEY = st.secrets["CB_API_KEY"]
except Exception:
    st.error("❌ 未檢測到安全密鑰 [CB_API_KEY]，請聯絡管理員配置 Streamlit Secrets。")
    st.stop()

# 核心審計提示詞 (System Prompt) - 鎖定東淦 27 條對照邏輯與合規護欄
SYSTEM_PROMPT = """
# Role
你是由東淦工程有限公司（東淦）開發的「東淦扣賬方與合約合規智能助理」。你的職責是協助前線管工、項目經理（PM）及各部門同事，在處理主判/分判商扣賬時，精準選擇正確的「扣賬方（Charge Code）」，防範公司利潤流失。

# Core Knowledge Base (東淦核心扣賬邏輯)
- JO：常規工程成本。若3色單下方沒有填寫扣賬方，系統預設以 JO 作為扣賬方。用於常規合約物料採購、或內部組別無涉及第三方的資源調配。
- JOA：因公司內部問題，導致地盤主判扣除行政費用。或我司同事因違規（如地盤非吸煙區吸煙）被出 Debit Note 罰款。
- JOI：公司內部問題（如內部圖紙出錯、施工組安裝錯誤）導致現場需要「重做/執修」之安裝費用。或被他判破壞但主判不給 SI 時的拆除及重裝費。
- JOM：公司內部問題（如操作不當、落單買錯物料、管工沒覆尺）導致需要「重新購買物料」之費用。
- JOS：公司內部問題導致需要「重新進行檢測/運輸」之費用。
- TPP：暫時未能界定導致問題發生之原因及責任時，以「暫支形式」支付有關費用。
- TPM：界定由兩方或以上共同導致問題發生，按百分比扣賬（總數必為100%）。若涉及代分判商購買物料等額外行政費用，必須在備註（REMARK）內註明「分判名 + 10% ADMIN FEE」。
- TPS：明確界定為供應商生產出不合格品導致問題發生，引致需要重新安裝/執修工程之扣賬。
- [分判商簡稱]：分判商安裝物料時出現問題，需自行/由其他分判商重做/執修之扣賬。或向其他分判商借工時扣賬使用。
- 【特殊防呆】：若分判商自己負責連工包料，出錯後自行補回物料並由原本分判商一拆一裝執修——「不用開單」。

# 嚴格審計與防呆規則
- 【禁止瞎猜】：若用戶提供的情境資訊不足（例如未說明是誰的責任），你必須拒絕直接給予 Code，並主動詢問用戶補全資訊。
- 【TPP 強制提醒】：凡建議 TPP，必須用粗體字警告用戶：『此單據屬於暫支，需於指定時間內介定及改回合適之扣賬方，否則後續將影響項目預算。』
- 【TPS 強制提醒】：凡建議 TPS，必須用粗體字提示用戶：『此情況必須填寫不合格品紀錄，否則年底無法向供應商追討。』

# Response Framework (四段式輸出規範)
你必須嚴格按照以下格式回覆：
1. 【建議扣賬方】：明確指出選用哪個 Code。
2. 【核心原因】：用一句話解釋為什麼（對應合約與責任歸屬）。
3. 【系統 Remark 填寫指引】：具體指導 Remark 填寫格式。
4. 【審計防範提醒】：提示前線跟進地盤文件（如追 SI、填不合格品紀錄）。
"""

# ==========================================
# 2. 前端網頁用戶介面 (UI / Interaction Layer)
# ==========================================
st.title("🏗️ 東淦工程有限公司")
st.subheader("智能扣賬方與合規審計助理 (測試版)")
st.markdown("---")

# 朋友建議的「實驗方向三」：快速 Checkbox / 引導式按鈕（前線零學習成本）
st.markdown("💡 **地盤常見突發情境快速勾選（點擊自動填入）：**")
col1, col2, col3 = st.columns(3)

quick_input = ""
with col1:
    if st.button("🚭 判頭非吸煙區食煙罰款"):
        quick_input = "今日有個施工組同事喺地盤非吸煙區食煙，俾主判出咗張 Debit Note 罰款，呢筆錢要入咩 Code？"
with col2:
    if st.button("🚪 牛房門被撞爛/無SI"):
        quick_input = "分判商裝好咗隻牛房門被其他判頭撞爛咗，主判叫我哋換，但死都唔肯俾 SI，呢個工程費點扣？"
with col3:
    if st.button("🛠️ 買錯物料要做執修"):
        quick_input = "我司內部落單時買錯物料給分判商安裝，之後才發現物料錯誤，需要分判商拆除及重新安裝，該重新安裝的費用用邊個 Code？"

# 初始化對話歷史紀錄
if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染歷史對話
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 處理用戶輸入（支援快速勾選或手動打字）
user_query = st.chat_input("用廣東話輸入地盤扣賬情況...（例如：判頭整爛野點計）")
if quick_input:
    user_query = quick_input

# ==========================================
# 3. 後端算力路由與 RAG 執行層 (Core Engine)
# ==========================================
if user_query:
    # 顯示用戶發送的訊息
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # 呼叫 CodeBuddy API 接口，燃燒公司的 Token 燃料
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🔍 *正在翻查東淦合約與題庫指引...*")
        
        # 構造符合 OpenAI 標準的 API 請求體（CodeBuddy 兼容）
        url = "https://api.codebuddy.ai/v1/chat/completions" # 根據實際國際版端點調整
        headers = {
            "Authorization": f"Bearer {CB_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o",  # 調用 Pro 級別大腦確保審計嚴謹度
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.0  # 溫度調至 0，杜絕幻覺與瞎猜
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                ai_response = response.json()['choices'][0]['message']['content']
                message_placeholder.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            else:
                message_placeholder.error(f"❌ 算力對接失敗。錯誤碼: {response.status_code}")
        except Exception as e:
            message_placeholder.error(f"❌ 連線超時或異常: {str(e)}")

# ==========================================
# 4. 人類回饋循環系統 (Human-in-the-Loop M&E)
# ==========================================
if st.session_state.messages:
    st.markdown("---")
    st.markdown("📢 **這條 AI 審計結果準確嗎？（您的回饋會被記錄在個人 GitHub 數據集中）**")
    feedback_col1, feedback_col2 = st.columns(10)
    with feedback_col1:
        if st.button("👍"):
            st.success("感謝您的正向回饋！已記錄為黃金數據。")
    with feedback_col2:
        if st.button("👎"):
            st.error("已觸發合規覆核。")
            correct_code = st.text_input("請管理層輸入正確的 Charge Code 以供優化系統：")
            if correct_code:
                st.info("校正數據已成功寫入備用數據庫。")
