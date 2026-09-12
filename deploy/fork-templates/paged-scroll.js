const managed = new WeakSet();
const pending = new WeakSet();
const fillState = new WeakMap();

const elementsFrom = (value) => {
  if (!value) return [];
  if (typeof value === 'string') return Array.from(document.querySelectorAll(value));
  const raw = value.$el || value;
  if (raw instanceof Element) return [raw];
  if (typeof raw.length === 'number') return Array.from(raw).filter((item) => item instanceof Element);
  return [];
};

const descendants = (root, selector) => {
  if (!(root instanceof Element)) return [];
  const result = [];
  if (root.matches(selector)) result.push(root);
  result.push(...root.querySelectorAll(selector));
  return result;
};

const scheduleFill = (element) => {
  if (!(element instanceof Element) || pending.has(element)) return;
  pending.add(element);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      pending.delete(element);
      if (!element.isConnected) return;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      if (element.scrollHeight > element.clientHeight + 1) {
        fillState.delete(element);
        return;
      }
      const previous = fillState.get(element) || { height: -1, count: 0 };
      const count = previous.height === element.scrollHeight ? previous.count + 1 : 1;
      fillState.set(element, { height: element.scrollHeight, count });
      if (count > 8) return;
      element.dispatchEvent(new Event('scroll'));
    });
  });
};

export const installPagedScroll = (app) => {
  if (!app || app.__pagedScrollInstalled) return;
  app.__pagedScrollInstalled = true;

  const infiniteCreate = app.infiniteScroll.create.bind(app.infiniteScroll);
  app.infiniteScroll.create = (value) => {
    let result;
    elementsFrom(value).forEach((element) => {
      if (!element.f7InfiniteScrollHandler) result = infiniteCreate(element);
    });
    return result;
  };

  const ptrCreate = app.ptr.create.bind(app.ptr);
  app.ptr.create = (value) => {
    let result;
    elementsFrom(value).forEach((element) => {
      if (!element.f7PullToRefresh) result = ptrCreate(element);
    });
    return result;
  };

  const initElement = (element) => {
    if (!(element instanceof Element)) return;
    if (element.classList.contains('infinite-scroll-content')) {
      app.infiniteScroll.create(element);
      if (!managed.has(element)) {
        managed.add(element);
        if (typeof ResizeObserver === 'function') {
          const observer = new ResizeObserver(() => scheduleFill(element));
          observer.observe(element);
        }
      }
      scheduleFill(element);
    }
    if (element.classList.contains('ptr-content')) app.ptr.create(element);
  };

  const initTree = (root) => {
    descendants(root, '.infinite-scroll-content, .ptr-content').forEach(initElement);
  };

  const observer = new MutationObserver((records) => {
    records.forEach((record) => {
      if (record.target instanceof Element) {
        const container = record.target.closest('.infinite-scroll-content');
        if (container) scheduleFill(container);
      }
      record.addedNodes.forEach((node) => {
        if (node instanceof Element) initTree(node);
      });
    });
  });

  document.querySelectorAll('.infinite-scroll-content, .ptr-content').forEach(initElement);
  observer.observe(document.body, { childList: true, subtree: true });
};
