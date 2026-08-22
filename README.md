# SM Release Center

软件发布中心：版本、制品签名、审批、回滚和发布审计。

```powershell
git clone https://github.com/luoshitianchen/SM-Release-Center.git
cd SM-Release-Center
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8550
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。
