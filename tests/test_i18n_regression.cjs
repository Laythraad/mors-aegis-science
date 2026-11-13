const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let writes = 0, callback;
const option = {tagName:'OPTION', textContent:'West', attrs:{}, hasAttribute(k){return k in this.attrs}, set value(v){this.attrs.value=v}};
function text(value, parentElement){return {nodeType:3,parentElement,get nodeValue(){return value},set nodeValue(v){writes++;value=v}}}
const identical = text('NASA EOSDIS FIRMS', {tagName:'SPAN'});
const optionText = text('West', option);
const body = {nodeType:1,tagName:'BODY',children:[identical,optionText],getAttribute(){return null},querySelectorAll(){return []}};
const document = {body,documentElement:{},getElementById(){return null},createTreeWalker(node){let i=0;return {nextNode(){return node.children?.[i++] || null}}}};
class MutationObserver {constructor(fn){callback=fn} observe(){}}
const context={document,localStorage:{getItem(){return 'ar'}},MutationObserver,Node:{TEXT_NODE:3,ELEMENT_NODE:1,DOCUMENT_FRAGMENT_NODE:11},NodeFilter:{SHOW_TEXT:4},window:{},location:{reload(){}}};
vm.runInNewContext(fs.readFileSync('app/static/i18n.js','utf8'),context);
assert.equal(identical.nodeValue,'NASA EOSDIS FIRMS');
assert.equal(optionText.nodeValue,'الغرب');
assert.equal(option.attrs.value,'West');
assert.equal(writes,1,'unchanged translations must not write');
callback([{type:'characterData',target:identical,addedNodes:[]}]);
assert.equal(writes,1,'observer must not repeatedly rewrite identical text');
console.log('Arabic translation observer and option values verified');
