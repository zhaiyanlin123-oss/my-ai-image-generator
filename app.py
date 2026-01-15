import streamlit as st
import requests
import time
import socket

st.title("🏥 网络连通性诊断")

st.write("正在检测 Streamlit 服务器的网络环境...")

# 1. 检查服务器在哪里
try:
    ip = requests.get('https://api.ipify.org').text
    location = requests.get(f'https://ipapi.co/{ip}/country_name/').text
    st.success(f"✅ 服务器自身外网正常！IP: {ip} (位于: {location})")
except Exception as e:
    st.error(f"❌ 服务器无法连接外网: {e}")

# 2. 检查能否连接到 ModelScope
st.write("正在 ping ModelScope API...")
start_time = time.time()
try:
    # 尝试访问 ModelScope 的基础端点（不带鉴权，仅测试连接）
    # 设置 5 秒超时，看是否能连上
    response = requests.get('https://api-inference.modelscope.cn/v1', timeout=5)
    ping = (time.time() - start_time) * 1000
    
    # 404/403/401 都是好消息，说明连上了（只是没权限）
    # 只有 ConnectionError 才是坏消息
    if response.status_code in [200, 401, 403, 404, 405]:
        st.success(f"✅ ModelScope 连接成功！")
        st.info(f"📶 延迟: {ping:.2f} ms (如果在 500ms 以上，说明跨国传输很慢)")
        st.json(response.json()) if response.text.startswith('{') else st.write(f"状态码: {response.status_code}")
    else:
        st.warning(f"⚠️ 连接通了，但状态码异常: {response.status_code}")

except requests.exceptions.ConnectTimeout:
    st.error("❌ 连接超时 (Timeout)：服务器在 5 秒内没有响应。")
except requests.exceptions.ConnectionError:
    st.error("❌ 连接失败 (Connection Error)：无法建立连接，可能是被墙了。")
except Exception as e:
    st.error(f"❌ 未知错误: {e}")
