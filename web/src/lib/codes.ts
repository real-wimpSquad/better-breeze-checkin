/**
 * Check-in code generation and decoding.
 *
 * Port of api/codes.py — pure math, no server round-trip needed.
 *
 * Encodes instance_id and person_id into a human-readable 7-char code (XXX-XXXX).
 * - instance_id mod 32768 (15 bits)
 * - person_id mod 32768 (15 bits)
 * - 1 checksum character
 */

// Base30 alphabet - removed confusing chars (0/O, 1/I/L)
const ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ';
const BASE = ALPHABET.length; // 30

function checksum(data: number): number {
	let total = 0;
	let d = data;
	while (d) {
		total += d & 0xf;
		d >>>= 4;
	}
	return total % BASE;
}

export function generateCode(personId: string | number, instanceId: string | number): string {
	const pid = typeof personId === 'string' ? parseInt(personId, 10) : personId;
	const iid = typeof instanceId === 'string' ? parseInt(instanceId, 10) : instanceId;

	// Pack: [instance:15][person:15] = 30 bits
	const packed = ((iid & 0x7fff) << 15) | (pid & 0x7fff);

	// Convert to base30 (LSB first, then reverse for MSB first)
	const chars: string[] = [];
	let temp = packed;
	for (let i = 0; i < 6; i++) {
		chars.push(ALPHABET[temp % BASE]);
		temp = Math.floor(temp / BASE);
	}
	chars.reverse();

	// Add checksum
	chars.push(ALPHABET[checksum(packed)]);

	const code = chars.join('');
	return `${code.slice(0, 3)}-${code.slice(3)}`;
}

export function decodeCode(
	code: string
): { instance_id: number; person_id: number } | null {
	const clean = code.toUpperCase().replace(/-/g, '').replace(/ /g, '');

	if (clean.length !== 7) return null;

	const indices: number[] = [];
	for (const c of clean) {
		const idx = ALPHABET.indexOf(c);
		if (idx === -1) return null;
		indices.push(idx);
	}

	const dataIndices = indices.slice(0, 6);
	const checksumIdx = indices[6];

	// Reconstruct packed integer (MSB first)
	let packed = 0;
	for (const idx of dataIndices) {
		packed = packed * BASE + idx;
	}

	if (checksum(packed) !== checksumIdx) return null;

	return {
		person_id: packed & 0x7fff,
		instance_id: (packed >>> 15) & 0x7fff
	};
}
