<template>
  <span class="styled-text-container">
    <template v-for="(part, index) in parts" :key="`${index}-${part.start}-${part.end}`">
      <span
        v-if="part.kind === 'formula'"
        class="styled-formula-wrap"
        :class="{ 'styled-formula-block': part.block }"
        :title="part.tex || '公式'"
      >
        <span
          v-if="part.html"
          class="styled-formula-katex"
          :class="{ 'styled-formula-katex-block': part.block }"
          v-html="part.html"
        ></span>
        <span v-else class="styled-formula-fallback">{{ part.tex || part.sourceText || '[公式]' }}</span>
      </span>

      <a
        v-else-if="part.href"
        class="styled-link"
        :class="part.classes"
        :href="part.href"
        target="_blank"
        rel="noopener noreferrer"
      >{{ part.text }}</a>

      <code v-else-if="part.classes.code" class="styled-code">{{ part.text }}</code>

      <span v-else :class="part.classes">{{ part.text }}</span>
    </template>
  </span>
</template>

<script setup>
import { computed } from 'vue';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { safeHttpUrl } from '../utils/content-text.js';

const props = defineProps({
  text: {
    type: String,
    default: '',
  },
  marks: {
    type: Array,
    default: () => [],
  },
});

function asIndex(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : fallback;
}

function getMarkUrl(mark) {
  const raw = (
    mark?.link?.href ||
    mark?.link?.url ||
    mark?.entity_word?.url ||
    mark?.url ||
    mark?.href ||
    mark?.link_url ||
    ''
  );
  return safeHttpUrl(raw);
}

function normalizeMarks(text, marks) {
  const length = text.length;
  return (Array.isArray(marks) ? marks : [])
    .map((mark) => {
      const start = Math.min(length, asIndex(mark?.start_index));
      const end = Math.min(length, asIndex(mark?.end_index, start));
      return { ...mark, start_index: start, end_index: Math.max(start, end) };
    })
    // Zero-width marks have no visible text range. reference_block links are
    // handled by ReferenceBlockRenderer instead of forcing them into text.
    .filter((mark) => mark.end_index > mark.start_index)
    .sort((a, b) => a.start_index - b.start_index || b.end_index - a.end_index);
}

function textClasses(activeMarks) {
  const types = new Set(activeMarks.map((mark) => mark?.type));
  return {
    bold: types.has('bold'),
    italic: types.has('italic'),
    underline: types.has('underline'),
    strikethrough: types.has('strikethrough') || types.has('strike'),
    code: types.has('code'),
    'styled-highlight': activeMarks.some((mark) =>
      ![
        'bold', 'italic', 'underline', 'strikethrough', 'strike',
        'code', 'link', 'entity_word', 'formula'
      ].includes(mark?.type)
    ),
  };
}

function normalizeFormulaTex(value) {
  let tex = String(value || '').trim();
  if (!tex) return '';

  const wrappers = [
    ['$$', '$$'],
    ['\\[', '\\]'],
    ['\\(', '\\)'],
  ];
  for (const [start, end] of wrappers) {
    if (tex.startsWith(start) && tex.endsWith(end) && tex.length >= start.length + end.length) {
      tex = tex.slice(start.length, tex.length - end.length).trim();
      break;
    }
  }

  if (tex.startsWith('$') && tex.endsWith('$') && !tex.startsWith('$$') && tex.length >= 2) {
    tex = tex.slice(1, -1).trim();
  }

  return tex;
}

function renderFormulaHtml(tex, displayMode) {
  if (!tex) return '';
  try {
    return katex.renderToString(tex, {
      displayMode,
      output: 'html',
      throwOnError: true,
      trust: false,
      strict: 'ignore',
      maxSize: 20,
      maxExpand: 1000,
    });
  } catch (error) {
    console.warn('KaTeX formula rendering failed:', { tex, error });
    return '';
  }
}

const parts = computed(() => {
  const text = props.text || '';
  const marks = normalizeMarks(text, props.marks);
  if (!text && marks.length === 0) return [];

  const formulaMarks = marks.filter((mark) => mark?.type === 'formula' && mark?.formula);
  const boundaries = new Set([0, text.length]);
  for (const mark of marks) {
    boundaries.add(mark.start_index);
    boundaries.add(mark.end_index);
  }
  const sortedBoundaries = [...boundaries].sort((a, b) => a - b);
  const result = [];
  const emittedFormula = new Set();

  for (let i = 0; i < sortedBoundaries.length - 1; i += 1) {
    const start = sortedBoundaries[i];
    const end = sortedBoundaries[i + 1];
    if (end <= start) continue;

    const formulaMark = formulaMarks.find(
      (mark) => mark.start_index <= start && mark.end_index >= end,
    );

    if (formulaMark) {
      const key = `${formulaMark.start_index}:${formulaMark.end_index}`;
      if (!emittedFormula.has(key)) {
        emittedFormula.add(key);
        const formula = formulaMark.formula || {};
        const formulaText = text.slice(formulaMark.start_index, formulaMark.end_index);
        const tex = normalizeFormulaTex(formula.content || formulaText);
        const block = text.trim() === formulaText.trim();
        result.push({
          kind: 'formula',
          start: formulaMark.start_index,
          end: formulaMark.end_index,
          tex,
          sourceText: formulaText,
          block,
          html: renderFormulaHtml(tex, block),
        });
      }
      continue;
    }

    const segmentText = text.slice(start, end);
    if (!segmentText) continue;
    const activeMarks = marks.filter(
      (mark) => mark.type !== 'formula' && mark.start_index <= start && mark.end_index >= end,
    );
    const linkMark = activeMarks.find((mark) => ['link', 'entity_word'].includes(mark?.type));

    result.push({
      kind: 'text',
      start,
      end,
      text: segmentText,
      classes: textClasses(activeMarks),
      href: linkMark ? getMarkUrl(linkMark) : '',
    });
  }

  return result;
});
</script>

<style scoped>
.styled-text-container {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bold {
  font-weight: 700;
}

.italic {
  font-style: italic;
}

.underline {
  text-decoration: underline;
}

.strikethrough {
  text-decoration: line-through;
}

.styled-highlight {
  background: color-mix(in srgb, currentColor 10%, transparent);
  border-radius: 3px;
}

.styled-code {
  padding: 0.12em 0.35em;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
  background: color-mix(in srgb, currentColor 9%, transparent);
}

.styled-link {
  color: var(--f7-theme-color, #0c7ff2);
  text-decoration: none;
}

.styled-link:hover {
  text-decoration: underline;
}

.styled-formula-wrap {
  display: inline-block;
  max-width: 100%;
  margin: 0 0.04em;
  color: inherit;
  vertical-align: baseline;
  white-space: nowrap;
}

.styled-formula-katex {
  display: inline;
  color: inherit;
}

.styled-formula-katex :deep(.katex) {
  color: inherit;
  font-size: 1em;
  line-height: 1.2;
  text-rendering: geometricPrecision;
}

.styled-formula-block {
  display: block;
  width: 100%;
  margin: 0.85em auto;
  overflow-x: auto;
  overflow-y: hidden;
  text-align: center;
  white-space: normal;
  -webkit-overflow-scrolling: touch;
}

.styled-formula-katex-block {
  display: block;
  width: max-content;
  min-width: 100%;
}

.styled-formula-block :deep(.katex-display) {
  margin: 0;
  overflow: visible;
}

.styled-formula-block :deep(.katex) {
  font-size: 1em;
}

.styled-formula-fallback {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  padding: 0.06em 0.2em;
  border-radius: 4px;
  font-family: "Times New Roman", "STIX Two Math", serif;
  font-size: 1em;
  line-height: 1.2;
  background: color-mix(in srgb, currentColor 7%, transparent);
}
</style>
