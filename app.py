import streamlit as st
import requests
import time
import json
from PIL import Image
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="AI 绘图 (BYOK版)", 
    page_icon="🎨",
    layout="centered"
)

st.title("🎨 AI 绘图生成器")
st.markdown("只需要输入你的 ModelScope API Key，即可使用 Tongyi-MAI 模型生成图片。")

# --- 2. 侧边栏：用户输入 Key ---
with st.sidebar:
    st.header("🔑 身份验证")
    user_api_key = st.text_input(
        "请输入 ModelScope API Key",
        type="password",
        help="你的 Key 不会被存储，仅用于本次请求转发。"
    )
    st.markdown("[👉 点击这里获取免费 API Key](https://modelscope.cn/my/myaccesstoken)")

# --- 3. 定义生成函数 (带智能重试机制) ---
def generate_image(prompt, api_key):
    base_url = 'https://api-inference.modelscope.cn/'
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true"
    }

    # === 第一步：提交任务 ===
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
        # print(f"任务已提交，ID: {task_id}") # 调试用
    except Exception as e:
        return None, f"任务提交失败: {str(e)}"

    # === 第二步：轮询结果 (智能重试) ===
    # 这里的逻辑改成了：就算服务器报错说找不到任务，我们也不放弃，而是等一下再问
    start_time = time.time()
    
    while True:
        # 1. 超时检查 (60秒)
        if time.time() - start_time > 60:
            return None, "生成超时，请稍后再试"

        try:
            # 查询状态
            task_resp = requests.get(
                f"{base_url}v1/tasks/{task_id}",
                headers=headers
            )
            
            # 【关键修改】：如果服务器返回 500 或 404 (通常是 Task not found)，我们不报错，而是忽略并重试
            if task_resp.status_code in [404, 500]:
                time.sleep(2)
                continue
                
            task_resp.raise_for_status() # 其他错误才抛出异常
            task_data = task_resp.json()
            status = task_data["task_status"]

            if status == "SUCCEED":
                image_url = task_data["output_images"][0]
                return Image.open(BytesIO(requests.get(image_url).content)), None
            elif status == "FAILED":
                return None, f"生成失败: {task_data}"
            
            # 如果状态是 PENDING 或 RUNNING，继续等待
            time.sleep(1)
            
        except Exception as e:
            # 如果是网络波动，也不崩溃，等待重试
            time.sleep(1)

# --- 4. 主界面逻辑 ---
prompt_text = st.text_area("想要生成什么画面？(推荐使用英文)", value="A cute rabbit in the forest", height=100)
generate_btn = st.button("🚀 开始生成", type="primary", use_container_width=True)

if generate_btn:
    if not user_api_key:
        st.error("⛔️ 请先在左侧侧边栏输入你的 API Key！")
        st.stop()
    
    if not prompt_text:
        st.warning("请输入提示词。")
        st.stop()

    with st.spinner("正在连接云端生成中... (大约需要 5-10 秒)"):
        image, error = generate_image(prompt_text, user_api_key)
        
        if error:
            st.error(error)
        else:
            st.success("生成成功！")
            st.image(image, caption=prompt_text, use_container_width=True)
            
            buf = BytesIO()
            image.save(buf, format="PNG")
            st.download_button("📥 下载图片", data=buf.getvalue(), file_name="ai_art.png", mime="image/png")
