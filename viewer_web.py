import os
import sys
import json
import sqlite3
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_FILE = "endfield_gacha_history.db"
PORT = 8000

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>엔드필드 가챠 기록 뷰어 (Web)</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            background-color: #f8f9fa; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .container { max-width: 1000px; margin-top: 40px; }
        .gacha-table th { background-color: #343a40; color: white; border-color: #454d55; }
        .rarity-6 { color: #ff5e00 !important; font-weight: bold; font-size: 1.05rem; }
        .rarity-5 { color: #ffb800 !important; font-weight: bold; }
        .bg-rarity-6 td { background-color: rgba(255, 94, 0, 0.08) !important; }
        .bg-rarity-5 td { background-color: rgba(255, 184, 0, 0.08) !important; }
        .rarity-4 { color: #0d6efd; }
        .summary-card { border-left: 5px solid #0d6efd; margin-bottom: 20px; }
        .card-title { font-weight: 600; color: #495057; }
        .stats-text { font-size: 1.1rem; }
        .table-responsive { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        tr:hover { background-color: #e9ecef !important; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="mb-4 text-center">📈 엔드필드 로컬 가챠 기록 뷰어</h2>
        
        <div class="card summary-card shadow-sm">
            <div class="card-body">
                <div class="row align-items-end">
                    <div class="col-md-5">
                        <label for="accountSelect" class="form-label text-muted fw-bold">1. 조회할 계정 선택:</label>
                        <select id="accountSelect" class="form-select" onchange="loadRecords()"></select>
                    </div>
                    <div class="col-md-5 mt-3 mt-md-0">
                        <label for="poolSelect" class="form-label text-muted fw-bold">2. 뽑기 종류(배너) 필터:</label>
                        <select id="poolSelect" class="form-select" onchange="renderTable()">
                            <option value="">-- 전체 기록 보기 --</option>
                        </select>
                    </div>
                    <div class="col-md-2 mt-3 mt-md-0 d-grid">
                        <button class="btn btn-outline-primary" onclick="loadRecords()">새로고침</button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mb-4 shadow-sm" id="statsCard" style="display: none;">
            <div class="card-body">
                <h5 class="card-title mb-3">통계 요약</h5>
                <p class="card-text stats-text" id="statsText"></p>
            </div>
        </div>

        <div class="table-responsive">
            <table class="table table-hover table-bordered mb-0 bg-white">
                <thead class="text-center">
                    <tr>
                        <th width="10%">순번</th>
                        <th width="20%">뽑은 시간</th>
                        <th width="15%">분류</th>
                        <th width="30%">이름</th>
                        <th width="10%">등급</th>
                        <th width="15%">배너 종류</th>
                    </tr>
                </thead>
                <tbody id="gachaBody" class="text-center align-middle">
                    <tr><td colspan="6" class="text-muted">데이터를 불러오는 중입니다...</td></tr>
                </tbody>
            </table>
        </div>
        
        <div class="text-center mt-4 mb-5 text-muted small">
            <p>Endfield Gacha Tracker 로컬 웹 뷰어 • 포트 8000</p>
        </div>
    </div>

    <script>
        let allData = [];
        let accountLoaded = false;
        
        async function fetchAccounts() {
            try {
                const res = await fetch('/api/accounts');
                const accounts = await res.json();
                const sel = document.getElementById('accountSelect');
                sel.innerHTML = '';
                
                if(accounts.length === 0) {
                    sel.innerHTML = '<option value="">(기록된 계정이 없습니다)</option>';
                    document.getElementById('gachaBody').innerHTML = '<tr><td colspan="6" class="text-center text-danger">저장된 데이터베이스가 비어있습니다. 파이썬 스크립트를 먼저 실행해주세요.</td></tr>';
                    return;
                }
                
                accounts.forEach(acc => {
                    const opt = document.createElement('option');
                    opt.value = acc.uid;
                    opt.textContent = acc.alias ? `${acc.alias} (UID: ${acc.uid})` : `UID: ${acc.uid}`;
                    sel.appendChild(opt);
                });
                
                accountLoaded = true;
                loadRecords();
            } catch (e) {
                console.error(e);
                document.getElementById('gachaBody').innerHTML = '<tr><td colspan="6" class="text-center text-danger">서버 접속 오류! 서버가 켜져있는지 콘솔을 확인해주세요.</td></tr>';
            }
        }

        async function loadRecords() {
            if(!accountLoaded) return;
            const uid = document.getElementById('accountSelect').value;
            if(!uid) return;
            
            try {
                const res = await fetch(`/api/records?uid=${encodeURIComponent(uid)}`);
                allData = await res.json();
                
                // 배너 목록 업데이트
                const poolSel = document.getElementById('poolSelect');
                const currentPool = poolSel.value;
                let pools = new Set();
                allData.forEach(r => {
                    if(r.poolName) pools.add(r.poolName);
                });
                
                poolSel.innerHTML = '<option value="">-- 전체 기록 보기 --</option>';
                poolSel.innerHTML += '<option value="__ALL_CHAR__">-- 전체 캐릭터 보기 --</option>';
                poolSel.innerHTML += '<option value="__ALL_WEAP__">-- 전체 무기 보기 --</option>';
                pools.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.textContent = p;
                    poolSel.appendChild(opt);
                });
                
                // 이전 선택값 유지 시도
                if(pools.has(currentPool)) {
                    poolSel.value = currentPool;
                }
                
                renderTable();
            } catch(e) {
                console.error(e);
            }
        }
        
        function renderTable() {
            const tb = document.getElementById('gachaBody');
            const poolFilter = document.getElementById('poolSelect').value;
            
            let filtered = allData;
            if(poolFilter === '__ALL_CHAR__') {
                filtered = filtered.filter(r => !r.weaponId);
            } else if (poolFilter === '__ALL_WEAP__') {
                filtered = filtered.filter(r => r.weaponId);
            } else if(poolFilter) {
                filtered = filtered.filter(r => r.poolName === poolFilter);
            }
            
            // 최신순으로 위에 오도록 역순 배치
            const displayData = [...filtered].reverse();
            
            if(displayData.length === 0) {
                tb.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">해당 조건의 가챠 기록이 없습니다.</td></tr>';
                document.getElementById('statsCard').style.display = 'none';
                return;
            }
            
            let count6 = 0;
            let count5 = 0;
            let charRecords = [];
            let weapRecords = [];
            
            displayData.forEach((r, idx) => {
                const serialNum = displayData.length - idx;
                if(r.weaponId) {
                    weapRecords.push({r, serialNum});
                } else {
                    charRecords.push({r, serialNum});
                }
            });

            let htmlStr = '';

            function createRowHTML(item) {
                const r = item.r;
                const serialNum = item.serialNum;
                const rarity = parseInt(r.rarity) || 0;
                let rClass = '';
                let bgClass = '';
                let starStr = '';
                
                if(rarity === 6) { rClass = 'rarity-6'; bgClass = 'bg-rarity-6'; count6++; starStr="★★★★★★"; }
                else if(rarity === 5) { rClass = 'rarity-5'; bgClass = 'bg-rarity-5'; count5++; starStr="★★★★★"; }
                else if(rarity === 4) { rClass = 'rarity-4'; starStr="★★★★"; }
                else { starStr = "★★★ 이하"; }
                
                let name = r.charName || r.weaponName || '알수없음';
                const isFree = (r.isFree === 'True' || r.isFree === '1' || r.isFree === true);
                if(isFree) {
                    name += ' <span class="badge bg-primary ms-1">무료</span>';
                }

                const type = r.charName ? '👤 캐릭터' : '⚔️ 무기';
                
                let timeStr = "";
                if(r.gachaTime) {
                    timeStr = r.gachaTime;
                } else if(r.gachaTs) { // fallback
                    const dt = new Date(parseInt(r.gachaTs));
                    timeStr = dt.getFullYear() + "-" + 
                              String(dt.getMonth() + 1).padStart(2, '0') + "-" + 
                              String(dt.getDate()).padStart(2, '0') + " " + 
                              String(dt.getHours()).padStart(2, '0') + ":" + 
                              String(dt.getMinutes()).padStart(2, '0') + ":" + 
                              String(dt.getSeconds()).padStart(2, '0');
                } else {
                    timeStr = "-";
                }
                
                return `<tr class="${bgClass}">
                    <td class="text-muted">${serialNum}</td>
                    <td>${timeStr}</td>
                    <td>${type}</td>
                    <td class="${rClass}">${name}</td>
                    <td class="${rClass}">${starStr}</td>
                    <td><span class="badge bg-secondary">${r.poolName || '알수없음'}</span></td>
                </tr>`;
            }

            if (charRecords.length > 0) {
                htmlStr += `<tr><td colspan="6" class="table-light text-center fw-bold text-muted py-2" style="background-color: #e9ecef;">👤 캐릭터 가챠 기록</td></tr>`;
                charRecords.forEach(item => { htmlStr += createRowHTML(item); });
            }
            if (weapRecords.length > 0) {
                htmlStr += `<tr><td colspan="6" class="table-light text-center fw-bold text-muted py-2" style="background-color: #e9ecef;">⚔️ 무기 가챠 기록</td></tr>`;
                weapRecords.forEach(item => { htmlStr += createRowHTML(item); });
            }
            
            tb.innerHTML = htmlStr;
            
            // Stats Update
            const total = displayData.length;
            const rate6 = total > 0 ? ((count6 / total) * 100).toFixed(2) : 0;
            const rate5 = total > 0 ? ((count5 / total) * 100).toFixed(2) : 0;
            
            document.getElementById('statsCard').style.display = 'block';
            document.getElementById('statsText').innerHTML = `
                현재 검색 조건(계정/배너) 기준 총 <strong>${total}</strong>회 뽑기 중:<br>
                ✨ <strong>6성 획득:</strong> <span class="rarity-6">${count6}</span>회 <span class="text-muted">(약 ${rate6}%)</span> <br>
                ⭐ <strong>5성 획득:</strong> <span class="rarity-5">${count5}</span>회 <span class="text-muted">(약 ${rate5}%)</span>
            `;
        }

        window.onload = fetchAccounts;
    </script>
</body>
</html>
"""

class GachaRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # HTTP 로그 숨기기 (터미널 깔끔하게 유지)
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif parsed.path == "/api/accounts":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # uid, alias 가져오기
                cur.execute("SELECT DISTINCT uid, alias FROM gacha_records ORDER BY uid")
                rows = cur.fetchall()
                conn.close()
                data = [{"uid": r["uid"], "alias": r["alias"] if "alias" in r.keys() else ""} for r in rows]
            except Exception as e:
                print(f"API Error (accounts): {e}")
                data = []
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        elif parsed.path == "/api/records":
            qs = parse_qs(parsed.query)
            uid = qs.get("uid", [""])[0]
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM gacha_records WHERE uid = ? ORDER BY CAST(gachaTs AS INTEGER) ASC, CAST(seqId AS INTEGER) ASC", (uid,))
                rows = cur.fetchall()
                conn.close()
                data = [dict(r) for r in rows]
            except Exception as e:
                print(f"API Error (records): {e}")
                data = []
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server_address = ('', 8000)
    # 포트 충돌 방지 로직 (간단 구현)
    global PORT
    while True:
        try:
            server_address = ('', PORT)
            httpd = HTTPServer(server_address, GachaRequestHandler)
            break
        except OSError:
            PORT += 1
            if PORT > 8050:
                print("❌ 사용 가능한 포트를 찾을 수 없습니다.")
                sys.exit(1)

    print("\n" + "="*50)
    print(f"🚀 웹 브라우저 뷰어 서버 구동 완료!")
    print(f"🌐 접속 주소: http://localhost:{PORT}")
    print("종료하려면 이 콘솔 창을 닫거나 Ctrl+C를 누르세요.")
    print("="*50 + "\n")
    
    # 0.5초 뒤 브라우저 자동 오픈
    threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n뷰어를 종료합니다.")
        httpd.server_close()
        sys.exit(0)

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print("❌ 저장된 데이터베이스 파일을 찾을 수 없습니다! (endfield_gacha_history.db)")
        print("본스크립트(endfield_tracker)로 게임 토큰을 읽어들여 데이터를 먼저 저장해주세요.")
        input("엔터를 누르면 종료됩니다...")
        sys.exit(1)
        
    run_server()
