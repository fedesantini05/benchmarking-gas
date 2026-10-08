import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [input,outputDir,label='case',erLast='53',bpLast='31']=process.argv.slice(2);
await fs.mkdir(outputDir,{recursive:true});
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
book.recalculate();
const checks=[];
for(const [sheet,range,suffix] of [['Estado de Resultados',`A1:M${erLast}`,'er'],['Balance Patrimonial',`A1:M${bpLast}`,'bp']]){
  const rendered=await book.render({sheetName:sheet,range,scale:1,format:'png'});
  await fs.writeFile(path.join(outputDir,`${label}_${suffix}.png`),new Uint8Array(await rendered.arrayBuffer()));
  checks.push({sheet,values:(await book.inspect({kind:'table',sheetId:sheet,range:sheet.startsWith('Estado')?'K43:M53':'K26:M31',include:'values,formulas',tableMaxRows:11,tableMaxCols:3,maxChars:3500})).ndjson});
}
await fs.writeFile(path.join(outputDir,`${label}_visual.json`),JSON.stringify(checks,null,2));
console.log(JSON.stringify({label,rendered:true}));
