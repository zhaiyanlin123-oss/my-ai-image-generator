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
    layout="wide"
)

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

st.title("🎨 AI 绘图生成器 Pro (强力重试版)")

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    
    input_key = st.text_input("输入 ModelScope Key", type="password", value=st.session_state.api_key)
    if st.button("✅ 确认保存 Key"):
        if input_key:
            st.session_state.api_key = input_key.strip()
            st.success("Key 已保存！")
    
    if st.session_state.api_key:
        st.caption("🟢 状态: 就绪")
    else:
        st.caption("🔴 状态: 未配置")
        
    st.markdown("---")
    
    size_option = st.selectbox(
        "画幅比例",
        options=["正方形 (1024x1024)", "横屏 (1280x720)", "竖屏 (720x1280)"],
        index=0
    )
    
    if "1024" in size_option:
        w, h = 1024, 1024
    elif "1280" in size_option:
        w, h = 1280, 720
    else:
        w, h = 720, 1280

# --- 3. 核心生成逻辑 (异步 + 强力重试) ---
def generate_image_async(prompt, api_key, width, height):
    base_url = 'https://api-inference.modelscope.cn/v1'
    
    # 基础 Header
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # === Step 1: 提交任务 (必须异步) ===
    try:
        # 强制开启异步模式
        submit_headers = {**headers, "X-ModelScope-Async-Mode": "true"}
        
        payload = {
            "model": "Tongyi-MAI/Z-Image-Turbo",
            "prompt": prompt,
            "parameters": {
                "width": width,
                "height": height
            }
        }
        
        response = requests.post(
            f"{base_url}/images/generations",
            headers=submit_headers,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8')
        )
        response.raise_for_status()
        task_id = response.json()["task_id"]
        # print(f"任务提交成功: {task_id}") # 调试用
        
    except Exception as e:
        return None, f"提交任务失败: {str(e)}"

    # === Step 2: 轮询结果 (专门解决 task not found) ===
    start_time = time.time()
    time.sleep(2) # 初始缓冲

    # 循环查询
    while True:
        # 超时保护 (60秒)
        if time.time() - start_time > 60:
            return None, "生成超时，请重试。"

        try:
            # 查询任务状态
            # 关键：带上 Task-Type 帮助服务器定位
            query_headers = {**headers, "X-ModelScope-Task-Type": "image_generation"}
            
            task_resp = requests.get(
                f"{base_url}/tasks/{task_id}",
                headers=query_headers
            )
            
            # 1. 处理 HTTP 层面错误 (404/500)
            if task_resp.status_code >= 400:
                # print(f"HTTP等待: {task_resp.status_code}") 
                time.sleep(1.5)
                continue

            # 2. 解析 JSON
            task_data = task_resp.json()
            status = task_data.get("task_status")

            # 3. 判断状态
            if status == "SUCCEED":
                # 成功！获取图片
                if "output_images" in task_data and task_data["output_images"]:
                    image_url = task_data["output_images"][0]
                    return Image.open(BytesIO(requests.get(image_url).content)), None
                else:
                    # 有时候成功了但没有 output_images，可能是 results
                    # print(task_data)
                    return None, f"数据解析异常: {task_data}"
            
            elif status == "FAILED":
                # === 核心修复逻辑 ===
                # 如果服务器说 FAILED，但原因是 "task not found"，这不算失败！
                error_msg = str(task_data)
                if "task not found" in error_msg or "500" in error_msg:
                    # print("服务器还没同步到任务，继续等待...")
                    time.sleep(1.5)
                    continue # 跳过报错，继续循环！
                
                # 如果是其他真正的错误，才报错
                return None, f"生成失败: {task_data}"
            
            # PENDING / RUNNING
            time.sleep(1)
            
        except Exception as e:
            # 网络波动，继续重试
            time.sleep(1)

# --- 4. 界面布局 ---
col1, col2 = st.columns([3, 1])

with col1:
    prompt_text = st.text_area("✨ 提示词 (Prompt)", value="A cute cat, 3d render", height=120)

with col2:
    st.write(" ")
    st.write(" ")
    run_btn = st.button("🚀 开始生成", type="primary", use_container_width=True)

st.divider()

if run_btn:
    final_key = st.session_state.api_key
    if not final_key:
        st.error("⚠️ 请先在左侧输入并保存 API Key")
        st.stop()
        
    with st.spinner("⚡️ 正在生成... (如遇波动会自动重试)"):
        img, err = generate_image_async(prompt_text, final_key, w, h)
        
        if err:
            st.error(err)
        else:
            st.balloons()
            st.success("✨ 生成成功!")
            st.image(img, caption=prompt_text, use_container_width=True)
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.download_button("📥 下载图片", data=buf.getvalue(), file_name="ai_image.png", mime="image/png", use_container_width=True)
