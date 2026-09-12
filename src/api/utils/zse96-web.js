import CryptoJS from 'crypto-js';

const WEB_ZSE_93 = '101_3_3.0';

const ROUND_TABLE = new Uint32Array([
    1170614578, 1024848638, 1413669199, 3951632832, 3528873006, 2921909214, 4151847688, 3997739139,
    1933479194, 3323781115, 3888513386, 460404854, 3747539722, 2403641034, 2615871395, 2119585428,
    2265697227, 2035090028, 2773447226, 4289380121, 4217216195, 2200601443, 3051914490, 1579901135,
    1321810770, 456816404, 2903323407, 4065664991, 330002838, 3506006750, 363569021, 2347096187,
]);

const BYTE_TABLE = new Uint8Array([
    20, 223, 245, 7, 248, 2, 194, 209, 87, 6, 227, 253, 240, 128, 222, 91, 237, 9, 125, 157, 230,
    93, 252, 205, 90, 79, 144, 199, 159, 197, 186, 167, 39, 37, 156, 198, 38, 42, 43, 168, 217,
    153, 15, 103, 80, 189, 71, 191, 97, 84, 247, 95, 36, 69, 14, 35, 12, 171, 28, 114, 178, 148,
    86, 182, 32, 83, 158, 109, 22, 255, 94, 238, 151, 85, 77, 124, 254, 18, 4, 26, 123, 176, 232,
    193, 131, 172, 143, 142, 150, 30, 10, 146, 162, 62, 224, 218, 196, 229, 1, 192, 213, 27, 110,
    56, 231, 180, 138, 107, 242, 187, 54, 120, 19, 44, 117, 228, 215, 203, 53, 239, 251, 127, 81,
    11, 133, 96, 204, 132, 41, 115, 73, 55, 249, 147, 102, 48, 122, 145, 106, 118, 74, 190, 29, 16,
    174, 5, 177, 129, 63, 113, 99, 31, 161, 76, 246, 34, 211, 13, 60, 68, 207, 160, 65, 111, 82,
    165, 67, 169, 225, 57, 112, 244, 155, 51, 236, 200, 233, 58, 61, 47, 100, 137, 185, 64, 17, 70,
    234, 163, 219, 108, 170, 166, 59, 149, 52, 105, 24, 212, 78, 173, 45, 0, 116, 226, 119, 136,
    206, 135, 175, 195, 25, 92, 121, 208, 126, 139, 3, 75, 141, 21, 130, 98, 241, 40, 154, 66, 184,
    49, 181, 46, 243, 88, 101, 183, 8, 23, 72, 188, 104, 179, 210, 134, 250, 201, 164, 89, 216,
    202, 220, 50, 221, 152, 140, 33, 235, 214,
]);

const ENCODE_TABLE = '6fpLRqJO8M/c3jnYxFkUVC4ZIG12SiH=5v0mXDazWBTsuw7QetbKdoPyAl+hN9rgE';
const SEED_BYTES = new TextEncoder().encode('059053f7d15e01d7');

function readBe32(bytes, offset) {
    return (
        ((bytes[offset] & 255) << 24) |
        ((bytes[offset + 1] & 255) << 16) |
        ((bytes[offset + 2] & 255) << 8) |
        (bytes[offset + 3] & 255)
    ) >>> 0;
}

function writeBe32(value, bytes, offset) {
    bytes[offset] = value >>> 24;
    bytes[offset + 1] = value >>> 16;
    bytes[offset + 2] = value >>> 8;
    bytes[offset + 3] = value;
}

function rotate32(value, bits) {
    return ((value << bits) | (value >>> (32 - bits))) >>> 0;
}

function mixWord(value) {
    const substituted = (
        (BYTE_TABLE[(value >>> 24) & 255] << 24) |
        (BYTE_TABLE[(value >>> 16) & 255] << 16) |
        (BYTE_TABLE[(value >>> 8) & 255] << 8) |
        BYTE_TABLE[value & 255]
    ) >>> 0;

    return (
        substituted ^
        rotate32(substituted, 2) ^
        rotate32(substituted, 10) ^
        rotate32(substituted, 18) ^
        rotate32(substituted, 24)
    ) >>> 0;
}

function encryptBlock(block) {
    const words = new Uint32Array(36);
    for (let index = 0; index < 4; index += 1) {
        words[index] = readBe32(block, index * 4);
    }

    for (let round = 0; round < 32; round += 1) {
        const input = (words[round + 1] ^ words[round + 2] ^ words[round + 3] ^ ROUND_TABLE[round]) >>> 0;
        words[round + 4] = (words[round] ^ mixWord(input)) >>> 0;
    }

    const output = new Uint8Array(16);
    [35, 34, 33, 32].forEach((source, index) => writeBe32(words[source], output, index * 4));
    return output;
}

function encryptRemainder(bytes, iv) {
    const output = new Uint8Array(bytes.length);
    let previous = new Uint8Array(iv);

    for (let offset = 0; offset < bytes.length; offset += 16) {
        const input = new Uint8Array(16);
        for (let index = 0; index < 16; index += 1) {
            input[index] = bytes[offset + index] ^ previous[index];
        }
        previous = encryptBlock(input);
        output.set(previous, offset);
    }
    return output;
}

function encodeBytes(input) {
    const paddedLength = Math.ceil(input.length / 3) * 3;
    const bytes = new Uint8Array(paddedLength);
    bytes.set(input);

    let output = '';
    let maskIndex = 0;
    for (let position = bytes.length - 1; position >= 0; position -= 3) {
        let packed = 0;
        for (let byteIndex = 0; byteIndex < 3; byteIndex += 1) {
            const mask = (58 >>> (8 * (maskIndex % 4))) & 255;
            maskIndex += 1;
            packed |= ((bytes[position - byteIndex] ^ mask) & 255) << (byteIndex * 8);
        }
        for (let shift = 0; shift <= 18; shift += 6) {
            output += ENCODE_TABLE[(packed >>> shift) & 63];
        }
    }
    return output;
}

export function encryptWebDigest(md5Hex) {
    const encoded = encodeURIComponent(md5Hex);
    const source = [210, 0];
    for (let index = 0; index < encoded.length; index += 1) {
        source.push(encoded.charCodeAt(index));
    }

    const paddingLength = 16 - (source.length % 16);
    source.push(...Array(paddingLength).fill(paddingLength));

    const plain = Uint8Array.from(source);
    const firstInput = new Uint8Array(16);
    for (let index = 0; index < 16; index += 1) {
        firstInput[index] = plain[index] ^ SEED_BYTES[index] ^ 42;
    }

    const firstCipher = encryptBlock(firstInput);
    const cipher = new Uint8Array(plain.length);
    cipher.set(firstCipher, 0);
    if (plain.length > 16) {
        cipher.set(encryptRemainder(plain.slice(16), firstCipher), 16);
    }
    return encodeBytes(cipher);
}

function getRequestTarget(url) {
    const scheme = url.indexOf('://');
    const slash = url.indexOf('/', scheme >= 0 ? scheme + 3 : 0);
    return slash >= 0 ? url.slice(slash) : '/';
}

export function signWebRequest(url, dC0, body = null) {
    if (!dC0) {
        throw new Error('Web 请求缺少有效 d_c0，无法生成 x-zse-96');
    }

    const parts = [WEB_ZSE_93, getRequestTarget(url), dC0];
    if (body !== null && body !== undefined) {
        parts.push(String(body));
    }
    const digest = CryptoJS.MD5(CryptoJS.enc.Utf8.parse(parts.join('+'))).toString(CryptoJS.enc.Hex);
    return {
        zse93: WEB_ZSE_93,
        zse96: `2.0_${encryptWebDigest(digest)}`,
    };
}

export { WEB_ZSE_93 };
