<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { f7 } from 'framework7-vue';
import { tokenManager } from '@/services/auth.js';
import { useUser } from '@/composables/userManager.js';
import { updateZhihuLoginData } from '@/services/zhihu/module.js';
import { extractWebCookies, normalizeWebCookies } from '@/services/web-cookie.js';

const dC0 = ref('');
const zC0 = ref('');
const cookieHeader = ref('');
const isVisible = ref(false);
const configured = ref({ ...tokenManager.getLoginData()?.manualWebCookies });
const { isLoggedIn, onUserUpdate } = useUser();
let stopUserUpdate;

onMounted(() => {
    stopUserUpdate = onUserUpdate(() => {
        configured.value = { ...tokenManager.getLoginData()?.manualWebCookies };
        clearInputs();
    });
});
onUnmounted(() => stopUserUpdate?.());

const clearInputs = () => {
    dC0.value = '';
    zC0.value = '';
    cookieHeader.value = '';
};

const save = () => {
    if (!isLoggedIn.value) return;
    try {
        const pasted = extractWebCookies(cookieHeader.value);
        if (cookieHeader.value.trim() && !Object.keys(pasted).length) {
            throw new Error('未找到 d_c0 或 z_c0');
        }
        const input = normalizeWebCookies({ d_c0: dC0.value, z_c0: zC0.value });
        const saved = tokenManager.getLoginData()?.manualWebCookies || {};
        const next = { ...saved, ...pasted, ...input };
        if (!tokenManager.saveWebCookies(next)) throw new Error('保存失败，请检查本地存储');
        updateZhihuLoginData(tokenManager.getLoginData());
        configured.value = next;
        clearInputs();
        f7.toast.show({ text: '网页 Cookie 已保存' });
    } catch (error) {
        f7.toast.show({ text: error.message || '保存失败' });
    }
};

const clear = () => {
    if (!isLoggedIn.value || !tokenManager.saveWebCookies({})) return;
    updateZhihuLoginData(tokenManager.getLoginData());
    configured.value = {};
    clearInputs();
    f7.toast.show({ text: '手动 Cookie 已清除' });
};
</script>

<template>
    <f7-page name="settings-web-cookie">
        <f7-navbar title="网页 Cookie" back-link="返回" />

        <f7-block strong inset>
            仅为需要网页签名的知乎接口补充凭证。手动值优先于登录响应中的 Cookie，普通 Android 请求不受影响。
        </f7-block>

        <f7-block-title>手动凭证</f7-block-title>
        <f7-list strong inset>
            <f7-list-input label="d_c0" :type="isVisible ? 'text' : 'password'" :disabled="!isLoggedIn"
                :placeholder="configured.d_c0 ? '已配置，留空不修改' : '输入 d_c0'" v-model:value="dC0" />
            <f7-list-input label="z_c0（可选）" :type="isVisible ? 'text' : 'password'" :disabled="!isLoggedIn"
                :placeholder="configured.z_c0 ? '已配置，留空不修改' : '输入 z_c0'" v-model:value="zC0" />
            <f7-list-input label="或粘贴完整 Cookie" :type="isVisible ? 'text' : 'password'" :disabled="!isLoggedIn"
                placeholder="只提取 d_c0、z_c0" v-model:value="cookieHeader" />
            <f7-list-item title="显示当前输入">
                <template #after>
                    <f7-toggle :checked="isVisible" @change="isVisible = $event.target.checked" />
                </template>
            </f7-list-item>
        </f7-list>

        <f7-block strong inset>
            <p>签名凭证：{{ configured.d_c0 ? '已配置' : '未配置' }} · 登录凭证：{{ configured.z_c0 ? '已配置' : '未配置' }}</p>
            <p v-if="!isLoggedIn">请先登录再设置网页 Cookie。</p>
            <p>凭证保存在本机登录数据中，退出登录或切换账号后不再保留。请勿在公共设备上保存。</p>
            <f7-button fill round :disabled="!isLoggedIn" @click="save">保存</f7-button>
            <f7-button outline round class="margin-top" :disabled="!isLoggedIn || !Object.keys(configured).length"
                @click="clear">清除手动 Cookie</f7-button>
        </f7-block>
    </f7-page>
</template>
