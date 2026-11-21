import {readFile,writeFile} from "node:fs/promises";
import {parseManifest} from "../../package-manager.mjs";
import {createMmse} from "../../archive-writer.mjs";

const manifest=await readFile(new URL("./manifest.json",import.meta.url),"utf8");
parseManifest(manifest);
const archive=await createMmse({manifest,assets:[]},{parseManifest});
const output=new URL("./mms-demo-recipes.mmse",import.meta.url);
await writeFile(output,archive);
console.log(`Wrote ${archive.length} bytes to ${output.pathname}`);
