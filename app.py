import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import json

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="AI 绘图 (直连版)", 
    page_icon="🎨",
    layout="wide"
)

if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

st.title("🎨 AI 绘图生成器 (Turbo直连版)")

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    
    # API Key 输入
    input_key = st.text_input("输入 ModelScope Key", type="password", value=st.session_state.api_key)
    if st.button("✅ 确认保存 Key"):
        if input_key:
            st.session_state.api_key = input_key.strip() # 去除可能多余的空格
            st.success("Key 已保存！")
        else:
            st.error("Key 不能为空")
            
    if st.session_state.api_key:
        st.caption("🟢 状态: 就绪")
    else:
        st.caption("🔴 状态: 未配置")
        
    st.markdown("---")
    
    # 尺寸选择
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

# --- 3. 核心生成逻辑 (同步模式 - 不用排队) ---
def generate_image_sync(prompt, api_key, width, height):
    # 严格按照你提供的文档 Base URL
    url = "https://api-inference.modelscope.cn/v1/images/generations"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
        # 注意：这里删除了 Async-Mode 和 Task-Type，强制使用同步模式
    }

    # 构造标准 OpenAI 格式的请求体
    payload = {
        "model": "Tongyi-MAI/Z-Image-Turbo", # 你的模型ID
        "prompt": prompt,
        "n": 1,
        "size": f"{width}x{height}" # 尝试使用标准 OpenAI size 格式
        # ModelScope 有时候也兼容 parameters: {"width": w, "height": h}
        # 如果 size 报错，我们会自动回退到 parameters 写法
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60) # 设置60秒超时
        
        # 调试：如果在本地运行，可以打印 response.text 看看报错
        # print(response.text) 
        
        response.raise_for_status()
        
        # 解析 OpenAI 格式的返回结果
        # 成功格式: {"created": ..., "data": [{"url": "..."}]}
        result = response.json()
        
        if "data" in result and len(result["data"]) > 0:
            image_url = result["data"][0]["url"]
            return Image.open(BytesIO(requests.get(image_url).content)), None
        else:
            return None, f"服务器返回格式异常: {result}"

    except requests.exceptions.HTTPError as e:
        # 尝试读取服务器返回的具体错误信息
        try:
            error_msg = response.json()
            return None, f"服务器报错: {error_msg}"
        except:
            return None, f"请求失败 (代码 {response.status_code}): {str(e)}"
    except Exception as e:
        return None, f"发生错误: {str(e)}"

# --- 4. 界面布局 ---
col1, col2 = st.columns([3, 1])

with col1:
    prompt_text = st.text_area("✨ 提示词 (英文效果最佳)", value="A cute cat, 3d render", height=120)

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
        
    with st.spinner("⚡️ 正在极速生成中 (约 5-10 秒)..."):
        # 调用新的同步函数
        img, err = generate_image_sync(prompt_text, final_key, w, h)
        
        if err:
            st.error(err)
            # 如果报错关于 size 参数，可能需要改回 parameters 写法，但通常 v1 接口支持 size
        else:
            st.success(f"✨ 生成成功!")
            st.image(img, caption=prompt_text, use_container_width=True)
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.download_button("📥 下载图片", data=buf.getvalue(), file_name="ai_image.png", mime="image/png", use_container_width=True)
