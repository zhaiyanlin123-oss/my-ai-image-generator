import streamlit as st
import requests
import time
from PIL import Image
from io import BytesIO

# --- 1. 页面配置 (改回居中布局，聚焦内容) ---
st.set_page_config(
    page_title="AI 绘图 Pro",
    page_icon="🎨",
    layout="centered", # <--- 关键修改：改回 centered，防止图片过大
    initial_sidebar_state="expanded"
)

# 自定义简单的 CSS 来美化界面 (可选，增加一点卡片感)
st.markdown("""
<style>
    .stTextArea textarea {
        font-size: 16px !important;
    }
    /* 让生成结果区域看起来像一张卡片 */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* 深色模式适配 */
    @media (prefers-color-scheme: dark) {
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            background-color: #262730;
        }
    }
</style>
""", unsafe_allow_html=True)

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

# 标题区域优化
st.title("🎨 AI 创意绘图工作台")
st.caption("搭载通义万相 Turbo 模型，专为跨境高延迟网络优化。")

# --- 2. 侧边栏 (保持不变) ---
with st.sidebar:
    st.header("⚙️ 参数设置")
    
    with st.expander("🔑 API Key 管理", expanded=True):
        input_key = st.text_input("输入 ModelScope Key", type="password", value=st.session_state.api_key, help="您的 Key 仅保存在当前会话中，刷新页面后需重新输入。")
        if st.button("✅ 确认保存", use_container_width=True):
            st.session_state.api_key = input_key.strip()
            if input_key:
                st.toast("API Key 已安全保存！", icon="🔒")
        
        if st.session_state.api_key:
            st.success("状态: 已连接")
        else:
            st.warning("状态: 未配置")

    st.markdown("---")
    st.subheader("📐 画幅选择")
    size_map = {
        "正方形 (1:1 社交媒体)": (1024, 1024, "🔳"),
        "横屏 (16:9 桌面壁纸)": (1280, 720, "🖥️"),
        "竖屏 (9:16 手机壁纸)": (720, 1280, "📱")
    }
    size_label = st.radio("选择比例", list(size_map.keys()), index=0, format_func=lambda x: f"{size_map[x][2]} {x}")
    w, h = size_map[size_label][0], size_map[size_label][1]

# --- 3. 核心逻辑 (保持之前的龟速重试内核) ---
def log(msg, type="info"):
    # 使用 toast 替代 info，减少页面干扰
    if type == "info":
        st.toast(msg, icon="🐢")
    elif type == "success":
        st.toast(msg, icon="🎉")
    elif type == "error":
        st.error(msg)

def generate_slow_mode(prompt, api_key, width, height):
    base_url = 'https://api-inference.modelscope.cn/v1'
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true"
    }
    
    # 1. 提交任务
    try:
        log("正在加密传输任务至云端...")
        payload = {
            "model": "Tongyi-MAI/Z-Image-Turbo",
            "prompt": prompt,
            "parameters": {"width": width, "height": height}
        }
        resp = requests.post(f"{base_url}/images/generations", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        task_id = resp.json()["task_id"]
        # log(f"任务已送达队列，ID: {task_id}")
        
    except Exception as e:
        return None, f"提交失败: {e}"

    time.sleep(5) # 等待服务器同步

    # 2. 慢速轮询
    start_time = time.time()
    retry_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    while True:
        elapsed = time.time() - start_time
        if elapsed > 120:
            status_text.empty()
            progress_bar.empty()
            return None, "连接超时。网络状况不佳，请稍后重试。"

        # 更新进度条假象
        progress = min(int((elapsed / 60) * 90), 95)
        progress_bar.progress(progress)
        status_text.caption(f"⚡️ AI 正在努力绘制中... (已耗时 {int(elapsed)}秒，网络延迟较高请耐心)")

        try:
            check_resp = requests.get(
                f"{base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}", "X-ModelScope-Task-Type": "image_generation"},
                timeout=30 
            )
            
            if check_resp.status_code >= 400:
                retry_count += 1
                time.sleep(3)
                continue

            data = check_resp.json()
            status = data.get("task_status")
            
            if status == "SUCCEED":
                progress_bar.progress(100)
                status_text.empty()
                time.sleep(0.5)
                progress_bar.empty()
                log("绘制完成！正在下载高清原图...", "success")
                img_url = data["output_images"][0]
                return Image.open(BytesIO(requests.get(img_url, timeout=60).content)), None
            
            elif status == "FAILED":
                if "task not found" in str(data):
                    time.sleep(3)
                    continue
                status_text.empty()
                progress_bar.empty()
                return None, f"生成失败: {data}"
            
            else:
                time.sleep(3)
                
        except Exception as e:
            time.sleep(3)

# --- 4. 主界面布局优化 ---
st.markdown("#### ✨ 创意描述")
prompt_text = st.text_area(
    label="提示词",
    placeholder="在这里输入画面描述，例如：一只穿着宇航服的可爱猫咪，在赛博朋克风格的城市里，电影感光影...",
    height=100,
    label_visibility="collapsed"
)

# 按钮居中并加大
col_spacer1, col_btn, col_spacer2 = st.columns([1, 2, 1])
with col_btn:
    run_btn = st.button("🚀 立即生成图像", type="primary", use_container_width=True)

st.divider()

# --- 5. 结果展示区 (卡片化) ---
if run_btn:
    if not st.session_state.api_key:
        st.error("请先在左侧侧边栏配置并保存 API Key。")
        st.stop()
    
    # 使用一个容器包裹结果，配合 CSS 实现卡片效果
    with st.container():
        # 这里不再需要 spinner，因为我们在函数里用了进度条
        img, err = generate_slow_mode(prompt_text, st.session_state.api_key, w, h)
        
        if img:
            # 成功展示区
            st.subheader("🎉 生成结果")
            # 居中显示图片，不再强制撑满宽度
            st.image(img, caption=prompt_text) 
            
            # 下载按钮
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.download_button(
                label="📥 下载高清无损 PNG",
                data=buf.getvalue(),
                file_name=f"ai_image_{int(time.time())}.png",
                mime="image/png",
                use_container_width=True
            )
        elif err:
            # 失败展示区
            st.error("生成过程中遇到了问题")
            with st.expander("查看错误详情"):
                st.code(err)
