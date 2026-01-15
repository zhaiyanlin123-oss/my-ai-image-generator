import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="AI 绘图 Pro", 
    page_icon="🎨",
    layout="wide" # 使用宽屏模式，预览体验更好
)

# 初始化 session_state 用于存储 API Key
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

st.title("🎨 AI 绘图生成器 Pro")

# --- 2. 侧边栏：设置中心 ---
with st.sidebar:
    st.header("⚙️ 设置")
    
    # --- A. API Key 确认区域 ---
    st.subheader("1. 身份验证")
    input_key = st.text_input("输入 ModelScope Key", type="password", value=st.session_state.api_key)
    
    if st.button("✅ 确认保存 Key"):
        st.session_state.api_key = input_key
        st.success("Key 已保存！")
    
    # 显示当前状态
    if st.session_state.api_key:
        st.caption("🟢当前状态: 已配置")
    else:
        st.caption("🔴当前状态: 未配置")
        
    st.markdown("---")
    
    # --- B. 尺寸选择 ---
    st.subheader("2. 图片尺寸")
    size_option = st.selectbox(
        "选择画幅比例",
        options=["正方形 (1024 x 1024)", "横屏 (1280 x 720)", "竖屏 (720 x 1280)"],
        index=0
    )
    
    # 解析尺寸
    if "1024" in size_option:
        width, height = 1024, 1024
    elif "1280" in size_option:
        width, height = 1280, 720
    else:
        width, height = 720, 1280

# --- 3. 核心生成逻辑 ---
def generate_image(prompt, api_key, w, h):
    base_url = 'https://api-inference.modelscope.cn/'
    
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # === Step 1: 提交任务 ===
    try:
        # 构造请求数据，加入尺寸参数
        payload = {
            "model": "Tongyi-MAI/Z-Image-Turbo",
            "prompt": prompt,
            "parameters": {
                "width": w,
                "height": h
            }
        }
        
        submit_headers = {**auth_headers, "X-ModelScope-Async-Mode": "true"}
        
        response = requests.post(
            f"{base_url}v1/images/generations",
            headers=submit_headers,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8')
        )
        response.raise_for_status()
        task_id = response.json()["task_id"]
    except Exception as e:
        return None, f"提交任务失败: {str(e)}"

    # === Step 2: 轮询结果 ===
    start_time = time.time()
    time.sleep(2) # 缓冲

    while True:
        if time.time() - start_time > 90:
            return None, "生成超时，请稍后再试。"

        try:
            # 必须带 Task-Type Header
            query_headers = {**auth_headers, "X-ModelScope-Task-Type": "image_generation"}
            
            task_resp = requests.get(
                f"{base_url}v1/tasks/{task_id}",
                headers=query_headers
            )
            
            # 网络错误重试
            if task_resp.status_code >= 400:
                time.sleep(2)
                continue

            task_data = task_resp.json()
            status = task_data.get("task_status")

            if status == "SUCCEED":
                image_url = task_data["output_images"][0]
                return Image.open(BytesIO(requests.get(image_url).content)), None
            
            elif status == "FAILED":
                # 忽略 "task not found" 的假报错
                if "task not found" in str(task_data):
                    time.sleep(2)
                    continue
                return None, f"生成失败: {task_data}"
            
            time.sleep(2)
            
        except Exception as e:
            time.sleep(2)

# --- 4. 主工作区 ---

# 使用两列布局：左边输入提示词，右边放生成按钮
col1, col2 = st.columns([3, 1])

with col1:
    prompt_text = st.text_area("✨ 想要生成什么画面？", value="A cute cat in space suit, cyberpunk style", height=120)

with col2:
    st.write(" ") # 占位空行，让按钮对齐
    st.write(" ")
    run_btn = st.button("🚀 开始生成", type="primary", use_container_width=True)

st.divider() # 分割线

# --- 5. 图片预览位置 (结果展示区) ---
result_container = st.container()

if run_btn:
    # 检查 Key
    final_key = st.session_state.api_key
    if not final_key:
        st.error("⚠️ 请先在左侧侧边栏输入并【确认保存】您的 API Key！")
        st.stop()
        
    with result_container:
        with st.spinner("🎨 AI 正在挥毫泼墨，请稍候..."):
            img, err = generate_image(prompt_text, final_key, width, height)
            
            if err:
                st.error(err)
            else:
                st.balloons() # 撒花特效
                st.success("✨ 生成成功！")
                
                # 居中显示大图
                st.image(img, caption=f"Prompt: {prompt_text}", use_container_width=True)
                
                # 下载按钮
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.download_button(
                    label="📥 下载高清原图",
                    data=buf.getvalue(),
                    file_name="ai_generated_image.png",
                    mime="image/png",
                    use_container_width=True
                )
