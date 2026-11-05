import { Fragment, type ReactNode } from 'react';

/** Render a deliberately small markdown vocabulary as React text; raw HTML/URLs are never executed. */
function inline(text: string, citationIds: string[]): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|\[\d+\])/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('*') && part.endsWith('*')) return <em key={i}>{part.slice(1, -1)}</em>;
    const citation = part.match(/^\[(\d+)\]$/);
    const target = citation && citationIds[Number(citation[1]) - 1];
    return target ? <a key={i} className="claim-reference" href={`#${target}`} aria-label={`Read citation ${citation![1]}`}>{part}</a> : <Fragment key={i}>{part}</Fragment>;
  });
}
export function AnswerMarkdown({ text, citationIds = [] }: { text: string; citationIds?: string[] }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i]!;
    if (!line.trim()) { i++; continue; }
    if (line.startsWith('```')) {
      const code: string[] = []; i++;
      while (i < lines.length && !lines[i]!.startsWith('```')) code.push(lines[i++]!);
      i++; blocks.push(<pre key={blocks.length}><code>{code.join('\n')}</code></pre>); continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+)/);
    if (heading) { blocks.push(<h4 key={blocks.length}>{inline(heading[1]!, citationIds)}</h4>); i++; continue; }
    if (/^\s*(?:[-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line), items: ReactNode[] = [];
      const pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/;
      while (i < lines.length && pattern.test(lines[i]!)) { items.push(<li key={i}>{inline(lines[i]!.replace(pattern, ''), citationIds)}</li>); i++; }
      blocks.push(ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>); continue;
    }
    if (line.startsWith('> ')) { blocks.push(<blockquote key={blocks.length}>{inline(line.slice(2), citationIds)}</blockquote>); i++; continue; }
    blocks.push(<p key={blocks.length}>{inline(line, citationIds)}</p>); i++;
  }
  return <div className="answer-markdown">{blocks}</div>;
}
