import {readFile,writeFile} from "node:fs/promises";

const htmlUrl=new URL("../../Minecraft_Mod_Studio_V25.html",import.meta.url);
const runtimeUrl=new URL("./v25-extension-runtime.js",import.meta.url);
const managerUrl=new URL("./v25-extension-manager.js",import.meta.url);
const start="<!-- MMS_V25_EXTENSION_INTEGRATION_START -->";
const end="<!-- MMS_V25_EXTENSION_INTEGRATION_END -->";
const [html,runtime,manager]=await Promise.all([
 readFile(htmlUrl,"utf8"),readFile(runtimeUrl,"utf8"),readFile(managerUrl,"utf8")
]);
if(runtime.includes("</script>")||manager.includes("</script>"))throw Error("Unsafe closing script token in integration source");
const a=html.indexOf(start),b=html.indexOf(end);
if(a<0||b<a||html.indexOf(start,a+start.length)>=0||html.indexOf(end,b+end.length)>=0)throw Error("V25 integration markers missing or duplicated");
const block=[start,"<script>",runtime,"</script>","<script>",manager,"</script>",end].join("\n");
const next=html.slice(0,a)+block+html.slice(b+end.length);
await writeFile(htmlUrl,next);
console.log(`Updated ${htmlUrl.pathname} with ${runtime.length+manager.length} bytes of extension integration code.`);
