<template>
  <span class="styled-text-container">
    <template v-for="(part, index) in parts" :key="`${index}-${part.start}-${part.end}`">
      <span
        v-if="part.kind === 'formula'"
        class="styled-formula-wrap"
        :class="{ 'styled-formula-block': part.block }"
        :title="part.tex || '公式'"
      >
        <img
          v-if="part.imgUrl && !failedFormulaUrls.has(part.imgUrl)"
          class="styled-formula-image"
          :class="{ 'styled-formula-image-block': part.block }"
          :src="part.imgUrl"
          :alt="part.tex || '公式'"
          :width="part.width || undefined"
          :height="part.height || undefined"
          loading="lazy"
          decoding="async"
          @error="markFormulaImageFailed(part.imgUrl)"
        />
        <span v-else class="styled-formula-fallback">{{ part.tex || '[公式]' }}</span>
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
import { computed, ref } from 'vue';
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

const failedFormulaUrls = ref(new Set());

function markFormulaImageFailed(url) {
  if (!url) return;
  const next = new Set(failedFormulaUrls.value);
  next.add(url);
  failedFormulaUrls.value = next;
}

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
        result.push({
          kind: 'formula',
          start: formulaMark.start_index,
          end: formulaMark.end_index,
          tex: formula.content || '',
          imgUrl: safeHttpUrl(formula.img_url || formula.image_url || ''),
          width: Number(formula.width) || null,
          height: Number(formula.height) || null,
          block: text.trim() === formulaText.trim(),
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
  display: inline-flex;
  max-width: 100%;
  vertical-align: -0.22em;
  align-items: center;
  justify-content: center;
  margin: 0 0.08em;
}

.styled-formula-image {
  display: inline-block;
  width: auto;
  max-width: min(100%, 56rem);
  height: auto;
  max-height: 1.75em;
  object-fit: contain;
  vertical-align: middle;
  border-radius: 2px;
}

:global(.dark) .styled-formula-image,
:global(html.dark) .styled-formula-image {
  filter: invert(1) hue-rotate(180deg);
  mix-blend-mode: screen;
}

.styled-formula-block {
  display: flex;
  width: 100%;
  margin: 0.8em auto;
  overflow-x: auto;
}

.styled-formula-image-block {
  max-height: none;
  max-width: 100%;
}

.styled-formula-fallback {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  padding: 0.08em 0.28em;
  border-radius: 4px;
  font-family: "Times New Roman", "STIX Two Math", serif;
  background: color-mix(in srgb, currentColor 7%, transparent);
}
</style>
