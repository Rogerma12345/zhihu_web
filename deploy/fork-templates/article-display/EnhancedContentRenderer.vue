<template>
  <div class="enhanced-content-renderer">
    <template v-for="(segment, index) in normalizedSegments" :key="segment?.id || `${segment?.type || 'unknown'}-${index}`">
      <component
        :is="headingTag(segment)"
        v-if="segment?.type === 'heading'"
        class="enhanced-heading"
      >
        <RenderStyledText
          :text="segment?.heading?.text || ''"
          :marks="segment?.heading?.marks || []"
        />
      </component>

      <CodeBlockRenderer
        v-else-if="segment?.type === 'code_block'"
        :code="segment?.code_block?.content || ''"
        :language="segment?.code_block?.language || segment?.code_block?.lang || ''"
      />

      <ReferenceBlockRenderer
        v-else-if="segment?.type === 'reference_block'"
        :block="segment?.reference_block || {}"
      />

      <TableSegmentRenderer
        v-else-if="segment?.type === 'table'"
        :segment="segment"
        :fallback-html="tableHtmlBySegmentIndex[index] || ''"
      />

      <ContentRenderer
        v-else-if="isLegacySupported(segment?.type)"
        :segments="[segment]"
        @imageClick="emit('imageClick', $event)"
      />

      <UnknownSegmentRenderer
        v-else
        :segment="segment"
      />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import ContentRenderer from './ContentRenderer.vue';
import RenderStyledText from './RenderStyledText.vue';
import CodeBlockRenderer from './CodeBlockRenderer.vue';
import ReferenceBlockRenderer from './ReferenceBlockRenderer.vue';
import TableSegmentRenderer from './TableSegmentRenderer.vue';
import UnknownSegmentRenderer from './UnknownSegmentRenderer.vue';

const emit = defineEmits(['imageClick']);

const props = defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
  sourceHtml: {
    type: String,
    default: '',
  },
});

const normalizedSegments = computed(() => (
  Array.isArray(props.segments) ? props.segments.filter(Boolean) : []
));

function sourceTableHtml(rawHtml) {
  let html = String(rawHtml || '').trim();
  if (!html || typeof DOMParser === 'undefined') return [];

  for (let pass = 0; pass < 2; pass += 1) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const tables = Array.from(doc.querySelectorAll('table[data-draft-type="table"], table'))
      .filter((table) => !table.parentElement?.closest('table'));
    if (tables.length) return tables.map((table) => table.outerHTML);

    const decoded = (doc.body.textContent || '').trim();
    if (!decoded || decoded === html) break;
    html = decoded;
  }

  return [];
}

const tableHtmlBySegmentIndex = computed(() => {
  const tables = sourceTableHtml(props.sourceHtml);
  let tableIndex = 0;

  return normalizedSegments.value.map((segment) => {
    if (segment?.type !== 'table') return '';
    const html = tables[tableIndex] || '';
    tableIndex += 1;
    return html;
  });
});

const LEGACY_SUPPORTED = new Set([
  'paragraph',
  'blockquote',
  'list_node',
  'image',
  'card',
  'video',
  'myapptip',
  'hr',
]);

function isLegacySupported(type) {
  return LEGACY_SUPPORTED.has(type);
}

function headingTag(segment) {
  const raw = Number(
    segment?.heading?.level ??
    segment?.heading?.depth ??
    segment?.heading?.heading_level ??
    2,
  );
  const level = Math.min(6, Math.max(2, Number.isFinite(raw) ? raw : 2));
  return `h${level}`;
}
</script>

<style scoped>
.enhanced-content-renderer {
  min-width: 0;
}

.enhanced-heading {
  margin: 1.35em 0 0.65em;
  color: var(--f7-text-color, inherit);
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

h2.enhanced-heading { font-size: 1.42em; }
h3.enhanced-heading { font-size: 1.28em; }
h4.enhanced-heading { font-size: 1.16em; }
h5.enhanced-heading,
h6.enhanced-heading { font-size: 1.05em; }
</style>
