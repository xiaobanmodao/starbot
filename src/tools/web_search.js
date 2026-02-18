import { tool } from './registry.js';

tool('web_search', 'Search the web via DuckDuckGo. Returns titles, URLs and snippets.', {
  properties: {
    query: { type: 'string', description: 'Search query' },
    max_results: { type: 'number', description: 'Max results (default 8)' },
  },
  required: ['query'],
}, false, async ({ query, max_results = 8 }) => {
  try {
    const r = await fetch(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
      redirect: 'follow',
    });
    const html = await r.text();
    const results = [];
    // Extract result blocks
    const blocks = html.split('class="result__body"').slice(1, max_results + 1);
    for (const block of blocks) {
      const titleM = block.match(/class="result__a"[^>]*>([^<]+)</);
      const urlM = block.match(/class="result__url"[^>]*>\s*([^<]+)/);
      const snippetM = block.match(/class="result__snippet"[^>]*>([^<]+)/);
      if (titleM) {
        let entry = titleM[1].trim();
        if (urlM) entry += `\n  ${urlM[1].trim()}`;
        if (snippetM) entry += `\n  ${snippetM[1].trim()}`;
        results.push(entry);
      }
    }
    return results.join('\n\n') || 'No results found';
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
