import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

st.set_page_config(page_title="AI 绘图 (高延迟版)", page_icon="🐢", layout="wide")

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

st.title("🐢 AI 绘图 (跨国高延迟专用版)")
st.caption("检测到网络延迟 >1000ms，已自动开启慢速轮询模式。")

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    input_key = st.text_input("API Key", type="password", value=st.session_state.api_key)
    if st.button("✅ 保存 Key"):
        st.session_state.api_key = input_key.strip()
        st.success("已保存")
        
    size_option = st.selectbox("画幅", ["正方形 (1024x1024)", "横屏 (1280x720)", "竖屏 (720x1280)"])
    if "1024" in size_option: w, h = 1024, 1024
    elif "1280" in size_option: w, h = 1280, 720
    else: w, h = 720, 1280

# --- 核心逻辑 ---
def log(msg):
    st.info(msg)

def generate_slow_mode(prompt, api_key, width, height):
    base_url = 'https://api-inference.modelscope.cn/v1'
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true" # 必须异步
    }
    
    # 1. 提交任务
    try:
        log("🐢 正在跨海传输任务，请耐心等待...")
        payload = {
            "model": "Tongyi-MAI/Z-Image-Turbo",
            "prompt": prompt,
            "parameters": {"width": width, "height": height}
        }
        
        # 【修改点1】超时时间设为 30秒，防止网络卡顿报错
        resp = requests.post(f"{base_url}/images/generations", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        task_id = resp.json()["task_id"]
        log(f"✅ 任务已送达！ID: {task_id}")
        
    except Exception as e:
        return None, f"提交失败: {e}"

    # 【修改点2】提交后，死等 5 秒。让子弹飞一会儿，给跨国数据库同步的时间
    time.sleep(5)

    # 2. 慢速轮询
    start_time = time.time()
    retry_count = 0
    
    while True:
        # 放宽总等待时间到 120秒
        if time.time() - start_time > 120:
            return None, "等待超时（超过2分钟）。网络实在太慢了。"

        try:
            # 【修改点3】查询也设置 30秒超时
            check_resp = requests.get(
                f"{base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}", "X-ModelScope-Task-Type": "image_generation"},
                timeout=30 
            )
            
            # 如果服务器返回 404/500，我们不认为是错，只是“还没同步好”
            if check_resp.status_code >= 400:
                retry_count += 1
                if retry_count % 2 == 0: # 减少刷屏
                    log(f"⏳ 服务器暂未响应 ({check_resp.status_code})，正在重试...")
                time.sleep(3) # 慢慢来，不急
                continue

            data = check_resp.json()
            status = data.get("task_status")
            
            if status == "SUCCEED":
                log("🎉 终于成功了！正在下载图片...")
                img_url = data["output_images"][0]
                return Image.open(BytesIO(requests.get(img_url, timeout=30).content)), None
            
            elif status == "FAILED":
                # 依然是防误判逻辑
                if "task not found" in str(data):
                    log("🕵️ 遇到 Task not found，忽略并重试...")
                    time.sleep(3)
                    continue
                return None, f"生成失败: {data}"
            
            else:
                # RUNNING / PENDING
                time.sleep(3) # 每次轮询间隔 3秒
                
        except Exception as e:
            log(f"⚠️ 网络波动: {e}，正在重连...")
            time.sleep(3)

# --- 界面 ---
col1, col2 = st.columns([3, 1])
with col1:
    prompt = st.text_area("提示词", "A cute cat", height=100)
with col2:
    st.write("")
    st.write("")
    btn = st.button("🚀 开始生成", type="primary", use_container_width=True)

if btn:
    if not st.session_state.api_key:
        st.error("请先保存 API Key")
        st.stop()
        
    img, err = generate_slow_mode(prompt, st.session_state.api_key, w, h)
    if img:
        st.image(img, use_container_width=True)
    else:
        st.error(err)
