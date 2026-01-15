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
    
    # 获取用户输入的 Key
    user_api_key = st.text_input(
        "请输入 ModelScope API Key",
        type="password",  # 设置为密码模式，隐藏明文
        help="你的 Key 不会被存储，仅用于本次请求转发。"
    )
    
    st.markdown("[👉 点击这里获取免费 API Key](https://modelscope.cn/my/myaccesstoken)")
    st.info("提示：新用户注册魔搭社区通常有免费额度。")

# --- 3. 定义生成函数 (接收动态 Key) ---
def generate_image(prompt, api_key):
    base_url = 'https://api-inference.modelscope.cn/'
    
    # 关键点：这里使用的是用户传进来的 api_key
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true"
    }

    # 发送请求
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
        time.sleep(3)  #
    except Exception as e:
        return None, f"任务提交失败 (请检查Key是否正确): {str(e)}"

    # 轮询状态
    start_time = time.time()
    while True:
        if time.time() - start_time > 60:
            return None, "生成超时"

        try:
            task_resp = requests.get(
                f"{base_url}v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )
            task_data = task_resp.json()
            status = task_data["task_status"]

            if status == "SUCCEED":
                image_url = task_data["output_images"][0]
                return Image.open(BytesIO(requests.get(image_url).content)), None
            elif status == "FAILED":
                return None, "生成失败: " + str(task_data)
            
            time.sleep(2)
        except Exception as e:
            return None, f"查询出错: {str(e)}"

# --- 4. 主界面逻辑 ---
prompt_text = st.text_area("想要生成什么画面？(推荐使用英文)", value="A cyberpunk city under the rain, neon lights", height=100)

generate_btn = st.button("🚀 开始生成", type="primary", use_container_width=True)

if generate_btn:
    # 检查 1: 用户有没有填 Key
    if not user_api_key:
        st.error("⛔️ 请先在左侧侧边栏输入你的 API Key 才能运行！")
        st.stop() # 停止往下执行
    
    # 检查 2: Key 的格式简单验证 (ModelScope Key 通常以 ms- 开头)
    if not user_api_key.startswith("ms-"):
        st.warning("⚠️ 这个 Key 看起来格式不对，通常是以 'ms-' 开头的。")

    # 检查 3: 有没有填提示词
    if not prompt_text:
        st.warning("请输入提示词。")
        st.stop()

    # 一切就绪，开始运行
    with st.spinner("正在连接 ModelScope 云端生成中..."):
        image, error = generate_image(prompt_text, user_api_key)
        
        if error:
            st.error(error)
        else:
            st.success("生成成功！")
            st.image(image, caption=prompt_text, use_container_width=True)
            
            # 下载按钮
            buf = BytesIO()
            image.save(buf, format="PNG")

            st.download_button("📥 下载图片", data=buf.getvalue(), file_name="ai_art.png", mime="image/png")
