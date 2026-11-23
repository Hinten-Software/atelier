// The given canvas of a commission studio (src/canvas-rule.ts):  node easel-mcp/test/canvas-rule.ts
import { canvasRefused } from "../src/canvas-rule.ts";

let failed = 0;
const check = (what: string, cond: boolean, detail?: unknown) => {
	if (!cond) failed++;
	console.log(`${cond ? "ok  " : "FAIL"} ${what}${cond ? "" : ": " + JSON.stringify(detail)}`);
};
const wide = { aspect: 1.7778, words: "16:9" };
const ok = (lua: string, rule = wide) => canvasRefused(lua, rule) === undefined;
const ground = 'ground={{pile={{"lead white", 3}}, um=60, apply="knife"}}';

check("the given shape passes", ok(`canvas{size=700, aspect=1.7778, linen={14, 12}, seed=4, ${ground}}`));
check("as a fraction", ok(`canvas{size=700, aspect=16/9, ${ground}}`));
check("in brackets, rounded", ok(`canvas({aspect = (16 / 9), size = 600})`) && ok("canvas{aspect=1.78}"));
check("another shape is refused", !ok(`canvas{size=600, aspect=0.8, ${ground}}`));
check("no shape is refused", !ok(`canvas{size=600, ${ground}}`));
check("a computed shape is refused", !ok("local a = 16/9\ncanvas{size=600, aspect=a}"));
check("a field of the ground is not the canvas's", !ok("canvas{size=600, ground={{aspect=1.7778}}}"));
check("a chunk that sets up no canvas passes", ok('p = pile{{"lead white", 1}}\nwork(rect(0, 0, 10, 10), {pile=p})'));
check("a comment or another name is no canvas", ok("-- canvas{aspect=0.8}\nlocal my_canvas = 1; mycanvas{aspect=1}; t.canvas{aspect=1}"));
check("the message names what to write", /aspect=1\.7778/.test(canvasRefused("canvas{aspect=1.25}", wide) ?? ""));
const sized = { ...wide, size: 700 };
check("a given size passes", ok("canvas{size=700, aspect=1.7778}", sized));
check("another size is refused", !ok("canvas{size=600, aspect=1.7778}", sized) && !ok("canvas{aspect=1.7778}", sized));
console.log(failed ? "FAILED" : "all ok");
process.exit(failed ? 1 : 0);
