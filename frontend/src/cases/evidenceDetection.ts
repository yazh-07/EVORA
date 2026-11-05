import type { Evidence } from './evidenceStore';

/** Inspect only the header; cancellation keeps a late read from overriding the investigator. */
export function detectEvidenceKind(file: File, detected: (kind: Evidence['kind']) => void, settled: () => void) {
  const extension = file.name.split('.').at(-1)?.toLowerCase() ?? '';
  const media = file.type.toLowerCase().split(';')[0] ?? '';
  const groups = {
    video: ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'm4v'],
    image: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'svg', 'gif', 'ico'],
    audio: ['wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac', 'wma', 'opus'],
    document: ['pdf', 'txt', 'docx', 'doc', 'json', 'jsonl', 'log', 'xml', 'md', 'yaml', 'yml', 'sql', 'ini', 'conf', 'html', 'csv', 'pcap', 'pcapng', 'bin', 'hex', 'raw', 'dump'],
  } as const;
  const kind = (Object.keys(groups) as (keyof typeof groups)[]).find(key =>
    (groups[key] as readonly string[]).includes(extension));
  const family = media.split('/')[0];
  detected(kind ?? (family === 'video' || family === 'image' || family === 'audio' ? family : 'document'));
  if (!(extension === 'csv' || extension === 'txt' || media.startsWith('text/') || media === 'application/csv')) {
    settled();
    return () => {};
  }
  const reader = new FileReader();
  let active = true;
  reader.onload = () => {
    if (!active || typeof reader.result !== 'string') return;
    const header = reader.result.split(/\r?\n|\r/, 1)[0]?.toLowerCase() ?? '';
    // Short keys must be column words: "recipient" contains "ip", and "plate" contains "lat".
    if (/(?:^|[^a-z0-9])lat(?:$|[^a-z0-9])/.test(header) || ['latitude', 'longitude'].some(key => header.includes(key))) detected('gps');
    else if (/(?:^|[^a-z0-9])ip(?:$|[^a-z0-9])/.test(header) || ['ip_address', 'packet', 'firewall'].some(key => header.includes(key))) detected('network_log');
    else if (['amount', 'currency', 'account_id'].some(key => header.includes(key))) detected('transaction');
    else if (['sender', 'recipient', 'message_id', 'body'].some(key => header.includes(key))) detected('message');
  };
  reader.onloadend = () => { if (active) settled(); };
  try { reader.readAsText(file.slice(0, 1024)); }
  catch { settled(); }
  return () => { active = false; if (reader.readyState === 1) reader.abort(); };
}
