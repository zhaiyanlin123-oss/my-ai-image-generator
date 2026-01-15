import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(page_title="AI 绘图 (BYOK版)", page_icon="🎨")
st.title("🎨 AI 绘图生成器")
st.markdown("输入 API Key，立刻生成图片。")

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("🔑 身份验证")
    user_api_key = st.text_input("请输入 ModelScope API Key", type="password")
    st.markdown("[👉 获取免费 Key](https://modelscope.cn/my/myaccesstoken)")

# --- 3. 核心生成逻辑 (带“死缠烂打”重试机制) ---
def generate_image(prompt, api_key):
    base_url = 'https://api-inference.modelscope.cn/'
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true"
    }

    # === Step 1: 提交任务 ===
    try:
        response = requests.post(
            f"{base_url}v1/images/generations",
            headers=headers,
            data=json.dumps({
                "model": "Tongyi-MAI/Z-Image-Turbo",
                "prompt": prompt
            }, ensure_ascii=False).encode('utf-8')
        )
        response.raise_for_status()
        task_id = response.json()["task_id"]
    except Exception as e:
        return None, f"提交任务失败: {str(e)}"

    # === Step 2: 轮询结果 (专门修复 task not found) ===
    start_time = time.time()
    
    # 强制等待 2 秒，给服务器一点喘息时间
    time.sleep(2)

    while True:
        # 1. 超时保护 (60秒)
        if time.time() - start_time > 60:
            return None, "等待超时，请重试。"

        try:
            task_resp = requests.get(
                f"{base_url}v1/tasks/{task_id}",
                headers=headers
            )
            
            # 如果 HTTP 层面报错（比如 404/500），直接重试，不报错
            if task_resp.status_code >= 400:
                time.sleep(2)
                continue

            task_data = task_resp.json()
            status = task_data.get("task_status")

            if status == "SUCCEED":
                image_url = task_data["output_images"][0]
                return Image.open(BytesIO(requests.get(image_url).content)), None
            
            elif status == "FAILED":
                # 【核心修复点】
                # 如果失败原因是 "task not found"，这不算真失败，这是服务器延迟。
                # 我们选择忽略它，继续重试！
                if "task not found" in str(task_data):
                    time.sleep(2)
                    continue  # <--- 关键：跳回循环开头，再问一次
                
                # 如果是其他真失败，才报错
                return None, f"生成失败: {task_data}"
            
            # 如果状态是 PENDING 或 RUNNING，继续等
            time.sleep(1)
            
        except Exception as e:
            # 网络波动也重试
            time.sleep(1)

# --- 4. 界面交互 ---
prompt_text = st.text_area("提示词 (Prompt):", value="A cute cat", height=100)
run_btn = st.button("🚀 开始生成", type="primary")

if run_btn:
    if not user_api_key:
        st.error("请先在左侧填入 API Key")
        st.stop()
        
    with st.spinner("正在生成中...如果出现波动会自动重试..."):
        img, err = generate_image(prompt_text, user_api_key)
        if err:
            st.error(err)
        else:
            st.success("成功！")
            st.image(img)
