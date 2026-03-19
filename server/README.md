# MindShadow Server

## 本地开发

```bash
python -m pip install -r requirements.txt
python app.py
```

默认端口 `5001`。

## 生产部署

1. 复制配置模板：

```bash
cp .env.production.example .env.local
```

2. 修改 `.env.local` 中的真实值，尤其是：

- `MINDSHADOW_LLM_API_KEY`
- `MINDSHADOW_OPS_TOKEN`
- `MINDSHADOW_DB_PATH`
- `MINDSHADOW_UPLOAD_DIR`

3. 安装生产依赖：

```bash
python -m pip install -r requirements-prod.txt
```

4. 启动服务：

```bash
gunicorn -c gunicorn.conf.py server.wsgi:app
```

## 健康检查

```bash
curl http://127.0.0.1:5001/api/health
```

## 回滚建议

- 保留上一版 `.env.local` 与镜像版本。
- 回滚时先替换应用版本，再恢复上一版配置并重启进程。
