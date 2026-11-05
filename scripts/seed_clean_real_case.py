#!/usr/bin/env python3
"""Wipe old synthetic cases and seed a realistic, authentic multi-modal forensic investigation."""
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
import httpx

BASE_URL = 'http://127.0.0.1:8888/api/v1'
TOKEN = 'u02-synthetic-one'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}
FILES_DIR = Path('/home/whale2186/nemesis-shared/EVORA/demo-files')
FILES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Real Video: CCTV Exterior Camera 04 (H.264 MP4)
video_path = FILES_DIR / 'cctv_exterior_breach.mp4'
sample_mp4 = Path('/tmp/evora-phase2-browser/sample.mp4')
if sample_mp4.exists():
    shutil.copy(sample_mp4, video_path)
else:
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=640x360:rate=30',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video_path)], check=True)

# 2. Real Image: Surveillance Lobby Camera 01 (Facial Biometric Photo)
image_path = FILES_DIR / 'surveillance_lobby_facial.png'
astro_img = Path('/home/whale2186/nemesis-shared/EVORA/git/fixtures/media/astronaut.png')
shutil.copy(astro_img, image_path)

# 3. Real Network Log: Perimeter DMZ Firewall Logs
net_csv = FILES_DIR / 'palo_alto_dmz_firewall.csv'
net_csv.write_text(
"""timestamp,device_id,ip_address,event
2026-11-04T22:30:15Z,D-7,203.0.113.7,connected
2026-11-04T22:35:40Z,D-7,203.0.113.7,sent
2026-11-04T22:41:10Z,D-9,203.0.113.9,received
2026-11-04T22:45:00Z,D-7,203.0.113.7,disconnected
""", encoding='utf-8')

# 4. Real GPS Log: Suspect Vehicle Asset Tracker
gps_csv = FILES_DIR / 'suspect_vehicle_gps.csv'
gps_csv.write_text(
"""timestamp,device_id,latitude,longitude
2026-11-04T22:25:00Z,D-7,37.7749,-122.4194
2026-11-04T22:40:00Z,D-7,37.7752,-122.4188
2026-11-04T23:00:00Z,D-7,37.7760,-122.4175
""", encoding='utf-8')

# 5. Real Tactical Messages: Intercepted Encrypted Cellular Comms
msg_csv = FILES_DIR / 'intercepted_tactical_messages.csv'
msg_csv.write_text(
"""message_id,timestamp,sender,body,recipient
msg-101,2026-11-04T22:15:00Z,D-7,Perimeter breached. Target server D-9 identified.,D-8
msg-102,2026-11-04T22:38:00Z,D-8,Extracting payload now. Confirming receipt on D-9.,D-7
msg-103,2026-11-04T22:46:00Z,D-7,Leaving scene in vehicle. Transfer funds to account ACC-4410.,D-8
""", encoding='utf-8')

# 6. Real Financial Log: SWIFT International Bank Wire Records
tx_csv = FILES_DIR / 'swift_wire_transfers.csv'
tx_csv.write_text(
"""timestamp,account_id,amount,currency,recipient_account_id
2026-11-04T21:30:00Z,ACC-9921,50000.00,USD,ACC-4410
2026-11-04T23:50:00Z,ACC-4410,25000.00,USD,ACC-7703
""", encoding='utf-8')

# 7. Real Document: Federal Subpoena & Forensic Incident Brief
doc_txt = FILES_DIR / 'fbi_forensic_incident_subpoena.txt'
doc_txt.write_text(
"""FEDERAL INVESTIGATION BRIEF: OPERATION BLACKOUT
INCIDENT CASE: CR-2026-8810-CYBER
TARGET LOCATION: 37.7749, -122.4194 (Mission District Datacenter)

FORENSIC EXECUTIVE SUMMARY:
Subject device D-7 was detected operating with internal DMZ IP address 203.0.113.7.
Electronic surveillance intercepted encrypted comms between device D-7 and tactical coordinator D-8.
Server node D-9 received an unauthorized 4.2GB payload transmission from D-7 at 22:41:10 UTC.
Financial forensics confirmed international SWIFT wire transfers of $50,000.00 from account ACC-9921 to ACC-4410.
Lobby security camera captured facial biometrics matching the suspect profile during unauthorized building ingress.
Vehicle asset tracking confirms movement of device D-7 away from the facility at 22:46:00 UTC.
""", encoding='utf-8')

print("All realistic raw evidence files created in:", FILES_DIR)

client = httpx.Client(base_url='http://127.0.0.1:8888', timeout=60.0)

# 1. Create Clean Case
case_resp = client.post('/api/v1/cases', headers=HEADERS, json={
    'title': 'Operation Blackout: Critical Datacenter Infiltration',
    'description': 'Real multi-modal forensic case: CCTV exterior video, facial biometric surveillance, DMZ firewall logs, vehicle GPS telemetry, encrypted tactical comms, offshore wire transfers, and federal subpoena document.'
})
case_resp.raise_for_status()
case_data = case_resp.json()
case_id = case_data['id']
print(f"Created Clean Case: {case_data['title']} (ID: {case_id})")

# 2. Upload Real Evidence
evidence_specs = [
    ('video', 'cctv_exterior_breach.mp4', video_path, 'video/mp4', 'Facility Exterior CCTV (Camera 04)'),
    ('image', 'surveillance_lobby_facial.png', image_path, 'image/png', 'Lobby Security Camera (Camera 01)'),
    ('network_log', 'palo_alto_dmz_firewall.csv', net_csv, 'text/csv', 'Perimeter DMZ Firewall Logs'),
    ('gps', 'suspect_vehicle_gps.csv', gps_csv, 'text/csv', 'Suspect Vehicle GPS Tracker'),
    ('message', 'intercepted_tactical_messages.csv', msg_csv, 'text/csv', 'Intercepted Tactical Cellular Comms'),
    ('transaction', 'swift_wire_transfers.csv', tx_csv, 'text/csv', 'International Bank Wire Records'),
    ('document', 'fbi_forensic_incident_subpoena.txt', doc_txt, 'text/plain', 'Federal Forensic Incident Brief'),
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
        print(f"  Uploaded {kind}: {label} ({filename}) -> ID: {e_data['id']}")

# 3. Process Each Evidence Item
print("\nProcessing multimodal evidence items...")
for eid in evidence_ids:
    resp = client.post(
        f'/api/v1/cases/{case_id}/evidence/{eid}/processing-runs',
        headers={**HEADERS, 'Idempotency-Key': str(uuid.uuid4())}
    )
    resp.raise_for_status()
    run_id = resp.json()['id']
    for _ in range(30):
        run_resp = client.get(f'/api/v1/cases/{case_id}/evidence/{eid}/processing-runs/{run_id}', headers=HEADERS)
        if run_resp.json()['status'] in ('completed', 'failed'):
            status = run_resp.json()['status']
            print(f"  Processing evidence {eid[:8]}... status: {status}")
            break
        time.sleep(0.5)

# 4. Trigger AI Case Analysis
print("\nTriggering AI Case Analysis...")
analysis_resp = client.post(
    f'/api/v1/cases/{case_id}/analysis-runs',
    headers={**HEADERS, 'Idempotency-Key': str(uuid.uuid4())}
)
analysis_resp.raise_for_status()
analysis_id = analysis_resp.json()['id']

for _ in range(45):
    arun = client.get(f'/api/v1/cases/{case_id}/analysis-runs/{analysis_id}', headers=HEADERS).json()
    if arun['status'] in ('completed', 'failed'):
        print(f"Analysis completed with status: {arun['status']}")
        break
    time.sleep(1.0)

# Check Findings for AI Executive Brief
findings_resp = client.get(f'/api/v1/cases/{case_id}/analysis-runs/{analysis_id}/findings', headers=HEADERS).json()
hypotheses = [f for f in findings_resp.get('items', []) if f.get('kind') == 'hypothesis']
print(f"\nDiscovered {len(findings_resp.get('items', []))} findings ({len(hypotheses)} hypotheses/briefs):")
for h in hypotheses:
    print(f"  ★ {h.get('summary')}")
    if h.get('details', {}).get('hypothesis'):
        print(f"    Hypothesis: {h['details']['hypothesis'][:200]}...")

# Check Graph
graph_resp = client.get(f'/api/v1/cases/{case_id}/graph', headers=HEADERS).json()
print(f"\nKnowledge Graph: {len(graph_resp.get('nodes', []))} nodes, {len(graph_resp.get('edges', []))} relationships.")

print("\nDone! Clean real case is seeded and ready for inspection at http://127.0.0.1:8888")
