#!/usr/bin/env node
import {mkdir,writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
import {gzipSync} from 'node:zlib';
import {generate,encodeNBT,paletteFor,walkability} from './core.mjs';
import {generateDungeon} from './dungeon.mjs';
try {
  const [preset,seed,output,dimensions,...rest]=process.argv.slice(2);
  if(!preset||seed===undefined||!output||rest.length||!/^\\d+$/.test(seed)||!output.endsWith('.nbt'))throw Error('Usage: node structure-studio/export.mjs house|tower|factory|dungeon SEED OUTPUT.nbt [WIDTH,HEIGHT,DEPTH]');
  if(dimensions&&!/^\\d+,\\d+,\\d+$/.test(dimensions))throw Error('Invalid dimensions');
  const options={preset,seed:Number(seed),...(dimensions?{size:dimensions.split(',').map(Number)}:{})};const s=preset==='dungeon'?generateDungeon({...options,rooms:8,style:'stone',hiddenRooms:1}):generate(options);
  const raw=encodeNBT(s,{dataVersion:4903,paletteKeys:'legacy'}),gzip=gzipSync(raw);
  await mkdir(dirname(output),{recursive:true});
  await writeFile(output,gzip,{flag:'wx'});
  console.log(JSON.stringify({target:'Minecraft Java 26.2',dataVersion:4903,preset,seed:Number(seed),size:s.size,cells:s.blocks.length,palette:paletteFor(s).palette.length,walkability:walkability(s),bytes:gzip.length,output},null,2));
} catch(err){console.error(err.message);process.exitCode=1;}
