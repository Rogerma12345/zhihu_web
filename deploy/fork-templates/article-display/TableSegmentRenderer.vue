<template>
  <figure class="table-segment">
    <div v-if="tableData.rows.length" class="table-scroll" role="region" aria-label="文章表格" tabindex="0">
      <table class="article-table">
        <tbody>
          <tr v-for="(row, rowIndex) in tableData.rows" :key="rowIndex">
            <component
              :is="cell.header ? 'th' : 'td'"
              v-for="(cell, cellIndex) in row"
              :key="cellIndex"
              :colspan="cell.colspan > 1 ? cell.colspan : undefined"
              :rowspan="cell.rowspan > 1 ? cell.rowspan : undefined"
              :scope="cell.header ? 'col' : undefined"
            >
              <RenderStyledText
                v-if="cell.text"
                :text="cell.text"
                :marks="cell.marks"
              />
            </component>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="table-empty">
      {{ tableData.fallback || '表格暂无可显示内容' }}
    </div>

    <figcaption v-if="tableData.caption" class="table-caption">
      {{ tableData.caption }}
    </figcaption>
  </figure>
</template>

<script setup>
import { computed } from 'vue';
import RenderStyledText from './RenderStyledText.vue';
import { htmlToPlainText } from '../utils/content-text.js';

const props = defineProps({
  segment: {
    type: Object,
    default: () => ({}),
  },
});

function positiveSpan(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 1;
  return Math.min(100, Math.max(1, Math.trunc(number)));
}

function plain(value) {
  if (value === null || value === undefined) return '';
  return htmlToPlainText(String(value));
}

function textFromValue(value, depth = 0) {
  if (value === null || value === undefined || depth > 5) return '';
  if (['string', 'number', 'boolean'].includes(typeof value)) return plain(value);
  if (Array.isArray(value)) {
    return value
      .map((item) => textFromValue(item, depth + 1))
      .filter(Boolean)
      .join('\n');
  }
  if (typeof value !== 'object') return '';

  const direct = [
    value.text,
    value.value,
    value.content,
    value.title,
    value.name,
    value.label,
    value.description,
  ];
  for (const candidate of direct) {
    if (candidate !== value) {
      const text = textFromValue(candidate, depth + 1);
      if (text) return text;
    }
  }

  for (const key of ['children', 'segments', 'items', 'spans', 'contents']) {
    const text = textFromValue(value[key], depth + 1);
    if (text) return text;
  }
  return '';
}

function normalizeCell(rawCell) {
  if (rawCell === null || rawCell === undefined || typeof rawCell !== 'object') {
    return {
      text: textFromValue(rawCell),
      marks: [],
      header: false,
      colspan: 1,
      rowspan: 1,
    };
  }

  const payload = rawCell.table_cell || rawCell.cell || rawCell;
  const nestedText = payload.text && typeof payload.text === 'object' ? payload.text : null;
  const type = String(payload.type || rawCell.type || '').toLowerCase();
  const tag = String(payload.tag || payload.tag_name || '').toLowerCase();
  const role = String(payload.role || '').toLowerCase();

  return {
    text: textFromValue(payload),
    marks: Array.isArray(payload.marks)
      ? payload.marks
      : (Array.isArray(nestedText?.marks) ? nestedText.marks : []),
    header: Boolean(
      payload.header ||
      payload.is_header ||
      payload.isHeader ||
      tag === 'th' ||
      role === 'columnheader' ||
      type === 'th' ||
      type.includes('header')
    ),
    colspan: positiveSpan(
      payload.colspan ?? payload.col_span ?? payload.column_span ?? payload.columnSpan,
    ),
    rowspan: positiveSpan(
      payload.rowspan ?? payload.row_span ?? payload.rowSpan,
    ),
  };
}

function rowCells(rawRow) {
  if (Array.isArray(rawRow)) return rawRow;
  if (!rawRow || typeof rawRow !== 'object') return [rawRow];
  const payload = rawRow.table_row || rawRow.row || rawRow;
  for (const key of ['cells', 'columns', 'items', 'children', 'values', 'data']) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  return [payload];
}

function normalizeRows(rawRows) {
  if (!Array.isArray(rawRows)) return [];
  return rawRows
    .map((row) => rowCells(row).map(normalizeCell))
    .filter((row) => row.length > 0);
}

function rowsFromFlatCells(cells) {
  if (!Array.isArray(cells) || cells.length === 0) return [];
  const positioned = cells.filter((cell) => {
    const payload = cell?.table_cell || cell?.cell || cell;
    return payload && typeof payload === 'object' && (
      payload.row !== undefined || payload.row_index !== undefined || payload.rowIndex !== undefined
    );
  });
  if (positioned.length !== cells.length) return [];

  const rows = new Map();
  positioned.forEach((cell, sourceIndex) => {
    const payload = cell.table_cell || cell.cell || cell;
    const rowIndex = Number(payload.row ?? payload.row_index ?? payload.rowIndex);
    const columnIndex = Number(
      payload.column ?? payload.col ?? payload.column_index ?? payload.columnIndex ?? sourceIndex,
    );
    if (!Number.isFinite(rowIndex)) return;
    if (!rows.has(rowIndex)) rows.set(rowIndex, []);
    rows.get(rowIndex).push({ cell, columnIndex: Number.isFinite(columnIndex) ? columnIndex : sourceIndex });
  });

  return [...rows.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, row]) => row
      .sort((a, b) => a.columnIndex - b.columnIndex)
      .map(({ cell }) => normalizeCell(cell)));
}

function rowsFromHtml(rawHtml) {
  const html = String(rawHtml || '').trim();
  if (!html || typeof DOMParser === 'undefined') return [];

  const parse = (source) => new DOMParser().parseFromString(source, 'text/html');
  let doc = parse(html);
  let table = doc.querySelector('table');

  // Some API responses escape the whole table as text once.
  if (!table && /&lt;\s*table/i.test(html)) {
    const decoded = doc.body.textContent || '';
    doc = parse(decoded);
    table = doc.querySelector('table');
  }
  if (!table) return [];

  return Array.from(table.rows || []).map((row) => (
    Array.from(row.cells || []).map((cell) => ({
      text: plain(cell.textContent || ''),
      marks: [],
      header: cell.tagName === 'TH',
      colspan: positiveSpan(cell.colSpan),
      rowspan: positiveSpan(cell.rowSpan),
    }))
  )).filter((row) => row.length > 0);
}

function tablePayload(segment) {
  if (!segment || typeof segment !== 'object') return {};
  const table = segment.table;
  if (Array.isArray(table)) return { rows: table };
  if (typeof table === 'string') return { content: table };
  if (table && typeof table === 'object') return table;
  return segment;
}

function findRows(payload) {
  const sources = [
    payload.rows,
    payload.data?.rows,
    payload.content?.rows,
    payload.body?.rows,
    payload.table_rows,
    payload.tableRows,
    Array.isArray(payload.data) ? payload.data : null,
    Array.isArray(payload.content) ? payload.content : null,
    payload.items,
    payload.children,
  ];
  for (const source of sources) {
    const rows = normalizeRows(source);
    if (rows.length) return rows;
  }

  for (const cells of [payload.cells, payload.data?.cells, payload.content?.cells]) {
    const rows = rowsFromFlatCells(cells);
    if (rows.length) return rows;
  }

  const htmlCandidates = [
    payload.html,
    payload.table_html,
    payload.tableHtml,
    payload.html_content,
    payload.content?.html,
    typeof payload.content === 'string' ? payload.content : '',
  ];
  for (const html of htmlCandidates) {
    const rows = rowsFromHtml(html);
    if (rows.length) return rows;
  }
  return [];
}

const tableData = computed(() => {
  const payload = tablePayload(props.segment);
  const rows = findRows(payload);
  const caption = [payload.caption, payload.title, payload.description]
    .map((value) => textFromValue(value))
    .find(Boolean) || '';

  const fallback = rows.length ? '' : textFromValue(
    payload.text ?? payload.value ?? (typeof payload.content === 'string' ? payload.content : ''),
  );

  return { rows, caption, fallback };
});
</script>

<style scoped>
.table-segment {
  margin: 24px 0;
  min-width: 0;
}

.table-scroll {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid color-mix(in srgb, var(--f7-text-color, CanvasText) 16%, transparent);
  border-radius: 10px;
  -webkit-overflow-scrolling: touch;
}

.article-table {
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
  background: var(--app-surface-bg, Canvas);
  color: var(--f7-text-color, CanvasText);
  font-size: 15px;
  line-height: 1.55;
}

.article-table th,
.article-table td {
  min-width: 7em;
  max-width: 30em;
  padding: 10px 12px;
  border-right: 1px solid color-mix(in srgb, currentColor 12%, transparent);
  border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent);
  text-align: left;
  vertical-align: top;
  white-space: normal;
  overflow-wrap: anywhere;
}

.article-table th {
  font-weight: 700;
  background: color-mix(in srgb, currentColor 6%, transparent);
}

.article-table tr:last-child > * {
  border-bottom: 0;
}

.article-table tr > *:last-child {
  border-right: 0;
}

.table-caption {
  margin-top: 8px;
  color: color-mix(in srgb, var(--f7-text-color, CanvasText) 65%, transparent);
  font-size: 0.875rem;
  line-height: 1.5;
  text-align: center;
}

.table-empty {
  padding: 12px 14px;
  border: 1px dashed color-mix(in srgb, var(--f7-text-color, CanvasText) 24%, transparent);
  border-radius: 8px;
  color: color-mix(in srgb, var(--f7-text-color, CanvasText) 65%, transparent);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
