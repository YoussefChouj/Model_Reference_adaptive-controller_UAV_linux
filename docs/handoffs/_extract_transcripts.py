"""Extract feature-relevant messages from all agent transcripts."""
import json, os, glob, re

BASE = r'C:\Users\Acer\.cursor\projects\c-Users-Acer-Desktop-UAV-lab-FreeRTOS-Six-Degrees-of-Freedom-Adaptive-controller\agent-transcripts'
OUT = r'C:\Users\Acer\Desktop\UAV_lab\FreeRTOS---Six_Degrees_of_Freedom _Adaptive_controller\docs\handoffs\_transcript_extract.txt'

KEYWORDS = re.compile(
    r'(GUI|ground.station|dashboard|Feature|feature|roadmap|proposal|plan|upgrade|'
    r'new.feature|telemetry|protocol|frame|0x|recommend|next.step|future|work.item|'
    r'persistence|EEPROM|OF.drift|optical.flow|mrac.weight|'
    r'sysid|OF-hold|OF_hold|estimator|EKF|calibrat|'
    r'Frame.C|frame.C|add.frame|new.frame|'
    r'GUI.layout|live.plot|real.time|altitude.hold|autopilot|'
    r'flight.mode|control.mode|multi.metric|logging|session.replay|replay|'
    r'drone.mode|arm.disarm|pre.arm|prearm|motor.test|bench.test|'
    r'optical.flow.xy|locxPID|locyPID|position.hold|height.hold|'
    r'mrac.persist|mrac.save|mrac.load|weight.save|'
    r'ADR-|adr-|TODO|FUTURE|deferred|left.to|remaining|'
    r'anything.else|what.else|else.to|also.want|also.need|'
    r'gui.upgrade|dashboard.upgrade|ground.station.upgrade|'
    r'protocol.upgrade|telemetry.upgrade)',
    re.IGNORECASE
)

with open(OUT, 'w', encoding='utf-8') as out_f:
    for fpath in sorted(glob.glob(os.path.join(BASE, '**', '*.jsonl'), recursive=True)):
        fname = os.path.basename(fpath)
        dirn = os.path.dirname(fpath)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            for lineno, line in enumerate(lines):
                try:
                    rec = json.loads(line.strip())
                    role = rec.get('role','')
                    if role not in ('user', 'assistant'):
                        continue
                    msg = rec.get('message', {})
                    content = msg.get('content', [])
                    texts = []
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                t = item.get('text','')
                                if t:
                                    texts.append(t)
                    elif isinstance(content, str):
                        texts.append(content)
                    full_text = '\n'.join(texts)
                    if len(full_text) > 80 and KEYWORDS.search(full_text):
                        ts = rec.get('timestamp','')
                        snippet = full_text[:1200].replace('\n', ' ')
                        out_f.write(f'\n=== {os.path.basename(dirn)} [{role}] ts={ts} ===\n')
                        out_f.write(snippet + '\n')
                except Exception:
                    pass
        except Exception as e:
            out_f.write(f'ERROR reading {fpath}: {e}\n')

print(f'Extracted to {OUT}')
