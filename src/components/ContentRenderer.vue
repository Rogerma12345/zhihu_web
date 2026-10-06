<script setup>
// src/components/ContentRenderer.vue
// 正文分段渲染：类型 → 组件注册表，段内标记、样式与交互归各段组件自己持有。
import { computed } from 'vue';
import SegmentParagraph from '@/components/segments/SegmentParagraph.vue';
import SegmentHeading from '@/components/segments/SegmentHeading.vue';
import SegmentBlockquote from '@/components/segments/SegmentBlockquote.vue';
import SegmentCodeBlock from '@/components/segments/SegmentCodeBlock.vue';
import SegmentList from '@/components/segments/SegmentList.vue';
import SegmentImage from '@/components/segments/SegmentImage.vue';
import SegmentCard from '@/components/segments/SegmentCard.vue';
import SegmentVideo from '@/components/segments/SegmentVideo.vue';
import SegmentTip from '@/components/segments/SegmentTip.vue';
import SegmentHr from '@/components/segments/SegmentHr.vue';
import SegmentReference from '@/components/segments/SegmentReference.vue';
import SegmentTable from '@/components/segments/SegmentTable.vue';
import SegmentUnknown from '@/components/segments/SegmentUnknown.vue';

const SEGMENTS = {
    paragraph: SegmentParagraph,
    heading: SegmentHeading,
    blockquote: SegmentBlockquote,
    code_block: SegmentCodeBlock,
    list_node: SegmentList,
    image: SegmentImage,
    card: SegmentCard,
    video: SegmentVideo,
    myapptip: SegmentTip,
    hr: SegmentHr,
    reference_block: SegmentReference,
    table: SegmentTable,
};

const props = defineProps({
    segments: {
        type: Array,
        default: () => []
    },
    sourceHtml: {
        type: String,
        default: ''
    }
});

const emit = defineEmits(['imageClick']);

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

    return props.segments.map((segment) => {
        if (segment?.type !== 'table') return '';
        const html = tables[tableIndex] || '';
        tableIndex += 1;
        return html;
    });
});

// 保留原数组下标，目录锚点依赖它，不能在渲染前重排。
const rendered = computed(() => props.segments.map((segment, index) => {
    const comp = SEGMENTS[segment?.type] || SegmentUnknown;
    let extraProps = {};
    if (comp === SegmentHeading) extraProps = { index };
    if (comp === SegmentTable) extraProps = { fallbackHtml: tableHtmlBySegmentIndex.value[index] || '' };

    return {
        comp,
        segment,
        index,
        extraProps,
    };
}));

const allImageUrls = computed(() => {
    return props.segments
        .filter(seg => seg?.type === 'image')
        .map(seg => seg.image.urls?.[0])
        .filter(url => !!url);
});

const handleImageClick = (url) => {
    const index = allImageUrls.value.indexOf(url);
    emit('imageClick', { url, index, allUrls: allImageUrls.value });
};
</script>

<template>
    <div class="content-renderer">
        <component v-for="entry in rendered" :is="entry.comp" :key="entry.index" :segment="entry.segment"
            v-bind="entry.extraProps" @image-click="handleImageClick" />
    </div>
</template>

<style scoped>
.content-renderer {
    line-height: 1.8;
}
</style>
