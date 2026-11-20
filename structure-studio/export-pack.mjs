#!/usr/bin/env node
import {readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {join,dirname,resolve} from 'node:path';
import {gzipSync} from 'node:zlib';
import {createPack} from './pack.mjs';
try {
  const [config,output,...rest]=process.argv.slice(2);
  if(!config||!output||rest.length)throw Error('Usage: node structure-studio/export-pack.mjs CONFIG.json NEW_OUTPUT_DIRECTORY');
  const input=await readFile(config,'utf8');
  if(input.length>65536)throw Error('Config too large');
  const {files,report}=createPack(JSON.parse(input));
  const target=resolve(output);
  // Require a new directory; never replace a world or an existing pack.
  await mkdir(target,{recursive:false});
  try {
    for(const [name,content] of files){
      const path=join(target,name);
      await mkdir(dirname(path),{recursive:true});
      await writeFile(path,typeof content==='string'?content:gzipSync(content),{flag:'wx'});
    }
  } catch(error){await rm(target,{recursive:true,force:true});throw error;}
  console.log(JSON.stringify({...report,output:target,files:files.size},null,2));
} catch(error){console.error(error.message);process.exitCode=1;}
