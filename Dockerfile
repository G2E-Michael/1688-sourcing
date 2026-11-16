# 1688-sourcing — container image
#
# 用途：在没有本机 Chrome / Node 环境的地方（Codespaces、CI、Linux 服务器）
# 直接跑 `run.py keyword|image`，最后由 Playwright 自带 Chromium 驱动 1688。
#
# 注意：容器里的 Chromium 指纹与真实 Chrome 不同，1688 触发滑块的概率更高；
# 首次使用仍要扫码登录（`docker run -it ... login --headed` 会打印二维码），
# 登录态落在 /data/profile，务必挂载持久卷，否则每次都要重新扫码。
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    BB1688_FORCE_CHROMIUM=1 \
    BB1688_PROFILE=/data/profile

# Node.js 20（1688-cli 的运行前提，需要 >= 20）
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# 1688-cli + 与其 playwright-core 同版本的 Chromium（版本必须一致，否则找不到浏览器）
RUN npm i -g 1688-cli \
 && PW="$(node -p "require('$(npm root -g)/1688-cli/node_modules/playwright-core/package.json').version")" \
 && echo "playwright-core version: $PW" \
 && npm i -g "playwright@$PW" \
 && npx playwright install --with-deps chromium \
 && chmod -R a+rX /root/.cache/ms-playwright \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m app && mkdir -p /data && chown -R app:app /app /data
USER app

VOLUME ["/data"]
WORKDIR /app
ENTRYPOINT ["python", "run.py"]
CMD ["check"]
