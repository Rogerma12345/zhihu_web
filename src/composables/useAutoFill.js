import { getCurrentInstance, onUnmounted } from 'vue';

const CHECK_DELAY = 50;
const SCROLL_EDGE = 80;
const DEFAULT_CONTEXT = Symbol('default');

export function useAutoFill({ getEl, onLoad }) {
    const instance = getCurrentInstance();
    const timers = new Map();
    const bindings = new Map();

    const defaultEl = () => {
        const root = instance?.proxy?.$el;
        const nodes = root?.querySelectorAll ? [...root.querySelectorAll('.page-content')] : [];
        return nodes.find((el) => el.clientHeight > 0) || null;
    };

    const nearEnd = (el) => el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_EDGE;

    const bind = (el, context) => {
        const current = bindings.get(el);
        if (current) {
            current.context = context;
            for (const child of el.children) current.resizeObserver?.observe(child);
            return;
        }

        const binding = {
            context,
            resizeObserver: null,
            onScroll: null,
        };

        binding.onScroll = () => {
            if (nearEnd(el)) onLoad(binding.context);
        };
        el.addEventListener('scroll', binding.onScroll, { passive: true });

        if (typeof ResizeObserver === 'function') {
            binding.resizeObserver = new ResizeObserver(() => schedule(binding.context));
            for (const child of el.children) binding.resizeObserver.observe(child);
        }

        bindings.set(el, binding);
    };

    const schedule = (context = null) => {
        const key = context ?? DEFAULT_CONTEXT;
        if (timers.has(key)) return;

        const timer = setTimeout(() => {
            timers.delete(key);
            const el = getEl ? getEl(context) : defaultEl();
            if (!el || !el.clientHeight) return;
            bind(el, context);
            if (nearEnd(el)) onLoad(context);
        }, CHECK_DELAY);

        timers.set(key, timer);
    };

    onUnmounted(() => {
        for (const timer of timers.values()) clearTimeout(timer);
        timers.clear();

        for (const [el, binding] of bindings) {
            el.removeEventListener('scroll', binding.onScroll);
            binding.resizeObserver?.disconnect();
        }
        bindings.clear();
    });

    return { schedule };
}
