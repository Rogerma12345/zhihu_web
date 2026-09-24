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

const ZHIHU_BASE_URL = 'https://www.zhihu.com/';
const ZHIHU_REDIRECT_HOST = 'link.zhihu.com';
const MAX_ZHIHU_REDIRECT_DEPTH = 4;

function isHttpUrl(url) {
  return url && ['http:', 'https:'].includes(url.protocol);
}

function unwrapZhihuRedirect(url) {
  let current = url;

  for (let depth = 0; depth < MAX_ZHIHU_REDIRECT_DEPTH; depth += 1) {
    if (current.hostname.toLowerCase() !== ZHIHU_REDIRECT_HOST) {
      return current.href;
    }

    // Zhihu's outbound redirect endpoint is HTTPS-only here. Reject unusual
    // variants rather than navigating through the intermediary.
    if (current.protocol !== 'https:' || current.port) return '';

    const target = current.searchParams.get('target');
    if (!target) return '';

    try {
      // Deliberately parse the target without a base URL. A redirect target
      // must be an absolute HTTP(S) URL and must never depend on deployment
      // origin or window.location. URLSearchParams already
      // performs the single percent-decoding required for the query value.
      current = new URL(target);
    } catch {
      return '';
    }

    if (!isHttpUrl(current)) return '';
  }

  // Do not fall back to visiting link.zhihu.com if an unexpectedly deep
  // redirect chain is supplied.
  return current.hostname.toLowerCase() === ZHIHU_REDIRECT_HOST ? '' : current.href;
}

export function safeHttpUrl(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';

  try {
    // Zhihu API content may contain relative href values. Resolve those
    // against a fixed Zhihu origin, never against the deployment origin.
    const url = new URL(raw, ZHIHU_BASE_URL);
    if (!isHttpUrl(url)) return '';
    return unwrapZhihuRedirect(url);
  } catch {
    return '';
  }
}

/**
 * Rewrite links inside Zhihu API HTML without executing link code.
 * - link.zhihu.com redirects become direct HTTP(S) targets.
 * - Framework7 is told not to treat absolute content links as app routes.
 * - Referrer/ping/attribution metadata is suppressed for outbound privacy.
 * - Existing target behavior is preserved unless forceNewTab is requested.
 */
export function normalizeZhihuHtmlLinks(value, { forceNewTab = false } = {}) {
  const html = String(value ?? '');
  if (!html || typeof DOMParser === 'undefined') return html;

  const doc = new DOMParser().parseFromString(html, 'text/html');

  doc.querySelectorAll('a[href]').forEach((anchor) => {
    // Never retain executable/event-based link behavior from API HTML.
    for (const attr of [...anchor.attributes]) {
      if (/^on/i.test(attr.name)) anchor.removeAttribute(attr.name);
    }
    anchor.removeAttribute('ping');
    anchor.removeAttribute('attributionsrc');

    const rawHref = anchor.getAttribute('href');
    if (!rawHref) return;

    const trimmedHref = rawHref.trim();
    // Hash links are document-local and are not outbound navigation.
    if (trimmedHref.startsWith('#')) return;

    // Preserve non-network handlers that are safe to hand to the browser,
    // while still keeping Framework7 away from them.
    if (/^(mailto|tel):/i.test(trimmedHref)) {
      anchor.classList.add('external', 'prevent-router');
      if (forceNewTab) anchor.setAttribute('target', '_blank');
      return;
    }

    const href = safeHttpUrl(trimmedHref);
    if (!href) {
      // Reject schemes/redirects that cannot be normalized to HTTP(S).
      anchor.removeAttribute('href');
      anchor.removeAttribute('target');
      return;
    }

    anchor.setAttribute('href', href);
    anchor.classList.add('external', 'prevent-router');
    anchor.setAttribute('referrerpolicy', 'no-referrer');

    const rel = new Set(
      (anchor.getAttribute('rel') || '').split(/\s+/).filter(Boolean),
    );
    rel.add('noopener');
    rel.add('noreferrer');
    anchor.setAttribute('rel', [...rel].join(' '));

    if (forceNewTab) anchor.setAttribute('target', '_blank');
  });

  return doc.body.innerHTML;
}
