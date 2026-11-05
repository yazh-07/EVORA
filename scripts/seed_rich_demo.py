#!/usr/bin/env python3
"""Build and populate a complete, realistic multi-modal forensic demo case."""
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
import httpx

BASE_URL = 'http://127.0.0.1:8888/api/v1'
TOKEN = 'u02-synthetic-one'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}
DEMO_DIR = Path('/tmp/evora-demo-files')
DEMO_DIR.mkdir(parents=True, exist_ok=True)

# 1. Video
sample_mp4 = Path('/tmp/evora-phase2-browser/sample.mp4')
video_path = DEMO_DIR / 'cctv_exterior.mp4'
if sample_mp4.exists():
    shutil.copy(sample_mp4, video_path)
else:
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=640x360:rate=30',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video_path)], check=True)

# 2. Image
astro_img = Path('/home/whale2186/nemesis-shared/EVORA/evora-clean/fixtures/media/astronaut.png')
image_path = DEMO_DIR / 'lobby_surveillance.png'
shutil.copy(astro_img, image_path)

# 3. Network Log
net_csv = DEMO_DIR / 'perimeter_firewall.csv'
net_csv.write_text(
"""timestamp,device_id,ip_address,event
2026-11-04T22:30:15Z,D-7,203.0.113.7,connected
2026-11-04T22:35:40Z,D-7,203.0.113.7,sent
2026-11-04T22:41:10Z,D-9,203.0.113.9,received
2026-11-04T22:45:00Z,D-7,203.0.113.7,disconnected
""", encoding='utf-8')

# 4. GPS Log
gps_csv = DEMO_DIR / 'suspect_gps.csv'
gps_csv.write_text(
"""timestamp,device_id,latitude,longitude
2026-11-04T22:25:00Z,D-7,37.7749,-122.4194
2026-11-04T22:40:00Z,D-7,37.7752,-122.4188
2026-11-04T23:00:00Z,D-7,37.7760,-122.4175
""", encoding='utf-8')

# 5. Messages
msg_csv = DEMO_DIR / 'intercepted_messages.csv'
msg_csv.write_text(
"""message_id,timestamp,sender,body,recipient
msg-001,2026-11-04T22:15:00Z,D-7,Perimeter breached. Target server D-9 identified.,D-8
msg-002,2026-11-04T22:38:00Z,D-8,Extracting payload now. Confirming receipt on D-9.,D-7
msg-003,2026-11-04T22:46:00Z,D-7,Leaving scene in vehicle. Transfer funds to account ACC-4410.,D-8
""", encoding='utf-8')

# 6. Transactions
tx_csv = DEMO_DIR / 'wire_transfers.csv'
tx_csv.write_text(
"""timestamp,account_id,amount,currency,recipient_account_id
2026-11-04T21:30:00Z,ACC-9921,50000.00,USD,ACC-4410
2026-11-04T23:50:00Z,ACC-4410,25000.00,USD,ACC-7703
""", encoding='utf-8')

# 7. Document
doc_txt = DEMO_DIR / 'incident_brief.txt'
doc_txt.write_text(
"""INCIDENTAL INVESTIGATION BRIEF: OPERATION NIGHTSHADE
CASE ID: SEC-2026-991A
LOCATION: 37.7749, -122.4194 (Mission District Datacenter)

SUMMARY OF FORENSIC FINDINGS:
Suspect device D-7 was detected operating with internal subnet IP 203.0.113.7.
Coordinated communication observed between D-7 and D-8 during the exfiltration window.
Server D-9 confirmed receiving exfiltrated packets from D-7 at 22:41:10 UTC.
Financial tracking confirms $50,000 wire transfer from account ACC-9921 to ACC-4410.
Lobby surveillance captured facial imagery matching suspect profile during ingress.
""", encoding='utf-8')

print("All realistic raw demo files written to", DEMO_DIR)

client = httpx.Client(base_url='http://127.0.0.1:8888', timeout=60.0)

# 1. Create Case
case_resp = client.post('/api/v1/cases', headers=HEADERS, json={
    'title': 'Operation Nightshade: Secure Datacenter Infiltration',
    'description': 'Full multimodal forensic investigation: CCTV footage, facial biometric photo, perimeter firewall logs, suspect GPS tracks, encrypted messages, wire transfers, and subpoena document.'
})
case_resp.raise_for_status()
case_data = case_resp.json()
case_id = case_data['id']
print(f"Created Case: {case_data['title']} (ID: {case_id})")

# 2. Upload Evidence
evidence_specs = [
    ('video', 'cctv_exterior.mp4', video_path, 'video/mp4', 'Facility Exterior CCTV (Camera 04)'),
    ('image', 'lobby_surveillance.png', image_path, 'image/png', 'Lobby Security Camera (Camera 01)'),
    ('network_log', 'perimeter_firewall.csv', net_csv, 'text/csv', 'Perimeter DMZ Firewall Logs'),
    ('gps', 'suspect_gps.csv', gps_csv, 'text/csv', 'Suspect Vehicle GPS Tracker'),
    ('message', 'intercepted_messages.csv', msg_csv, 'text/csv', 'Intercepted Tactical Cellular Comms'),
    ('transaction', 'wire_transfers.csv', tx_csv, 'text/csv', 'International Bank Wire Records'),
    ('document', 'incident_brief.txt', doc_txt, 'text/plain', 'Forensic Incident Brief & Subpoena'),
]

evidence_ids = []
for kind, filename, file_path, media_type, label in evidence_specs:
    with open(file_path, 'rb') as f:
        files = {'file': (filename, f, media_type)}
        data = {'kind': kind, 'source_label': label}
        resp = client.post(f'/api/v1/cases/{case_id}/evidence', headers=HEADERS, data=data, files=files)
        resp.raise_for_status()
        e_data = resp.json()
        evidence_ids.append(e_data['id'])
        print(f"Uploaded {kind}: {label} ({filename}) -> ID: {e_data['id']}")

# 3. Process Each Evidence Item
for eid in evidence_ids:
    resp = client.post(
        f'/api/v1/cases/{case_id}/evidence/{eid}/processing-runs',
        headers={**HEADERS, 'Idempotency-Key': str(uuid.uuid4())}
    )
    resp.raise_for_status()
    run_id = resp.json()['id']
    # Poll until completed
    for _ in range(30):
        run_resp = client.get(f'/api/v1/cases/{case_id}/evidence/{eid}/processing-runs/{run_id}', headers=HEADERS)
        if run_resp.json()['status'] in ('completed', 'failed'):
            status = run_resp.json()['status']
            print(f"Processing run for evidence {eid[:8]}... completed with status '{status}'")
            break
        time.sleep(0.5)

# 4. Trigger Case Analysis
print("Triggering full case analysis...")
analysis_resp = client.post(
    f'/api/v1/cases/{case_id}/analysis-runs',
    headers={**HEADERS, 'Idempotency-Key': str(uuid.uuid4())}
)
analysis_resp.raise_for_status()
analysis_id = analysis_resp.json()['id']

# Poll analysis run
for _ in range(30):
    arun = client.get(f'/api/v1/cases/{case_id}/analysis-runs/{analysis_id}', headers=HEADERS).json()
    if arun['status'] in ('completed', 'failed'):
        print(f"Analysis run {analysis_id[:8]} completed with status: {arun['status']}")
        break
    time.sleep(0.5)

# Check graph
graph_resp = client.get(f'/api/v1/cases/{case_id}/graph', headers=HEADERS).json()
print(f"Knowledge Graph populated: {len(graph_resp.get('nodes', []))} nodes, {len(graph_resp.get('edges', []))} relationships!")
for e in graph_resp.get('edges', [])[:10]:
    print(f"  Edge: {e.get('from_id')} --({e.get('label')})--> {e.get('to_id')}")

# Check triage
triage_resp = client.get(f'/api/v1/cases/{case_id}/triage', headers=HEADERS).json()
print(f"Triage Rankings: {len(triage_resp.get('items', []))} prioritized evidence sources")
for t in triage_resp.get('items', []):
    s = t.get('score')
    score_str = f"{s:.1f}" if isinstance(s, (int, float)) else "N/A"
    print(f"  [{t.get('priority')}] Score {score_str} - Evidence: {t.get('evidence_id')}")

print("\nDemo case fully seeded and ready for inspection!")
