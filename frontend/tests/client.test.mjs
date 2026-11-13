import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/lib/api/client.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const client = await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const envelope = {csrfToken:'synthetic-csrf',principal:{csrfToken:'synthetic-csrf'}};
test('mutations preserve CSRF and same-origin transport; empty responses work',async()=>{
 client.beginSessionTransition();client.setSession(envelope);client.setActiveProject('one');
 globalThis.fetch=async(url,init)=>{assert.equal(url,'/api/v1/projects/one/resources');assert.equal(init.headers.get('X-CSRF-Token'),'synthetic-csrf');assert.equal(init.credentials,'same-origin');assert.equal(init.cache,'no-store');return new Response(null,{status:204})};
 assert.equal(await client.api('projects/one/resources',{method:'POST',body:'{}'}),undefined);
});
test('late response is rejected after project/session generation changes',async()=>{
 client.beginSessionTransition();client.setSession(envelope);client.setActiveProject('one');
 let finish;globalThis.fetch=()=>new Promise(resolve=>finish=resolve);
 const response=client.api('projects/one/resources');client.advanceApiGeneration();client.setActiveProject('two');
 finish(new Response(JSON.stringify({items:[]})));await assert.rejects(response,client.StaleApiRequest);
 let called=false;globalThis.fetch=async()=>{called=true};await assert.rejects(client.api('projects/one/resources'),client.StaleApiRequest);assert.equal(called,false);
});
test('expiry callback handles 401 while outage remains a typed error',async()=>{
 client.beginSessionTransition();let expired=0;client.setAuthenticationExpiryHandler(()=>expired++);
 globalThis.fetch=async()=>new Response('{}',{status:401});await assert.rejects(client.api('me/browser'),client.StaleApiRequest);assert.equal(expired,1);
 globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Synthetic outage'}),{status:503});await assert.rejects(client.api('me/browser'),e=>e instanceof client.ApiError&&e.status===503);assert.equal(expired,1);
 await assert.rejects(client.api('auth/login'),e=>e instanceof client.ApiError&&e.status===503);
 client.setAuthenticationExpiryHandler(null);
});
test('logout invalidates older requests without dropping its CSRF credential',async()=>{
 client.beginSessionTransition();client.setSession(envelope);client.setActiveProject('one');
 const previous=client.apiGeneration();client.beginAuthenticatedMutation();assert.equal(client.isApiGenerationCurrent(previous),false);
 globalThis.fetch=async(url,init)=>{assert.equal(url,'/api/v1/auth/logout');assert.equal(init.headers.get('X-CSRF-Token'),'synthetic-csrf');return new Response(null,{status:204})};
 await client.api('auth/logout',{method:'POST',body:'{}'});
});
