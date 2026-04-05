# -*- coding: utf-8 -*-
"""
Sharkfin Bot Web Dashboard
FastAPI + HTML interface for bot control
"""
import os
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Sharkfin Bot Dashboard")

# Paths
BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "sharkfin_state.json"
LOG_FILE = BASE_DIR / "sharkfin.log"
BOT_SCRIPT = BASE_DIR / "bot_sharkfin.py"

# Bot process
bot_process: Optional[asyncio.subprocess.Process] = None


def load_state():
    """Load bot state"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"running": False}


def load_config():
    """Load config"""
    config_file = BASE_DIR / "bot_config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"spacing": 0.03, "levels": 40, "range_width": 0.5, "position_size": 150, "stop_loss": 1.5}


def save_state(state: dict):
    """Save bot state"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_log_lines(n: int = 50):
    """Get last n log lines"""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return lines[-n:]
    except:
        return []


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page"""
    state = load_state()
    logs = get_log_lines(30)
    config = load_config()
    
    html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sharkfin Bot Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            color: #00d9ff;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .status-badge {{
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }}
        .running {{ background: #00c853; }}
        .stopped {{ background: #ff5252; }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .card h2 {{
            color: #00d9ff;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        .stat {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #333;
        }}
        .stat:last-child {{ border-bottom: none; }}
        .stat-label {{ color: #888; }}
        .stat-value {{ font-weight: bold; color: #fff; }}
        .positive {{ color: #00c853; }}
        .negative {{ color: #ff5252; }}
        
        .controls {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        button {{
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .btn-start {{
            background: #00c853;
            color: white;
        }}
        .btn-stop {{
            background: #ff5252;
            color: white;
        }}
        .btn-save {{
            background: #2196f3;
            color: white;
        }}
        button:hover {{ opacity: 0.8; }}
        button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        
        .param-group {{
            margin-bottom: 15px;
        }}
        .param-group label {{
            display: block;
            margin-bottom: 5px;
            color: #888;
            font-size: 14px;
        }}
        .param-group input {{
            width: 100%;
            padding: 10px;
            background: #0f3460;
            border: 1px solid #333;
            border-radius: 5px;
            color: #fff;
            font-size: 16px;
        }}
        .param-group input:focus {{
            outline: none;
            border-color: #00d9ff;
        }}
        
        .log-container {{
            background: #0f0f23;
            border-radius: 10px;
            padding: 15px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .log-line {{
            padding: 3px 0;
            border-bottom: 1px solid #222;
        }}
        .log-time {{ color: #666; }}
        .log-filled {{ color: #00c853; }}
        .log-error {{ color: #ff5252; }}
        .log-info {{ color: #2196f3; }}
        
        .refresh-info {{
            text-align: center;
            color: #666;
            margin-top: 20px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>
            Sharkfin Bot Dashboard
            <span class="status-badge {'running' if state.get('running') else 'stopped'}">
                {'RUNNING' if state.get('running') else 'STOPPED'}
            </span>
        </h1>
        
        <div class="grid">
            <div class="card">
                <h2>📊 Status</h2>
                <div class="stat">
                    <span class="stat-label">Range</span>
                    <span class="stat-value">${state.get('range_lower', 0):,.0f} - ${state.get('range_upper', 0):,.0f}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Center</span>
                    <span class="stat-value">${state.get('range_center', 0):,.0f}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Position</span>
                    <span class="stat-value">{state.get('position', 0):.6f} BTC</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Trades</span>
                    <span class="stat-value">{state.get('trades', 0)}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Total PnL</span>
                    <span class="stat-value {'positive' if state.get('total_pnl', 0) >= 0 else 'negative'}">
                        ${state.get('total_pnl', 0):.2f}
                    </span>
                </div>
                
                <div class="controls">
                    <button class="btn-start" onclick="startBot()" {'disabled' if state.get('running') else ''}>
                        ▶ Start
                    </button>
                    <button class="btn-stop" onclick="stopBot()" {'disabled' if not state.get('running') else ''}>
                        ⏹ Stop
                    </button>
                    <button onclick="location.reload()">🔄 Refresh</button>
                </div>
            </div>
            
            <div class="card">
                <h2>⚙️ Parameters</h2>
                <div class="param-group">
                    <label>Grid Spacing (%)</label>
                    <input type="number" id="spacing" value="{config.get('spacing', 0.03)}" step="0.01" min="0.01" max="1.0">
                </div>
                <div class="param-group">
                    <label>Grid Levels</label>
                    <input type="number" id="levels" value="{config.get('levels', 40)}" min="10" max="100">
                </div>
                <div class="param-group">
                    <label>Range Width (%)</label>
                    <input type="number" id="range_width" value="{config.get('range_width', 0.5)}" step="0.1" min="0.5" max="5.0">
                </div>
                <div class="param-group">
                    <label>Position Size (USD)</label>
                    <input type="number" id="position_size" value="{config.get('position_size', 150)}" min="50" max="1000">
                </div>
                <div class="param-group">
                    <label>Stop Loss (%)</label>
                    <input type="number" id="stop_loss" value="{config.get('stop_loss', 1.5)}" step="0.1" min="0.5" max="5.0">
                </div>
                <div class="controls">
                    <button class="btn-save" onclick="saveParams()">💾 Save</button>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>📜 Log (Last 30 lines)</h2>
            <div class="log-container">
                {''.join([f'<div class="log-line"><span class="log-time">{line.split("|")[0] if "|" in line else ""}</span> {line.split("|")[1] if "|" in line else line}</div>' for line in logs])}
            </div>
        </div>
        
        <p class="refresh-info">Auto-refresh every 10 seconds | Last update: {datetime.now().strftime('%H:%M:%S')}</p>
    </div>
    
    <script>
        async function startBot() {{
            const response = await fetch('/api/start', {{ method: 'POST' }});
            const data = await response.json();
            alert(data.message);
            location.reload();
        }}
        
        async function stopBot() {{
            const response = await fetch('/api/stop', {{ method: 'POST' }});
            const data = await response.json();
            alert(data.message);
            location.reload();
        }}
        
        async function saveParams() {{
            const params = {{
                spacing: parseFloat(document.getElementById('spacing').value),
                levels: parseInt(document.getElementById('levels').value),
                range_width: parseFloat(document.getElementById('range_width').value),
                position_size: parseFloat(document.getElementById('position_size').value),
                stop_loss: parseFloat(document.getElementById('stop_loss').value)
            }};
            
            const response = await fetch('/api/params', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(params)
            }});
            const data = await response.json();
            alert(data.message);
        }}
        
        // Auto refresh
        setTimeout(() => location.reload(), 10000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.post("/api/start")
async def api_start():
    """Start the bot"""
    global bot_process
    
    state = load_state()
    if state.get("running"):
        return {"success": False, "message": "Bot is already running"}
    
    # Start bot process
    try:
        bot_process = await asyncio.create_subprocess_exec(
            "python", str(BOT_SCRIPT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        state["running"] = True
        save_state(state)
        return {"success": True, "message": "Bot started"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@app.post("/api/stop")
async def api_stop():
    """Stop the bot"""
    global bot_process
    
    state = load_state()
    if not state.get("running"):
        return {"success": False, "message": "Bot is not running"}
    
    # Kill bot process
    try:
        # Use taskkill on Windows
        subprocess.run(["taskkill", "/F", "/IM", "python.exe"], capture_output=True)
        state["running"] = False
        save_state(state)
        return {"success": True, "message": "Bot stopped"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@app.post("/api/params")
async def api_params(request: Request):
    """Save parameters"""
    params = await request.json()
    
    # Save to config file
    config_file = BASE_DIR / "bot_config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    
    return {"success": True, "message": "Parameters saved. Restart bot to apply."}


@app.get("/api/status")
async def api_status():
    """Get bot status as JSON"""
    state = load_state()
    logs = get_log_lines(10)
    return {
        "state": state,
        "logs": [line.strip() for line in logs]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
