import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(page_title="AI 绘图 (BYOK版)", page_icon="🎨")
st.title("🎨 AI 绘图生成器")
st.caption("基于 ModelScope 通义模型")

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("🔑 身份验证")
    user_api_key = st.text_input("请输入 ModelScope API Key", type="password")
    st.markdown("[👉 获取免费 Key](https://modelscope.cn/my/myaccesstoken)")

# --- 3. 核心生成逻辑 ---
def generate_image(prompt, api_key):
    base_url = 'https://api-inference.modelscope.cn/'
    
    # 基础 Header
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # === Step 1: 提交任务 ===
    try:
        # 发送请求时开启异步模式
        submit_headers = {**auth_headers, "X-ModelScope-Async-Mode": "true"}
        
        response = requests.post(
            f"{base_url}v1/images/generations",
            headers=submit_headers,
            data=json.dumps({
                "model": "Tongyi-MAI/Z-Image-Turbo",
                "prompt": prompt
            }, ensure_ascii=False).encode('utf-8')
        )
        response.raise_for_status()
        task_id = response.json()["task_id"]
    except Exception as e:
        return None, f"提交任务失败: {str(e)}"

    # === Step 2: 轮询结果 ===
    start_time = time.time()
    time.sleep(2) # 给服务器 2 秒缓冲

    while True:
        # 超时时间延长到 90 秒
        if time.time() - start_time > 90:
            return None, "生成超时（服务器响应过慢），请稍后再试。"

        try:
            # 【关键修正】：查询时必须带上 Task-Type，否则服务器找不到任务！
            query_headers = {**auth_headers, "X-ModelScope-Task-Type": "image_generation"}
            
            task_resp = requests.get(
                f"{base_url}v1/tasks/{task_id}",
                headers=query_headers
            )
            
            # 遇到 404/500 依然等待重试
            if task_resp.status_code >= 400:
                time.sleep(2)
                continue

            task_data = task_resp.json()
            status = task_data.get("task_status")

            if status == "SUCCEED":
                image_url = task_data["output_images"][0]
                return Image.open(BytesIO(requests.get(image_url).content)), None
            
            elif status == "FAILED":
                # 依然保持防误判逻辑
                if "task not found" in str(task_data):
                    time.sleep(2)
                    continue
                return None, f"生成失败: {task_data}"
            
            # PENDING / RUNNING
            time.sleep(2)
            
        except Exception as e:
            time.sleep(2)

# --- 4. 界面交互 ---
prompt_text = st.text_area("提示词 (Prompt):", value="A futuristic cyberpunk city, neon lights, high detail", height=100)
run_btn = st.button("🚀 开始生成", type="primary")

if run_btn:
    if not user_api_key:
        st.error("请先在左侧填入 API Key")
        st.stop()
        
    with st.spinner("正在生成中..."):
        img, err = generate_image(prompt_text, user_api_key)
        if err:
            st.error(err)
        else:
            st.success("成功！")
            st.image(img)
