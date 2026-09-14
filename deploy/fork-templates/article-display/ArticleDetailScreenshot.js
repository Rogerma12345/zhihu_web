// BEGIN fork screenshot export
// Save article as image
const SCREENSHOT_MAX_CANVAS_EDGE = 32760;
const SCREENSHOT_MAX_CANVAS_AREA = 268000000;
const SCREENSHOT_PREFERRED_SCALE = 2;
const SCREENSHOT_MIN_SCALE = 1;
const SCREENSHOT_RESOURCE_TIMEOUT = 15000;
const SCREENSHOT_DOWNLOAD_URL_LIFETIME = 30000;

let screenshotInProgress = false;

const createScreenshotError = (code, message, cause) => {
    const error = new Error(message);
    error.code = code;
    if (cause) error.cause = cause;
    return error;
};

const isTransparentColor = (value) => {
    const normalized = String(value || '').replace(/\s+/g, '').toLowerCase();
    return !normalized
        || normalized === 'transparent'
        || normalized === 'rgba(0,0,0,0)'
        || normalized.endsWith('/0)');
};

const resolveCaptureBackground = (element) => {
    let current = element;
    while (current instanceof HTMLElement) {
        const backgroundColor = window.getComputedStyle(current).backgroundColor;
        if (!isTransparentColor(backgroundColor)) return backgroundColor;
        current = current.parentElement;
    }

    const rootStyle = window.getComputedStyle(document.documentElement);
    const pageBackground = rootStyle.getPropertyValue('--f7-page-bg-color').trim();
    if (pageBackground && !pageBackground.includes('var(')) return pageBackground;

    return document.documentElement.classList.contains('dark') ? '#1c1c1d' : '#ffffff';
};

const withTimeout = (promise, timeoutMs, timeoutMessage) => new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
        reject(createScreenshotError('RESOURCE_TIMEOUT', timeoutMessage));
    }, timeoutMs);

    Promise.resolve(promise).then(
        (value) => {
            window.clearTimeout(timer);
            resolve(value);
        },
        (error) => {
            window.clearTimeout(timer);
            reject(error);
        }
    );
});

const waitForCaptureImage = async (image) => {
    const source = image.currentSrc || image.src;
    if (!source) return;

    if (!image.complete) {
        await new Promise((resolve, reject) => {
            let timer = null;
            let settled = false;

            const cleanup = () => {
                if (timer !== null) window.clearTimeout(timer);
                image.removeEventListener('load', handleLoad);
                image.removeEventListener('error', handleError);
            };
            const settle = (callback) => {
                if (settled) return;
                settled = true;
                cleanup();
                callback();
            };
            const handleLoad = () => settle(resolve);
            const handleError = () => settle(() => {
                reject(createScreenshotError('IMAGE_LOAD_FAILED', `Image failed to load: ${source}`));
            });

            image.addEventListener('load', handleLoad, { once: true });
            image.addEventListener('error', handleError, { once: true });
            timer = window.setTimeout(() => settle(() => {
                reject(createScreenshotError('RESOURCE_TIMEOUT', `Image load timed out: ${source}`));
            }), SCREENSHOT_RESOURCE_TIMEOUT);

            if (image.complete) {
                queueMicrotask(() => {
                    if (image.naturalWidth > 0 && image.naturalHeight > 0) handleLoad();
                    else handleError();
                });
            }
        });
    }

    if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
        throw createScreenshotError('IMAGE_LOAD_FAILED', `Image has no decoded pixels: ${source}`);
    }

    if (typeof image.decode === 'function') {
        await withTimeout(
            image.decode().catch((error) => {
                if (image.complete && image.naturalWidth > 0 && image.naturalHeight > 0) return;
                throw error;
            }),
            SCREENSHOT_RESOURCE_TIMEOUT,
            `Image decode timed out: ${source}`
        );
    }
};

const prepareCaptureResources = async (rootElement) => {
    const images = Array.from(rootElement.querySelectorAll('img'));
    const imageStates = images.map((image) => ({
        image,
        loading: image.getAttribute('loading'),
        fetchPriority: image.getAttribute('fetchpriority'),
    }));

    for (const { image } of imageStates) {
        image.setAttribute('loading', 'eager');
        image.setAttribute('fetchpriority', 'high');
    }

    if (document.fonts?.ready) {
        try {
            await withTimeout(document.fonts.ready, SCREENSHOT_RESOURCE_TIMEOUT, 'Font loading timed out');
        } catch (error) {
            console.warn('Screenshot font preparation did not complete:', error);
        }
    }

    const imageResults = await Promise.allSettled(images.map(waitForCaptureImage));
    const failedImages = imageResults
        .map((result, index) => ({ result, image: images[index] }))
        .filter(({ result }) => result.status === 'rejected');

    if (failedImages.length > 0) {
        console.warn('Screenshot image preparation failures:', failedImages.map(({ result, image }) => ({
            src: image.currentSrc || image.src,
            reason: result.reason,
        })));
    }

    return {
        failedImageCount: failedImages.length,
        restore: () => {
            for (const { image, loading, fetchPriority } of imageStates) {
                if (loading === null) image.removeAttribute('loading');
                else image.setAttribute('loading', loading);

                if (fetchPriority === null) image.removeAttribute('fetchpriority');
                else image.setAttribute('fetchpriority', fetchPriority);
            }
        },
    };
};

const calculateCaptureScale = (width, height) => {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        throw createScreenshotError('INVALID_CAPTURE_SIZE', 'Invalid screenshot dimensions');
    }

    const scaleByEdge = Math.min(
        SCREENSHOT_MAX_CANVAS_EDGE / width,
        SCREENSHOT_MAX_CANVAS_EDGE / height
    );
    const scaleByArea = Math.sqrt(SCREENSHOT_MAX_CANVAS_AREA / (width * height));
    const safeScale = Math.min(SCREENSHOT_PREFERRED_SCALE, scaleByEdge, scaleByArea);

    if (safeScale < SCREENSHOT_MIN_SCALE) {
        throw createScreenshotError('CONTENT_TOO_LONG', 'Content exceeds the single-image canvas limit');
    }

    return Math.max(
        SCREENSHOT_MIN_SCALE,
        Math.floor(safeScale * 100) / 100
    );
};

const canvasToPngBlob = (canvas) => new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
        if (!blob) {
            reject(createScreenshotError('PNG_ENCODING_FAILED', 'Canvas PNG encoding failed'));
            return;
        }
        resolve(blob);
    }, 'image/png');
});

const triggerScreenshotDownload = (blob) => {
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `zhihu-${type || 'content'}-${id || 'export'}.png`;
    link.classList.add('external', 'prevent-router');
    link.style.display = 'none';
    link.addEventListener('click', (event) => {
        event.stopPropagation();
    }, { once: true });
    document.body.appendChild(link);
    link.click();
    link.remove();

    window.setTimeout(() => {
        URL.revokeObjectURL(downloadUrl);
    }, SCREENSHOT_DOWNLOAD_URL_LIFETIME);
};

const openScreenshotPreview = (blob, failedImageCount, captureScale) => {
    const previewUrl = URL.createObjectURL(blob);
    let previewUrlReleased = false;

    const releasePreviewUrl = () => {
        if (previewUrlReleased) return;
        previewUrlReleased = true;
        URL.revokeObjectURL(previewUrl);
    };

    const warningParts = [];
    if (failedImageCount > 0) {
        warningParts.push(`有 ${failedImageCount} 张图片未完成加载，导出内容可能缺少对应图片。`);
    }
    if (captureScale < SCREENSHOT_PREFERRED_SCALE) {
        warningParts.push(`文章较长，导出倍率已调整为 ${captureScale.toFixed(2)}。`);
    }
    const warningHtml = warningParts.length > 0
        ? `<div style="margin-top: 8px; text-align: left; font-size: 12px; opacity: 0.72;">${warningParts.join('<br>')}</div>`
        : '';

    f7.dialog.create({
        title: '截图预览',
        destroyOnClose: true,
        content: `
            <div style="padding: 10px; text-align: center;">
                <img src="${previewUrl}" alt="截图预览" style="max-width: 100%; max-height: 60vh; border-radius: 8px;" />
                ${warningHtml}
            </div>
        `,
        buttons: [
            {
                text: '取消',
                role: 'cancel',
            },
            {
                text: '下载',
                onClick: () => {
                    triggerScreenshotDownload(blob);
                    f7.toast.show({ text: '已发起图片下载' });
                }
            }
        ],
        verticalButtons: false,
        on: {
            closed: releasePreviewUrl,
        }
    }).open();
};

const getScreenshotErrorMessage = (error) => {
    switch (error?.code) {
        case 'CONTENT_NOT_FOUND':
            return '截图失败，未找到文章内容';
        case 'INVALID_CAPTURE_SIZE':
            return '截图失败，文章尺寸无效';
        case 'CONTENT_TOO_LONG':
            return '截图失败，文章超过 Chrome 单张图片尺寸限制';
        case 'PNG_ENCODING_FAILED':
            return '截图失败，PNG 图片生成失败';
        default:
            return '截图失败，请查看浏览器控制台获取详细信息';
    }
};

const saveAsImage = async () => {
    if (!item.value) return;
    if (screenshotInProgress) {
        f7.toast.show({ text: '截图正在生成' });
        return;
    }

    screenshotInProgress = true;
    f7.toast.show({ text: '正在生成截图...' });

    let restoreResources = null;
    let captureRoot = null;

    try {
        captureRoot = document.querySelector('.page-current .content-wrapper');
        if (!captureRoot) {
            throw createScreenshotError('CONTENT_NOT_FOUND', 'Content wrapper not found');
        }

        const captureWidth = Math.ceil(captureRoot.scrollWidth || captureRoot.offsetWidth);
        const captureHeight = Math.ceil(captureRoot.scrollHeight || captureRoot.offsetHeight);
        const captureScale = calculateCaptureScale(captureWidth, captureHeight);
        const captureBackground = resolveCaptureBackground(captureRoot);
        const darkMode = document.documentElement.classList.contains('dark');

        const preparedResources = await prepareCaptureResources(captureRoot);
        restoreResources = preparedResources.restore;

        captureRoot.setAttribute('data-screenshot-capture-root', 'true');

        const canvas = await html2canvas(captureRoot, {
            width: captureWidth,
            height: captureHeight,
            scale: captureScale,
            useCORS: true,
            imageTimeout: SCREENSHOT_RESOURCE_TIMEOUT,
            logging: false,
            backgroundColor: captureBackground,
            onclone: (clonedDocument) => {
                clonedDocument.documentElement.classList.toggle('dark', darkMode);
                const clonedRoot = clonedDocument.querySelector('[data-screenshot-capture-root="true"]');
                if (clonedRoot) {
                    clonedRoot.style.backgroundColor = captureBackground;
                    clonedRoot.style.colorScheme = darkMode ? 'dark' : 'light';
                }
            },
        });

        const blob = await canvasToPngBlob(canvas);
        openScreenshotPreview(blob, preparedResources.failedImageCount, captureScale);
    } catch (error) {
        console.error('Failed to save as image:', error);
        f7.toast.show({ text: getScreenshotErrorMessage(error) });
    } finally {
        if (captureRoot) captureRoot.removeAttribute('data-screenshot-capture-root');
        restoreResources?.();
        screenshotInProgress = false;
    }
};

// END fork screenshot export
