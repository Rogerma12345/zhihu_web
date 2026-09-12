const BLOCK_TAGS = new Set([
  'ADDRESS', 'ARTICLE', 'ASIDE', 'BLOCKQUOTE', 'DIV', 'DL', 'DT', 'DD',
  'FIGCAPTION', 'FIGURE', 'FOOTER', 'HEADER', 'H1', 'H2', 'H3', 'H4',
  'H5', 'H6', 'LI', 'MAIN', 'NAV', 'OL', 'P', 'PRE', 'SECTION', 'TABLE',
  'TBODY', 'TD', 'TFOOT', 'TH', 'THEAD', 'TR', 'UL'
]);

const DANGEROUS_SELECTOR = [
  'script', 'style', 'noscript', 'template', 'iframe', 'object', 'embed',
  'svg', 'canvas', 'audio', 'video', 'source'
].join(',');

function normalizeWhitespace(value) {
  return String(value ?? '')
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[\t\f\v ]+\n/g, '\n')
    .replace(/\n[\t\f\v ]+/g, '\n')
    .replace(/[\t\f\v ]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function looksLikeMarkup(value) {
  const text = String(value ?? '');
  return /<\/?[a-z][^>]*>/i.test(text) || /&(lt|gt|amp|quot|#\d+|#x[0-9a-f]+);/i.test(text);
}

function parseHtmlOnce(value) {
  const input = String(value ?? '');
  if (!input) return '';

  if (typeof DOMParser === 'undefined') {
    return input
      .replace(/<\s*br\s*\/?>/gi, '\n')
      .replace(/<\/(p|div|li|blockquote|h[1-6]|tr|section|article)>/gi, '\n')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'")
      .replace(/&amp;/gi, '&');
  }

  const doc = new DOMParser().parseFromString(input, 'text/html');
  doc.querySelectorAll(DANGEROUS_SELECTOR).forEach((node) => node.remove());

  doc.querySelectorAll('br').forEach((node) => {
    node.replaceWith(doc.createTextNode('\n'));
  });

  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT);
  const blocks = [];
  while (walker.nextNode()) {
    if (BLOCK_TAGS.has(walker.currentNode.tagName)) {
      blocks.push(walker.currentNode);
    }
  }
  blocks.forEach((node) => {
    node.appendChild(doc.createTextNode('\n'));
  });

  return doc.body.textContent || '';
}

/**
 * Convert user-generated Zhihu HTML / escaped HTML into display-safe plain text.
 * It intentionally returns text only and never returns executable markup.
 */
export function htmlToPlainText(value) {
  if (value === null || value === undefined) return '';

  let text = String(value);
  // Some endpoints return already-escaped HTML. Two passes handle both
  // "<p>text</p>" and "&lt;p&gt;text&lt;/p&gt;" without looping forever.
  for (let pass = 0; pass < 2 && looksLikeMarkup(text); pass += 1) {
    const parsed = parseHtmlOnce(text);
    if (parsed === text) break;
    text = parsed;
  }

  return normalizeWhitespace(text);
}

export function safeHttpUrl(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, 'https://www.zhihu.com/');
    if (!['http:', 'https:'].includes(url.protocol)) return '';
    return url.href;
  } catch {
    return '';
  }
}
