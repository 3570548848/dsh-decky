import deckyPlugin from "@decky/rollup";

// @decky/rollup merges the caller's options with its defaults via
// mergeAndConcat, where a scalar conflict is won by the *defaults* — so
// passing `output: { sourcemap: false }` here does NOT take effect. The
// returned config is mutated instead.
//
// Why disable it: the default `sourcemap: true` embeds every bundled file's
// original source through `sourcesContent`. Bundling a single react-icons icon
// pulls in all of `react-icons/fa` (~1.36 MB), so the map is ~1.4 MB against a
// ~20 KB script. Nothing loads the map at runtime — Decky executes index.js —
// so shipping it only inflates the zip.
const config = deckyPlugin({});

if (config.output && !Array.isArray(config.output)) {
  config.output.sourcemap = false;
}

export default config;
