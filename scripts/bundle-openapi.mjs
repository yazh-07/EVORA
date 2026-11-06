// Use the YAML parser already pinned by the frontend tooling; never fetch a spec.
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const [source,output,frontend]=process.argv.slice(2);
if(!source||!output||!frontend)throw Error('Usage: bundle-openapi.mjs SPEC OUTPUT FRONTEND_DIRECTORY');
const require=createRequire(resolve(frontend,'package.json'));
const yaml=require('js-yaml');
const spec=yaml.load(await readFile(source,'utf8'),{schema:yaml.JSON_SCHEMA});
if(!spec||typeof spec!=='object'||!spec.openapi||!spec.paths)throw Error('Expected an OpenAPI document');
function verify(value){
  if(!value||typeof value!=='object')return;
  if('$ref' in value){
    const ref=value.$ref;
    if(typeof ref!=='string'||!ref.startsWith('#/'))throw Error('External reference requires explicit bundling');
    let target=spec;
    for(const segment of ref.slice(2).split('/')){
      const key=segment.replaceAll('~1','/').replaceAll('~0','~');
      if(!target||typeof target!=='object'||!Object.hasOwn(target,key))throw Error(`Broken reference: ${ref}`);
      target=target[key];
    }
  }
  for(const child of Object.values(value))verify(child);
}
verify(spec);
await writeFile(output,JSON.stringify(spec));
console.log(`Bundled ${source}`);
