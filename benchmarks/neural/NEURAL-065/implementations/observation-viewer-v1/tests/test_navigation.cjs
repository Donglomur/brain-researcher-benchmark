// Generated script/DOM controls; this is not a browser qualification.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "..", "view.py"), "utf8");
const page = source.match(/PAGE = r'''([\s\S]*?)'''/)[1];
const script = page.match(/<script>\s*([\s\S]*?)<\/script>/)[1];

function run(values, shape) {
  const buffer = Buffer.alloc(values.length*8);
  values.forEach((value, i) => buffer.writeDoubleLE(value, i*8));
  const obs = {query_id:"a".repeat(32),packet_sha256:"4".repeat(64),shape,
    sampling_frequency_hz:500,channel_ids:Array.from({length:shape[1]},(_,i)=>"EEG"+String(i).padStart(3,"0")),data_base64:buffer.toString("base64")};
  class Element {
    constructor(tag) {this.tag=tag;this.children=[];this.value="";this.textContent="";}
    appendChild(child){this.children.push(child);if(this.tag==="select"&&this.children.length===1)this.value=child.value;return child;}
    replaceChildren(fragment){this.children=fragment.children;}
  }
  const ids={};
  for(const id of ["observation","channel","first","count","identity","dimensions","error","range","plot","values","show","next","previous"])ids[id]=new Element(id==="channel"?"select":"div");
  ids.observation.textContent=JSON.stringify(obs);ids.first.value="0";
  const coordinates=[];
  const ctx={clearRect(){coordinates.length=0;},fillText(){},beginPath(){},moveTo(x,y){coordinates.push([x,y]);},lineTo(x,y){coordinates.push([x,y]);},stroke(){},arc(x,y){coordinates.push([x,y]);},fill(){}};
  ids.plot.getContext=()=>ctx;
  const document={getElementById:id=>ids[id],createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element("fragment")};
  vm.runInNewContext(script,{document,atob:value=>Buffer.from(value,"base64").toString("binary")},{timeout:1000});
  function rows(){return ids.values.children.map(row=>row.children.map(cell=>cell.textContent));}
  return {ids,coordinates,rows};
}

const small=run([1e-6,10,2e-6,20,3e-6,30,4e-6,40,5e-6,50],[5,2]);
assert.equal(small.ids.error.textContent,"");assert.equal(small.rows().length,5);
assert.deepEqual(small.rows()[1],["1","0.002","0.000002"]);
small.ids.channel.value="1";small.ids.channel.onchange();assert.equal(small.rows()[4][2],"50");
small.ids.count.value="2";small.ids.first.value="0";small.ids.show.onclick();
assert.deepEqual(small.rows().map(row=>row[0]),["0","1"]);
small.ids.next.onclick();assert.deepEqual(small.rows().map(row=>row[0]),["2","3"]);
small.ids.next.onclick();assert.deepEqual(small.rows().map(row=>row[0]),["4"]);
small.ids.previous.onclick();assert.deepEqual(small.rows().map(row=>row[0]),["2","3"]);
small.ids.first.value="5";small.ids.show.onclick();assert.match(small.ids.error.textContent,/valid first sample/);
small.ids.first.value="0";small.ids.count.value="4097";small.ids.show.onclick();assert.match(small.ids.error.textContent,/1–4096/);
const large=run(Array.from({length:4100},(_,i)=>i),[4100,1]);
large.ids.count.value="4096";large.ids.show.onclick();assert.equal(large.rows().length,4096);
large.ids.next.onclick();assert.deepEqual(large.rows().map(row=>row[0]),["4096","4097","4098","4099"]);
for(const values of [[-Number.MAX_VALUE,Number.MAX_VALUE],[Number.MAX_VALUE,Number.MAX_VALUE],[0,0],[Number.MIN_VALUE,0]]){
  const extreme=run(values,[2,1]);assert.equal(extreme.ids.error.textContent,"");
  assert(extreme.coordinates.every(pair=>pair.every(Number.isFinite)));
  assert.equal(extreme.rows()[0][2],String(values[0]));assert.equal(extreme.rows()[1][2],String(values[1]));
}
assert(process.resourceUsage().maxRSS < 1024*1024,"RSS must remain below 1 GiB");
console.log("navigation controls passed; peak RSS KiB",process.resourceUsage().maxRSS);
