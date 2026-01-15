import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="AI 绘图 (终极版)", 
    page_icon="🛠️",
    layout="wide"
)

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

st.title("🛠️ AI 绘图生成器 (自动重投版)")
st.markdown("针对“Task not found”错误的终极解决方案：**查不到就重发，直到成功。**")

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    
    input_key = st.text_input("ModelScope Key", type="password", value=st.session_state.api_key)
    if st.button("✅ 确认保存 Key"):
        if input_key:
            st.session_state.api_key = input_key.strip()
            st.success("已保存")
    
    # 尺寸选择
    size_option = st.selectbox(
        "画幅",
        options=["正方形 (1024x1024)", "横屏 (1280x720)", "竖屏 (720x1280)"],
        index=0
    )
    
    if "1024" in size_option:
        w, h = 1024, 1024
    elif "1280" in size_option:
        w, h = 1280, 720
    else:
        w, h = 720, 1280

    st.divider()
    show_debug = st.checkbox("显示调试日志 (Debug)", value=True)

# --- 3. 核心逻辑：带“弃单重投”机制 ---
def log(msg):
    if show_debug:
        st.code(msg, language="text")

def generate_with_retry(prompt, api_key, width, height):
    base_url = 'https://api-inference.modelscope.cn/v1'
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true" # 必须异步
    }
    
    # === 外层循环：尝试提交任务（最多重试 3 次）===
    max_submission_retries = 3
    
    for attempt in range(max_submission_retries):
        log(f"🔄 [第 {attempt + 1} 次尝试] 正在提交新任务...")
        
        try:
            # 1. 提交任务
            payload = {
                "model": "Tongyi-MAI/Z-Image-Turbo",
                "prompt": prompt,
                "parameters": {"width": width, "height": height}
            }
            
            resp = requests.post(
                f"{base_url}/images/generations",
                headers=headers,
                data=json.dumps(payload),
                timeout=10
            )
            resp.raise_for_status()
            task_id = resp.json()["task_id"]
            log(f"✅ 任务提交成功，ID: {task_id}")
            
        except Exception as e:
            log(f"❌ 提交阶段报错: {e}")
            time.sleep(2)
            continue # 提交都失败了，直接下一次循环
            
        # 2. 轮询查结果 (如果 10 秒内一直 task not found，就跳出，重新提交)
        poll_start = time.time()
        not_found_count = 0
        
        while True:
            # 如果轮询超过 25 秒还没结果，认为这个 ID 废了，强制重开
            if time.time() - poll_start > 25:
                log("⚠️ 单次轮询超时，放弃此 ID，准备重新提交...")
                break 
            
            try:
                # 查询状态
                # 技巧：尝试去掉 Task-Type header，有时候反而能查到
                check_resp = requests.get(
                    f"{base_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {api_key}"}, # 简化 Header 试试
                    timeout=10
                )
                
                # 处理 500/404 Task not found
                if check_resp.status_code >= 400:
                    not_found_count += 1
                    log(f"⏳ 服务器暂未找到任务 ({check_resp.status_code}) - {not_found_count}次")
                    
                    # 如果连续 5 次都找不到，说明这个 ID 是死 ID
                    if not_found_count > 5:
                        log("🚫 连续多次找不到任务，判定为死任务。")
                        break # 跳出内层 while，触发外层 for 重新提交
                        
                    time.sleep(2)
                    continue

                data = check_resp.json()
                status = data.get("task_status")
                
                if status == "SUCCEED":
                    log("🎉 任务成功！正在下载图片...")
                    img_url = data["output_images"][0]
                    return Image.open(BytesIO(requests.get(img_url).content)), None
                
                elif status == "FAILED":
                    # 再次检查是不是假失败
                    if "task not found" in str(data):
                        not_found_count += 1
                        log(f"🕵️ 伪装的失败 (Task not found) - 继续等待")
                        time.sleep(2)
                        continue
                    else:
                        return None, f"生成失败: {data}"
                
                else:
                    log(f"🚀 状态: {status}...")
                    time.sleep(2)
                    
            except Exception as e:
                log(f"⚠️ 网络波动: {e}")
                time.sleep(2)
        
        # 如果代码跑到这里，说明 break 了 inner loop，准备进入下一次 attempt
        log("🔁 正在重新尝试新的任务提交...")
        time.sleep(2)

    return None, "❌ 已尝试 3 次重新提交，但服务器依然无响应。请检查 API Key 余额或稍后再试。"

# --- 4. 界面布局 ---
col1, col2 = st.columns([3, 1])
with col1:
    prompt_text = st.text_area("提示词", value="A cute cat, high quality", height=100)
with col2:
    st.write(" ")
    st.write(" ")
    run_btn = st.button("🚀 强力生成", type="primary", use_container_width=True)

st.divider()

if run_btn:
    key = st.session_state.api_key
    if not key:
        st.error("请先在左侧保存 API Key")
        st.stop()
    
    with st.container():
        # 这里不显示 spinner，因为我们有自定义 log
        st.info("正在执行强力生成模式... 请关注下方日志")
        img, err = generate_with_retry(prompt_text, key, w, h)
        
        if img:
            st.success("生成成功！")
            st.image(img, use_container_width=True)
            # 下载
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.download_button("📥 下载原图", data=buf.getvalue(), file_name="final_result.png")
        else:
            st.error(err)
