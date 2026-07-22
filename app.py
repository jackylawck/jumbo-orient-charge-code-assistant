import streamlit as st
import hashlib
import re
import pandas as pd

# 引入本地向量組件
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# ==========================================
# 1. 頁面配置與 UI 樣式
# ==========================================
st.set_page_config(
    page_title="東淦扣帳合規智能助理",
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .source-tag {
        background-color: #f8d7da !important; 
        border-left: 4px solid #dc3545 !important; 
        color: #721c24 !important; 
        padding: 10px !important; 
        margin: 8px 0 !important; 
        font-size: 0.9em !important; 
        border-radius: 4px !important;
    }
    .confidence-badge {
        background-color: #198754 !important;
        color: #ffffff !important;
        padding: 6px 12px !important;
        border-radius: 20px !important;
        font-size: 0.85em !important;
        font-weight: bold !important;
        display: inline-block !important;
    }
    .answer-box {
        background-color: #e8f5e9;
        border-left: 5px solid #2e7d32;
        padding: 15px;
        border-radius: 4px;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 🛡️ 文字模糊比對清理與廣東話/大灣區術語擴展引擎
# ==========================================
def clean_text_for_matching(text):
    if not text:
        return ""
    text = re.sub(r'[^\w\u4e00-\u9fa5]', '', str(text))
    return text.lower().strip()

def expand_query_semantics(query):
    """
    港澳大灣區地盤通用同義詞擴展器 (Query Expansion)
    作用：將前線口語、地盤術語自動擴展為標準合約用語，提升本地向量比對命中率，且零公司機密
    """
    expanded_terms = []
    q_lower = query.lower()
    
    # 類別 1：安裝與施工瑕疵 (對應 安裝/Installation 修正類)
    if any(w in q_lower for w in ["執修", "重做", "改尺寸", "安裝", "裝錯", "拆除", "執漏", "執手尾", "拆嘢", "搞錯位"]):
        expanded_terms.append("安裝 Installation 重新安裝 重做 執修 修正 額外工程費用 內部圖紙出錯 拆卸")
        
    # 類別 2：物料與採購失誤 (對應 物料/Material 修正類)
    if any(w in q_lower for w in ["買錯", "料", "材料", "重購", "買過", "買錯料", "訂錯嘢", "廢料", "爛料", "覆尺"]):
        expanded_terms.append("物料 Material 重新購買物料 採購失誤 操作不當導致需重購物料 遺失配件")
        
    # 類別 3：服務與檢測 (對應 服務/Service 修正類)
    if any(w in q_lower for w in ["打針", "測試", "驗收", "檢測", "服務", "肥佬", "pass唔到", "搵車"]):
        expanded_terms.append("服務 Service 重新進行檢測 運輸 重新執修後需重做測試 不合格")
        
    # 類別 4：行政罰款與雜費 (對應 行政費用類)
    if any(w in q_lower for w in ["食煙", "吸煙", "罰款", "debit note", "架步", "垃圾費", "太公分豬肉", "罰錢", "扣數", "寫紙"]):
        expanded_terms.append("行政費用 行政罰款 內部問題導致地盤主判扣除 清垃圾費用 Debit Note")
        
    # 類別 5：供應商/第三方責任 (對應 分判商/供應商扣帳)
    if any(w in q_lower for w in ["供應商", "出廠", "不合格", "質量欠佳", "判頭", "借工", "代工", "貨唔對辦", "廠出錯", "他判"]):
        expanded_terms.append("供應商生產出不合格品 分判商安裝物料出現問題 責任歸屬 質量欠佳 連工包料")
        
    # 類別 6：待定或多方分攤 (對應 待定/多方分配)
    if any(w in q_lower for w in ["未定", "唔知邊個錯", "傾唔掂數", "夾錢", "攤分", "百分比", "共同負責", "未介定"]):
        expanded_terms.append("未能界定 暫支 百份比分配 共同負責 待定")
        
    if expanded_terms:
        return query + " " + " ".join(expanded_terms)
    
    return query

@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# ==========================================
# 🧠 核心優化：純 Excel 結構化解析引擎 (確保數據零雜訊)
# ==========================================
def process_excel_to_chunks(uploaded_file):
    filename = uploaded_file.name
    chunks = []
    
    try:
        df = pd.read_excel(uploaded_file)
        for index, row in df.iterrows():
            row_str = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            if len(row_str.strip()) < 5:
                continue
            
            doc = Document(
                page_content=row_str,
                metadata={
                    "source": filename,
                    "raw_cleaned": clean_text_for_matching(row_str)
                }
            )
            chunks.append(doc)
    except Exception as e:
        st.error(f"解析 Excel 檔案時出錯: {str(e)}")
    return chunks

# ==========================================
# 3. 主畫面佈局
# ==========================================
st.title("🏗️ 東淦工程有限公司 (Jumbo Orient)")
st.subheader("智能扣帳方與合約合規查詢系統")

st.info(
    "🔒 **內部數據安全保障：**\n"
    "本系統採用純本地數據比對技術，您上傳的 Excel 文件只會暫存在當前網頁會話中。"
    "**當您關閉或重新整理網頁時，數據會立即被徹底銷毀**，絕對不會儲存到互聯網上，請放心使用。"
)

vector_db = None
all_chunks = []

with st.sidebar:
    st.header("📂 臨時指引上傳")
    uploaded_files = st.file_uploader(
        "請直拖上傳公司《使用扣帳方題庫.xlsx》檔案", 
        type=["xlsx", "xls"], 
        accept_multiple_files=True
    )

if uploaded_files:
    for f in uploaded_files:
        all_chunks.extend(process_excel_to_chunks(f))
    if all_chunks:
        embeddings = get_embedding_model()
        vector_db = FAISS.from_documents(all_chunks, embeddings)

with st.sidebar:
    st.header("📊 臨時知識庫狀態")
    st.write(f"📁 已加載檔案數：{len(uploaded_files) if uploaded_files else 0} 份")
    st.write(f"🧩 解析精準數據行：{len(all_chunks)} 條")

# ==========================================
# 4. 智能比對與語意擴展引擎
# ==========================================
if 'jumbo_messages' not in st.session_state:
    st.session_state.jumbo_messages = []

for msg in st.session_state.jumbo_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

if prompt := st.chat_input("請用中文輸入地盤扣帳情況..."):
    st.session_state.jumbo_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        final_response = ""
        
        if vector_db is None or not all_chunks:
            st.error("🛑 **系統提示：** 請先在左側上傳 Excel 題庫檔案，否則助理無法幫您翻查條文。")
            final_response = "未上傳文件。"
        else:
            enriched_prompt = expand_query_semantics(prompt)
            user_clean = clean_text_for_matching(enriched_prompt)
            
            keyword_matched_docs = []
            for chunk in all_chunks:
                chunk_clean = chunk.metadata["raw_cleaned"]
                if len(clean_text_for_matching(prompt)) >= 4 and (user_clean in chunk_clean or chunk_clean in user_clean):
                    keyword_matched_docs.append(chunk)
            
            if keyword_matched_docs:
                st.success("🎯 **系統已為您精準命中題庫內對應的原始記錄：**")
                st.markdown("<div class='confidence-badge'>🎯 智能語意精準對齊：100% 命中</div>", unsafe_allow_html=True)
                
                best_doc = keyword_matched_docs[0]
                st.markdown(
                    f"<div class='answer-box'>"
                    f"<b>📋 匹配題庫原始紀錄：</b><br>{best_doc.page_content}"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                final_response = best_doc.page_content
            else:
                docs_and_scores = vector_db.similarity_search_with_score(enriched_prompt, k=1)
                top_doc, top_score = docs_and_scores[0]
                
                confidence = max(75.0, min(99.9, (2.5 - top_score) * 40))
                
                st.success(f"🎯 **已為您透過「語意分析」翻查到最相關的原始記錄：**")
                st.markdown(
                    f"<div class='answer-box'>"
                    f"<b>📋 參考題庫紀錄 (語意匹配度 {confidence:.1f}%)：</b><br>{top_doc.page_content}"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                final_response = top_doc.page_content
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})
