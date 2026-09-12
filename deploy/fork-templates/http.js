import {
	initZhihu,
	updateZhihuLoginData,
	getZhihuInstance
} from './utils/zhihu-module.js';

class PaginatedResult {
	constructor(data, paging, options, extra = {}) {
		const source = paging && typeof paging === 'object' ? paging : {};
		Object.assign(this, extra);
		this._data = data;
		this.paging = {
			...source,
			next: source.next || null,
			previous: source.previous || null,
			is_end: source.is_end === true || !source.next,
		};
		this.options = options;
	}

	get data() {
		return this._data;
	}

	async next() {
		if (!this.paging.next) return null;
		const zhihuRequest = getZhihuInstance();
		const res = await zhihuRequest.get(this.paging.next, this.options);
		return createPaginatedResult(res, this.options, true);
	}

	async prev() {
		if (!this.paging.previous) return null;
		const zhihuRequest = getZhihuInstance();
		const res = await zhihuRequest.get(this.paging.previous, this.options);
		return createPaginatedResult(res, this.options, true);
	}
}

const createPaginatedResult = (res, options, force = false) => {
	if (!res || typeof res !== 'object') return res;
	if (!force && !(res.paging && typeof res.paging === 'object')) return res;
	const { data, paging, ...extra } = res;
	return new PaginatedResult(data, paging, options, extra);
};

const httpMethods = {
	get(url, options) {
		const zhihuRequest = getZhihuInstance();
		return zhihuRequest.get(url, options).then(res => createPaginatedResult(res, options));
	},

	post(url, data, options) {
		const zhihuRequest = getZhihuInstance();
		return zhihuRequest.post(url, data, options).then(res => res);
	},

	patch(url, data, options) {
		const zhihuRequest = getZhihuInstance();
		return zhihuRequest.patch(url, data, options).then(res => res);
	},

	put(url, data, options) {
		const zhihuRequest = getZhihuInstance();
		return zhihuRequest.put(url, data, options).then(res => res);
	},

	delete(url, dataOrOptions, options) {
		const zhihuRequest = getZhihuInstance();
		const requestOptions = options ?? (
			dataOrOptions && typeof dataOrOptions === 'object'
				? dataOrOptions
				: undefined
		);
		return zhihuRequest.delete(url, requestOptions).then(res => res);
	},
};

export {
	initZhihu,
	updateZhihuLoginData,
	getZhihuInstance
};

export default httpMethods;
