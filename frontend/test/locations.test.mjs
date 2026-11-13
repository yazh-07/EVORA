import test from 'node:test';
import assert from 'node:assert/strict';
import { locationTracks, streetViewUrl } from '../.test-build/src/cases/LocationsWorkspace.mjs';
const point=(id,time,lon=77,device='D-1',source='one')=>({id,evidence_id:source,processing_run_id:'run',basis:'gps',device,observed_at_utc:time,geometry:{type:'Point',coordinates:[lon,12]}});
test('paths preserve source/device boundaries and break at gaps, equal times and date-line crossings',()=>{
 const rows=[point('1','2026-01-01T00:00:00Z'),point('2','2026-01-01T00:01:00Z',77.1),point('3','2026-01-01T02:00:00Z',77.2),point('4','2026-01-01T02:01:00Z',77.3),point('5','2026-01-01T00:00:00Z',77,'D-2'),point('6','2026-01-01T00:01:00Z',77.1,'D-1','two')];
 assert.equal(locationTracks(rows).features.length,2);
 assert.equal(locationTracks([point('a','2026-01-01T00:00:00Z',179),point('b','2026-01-01T00:01:00Z',-179)]).features.length,0);
 assert.equal(locationTracks([point('a',null),{...point('b','2026-01-01T00:01:00Z'),basis:'place_mention'}]).features.length,0);
});
test('Street View uses GPS latitude/longitude only, preserves zero, and excludes approximate or invalid locations',()=>{
 const row=point('sensitive-record','2026-01-01T00:00:00Z',77.5);
 const url=new URL(streetViewUrl(row));
 assert.equal(url.origin,'https://www.google.com');assert.equal(url.pathname,'/maps/@');
 assert.deepEqual([...url.searchParams],[['api','1'],['map_action','pano'],['viewpoint','12,77.5']]);
 assert.equal(url.href.includes('sensitive-record'),false);
 assert.equal(new URL(streetViewUrl({...row,geometry:{type:'Point',coordinates:[0,0]}})).searchParams.get('viewpoint'),'0,0');
 for(const coordinates of [[181,12],[77,91],[NaN,12],[77,Infinity],[null,12],['77',12],[]])assert.equal(streetViewUrl({...row,geometry:{type:'Point',coordinates}}),undefined);
 assert.equal(streetViewUrl({...row,basis:'place_mention'}),undefined);
 assert.equal(streetViewUrl({...row,geometry:{type:'Polygon',coordinates:[]}}),undefined);
});
