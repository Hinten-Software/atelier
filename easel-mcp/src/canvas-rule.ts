// A studio whose canvas is given (a commission studio; runner/commission.py): the runner writes the shape, and the
// size if the owner set one, to <studio>/bin/canvas, {"aspect": 1.7778, "words": "16:9", "size": 700}. A chunk that sets
// up the painting's canvas otherwise is refused before it reaches the easel, so nothing is laid and nothing is lost
// (there is no undo of a canvas). The check reads the chunk as written: `aspect` and `size` must be plain numbers
// (or a/b), which is how every painter has written them. Studios without the file are untouched.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

export type CanvasRule = { aspect: number; words: string; size?: number };

export function canvasRule(studio: string): CanvasRule | undefined {
	const path = resolve(studio, "bin", "canvas");
	if (!existsSync(path)) return undefined;
	const r = JSON.parse(readFileSync(path, "utf8"));
	if (typeof r.aspect !== "number" || !(r.aspect > 0)) throw new Error("bin/canvas: no aspect");
	return { aspect: r.aspect, words: String(r.words ?? r.aspect), size: typeof r.size === "number" ? r.size : undefined };
}

/** A number as a painter writes one: 1.7778, 16/9, (16 / 9). */
function plain(expr: string): number | undefined {
	const m = expr.trim().replace(/^\((.*)\)$/, "$1").match(/^(\d+(?:\.\d+)?)\s*(?:\/\s*(\d+(?:\.\d+)?))?$/);
	if (!m) return undefined;
	const v = m[2] === undefined ? Number(m[1]) : Number(m[1]) / Number(m[2]);
	return Number.isFinite(v) ? v : undefined;
}

/** The arguments of each `canvas{...}` / `canvas({...})` in the chunk: what stands between its outer braces. */
function canvasCalls(lua: string): string[] {
	const code = lua.replace(/--\[\[[\s\S]*?\]\]/g, "").replace(/--[^\n]*/g, "");
	const calls: string[] = [];
	for (const m of code.matchAll(/(?<![\w.:])canvas\s*\(?\s*\{/g)) {
		let depth = 0;
		const start = m.index! + m[0].length;
		for (let i = start - 1; i < code.length; i++) {
			if (code[i] === "{") depth++;
			else if (code[i] === "}" && --depth === 0) {
				calls.push(code.slice(start, i));
				break;
			}
		}
	}
	return calls;
}

/** A field of the canvas's own table (not of a table inside it, such as the ground's). */
function field(args: string, name: string): string | undefined {
	let depth = 0, top = "";
	for (const ch of args) {
		if (ch === "{") depth++;
		else if (ch === "}") depth--;
		else if (depth === 0) top += ch;
	}
	return top.match(new RegExp(`(?:^|[,;\\s])${name}\\s*=\\s*([^,;]+)`))?.[1];
}

/** Why this chunk may not set up the painting's canvas, in the studio's words; undefined if it may (or sets none up). */
export function canvasRefused(lua: string, rule: CanvasRule): string | undefined {
	const want = `aspect=${Number(rule.aspect.toFixed(4))}` + (rule.size ? `, size=${rule.size}` : "");
	const say = (what: string) => `paint: ${what} In canvas{}, write ${want} as plain numbers; the rest of the canvas is yours. Nothing was changed.`;
	for (const args of canvasCalls(lua)) {
		const a = field(args, "aspect");
		const aspect = a === undefined ? undefined : plain(a);
		if (aspect === undefined) return say(`this studio's canvas has a given shape, ${rule.words}.`);
		if (Math.abs(aspect / rule.aspect - 1) > 0.005) return say(`this studio's canvas is ${rule.words}, not aspect=${a.trim()}.`);
		if (rule.size) {
			const s = field(args, "size");
			const size = s === undefined ? undefined : plain(s);
			if (size === undefined || Math.abs(size - rule.size) > 0.5) return say(`this studio's canvas is ${rule.size} mm wide.`);
		}
	}
	return undefined;
}
